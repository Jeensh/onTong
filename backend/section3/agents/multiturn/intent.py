"""Phase 2 Gate I — multiturn intent classifier (simulate / impact / ambiguous).

기존 `backend/section3/llm/intent_classifier.py` 와 별개:
  - 기존: 3 intent (impact_analysis / simulate / explain) + parameters
  - 신규: 3 intent (simulate / impact / ambiguous) — Gate I 두 분기 + 모호

ambiguous 면 UI 가 "어느 쪽이 의도?" 카드 surface (spec v2 §1.1).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


MultiturnIntent = Literal[
    "simulate", "impact", "ambiguous", "locate", "explain", "hypothesis",
]
_VALID_INTENTS: frozenset[str] = frozenset(
    {"simulate", "impact", "ambiguous", "locate", "explain", "hypothesis"},
)


# ─────────────────────────────────────────────────────────────────────────────
# DTO
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IntentDecision:
    intent: MultiturnIntent
    confidence: float
    reasoning: str
    search_terms: list[str] = field(default_factory=list)
    # Phase 13c — hypothesis intent 용. 일반 intent 면 빈 list. 각 dict 는
    # {"var": str, "op": str, "value": str, "unit": str} 형태.
    conditions: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.intent not in _VALID_INTENTS:
            raise ValueError(
                f"intent must be one of {sorted(_VALID_INTENTS)}, got {self.intent!r}",
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0, 1], got {self.confidence}",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Protocol — test 에서 swap-able
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class MultiturnIntentClassifier(Protocol):
    def classify(self, user_query: str) -> IntentDecision: ...


# ─────────────────────────────────────────────────────────────────────────────
# Stub — test fixture
# ─────────────────────────────────────────────────────────────────────────────


class StubIntentClassifier:
    """test 용. forced_intent + 특정 query 별 override 지원."""

    def __init__(
        self,
        *,
        forced_intent: MultiturnIntent = "ambiguous",
        forced_confidence: float = 0.5,
        forced_reasoning: str = "stub",
        forced_search_terms: list[str] | None = None,
        forced_conditions: list[dict[str, str]] | None = None,
        per_query: dict[str, MultiturnIntent] | None = None,
    ) -> None:
        self._forced_intent = forced_intent
        self._forced_confidence = forced_confidence
        self._forced_reasoning = forced_reasoning
        self._forced_search_terms = list(forced_search_terms or [])
        self._forced_conditions = list(forced_conditions or [])
        self._per_query = per_query or {}

    def classify(self, user_query: str) -> IntentDecision:
        for needle, intent in self._per_query.items():
            if needle in user_query:
                return IntentDecision(
                    intent=intent,
                    confidence=self._forced_confidence,
                    reasoning=f"stub: matched {needle!r}",
                    search_terms=list(self._forced_search_terms),
                    conditions=list(self._forced_conditions),
                )
        return IntentDecision(
            intent=self._forced_intent,
            confidence=self._forced_confidence,
            reasoning=self._forced_reasoning,
            search_terms=list(self._forced_search_terms),
            conditions=list(self._forced_conditions),
        )


# ─────────────────────────────────────────────────────────────────────────────
# LLM-based — OpenAI (chat_json)
# ─────────────────────────────────────────────────────────────────────────────


_SYSTEM_PROMPT = """당신은 제조 IT 시스템의 ontology query 어시스턴트입니다.
사용자의 자연어 질문이 여섯 카테고리 중 어느 쪽인지 분류합니다.

분류 라벨 (여섯 중 하나):
1. simulate — "X 시뮬해줘" / "X 테스트 케이스 만들어줘" / "X 돌려보자"
2. impact — "X 바꾸면 어디 영향?" / "X 변경 시 어떤 모듈 깨지나" / "X 의존 관계"
3. locate — "X 어디 있나?" / "X 어디서 정의?" / "X 위치" / "어느 파일에"
4. explain — "X 뭐함?" / "X 가 뭐지?" / "X 동작 설명" / "X 가 어떻게 계산?"
5. hypothesis — "X 가 Y 이면?" / "X 가 임계값 미만이면 ...?" / "X = 0 일 때 어떤 결과?"
   (boundary value / edge case 질의 — 조건 → 결과를 묻는 형식)
6. ambiguous — 의도 불명 또는 위 모두 해당할 수 있는 경우

판단 가이드:
- locate 와 explain 은 destructive 가 아닌 read-only 조회/이해 의도. "어디 / 위치" 는 locate,
  "뭐함 / 어떻게 / 설명" 은 explain. 둘 사이 모호하면 explain 으로 우선.
- "X 어디서 계산해?" 같이 위치+동작 모두 포함이면 explain (응답이 더 풍부).
- "X 바꾸면 ..." / "X 변경 시 ..." 류는 무조건 impact.
- 메서드명/클래스명만 던지고 의도 없으면 (예: "validateOrder") → explain (가장 흔한 의도).
- hypothesis 의 시그널: 숫자 + 비교 연산자 ("미만", "초과", "이상", "=", "<", ">"),
  "~이면" / "~일 때" / "~한 경우" + 결과 묻는 표현 ("어떻게 되나", "처리되나", "실패하나").
