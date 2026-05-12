"""코드 변경 영향도 분석 agent — method / class / column 단위.

흐름:
1. modeling.query(intent=impact_analysis, target={kind:method|class|column, id}) 호출
2. response 의 direct_impact / indirect_impact / risk_level / ontology_trace 그대로 forward
3. layer 순서 스캔 (Method → Step → 다운스트림 Step) progress
4. risk_level 에 따라 사용자에게 안내 message
"""

from __future__ import annotations

from typing import AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.contracts import (
    AgentFinalResult,
    CodeImpactRequest,
    StreamEvent,
)


class CodeImpactAgent(BaseAgent):
    name = "code_impact"

    async def run(self, req: CodeImpactRequest) -> AsyncIterator[StreamEvent]:
        yield self.thinking(
            f"코드 영향도 agent — {req.target_kind}={req.target_id!r}"
        )

        parameters = {"target": {"kind": req.target_kind, "id": req.target_id}}
        yield self.modeling_call("impact_analysis", parameters)
        try:
            resp = await self.modeling.query(
                intent="impact_analysis",
                parameters=parameters,
                request_id=req.request_id,
            )
        except Exception as e:
            yield self.error(f"modeling /query 호출 실패: {e}")
            return

        status = resp.get("status")
        if status == "need_more_info":
            yield self.need_more_info(resp.get("missing_info") or {})
            return
        if status in ("unsupported", "error"):
            result = resp.get("result") or {}
            yield self.error(
                f"modeling 응답 {status}: {result.get('message', '')}",
                response=resp,
            )
            return

        yield self.modeling_result(resp)

        result = resp.get("result") or {}
        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        risk = result.get("risk_level", "UNKNOWN")
        factors = result.get("risk_factors") or []
        summary = result.get("summary") or f"{req.target_kind} {req.target_id} 영향 분석 완료"

        yield self.final(
            AgentFinalResult(
                ok=True,
                summary=f"[{risk}] {summary}" + (f" · 위험요인: {', '.join(factors)}" if factors else ""),
                modeling_response=resp,
                visualization=result.get("ontology_trace"),
            ).model_dump()
        )


__all__ = ["CodeImpactAgent"]
