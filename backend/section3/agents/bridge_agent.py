"""온톨로지 브릿지 agent (chat) — Section 3 의 메인 entry.

흐름:
1. 사용자 자연어 message + history
2. LLM 으로 intent 분류 (impact_analysis / simulate / explain)
3. 적절한 task agent 호출 (또는 explain 은 자체 처리 — modeling.query 직접)
4. task agent 의 streaming events 를 그대로 forward + chat assistant message 부착

원칙:
- bridge agent 는 LLM 으로 자연어 → intent 만 변환. 도메인 지식 hardcoded 0건.
- explain intent 는 task agent 없이 modeling.query 직접 호출 + layer 스캔만 표시.
"""

from __future__ import annotations

from typing import AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.agents.code_impact_agent import CodeImpactAgent
from backend.section3.agents.data_impact_agent import DataImpactAgent
from backend.section3.agents.sandbox_agent import SandboxAgent
from backend.section3.contracts import (
    AgentFinalResult,
    ChatMessage,
    ChatRequest,
    CodeImpactRequest,
    DataImpactRequest,
    SandboxRequest,
    StreamEvent,
)
from backend.section3.llm.intent_classifier import classify_intent


class BridgeAgent(BaseAgent):
    name = "bridge"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sandbox = SandboxAgent(self.modeling, self.llm)
        self._code_impact = CodeImpactAgent(self.modeling, self.llm)
        self._data_impact = DataImpactAgent(self.modeling, self.llm)

    async def run(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield self.thinking(f"의도 분석 중 — {req.message!r}")

        try:
            ic = classify_intent(req.message, req.history, llm=self.llm)
        except Exception as e:
            yield self.error(f"의도 분류 실패: {e}")
            return

        yield self.event(
            "intent_classification",
            modeling_intent=ic.modeling_intent,
            parameters=ic.parameters,
            confidence=ic.confidence,
            reasoning=ic.reasoning,
            suggested_followups=ic.suggested_followups,
        )

        # routing
        target = (ic.parameters or {}).get("target") or {}
        kind = target.get("kind")
        target_id = target.get("id")

        if ic.modeling_intent == "explain":
            # explain 은 task agent 없이 직접 처리
            async for ev in self._handle_explain(req.message):
                yield ev
            return

        if ic.modeling_intent == "simulate":
            if not target_id or kind not in ("step", "method", "class"):
                # parameter 부족 — modeling missing_info 형식으로 사용자에게 되묻기
                yield self.need_more_info({
                    "reason": "어떤 step 을 시뮬할지 명시 필요 (예: 'Step 1', 'thickness')",
                    "questions": [{
                        "field": "target",
                        "question": "어느 step / method 를 시뮬할까요?",
                        "input_type": "text",
                    }],
                })
                return
            sb_req = SandboxRequest(
                target_kind=kind if kind in ("step", "method", "class") else "step",
                target_id=target_id,
            )
            async for ev in self._sandbox.run(sb_req):
                yield ev
            return

        if ic.modeling_intent == "impact_analysis":
            if not target_id or not kind:
                yield self.need_more_info({
                    "reason": "어떤 대상의 변경 영향을 분석할지 명시 필요",
                    "questions": [{
                        "field": "target.kind",
                        "question": "변경 대상이 무엇인가요?",
                        "input_type": "select",
                        "options": [
                            {"id": "table", "label": "테이블"},
                            {"id": "method", "label": "메서드"},
                            {"id": "class", "label": "클래스"},
                            {"id": "standard_value", "label": "SC 기준값"},
                            {"id": "order", "label": "주문"},
                        ],
                    }],
                })
                return
            if kind in ("method", "class", "column"):
                ci_req = CodeImpactRequest(target_kind=kind, target_id=target_id)
                async for ev in self._code_impact.run(ci_req):
                    yield ev
            else:
                di_req = DataImpactRequest(target_kind=kind, target_id=target_id)
                async for ev in self._data_impact.run(di_req):
                    yield ev
            return

        yield self.error(f"지원하지 않는 intent: {ic.modeling_intent}")

    async def _handle_explain(self, message: str) -> AsyncIterator[StreamEvent]:
        """explain intent — modeling.query 직접 호출 + layer 스캔."""
        yield self.modeling_call("explain", {"natural_language": message})
        try:
            resp = await self.modeling.query(
                intent="explain", natural_language=message
            )
        except Exception as e:
            yield self.error(f"modeling /query (explain) 호출 실패: {e}")
            return

        status = resp.get("status")
        if status in ("unsupported", "error"):
            result = resp.get("result") or {}
            yield self.error(f"explain 응답 {status}: {result.get('message')}", response=resp)
            return

        yield self.modeling_result(resp)

        result = resp.get("result") or {}
        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        summary = result.get("summary") or "위치 정보를 조회했습니다"
        yield self.final(
            AgentFinalResult(
                ok=True,
                summary=summary,
                modeling_response=resp,
                visualization=result.get("ontology_trace"),
            ).model_dump()
        )


__all__ = ["BridgeAgent"]
