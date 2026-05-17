"""Section 3 ↔ sim_v2 통합 브리지 (Sprint 1 — recipe-4 인계).

목적:
- sim_v2 의 W74 `build_stub_namespace` 와 W72 `TwinInvariantRunner` 를
  Section 3 의 sandbox 흐름에 plug-in.
- 기존 subprocess 경로(`run_python_multi`) 와 동일한 case_result shape 을
  반환하여 frontend / final event 가 회귀 없이 동작.

새 필드:
- case_result["invariant_status"] ∈ {PASS, FAIL_NONDETERMINISTIC,
  FAIL_UNEXPECTED_THROW, FAIL_RETURN_TYPE, ERROR}
- case_result["matched_expected"] = None — 본 경로는 expected_output 구조
  비교 대신 invariant_status 로 판정.

호출 흐름 (sandbox_agent.py 가 사용):
    session = open_sim_v2_session()
    stubs   = build_stubs(session, method_fqn, repo_id, python_source)
    results = run_in_process(python_source, function_name, param_names, cases,
                             stub_namespace=stubs, declared_return=...)

session 이 None 이면 기존 subprocess 경로로 폴백 (sandbox_agent 측 책임).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# 권장 allowed exceptions — recipe-4 의 UC40 permissive 세트.
DEFAULT_ALLOWED_EXCEPTIONS: tuple[str, ...] = (
    "AlgorithmException",
    "IllegalStateException",
    "ValueError",
    "TypeError",
    "RuntimeError",
    "ArithmeticError",
    "AttributeError",
)


def open_sim_v2_session():
    """slab-v2-handoff.db 에 read-only SQLAlchemy session 을 연다.

    DB 가 없거나 sim_v2 의존성 import 실패 시 None 반환 (예외 안 던짐).
    호출자는 None 인 경우 기존 경로로 폴백해야 한다.
    """
    try:
        from backend.sim_v2.demos.uc10_production_inspector.run import (
            PRODUCTION_DB_PATH,
            open_readonly_session,
        )
    except ImportError as e:
        logger.info("sim_v2 임포트 실패 — 폴백: %s", e)
        return None

    if not PRODUCTION_DB_PATH.exists():
        logger.info("sim_v2 DB 미존재: %s — 폴백", PRODUCTION_DB_PATH)
        return None

    try:
        return open_readonly_session()
    except Exception as e:  # noqa: BLE001
        logger.warning("sim_v2 session 열기 실패: %s — 폴백", e)
        return None


def build_stubs(
    session,
    *,
    method_fqn: str,
    repo_id: str,
    python_source: str,
    code_types_lookup_fqns: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """W74 build_stub_namespace 의 thin wrapper.

    실패 시 빈 dict 반환 — 빈 dict 로도 in-process exec 자체는 가능하므로
    호출자가 None-check 분기를 만들 필요 없음.
    """
    try:
        from backend.sim_v2.core.verification.sandbox_stubs import (
            build_stub_namespace,
        )
    except ImportError as e:
        logger.info("W74 임포트 실패: %s — 빈 stub 반환", e)
        return {}

    try:
        return build_stub_namespace(
            session,
            method_fqn=method_fqn,
            repo_id=repo_id,
            python_source=python_source,
            code_types_lookup_fqns=code_types_lookup_fqns,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("build_stub_namespace 실패: %s — 빈 stub 반환", e)
        return {}


def run_in_process(
    *,
    python_source: str,
    function_name: str,
    param_names: list[str],
    cases: list[dict[str, Any]],
    stub_namespace: Optional[dict[str, Any]] = None,
    declared_return: str = "Any",
    allowed_exceptions: tuple[str, ...] = DEFAULT_ALLOWED_EXCEPTIONS,
) -> list[dict[str, Any]]:
    """W72 TwinInvariantRunner.check() 를 case 별로 실행하고 결과를 section3 shape 로 반환.

    반환 shape (case 당):
        {
            "case_id": str | None,
            "case_type": str | None,
            "input": dict,
            "expected_output": Any,
            "execution": {
                "ok": bool,                  # invariant PASS 여부
                "result": {"ok": bool, "result": str},  # first_output_repr
                "stdout": "",                # in-process 라 비어 있음
                "stderr": "",
                "elapsed_sec": float,
                "error": str | None,
                "returncode": 0 | 1,
            },
            "matched_expected": None,        # invariant 경로는 미사용
            "invariant_status": str,         # PASS / FAIL_* / ERROR
        }

    `param_names` 순서대로 case["input"] 의 값을 positional arg 로 매핑.
    """
    from backend.sim_v2.core.verification.behavior_twin_runner import (
        BehaviorFixture,
    )
    from backend.sim_v2.core.verification.twin_invariants import (
        TwinInvariantRunner,
    )

    runner = TwinInvariantRunner(
        declared_return=declared_return,
        allowed_exceptions=allowed_exceptions,
        stub_namespace=stub_namespace,
    )

    out: list[dict[str, Any]] = []
    for i, tc in enumerate(cases):
        inputs = tc.get("input") or {}
        args = tuple(inputs.get(p) for p in param_names)

        fixture = BehaviorFixture(
            fixture_id=str(tc.get("case_id") or f"case_{i}"),
            python_source=python_source,
            function_name=function_name,
            input_args=args,
            input_kwargs={},
            expected_output=tc.get("expected_output"),
        )

        start = time.monotonic()
        chk = runner.check(fixture)
        elapsed = time.monotonic() - start

        passed = chk.passed
        out.append({
            "case_id": tc.get("case_id"),
            "case_type": tc.get("case_type"),
            "input": inputs,
            "expected_output": tc.get("expected_output"),
            "execution": {
                "ok": passed,
                "result": {
                    "ok": passed,
                    "result": chk.first_output_repr,
                },
                "stdout": "",
                "stderr": "",
                "elapsed_sec": round(elapsed, 4),
                "error": chk.error or (None if passed else chk.status),
                "returncode": 0 if passed else 1,
            },
            "matched_expected": None,
            "invariant_status": chk.status,
        })
    return out


def load_action(session, action_fqn: str, repo_id: str):
    """sim_v2 ProductionAction (ActionView) lookup. 실패 시 None."""
    try:
        from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
            load_actions,
        )
    except ImportError as e:
        logger.info("production_domain_loader 임포트 실패: %s", e)
        return None
    try:
        actions = load_actions(session, repo_id)
        return next((a for a in actions if a.fqn == action_fqn), None)
    except Exception as e:  # noqa: BLE001
        logger.warning("load_actions 실패: %s", e)
        return None


def load_body_text(session, code_method_fqn: str, repo_id: str) -> Optional[str]:
    """code_methods.body_text 조회. 없으면 None."""
    from sqlalchemy import text

    try:
        row = session.execute(
            text(
                "SELECT body_text FROM code_methods "
                "WHERE fqn = :f AND repo_id = :r"
            ),
            {"f": code_method_fqn, "r": repo_id},
        ).fetchone()
        return row[0] if row and row[0] else None
    except Exception as e:  # noqa: BLE001
        logger.warning("body_text 조회 실패: %s", e)
        return None


def translate_java_to_python(body_text: str) -> Optional[tuple[str, str]]:
    """Java body_text → Section3Translator (sim_v2 subclass, W75 idiom 자동 + section3 idiom patch).

    반환: (python_source, function_name) 또는 None (파싱/번역 실패).
    """
    try:
        import tree_sitter_java as tsjava
        from tree_sitter import Language, Parser

        from backend.section3.section3_translator import Section3Translator
    except ImportError as e:
        logger.info("sim_v2 translator 임포트 실패: %s", e)
        return None

    translator = Section3Translator()
    if translator is None:
        # sim_v2 base 가 없을 때 (Section3Translator.__new__ 가 None 반환)
        return None

    try:
        wrapped = f"public class C {{ {body_text} }}"
        tree = Parser(Language(tsjava.language())).parse(wrapped.encode())
        method = None
        for c in tree.root_node.children:
            if c.type == "class_declaration":
                body_n = next(
                    (x for x in c.children if x.type == "class_body"), None
                )
                if body_n is None:
                    return None
                for m in body_n.named_children:
                    if m.type == "method_declaration":
                        method = m
                        break
        if method is None:
            return None

        result = translator.translate(method, indent=0)
    except Exception as e:  # noqa: BLE001
        logger.warning("translate 실패: %s", e)
        return None

    src = result.python_source
    if not src:
        return None
    first = src.splitlines()[0]
    if not first.startswith("def "):
        return None
    fn = first[4:].split("(", 1)[0].strip()
    return src, fn


def synthesize_fixtures(
    session,
    action,
    *,
    function_name: str,
    python_source: str,
    max_combinations: int = 12,
):
    """W71 synthesize_fixtures_for_action 래퍼. 실패 시 None."""
    try:
        from backend.sim_v2.core.verification.fixture_synthesizer import (
            synthesize_fixtures_for_action,
        )
    except ImportError as e:
        logger.info("W71 임포트 실패: %s", e)
        return None
    try:
        return synthesize_fixtures_for_action(
            session, action,
            function_name=function_name,
            python_source=python_source,
            max_combinations=max_combinations,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("synthesize_fixtures_for_action 실패: %s", e)
        return None


def run_fixtures_with_baseline(
    fixtures,
    *,
    function_name: str,
    baseline_map: Optional[dict[tuple, Any]] = None,
    stub_namespace: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Sprint 2 — BehaviorTwinRunner 로 fixture 실행 + Java baseline 비교.

    `baseline_map`: dict 키 = `input_args` tuple (self 포함), 값 = expected output.
    제공된 fixture 만 baseline 부착하여 비교. baseline 미제공 fixture 는
    actual_value 만 surface 하고 status='UNVERIFIED'.

    반환 (case 당):
        {
            "case_id", "case_type", "input", "expected_value", "actual_value",
            "output_match": bool | None,
            "execution": {...},
            "matched_expected": bool | None,
            "status": "PASS" / "FAIL_OUTPUT" / "ERROR" / "UNVERIFIED",
            "diff_summary": str,
        }
    """
    from backend.sim_v2.core.verification.behavior_twin_runner import (
        BehaviorFixture,
        BehaviorFixtureStore,
        BehaviorTwinRunner,
    )

    # baseline 부착 — fixture 의 expected_output 을 입력 args 매칭으로 채움
    bm = baseline_map or {}
    annotated: list[BehaviorFixture] = []
    for fix in fixtures:
        key = tuple(fix.input_args)
        if key in bm:
            annotated.append(BehaviorFixture(
                fixture_id=fix.fixture_id,
                python_source=fix.python_source,
                function_name=fix.function_name,
                input_args=fix.input_args,
                input_kwargs=fix.input_kwargs,
                expected_output=bm[key],
            ))
        else:
            annotated.append(fix)

    store = BehaviorFixtureStore(annotated)
    runner = BehaviorTwinRunner(store, stub_namespace=stub_namespace)

    out: list[dict[str, Any]] = []
    for fix in annotated:
        start = time.monotonic()
        oresult = runner.run_fixture(fix.fixture_id, plugin="section3", apply_diffs={})
        elapsed = time.monotonic() - start

        has_baseline = tuple(fix.input_args) in bm
        match = oresult.output_diff.is_equivalent if has_baseline else None
        status = (
            oresult.status
            if has_baseline
            else ("UNVERIFIED" if oresult.error is None else "ERROR")
        )
        passed = (status == "PASS") or (status == "UNVERIFIED" and oresult.error is None)

        out.append({
            "case_id": fix.fixture_id,
            "case_type": "synthesized",
            "input": {
                "args": [_safe_jsonable(v) for v in fix.input_args],
                "kwargs": {k: _safe_jsonable(v) for k, v in fix.input_kwargs.items()},
            },
            "expected_value": _safe_jsonable(fix.expected_output) if has_baseline else None,
            "actual_value": _safe_jsonable(oresult.python_proposal_output),
            "output_match": match,
            "execution": {
                "ok": passed,
                "result": {
                    "ok": passed,
                    "result": _safe_jsonable(oresult.python_proposal_output),
                },
                "stdout": "",
                "stderr": "",
                "elapsed_sec": round(elapsed, 4),
                "error": oresult.error,
                "returncode": 0 if passed else 1,
            },
            "matched_expected": match,
            "invariant_status": status,
            "diff_summary": oresult.output_diff.summary or "",
        })
    return out


