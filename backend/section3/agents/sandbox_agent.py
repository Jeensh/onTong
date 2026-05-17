"""샌드박스 agent — 실시간 ontology API → Java AST 파싱 → Python 변환 → 격리 실행.

파이프라인 (ONTOLOGY_API_AUDIT.md §7.7 결론에 따른 자체 합성):
1. OntologyComposer.simulate(target) — legacy `/api/ontology/*` 실시간 호출
   → action/method param schema + body_text + valid_range
2. JavaToPythonTranspiler — body_text 의 tree-sitter-java AST 파싱 → Python source
3. sandbox.run_python_multi — case 별 subprocess 격리 실행
4. modeling.query 는 step kind 전용 fallback (composer 가 지원 안 하는 영역)

원칙:
- modeling Neo4j 적재 의존 ❌. 매 호출 legacy API 실시간 호출.
- 변환 실패 / 미지원 노드는 warning 으로 노출 → LLM 후처리 가능.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.composer import OntologyComposer, _is_action_fqn
from backend.section3.contracts import (
    AgentFinalResult,
    SandboxRequest,
    StreamEvent,
)
from backend.section3.sandbox.runner import run_python_multi
from backend.section3.sim_v2_bridge import (
    build_stubs,
    load_action,
    load_baseline_map,
    load_body_text,
    open_sim_v2_session,
    run_fixtures_in_process,
    run_fixtures_with_baseline,
    synthesize_fixtures,
    translate_java_to_python,
)
from backend.section3.transpiler import JavaToPythonTranspiler

logger = logging.getLogger(__name__)

# v2 통합 경로 활성화 repo — Section 4 인계 패키지가 다룬 production DB.
SIM_V2_REPO_ID = "slab-design-real-v2"


class SandboxAgent(BaseAgent):
    name = "sandbox"

    async def run(self, req: SandboxRequest) -> AsyncIterator[StreamEvent]:
        yield self.thinking(
            f"샌드박스 — {req.target_kind}={req.target_id!r}, case_types={req.case_types}"
        )

        # ─── 0. sim_v2 인계 패키지 직통 (recipe-4) — action 우선 ──────────
        # data/slab-v2-handoff.db 에서 action 을 직접 찾으면 W71→W74→W72
        # full pipeline 으로 in-process 실행. 실패 시 기존 legacy 경로로 폴백.
        # 활성화 조건: target_id 가 action.* FQN 패턴 (contract 의 target_kind 가
        # "action" 을 직접 허용하지 않으므로 target_id 패턴으로 감지).
        if _is_action_fqn(req.target_id):
            sim_session = open_sim_v2_session()
            if sim_session is not None:
                routed = False
                try:
                    action = load_action(sim_session, req.target_id, SIM_V2_REPO_ID)
                    if action is not None and action.code_method_fqn:
                        routed = True
                        async for ev in self._run_via_simv2(req, sim_session, action):
                            yield ev
                except Exception as e:
                    logger.warning("sim_v2 직통 경로 실패 → legacy 폴백: %s", e)
                    routed = False
                finally:
                    try:
                        sim_session.close()
                    except Exception:
                        pass
                if routed:
                    return

        # ─── 1. composer (legacy 실시간) — step 만 modeling fallback ────────
        if req.target_kind == "step":
            async for ev in self._run_via_modeling(req):
                yield ev
            return

        yield self.modeling_call("composer.simulate", {"target": {"kind": req.target_kind, "id": req.target_id}})
        composer = OntologyComposer(self.modeling)
        try:
            resp = await composer.simulate(req.target_kind, req.target_id)
        except Exception as e:
            yield self.error(f"composer.simulate 실패: {e}")
            return

        status = resp.get("status")
        if status == "unsupported":
            yield self.error(f"composer unsupported: {resp.get('result', {}).get('message')}")
            return
        if status == "error":
            yield self.error(f"composer error: {resp.get('result', {}).get('message')}")
            return

        yield self.modeling_result(resp)
        result = resp.get("result") or {}

        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        cases = [c for c in (result.get("test_cases") or []) if c.get("case_type") in req.case_types]
        if not cases:
            yield self.error(f"composer 가 반환한 cases 중 {req.case_types} 해당 없음")
            return

        # ─── 2. AST transpile (Java body_text → Python source) ────────────
        src_meta = result.get("source_for_transpile") or {}
        body_text = src_meta.get("body_text")
        if not body_text:
            yield self.error(
                "transpile 입력 없음 — legacy code-types 에 body_text 가 없는 method. "
                "modeling 응답 기반 LLM fallback 필요.",
                composer_result=result,
            )
            return

        yield self.thinking("Java body_text → tree-sitter AST → Python 변환 중…")
        transpiler = JavaToPythonTranspiler()
        method_name = (src_meta.get("method_fqn") or "method").rsplit(".", 1)[-1].split("(")[0]
        transpiled = transpiler.transpile(
            body_text,
            method_name=method_name,
            params=src_meta.get("params") or [],
            return_type=src_meta.get("return_type") or (src_meta.get("output") or {}).get("type"),
            class_fields=src_meta.get("class_fields") or [],
            method_anchors=src_meta.get("method_anchors") or [],
        )
        if not transpiled.get("ok"):
            yield self.error(
                f"transpile 실패: {transpiled.get('warnings')}",
                python_source=transpiled.get("python_source"),
            )
            return
        if transpiled.get("warnings"):
            yield self.event("transpile_warnings", warnings=transpiled["warnings"])

        # ─── 3. sandbox runner 가 받을 형식으로 wrap ─────────────────────
        wrapped = _wrap_for_sandbox(transpiled)
        yield self.code_gen(wrapped)

        # ─── 4. case 별 input 매핑 (case.input keys → param_names) ──────
        param_names = transpiled["param_names"]
        normalized_cases = []
        for c in cases:
            inp = c.get("input") or {}
            # case.input 의 key 가 param_names 와 일치하지 않으면 순서대로 매핑
            mapped = {}
            inp_keys = list(inp.keys())
            for i, pname in enumerate(param_names):
                if pname in inp:
                    mapped[pname] = inp[pname]
                elif i < len(inp_keys):
                    mapped[pname] = inp[inp_keys[i]]
                else:
                    mapped[pname] = None
            normalized_cases.append({**c, "input": mapped})

        if not req.run_after_generate:
            yield self.final(AgentFinalResult(
                ok=True,
                summary="composer + transpile 완료 (실행 skip)",
                modeling_response=resp,
                generated_python=wrapped,
            ).model_dump())
            return

        # ─── 5. subprocess 격리 실행 ─────────────────────────────────────
        yield self.sandbox_run(f"{len(normalized_cases)} case 격리 실행")
        case_results = run_python_multi(wrapped, normalized_cases, timeout_per_case=5.0)
        yield self.sandbox_result(case_results)

        ok_count = sum(1 for r in case_results if r["execution"]["ok"])
        matched_count = sum(1 for r in case_results if r.get("matched_expected"))
        summary = f"{len(case_results)} case — 성공 {ok_count} · expected 일치 {matched_count}"
        yield self.final(AgentFinalResult(
            ok=ok_count > 0,
            summary=summary,
            modeling_response=resp,
            generated_python=wrapped,
            sandbox_result={"cases": case_results, "ok_count": ok_count, "matched_count": matched_count},
            visualization=result.get("ontology_trace"),
        ).model_dump())

    # ─── sim_v2 인계 패키지 직통 (recipe-4 등가) ───────────────────────

    async def _run_via_simv2(
        self,
        req: SandboxRequest,
        session,
        action,
    ) -> AsyncIterator[StreamEvent]:
        """recipe-4 full pipeline: W71 fixture → W75 translate → W74 stub → W72 invariant.

        Section 4 인계 패키지 (data/slab-v2-handoff.db) 의 action 에 대해
        in-process 안전 실행으로 PASS/FAIL_* 결과를 surface.
        """
        yield self.thinking(
            f"sim_v2 직통 — action {action.fqn} → code {action.code_method_fqn}"
        )

        # 1. Java body 로드
        body_text = load_body_text(session, action.code_method_fqn, action.repo_id)
        if not body_text:
            yield self.error(
                f"sim_v2 code_methods.body_text 누락: {action.code_method_fqn}"
            )
            return

        # 2. sim_v2 translator (W75 idiom 자동 적용)
        yield self.thinking("Java body → sim_v2 translator (W75 idiom rewrite)")
        translated = translate_java_to_python(body_text)
        if translated is None:
            yield self.error("sim_v2 translator 실패")
            return
        python_source, function_name = translated
        yield self.code_gen(python_source)

        # 3. W71 fixture 합성
        yield self.thinking("W71 fixture 합성")
        report = synthesize_fixtures(
            session, action,
            function_name=function_name,
            python_source=python_source,
        )
        if report is None or not report.fixtures:
            yield self.error("W71 fixture 합성 실패 (params object_ref-only 가능)")
            return
        yield self.event(
            "simv2_fixtures",
            count=len(report.fixtures),
            synthesizable=report.synthesizable_params,
            skipped=report.skipped_params,
        )

        # 4. W74 stub_namespace 자동 derive
        yield self.thinking("W74 stub_namespace derive (anchor + AST + entity)")
        stubs = build_stubs(
            session,
            method_fqn=action.code_method_fqn,
            repo_id=action.repo_id,
            python_source=python_source,
        )
        yield self.event(
            "simv2_stubs",
            count=len(stubs),
            sample=list(stubs.keys())[:6],
        )

        if not req.run_after_generate:
            yield self.final(AgentFinalResult(
                ok=True,
                summary=(
                    f"sim_v2 합성 완료 (실행 skip) — "
                    f"{len(report.fixtures)} fixtures · {len(stubs)} stubs"
                ),
                generated_python=python_source,
            ).model_dump())
            return

        # 5a. Sprint 2 — Java baseline 부착 시도 (file-based)
        baseline_map = load_baseline_map(action.code_method_fqn)
        use_oracle = bool(baseline_map)
        if use_oracle:
            yield self.event(
                "simv2_baseline",
                source="file",
                method_fqn=action.code_method_fqn,
                entries=len(baseline_map),
            )

        # 5b. 실행 — baseline 있으면 BehaviorTwinRunner (oracle), 없으면 W72 invariant
        if use_oracle:
            yield self.sandbox_run(
                f"{len(report.fixtures)} fixture · BehaviorTwinRunner (Java baseline {len(baseline_map)}건)"
            )
            case_results = run_fixtures_with_baseline(
                list(report.fixtures),
                function_name=function_name,
                baseline_map=baseline_map,
                stub_namespace=stubs,
            )
        else:
            yield self.sandbox_run(
                f"{len(report.fixtures)} fixture · W72 invariant (baseline 없음)"
            )
            case_results = run_fixtures_in_process(
                list(report.fixtures),
                stub_namespace=stubs,
                declared_return="Any",
            )
        yield self.sandbox_result(case_results)

        passing = sum(
            1 for r in case_results if r.get("invariant_status") == "PASS"
        )
        matched = sum(
            1 for r in case_results if r.get("matched_expected") is True
        )
        summary_oracle = (
            f"oracle (Java baseline {len(baseline_map)}건) — matched {matched}"
            if use_oracle else "invariant only"
        )
        summary = (
            f"sim_v2 직통 — {len(case_results)} fixture · "
            f"PASS {passing} · stubs {len(stubs)} · {summary_oracle}"
        )
        yield self.final(AgentFinalResult(
            ok=passing > 0,
            summary=summary,
            generated_python=python_source,
            sandbox_result={
                "cases": case_results,
                "ok_count": passing,
                "matched_count": matched,
                "stub_summary": {
                    "count": len(stubs),
                    "sample": list(stubs.keys())[:6],
                },
                "baseline_summary": {
                    "enabled": use_oracle,
                    "entries": len(baseline_map),
                    "method_fqn": action.code_method_fqn,
                },
                "via": "sim_v2",
            },
        ).model_dump())

    # ─── step kind — modeling fallback ──────────────────────────────────

    async def _run_via_modeling(self, req: SandboxRequest) -> AsyncIterator[StreamEvent]:
        """step kind 는 modeling 의 simulate 응답이 가장 정확 (test_cases 직접 줌)."""
        from backend.section3.llm.code_generator import generate_python_from_modeling

        parameters = {"target": {"kind": "step", "id": req.target_id}}
        yield self.modeling_call("simulate", parameters)
        try:
            resp = await self.modeling.query(
                intent="simulate", parameters=parameters, request_id=req.request_id
            )
        except Exception as e:
            yield self.error(f"modeling /query 실패: {e}")
            return

        if resp.get("status") in ("error", "unsupported"):
            msg = (resp.get("result") or {}).get("message", "")
            yield self.error(f"modeling 응답 {resp.get('status')}: {msg}", response=resp)
            return

        yield self.modeling_result(resp)
        result = resp.get("result") or {}
        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        cases = [c for c in (result.get("test_cases") or []) if c.get("case_type") in req.case_types]
        if not cases:
            yield self.error("modeling 이 cases 미반환")
            return

        try:
            source = generate_python_from_modeling(result, intent_context=f"step {req.target_id}")
        except Exception as e:
            yield self.error(f"LLM 코드 합성 실패: {e}")
            return
        yield self.code_gen(source)

        if not req.run_after_generate:
            yield self.final(AgentFinalResult(
                ok=True, summary="step 합성 완료 (실행 skip)",
                modeling_response=resp, generated_python=source,
            ).model_dump())
            return

        yield self.sandbox_run(f"{len(cases)} case 격리 실행")
        case_results = run_python_multi(source, cases, timeout_per_case=5.0)
        yield self.sandbox_result(case_results)

        ok = sum(1 for r in case_results if r["execution"]["ok"])
        matched = sum(1 for r in case_results if r.get("matched_expected"))
        yield self.final(AgentFinalResult(
            ok=ok > 0,
            summary=f"step {req.target_id} — {len(case_results)} case · 성공 {ok} · 일치 {matched}",
            modeling_response=resp,
            generated_python=source,
            sandbox_result={"cases": case_results, "ok_count": ok, "matched_count": matched},
            visualization=result.get("ontology_trace"),
        ).model_dump())


# ─── sandbox 입력 형식 wrapping ───────────────────────────────────


def _wrap_for_sandbox(transpiled: dict[str, Any]) -> str:
    """transpiled function → run_python_multi 가 기대하는 stdin/stdout JSON 인터페이스."""
    src = transpiled["python_source"]
    fn = transpiled["function_name"]
    params = transpiled["param_names"]

    runner_lines = [
        "",
        "# ─── sandbox runner wrapper ─────────────────────────────────",
        "import json, sys",
        "from decimal import Decimal",
        "",
        "def _serialize(v):",
        "    if isinstance(v, Decimal):",
        "        return str(v)",
        "    return v",
        "",
        "def run(inputs):",
        f"    param_names = {params!r}",
        "    args = [inputs.get(p) for p in param_names]",
        "    try:",
        f"        out = {fn}(*args)",
        "    except Exception as e:",
        '        return {"ok": False, "error": str(e), "type": e.__class__.__name__}',
        '    return {"ok": True, "result": _serialize(out)}',
        "",
        'if __name__ == "__main__":',
        '    raw = sys.stdin.read() or "{}"',
        "    inputs = json.loads(raw)",
        "    print(json.dumps(run(inputs), ensure_ascii=False, default=str))",
        "",
    ]
    return src + "\n" + "\n".join(runner_lines)


__all__ = ["SandboxAgent"]
