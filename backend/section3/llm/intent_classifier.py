"""자연어 사용자 메시지 → modeling intent + parameters 분류.

원칙:
- 분류 대상은 modeling 의 3 intent: impact_analysis / simulate / explain
- parameters 는 modeling 측 schema 정확히 따름:
  - impact_analysis: { target: { kind: table|method|class|standard_value|order, id: str } }
  - simulate:        { target: { kind: step|method|class, id: str } }
  - explain:         natural_language 만, parameters 없음
- LLM 이 분류 불가 / parameter 부족 시 confidence 낮춤 — bridge_agent 가 사용자에게 되묻기
"""

from __future__ import annotations

import json
from typing import Any

from backend.section3.contracts import ChatMessage, IntentClassification
from backend.section3.llm.openai_client import LLMClient

SYSTEM_PROMPT = """당신은 제조 IT 시스템의 ontology query 어시스턴트입니다.
사용자의 자연어 질문을 받아, 적절한 modeling API intent + parameters 로 변환합니다.

가능한 intent (셋 중 하나):
1. impact_analysis — "X 를 바꾸면 무엇이 영향 받나" / "X 변경 시 어디가 깨지나"
   parameters: { "target": { "kind": "<table|method|class|standard_value|order|column>", "id": "<식별자>" } }

2. simulate — "X 의 테스트 케이스 만들어줘" / "X 시뮬레이션 해보자"
   parameters: { "target": { "kind": "<step|method|class>", "id": "<식별자>" } }

3. explain — "X 가 어디서 계산되나" / "X 가 뭐야" (위치/의미 설명)
   parameters: {}, natural_language 만 사용

분류 규칙:
- "영향" / "바꾸면" / "변경 시" → impact_analysis
- "테스트" / "시뮬" / "샘플 케이스" → simulate
- "어디" / "뭐야" / "찾아줘" → explain
- target.id 가 모호하면 빈 문자열 — 추후 modeling 이 need_more_info 로 응답

응답은 반드시 다음 JSON 형식:
{
  "modeling_intent": "impact_analysis" | "simulate" | "explain",
  "parameters": { ... },
  "confidence": 0.0 ~ 1.0,
  "reasoning": "왜 이렇게 분류했는지 1~2 문장",
  "suggested_followups": ["사용자가 다음에 물어볼만한 질문", ...]
}
"""


def classify_intent(
    user_message: str,
    history: list[ChatMessage] | None = None,
    llm: LLMClient | None = None,
) -> IntentClassification:
    """자연어 → IntentClassification."""
    if llm is None:
        from backend.section3.llm.openai_client import get_llm_client
        llm = get_llm_client()

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        # 마지막 6턴만 컨텍스트로 (토큰 절약)
        for m in history[-6:]:
            if m.role in ("user", "assistant"):
                messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_message})

    data = llm.chat_json(messages, temperature=0.0)

    # 안전망 — LLM 이 잘못된 형식 줬을 때 fallback
    intent = data.get("modeling_intent")
    if intent not in ("impact_analysis", "simulate", "explain"):
        return IntentClassification(
            modeling_intent="explain",  # 기본 — 안전한 explain 으로 fall back
            parameters={},
            confidence=0.0,
            reasoning=f"LLM 분류 실패 → explain fallback. raw={json.dumps(data)[:200]}",
        )

    return IntentClassification(
        modeling_intent=intent,
        parameters=data.get("parameters") or {},
        confidence=float(data.get("confidence", 0.5)),
        reasoning=data.get("reasoning", ""),
        suggested_followups=data.get("suggested_followups") or [],
    )


__all__ = ["classify_intent", "SYSTEM_PROMPT"]