def run_fixtures_in_process(
    fixtures,
    *,
    stub_namespace: Optional[dict[str, Any]] = None,
    declared_return: str = "Any",
    allowed_exceptions: tuple[str, ...] = DEFAULT_ALLOWED_EXCEPTIONS,
) -> list[dict[str, Any]]:
    """W71 이 만든 BehaviorFixture 리스트를 W72 invariant 로 실행.

    `run_in_process` 와 동일한 case_result shape 을 반환.
    """
    from backend.sim_v2.core.verification.twin_invariants import (
        TwinInvariantRunner,
    )

    runner = TwinInvariantRunner(
        declared_return=declared_return,
        allowed_exceptions=allowed_exceptions,
        stub_namespace=stub_namespace,
    )

    out: list[dict[str, Any]] = []
    for fix in fixtures:
        start = time.monotonic()
        chk = runner.check(fix)
        elapsed = time.monotonic() - start
        passed = chk.passed
        out.append({
            "case_id": fix.fixture_id,
            "case_type": "synthesized",
            "input": {
                "args": [_safe_jsonable(v) for v in fix.input_args],
                "kwargs": {k: _safe_jsonable(v) for k, v in fix.input_kwargs.items()},
            },
            "expected_output": fix.expected_output,
            "execution": {
                "ok": passed,
                "result": {"ok": passed, "result": chk.first_output_repr},
                "stdout": "",
                "stderr": "",
                "elapsed_sec": round(elapsed, 4),
                "error": chk.error or (None if passed else chk.status),
                "returncode": 0 if passed else 1,
            },
            "matched_expected": None,
            "invariant_status": chk.status,
        })
    return out