- hypothesis 만 분류한 후 simulate / impact 차감 — boundary 질의를 단순 simulate 로
  분류하면 안 됨.

search_terms 추출 (검색 키워드만 골라내기):
- 의도/조사 ("바꾸면", "어디", "영향", "변경 시") 와 일반 동사 ("해줘", "알려줘") 는 제외.
- 숫자/단위는 search_terms 가 아니라 conditions 로 분리 (아래 참조).
- 도메인 명사 + 메서드/클래스명 + 비즈니스 용어만 골라 1~5 개.
- 한국어 도메인 단어 (예: 엣징, 마진, 두께, 검증) + 영문 식별자 (예: validateOrder,
  OrderService) 둘 다 모두 포함 가능.
- 예: "엣징 마진 변경하면 어디 영향?" → ["엣징", "마진"]
- 예: "validateOrder 어디 있어?" → ["validateOrder"]
- 예: "엣징 마진이 1.0 미만이면?" → search_terms=["엣징", "마진"], conditions=...
- 추출할 명확한 키워드 없으면 빈 list [].

conditions 추출 (hypothesis intent 에서만 — 다른 intent 면 빈 list):
- 각 조건은 {"var": "...", "op": "...", "value": "...", "unit": "..."} 형태.
- var: 변수/속성/도메인 용어 (예: "엣징 마진", "두께", "주문 수량")
- op: "<", "<=", "=", "!=", ">=", ">" 중 하나 (한국어 표현 매핑: "미만"→"<",
  "이하"→"<=", "초과"→">", "이상"→">=", "와 같다"→"=", "다르다"→"!=").
- value: 수치 또는 문자열 (예: "1.0", "0.1", "0")
- unit: 단위 (예: "mm", "kg", "") — 없으면 빈 문자열
- 예: "엣징 마진이 1.0 미만이면?" → [{"var":"엣징 마진","op":"<","value":"1.0","unit":""}]
- 예: "두께 0.1mm 인 슬라브" → [{"var":"두께","op":"=","value":"0.1","unit":"mm"}]
- 예: "주문 수량이 0 이면 어떤 에러?" → [{"var":"주문 수량","op":"=","value":"0","unit":""}]

응답은 반드시 다음 JSON:
{
  "intent": "simulate" | "impact" | "locate" | "explain" | "hypothesis" | "ambiguous",
  "confidence": 0.0 ~ 1.0,
  "reasoning": "왜 이렇게 분류했는지 1~2 문장 (한국어 OK)",
  "search_terms": ["키워드1", "키워드2"],
  "conditions": [{"var": "...", "op": "<", "value": "1.0", "unit": ""}]
}
"""


def classify_with_llm(
    user_query: str,
    *,
    llm=None,
) -> IntentDecision:
    """OpenAI 기반 분류. llm=None 이면 default OpenAI client 사용.

    LLM 이 unknown intent / parse 실패 → ambiguous(confidence=0) fallback.
    """
    if llm is None:
        from backend.section3.llm.openai_client import get_llm_client
        llm = get_llm_client()

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    raw = llm.chat_json(messages, temperature=0.0)

    intent = raw.get("intent")
    if intent not in _VALID_INTENTS:
        logger.info(
            "multiturn intent classify fallback (invalid raw=%s)",
            json.dumps(raw, ensure_ascii=False)[:200],
        )
        return IntentDecision(
            intent="ambiguous",
            confidence=0.0,
            reasoning=f"LLM 분류 실패 → ambiguous fallback. raw={raw!r}"[:300],
        )

    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    raw_terms = raw.get("search_terms") or []
    if isinstance(raw_terms, list):
        search_terms = [str(t).strip() for t in raw_terms if str(t).strip()][:5]
    else:
        search_terms = []

    raw_conds = raw.get("conditions") or []
    conditions: list[dict[str, str]] = []
    if isinstance(raw_conds, list):
        for c in raw_conds[:5]:
            if not isinstance(c, dict):
                continue
            entry = {
                "var": str(c.get("var", "")).strip(),
                "op": str(c.get("op", "")).strip(),
                "value": str(c.get("value", "")).strip(),
                "unit": str(c.get("unit", "")).strip(),
            }
            # var / value 가 비면 skip
            if entry["var"] and entry["value"]:
                conditions.append(entry)

    return IntentDecision(
        intent=intent,
        confidence=confidence,
        reasoning=str(raw.get("reasoning", "")).strip()[:500],
        search_terms=search_terms,
        conditions=conditions,
    )


class OpenAIIntentClassifier:
    """Protocol adapter — `classify_with_llm` 을 stateful object 로 wrap.

    FastAPI `Depends(get_classifier)` 또는 router DI 에서 사용.
    """

    def __init__(self, *, llm=None) -> None:
        self._llm = llm

    def classify(self, user_query: str) -> IntentDecision:
        return classify_with_llm(user_query, llm=self._llm)


__all__ = [
    "IntentDecision",
    "MultiturnIntent",
    "MultiturnIntentClassifier",
    "OpenAIIntentClassifier",
    "StubIntentClassifier",
    "classify_with_llm",
]
