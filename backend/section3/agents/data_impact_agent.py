"""데이터 변경 영향도 분석 agent — table / standard_value / order 단위.

흐름은 CodeImpactAgent 와 동일하지만 target.kind 가 데이터 layer (table/standard/order).

* 사용자 요구의 "기준 변경 / slab data 변경 영향도" 매핑:
    - "기준" → standard_value
    - "slab data" → table
    - "주문" → order (14 Step 전체 시뮬)
"""

from __future__ import annotations

from typing import AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.contracts import (
    AgentFinalResult,
    DataImpactRequest,
    StreamEvent,
)


class DataImpactAgent(BaseAgent):
    name = "data_impact"

    async def run(self, req: DataImpactRequest) -> AsyncIterator[StreamEvent]:
        yield self.thinking(
            f"데이터 변경 영향도 agent — {req.target_kind}={req.target_id!r}"
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
        # "대상 미존재" 응답 — 친절 안내
        if "대상 미존재" in (result.get("risk_factors") or []):
            yield self.error(
                f"'{req.target_id}' 은(는) ontology DB 의 {req.target_kind} 에 등록되지 않았습니다. "
                "정확한 id 를 자연어 검색으로 찾아보세요.",
                response=resp,
            )
            return

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


__all__ = ["DataImpactAgent"]