def _safe_jsonable(v: Any) -> Any:
    """fixture input 의 Decimal / 큰 int 등을 frontend 표시용으로 안전화."""
    from decimal import Decimal

    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (int, float, bool, str, type(None))):
        return v
    return repr(v)


def find_action_candidates(
    session,
    user_query: str,
    repo_id: str,
    *,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Sprint 4 helper — user 자연어 query 로 후보 action 들을 찾아 반환.

    1) KoreanTermResolver (W77 + W78) — business_terms 에서 매칭되는 term FQN 도출
    2) `actions.declared_on_term` 가 매칭 term 의 fqn 인 액션
    3) 보완 — actions.label / aliases_json 에 query token 이 LIKE 매치 되는 액션

    반환 (각 후보):
        { "fqn", "label", "code_method_fqn", "score", "matched_via" }
    """
    from sqlalchemy import text

    out: dict[str, dict[str, Any]] = {}

    # 1) W77+W78 — term resolver
    try:
        from backend.sim_v2.core.search.korean_term_resolver import (
            KoreanTermResolver,
        )
        resolver = KoreanTermResolver.from_session(session, repo_id)
        hits = resolver.resolve(user_query, use_fuzzy=True)
    except Exception as e:
        logger.info("KoreanTermResolver 실패 → LIKE fallback 만 사용: %s", e)
        hits = []

    term_fqns_by_score: dict[str, float] = {}
    for h in hits[:8]:
        term_fqns_by_score[h.term.fqn] = h.score

    # 2) actions where declared_on_term in matched terms
    if term_fqns_by_score:
        placeholders = ",".join(f":t{i}" for i in range(len(term_fqns_by_score)))
        params = {f"t{i}": fqn for i, fqn in enumerate(term_fqns_by_score)}
        params["r"] = repo_id
        try:
            rows = session.execute(
                text(
                    f"SELECT fqn, label, description, declared_on_term "
                    f"FROM actions WHERE repo_id = :r "
                    f"AND declared_on_term IN ({placeholders})"
                ),
                params,
            ).fetchall()
            for row in rows:
                fqn = row[0]
                if fqn in out:
                    continue
                out[fqn] = {
                    "fqn": fqn,
                    "label": row[1] or fqn.rsplit(".", 1)[-1],
                    "code_method_fqn": _extract_method_fqn_from_description(row[2]),
                    "score": term_fqns_by_score.get(row[3], 5.0),
                    "matched_via": f"term:{row[3]}",
                }
        except Exception as e:
            logger.warning("actions by declared_on_term 조회 실패: %s", e)

    # 3) actions.label / aliases LIKE 매치 — 보완
    tokens = [t for t in user_query.split() if len(t) >= 2]
    for tok in tokens[:4]:
        try:
            rows = session.execute(
                text(
                    "SELECT fqn, label, description FROM actions "
                    "WHERE repo_id = :r AND ("
                    "  lower(label) LIKE :pat OR "
                    "  lower(aliases_json) LIKE :pat OR "
                    "  lower(fqn) LIKE :pat"
                    ") LIMIT 5"
                ),
                {"r": repo_id, "pat": f"%{tok.lower()}%"},
            ).fetchall()
            for row in rows:
                fqn = row[0]
                if fqn in out:
                    out[fqn]["score"] = out[fqn]["score"] + 1.0
                    continue
                out[fqn] = {
                    "fqn": fqn,
                    "label": row[1] or fqn.rsplit(".", 1)[-1],
                    "code_method_fqn": _extract_method_fqn_from_description(row[2]),
                    "score": 3.0,
                    "matched_via": f"like:{tok}",
                }
        except Exception as e:
            logger.warning("actions LIKE 조회 실패 (token=%s): %s", tok, e)

    ranked = sorted(out.values(), key=lambda x: -x["score"])
    return ranked[:top_n]


def _extract_method_fqn_from_description(description: Optional[str]) -> Optional[str]:
    """actions.description 의 '자동 추천 — <method_fqn>' 패턴에서 method_fqn 추출."""
    if not description:
        return None
    try:
        from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
            extract_method_fqn_from_description,
        )
        return extract_method_fqn_from_description(description)
    except Exception:
        return None


def quick_diagnose_action(
    session,
    action,
) -> dict[str, Any]:
    """Sprint 3 helper — 후보 action 에 대해 W71→W74→W72 quick diagnose.

    반환: { "ok", "fixtures", "stubs", "passing", "primary_failure" }
    """
    if not action.code_method_fqn:
        return {
            "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
            "primary_failure": "code_method_fqn 없음",
        }
    body = load_body_text(session, action.code_method_fqn, action.repo_id)
    if not body:
        return {
            "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
            "primary_failure": "body_text 없음",
        }
    translated = translate_java_to_python(body)
    if translated is None:
        return {
            "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
            "primary_failure": "translate 실패",
        }
    py_src, fn_name = translated
    report = synthesize_fixtures(
        session, action, function_name=fn_name, python_source=py_src,
    )
    if report is None or not report.fixtures:
        return {
            "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
            "primary_failure": "fixture 합성 실패 (params object_ref-only)",
        }
    stubs = build_stubs(
        session,
        method_fqn=action.code_method_fqn,
        repo_id=action.repo_id,
        python_source=py_src,
    )
    results = run_fixtures_in_process(
        list(report.fixtures), stub_namespace=stubs,
    )
    passing = sum(1 for r in results if r.get("invariant_status") == "PASS")
    primary_fail = ""
    if passing < len(results):
        from collections import Counter
        fails = [r["invariant_status"] for r in results if r["invariant_status"] != "PASS"]
        c = Counter(fails).most_common(1)
        if c:
            primary_fail = c[0][0]
    return {
        "ok": passing > 0,
        "fixtures": len(results),
        "stubs": len(stubs),
        "passing": passing,
        "primary_failure": primary_fail,
    }


def load_baseline_map(method_fqn: str) -> dict[tuple, Any]:
    """Sprint 2 — Java baseline 로드 (file-based, optional).

    경로 규칙: `data/baselines/{method_fqn.replace('.', '_')}.json`
    JSON shape:
        [
            { "args": [arg0, arg1, ...], "expected": <any> },
            ...
        ]
    args 의 list 는 input_args tuple 로 변환되어 매칭 키로 사용.

    파일 없으면 빈 dict — `_run_via_simv2` 가 정상 fallthrough.
    """
    import json
    from pathlib import Path

    safe = method_fqn.replace(".", "_").replace("(", "_").replace(")", "_").replace(",", "_")
    p = Path("data") / "baselines" / f"{safe}.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("baseline 파일 로드 실패 %s: %s", p, e)
        return {}
    if not isinstance(raw, list):
        return {}
    out: dict[tuple, Any] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        args = entry.get("args")
        if not isinstance(args, list):
            continue
        out[tuple(args)] = entry.get("expected")
    return out


__all__ = [
    "DEFAULT_ALLOWED_EXCEPTIONS",
    "open_sim_v2_session",
    "load_action",
    "load_body_text",
    "load_baseline_map",
    "translate_java_to_python",
    "synthesize_fixtures",
    "build_stubs",
    "find_action_candidates",
    "quick_diagnose_action",
    "run_in_process",
    "run_fixtures_in_process",
    "run_fixtures_with_baseline",
]
