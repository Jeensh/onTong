"""Phase 2 Step 2a — Multiturn intent classifier (simulate / impact / ambiguous).

기존 `backend/section3/llm/intent_classifier.py` 와 별개. 라벨이 다름:
  - 기존: impact_analysis / simulate / explain (3 intent + parameters)
  - 신규: simulate / impact / ambiguous (Gate I 의 두 분기 + 모호)
"""
from __future__ import annotations

import pytest

from backend.section3.agents.multiturn.intent import (
    IntentDecision,
    MultiturnIntentClassifier,
    StubIntentClassifier,
    classify_with_llm,
)


# ─────────────────────────────────────────────────────────────────────────────
# IntentDecision DTO
# ─────────────────────────────────────────────────────────────────────────────


def test_intent_decision_holds_required_fields() -> None:
    d = IntentDecision(
        intent="simulate", confidence=0.85, reasoning="시뮬 키워드 검출",
    )
    assert d.intent == "simulate"
    assert d.confidence == 0.85
    assert d.reasoning == "시뮬 키워드 검출"


def test_intent_decision_rejects_unknown_intent() -> None:
    # Phase 13a: "explain" 은 valid 가 됨. "bogus" 같이 진짜 미정의 값으로 확인.
    with pytest.raises(ValueError):
        IntentDecision(intent="bogus_invalid_xyz", confidence=0.5, reasoning="x")


def test_intent_decision_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        IntentDecision(intent="simulate", confidence=1.5, reasoning="x")


# ─────────────────────────────────────────────────────────────────────────────
# Protocol — 둘 다 implement 해야
# ─────────────────────────────────────────────────────────────────────────────


def test_stub_implements_protocol() -> None:
    classifier = StubIntentClassifier(forced_intent="impact")
    assert isinstance(classifier, MultiturnIntentClassifier)


def test_stub_returns_forced_intent() -> None:
    classifier = StubIntentClassifier(
        forced_intent="impact",
        forced_confidence=0.9,
        forced_reasoning="stub",
    )
    out = classifier.classify("x")
    assert out.intent == "impact"
    assert out.confidence == 0.9
    assert out.reasoning == "stub"


def test_stub_per_query_override() -> None:
    """Specific query 마다 다른 intent 반환 (test 시나리오)."""
    classifier = StubIntentClassifier(
        forced_intent="ambiguous",
        per_query={"바꾸면": "impact", "시뮬": "simulate"},
    )
    assert classifier.classify("xxx 바꾸면 영향?").intent == "impact"
    assert classifier.classify("시뮬해줘").intent == "simulate"
    assert classifier.classify("unrelated").intent == "ambiguous"


# ─────────────────────────────────────────────────────────────────────────────
# LLM-based classifier — mocked
# ─────────────────────────────────────────────────────────────────────────────


class _FakeLLM:
    """LLMClient stand-in. chat_json 만 mock."""

    def __init__(self, response: dict) -> None:
        self._response = response
        self.calls: list[list[dict[str, str]]] = []

    def chat_json(self, messages, *, temperature: float = 0.0) -> dict:
        self.calls.append(messages)
        return self._response


def test_classify_with_llm_parses_simulate() -> None:
    llm = _FakeLLM({
        "intent": "simulate",
        "confidence": 0.92,
        "reasoning": "시뮬 키워드",
    })
    out = classify_with_llm("주문 검증 시뮬", llm=llm)
    assert out.intent == "simulate"
    assert out.confidence == 0.92


def test_classify_with_llm_parses_impact() -> None:
    llm = _FakeLLM({
        "intent": "impact",
        "confidence": 0.88,
        "reasoning": "영향도 키워드",
    })
    out = classify_with_llm("cumulativeProductivity 바꾸면 어디 영향?", llm=llm)
    assert out.intent == "impact"


def test_classify_with_llm_falls_back_to_ambiguous_on_invalid() -> None:
    """LLM 이 unknown intent 줬을 때 ambiguous 로 안전 fallback.

    Phase 13a: simulate/impact/ambiguous + locate/explain = 5종 valid. 그 외 값
    (e.g. LLM 환각으로 "compare", "test_run" 등) 받으면 ambiguous 로.
    """
    llm = _FakeLLM({
        "intent": "compare_diff",   # Phase 13a 신규 schema 에도 없는 값
        "confidence": 0.5,
        "reasoning": "x",
    })
    out = classify_with_llm("query", llm=llm)
    assert out.intent == "ambiguous"
    assert out.confidence == 0.0  # fallback 시 확신 없음


def test_classify_with_llm_sends_query_as_user_message() -> None:
    llm = _FakeLLM({"intent": "simulate", "confidence": 0.9, "reasoning": "x"})
    classify_with_llm("hello", llm=llm)
    last_msg = llm.calls[0][-1]
    assert last_msg["role"] == "user"
    assert "hello" in last_msg["content"]
