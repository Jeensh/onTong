"""샌드박스 agent — 테스트 데이터 생성 + Python 코드 합성 + 격리 실행.

흐름:
1. modeling.query(intent=simulate, target=...) → test_cases / data_dependencies / ontology_trace
2. ontology trace 를 layer 순서로 스캔하며 progress 이벤트 송출
3. modeling 응답 메타 → LLM 코드 합성 (slab-design 참조 0건)
4. 각 test_case 별 sandbox 격리 실행
5. 결과 + matched_expected 종합 반환
"""

from __future__ import annotations

from typing import AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.contracts import (
    AgentFinalResult,
    SandboxRequest,
    StreamEvent,
    StreamEventType,
)
from backend.section3.llm.code_generator import generate_python_from_modeling
from backend.section3.sandbox.runner import run_python_multi


class SandboxAgent(BaseAgent):
    name = "sandbox"

    async def run(self, req: SandboxRequest) -> AsyncIterator[StreamEvent]:
        yield self.thinking(
            f"샌드박스 agent — {req.target_kind}={req.target_id!r}, "
            f"case_types={req.case_types}"
        )

        # 1. modeling.simulate 호출
        parameters = {"target": {"kind": req.target_kind, "id": req.target_id}}
        yield self.modeling_call("simulate", parameters)
        try:
            modeling_resp = await self.modeling.query(
                intent="simulate", parameters=parameters, request_id=req.request_id
            )
        except Exception as e:
            yield self.error(f"modeling /query 호출 실패: {e}")
            return

        # 2. missing_info / unsupported / error 분기
        status = modeling_resp.get("status")
        if status == "need_more_info":
            yield self.need_more_info(modeling_resp.get("missing_info") or {})
            return
        if status in ("unsupported", "error"):
            result = modeling_resp.get("result") or {}
            yield self.error(
                f"modeling 응답 {status}: {result.get('message', '')}",
                response=modeling_resp,
            )
            return

        yield self.modeling_result(modeling_resp)

        result = modeling_resp.get("result") or {}

        # 3. layer 순서로 스캔 progress
        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        # 4. test_cases 추출 + case_types 필터
        all_cases = result.get("test_cases") or []
        cases = [c for c in all_cases if c.get("case_type") in req.case_types]
        if not cases:
            yield self.error(
                f"modeling 이 반환한 test_cases 중 요청한 case_types {req.case_types} 에 해당하는 것이 없음"
            )
            return

        # 5. Python 코드 합성
        yield self.thinking(
            f"LLM 으로 Python 코드 합성 중 — modeling 응답 메타만 사용 (slab-design 참조 0건)"
        )
        intent_context = (
            f"{req.target_kind}={req.target_id} — "
            f"{result.get('summary', '')}"
        )
        try:
            source = generate_python_from_modeling(result, intent_context=intent_context)
        except Exception as e:
            yield self.error(f"LLM 코드 합성 실패: {e}")
            return
        yield self.code_gen(source)

        # 6. sandbox 실행
        if not req.run_after_generate:
            yield self.final(
                AgentFinalResult(
                    ok=True,
                    summary="코드 합성 완료 (실행 skip)",
                    modeling_response=modeling_resp,
                    generated_python=source,
                ).model_dump()
            )
            return

        yield self.sandbox_run(f"{len(cases)}개 케이스 격리 subprocess 실행")
        case_results = run_python_multi(source, cases, timeout_per_case=5.0)
        yield self.sandbox_result(case_results)

        # 7. 종합
        ok_count = sum(1 for r in case_results if r["execution"]["ok"])
        matched_count = sum(1 for r in case_results if r.get("matched_expected"))
        summary = (
            f"{len(case_results)}개 케이스 실행 — 성공 {ok_count} / "
            f"expected 일치 {matched_count}"
        )
        yield self.final(
            AgentFinalResult(
                ok=ok_count > 0,
                summary=summary,
                modeling_response=modeling_resp,
                generated_python=source,
                sandbox_result={"cases": case_results, "ok_count": ok_count, "matched_count": matched_count},
                visualization=result.get("ontology_trace"),
            ).model_dump()
        )


__all__ = ["SandboxAgent"]
