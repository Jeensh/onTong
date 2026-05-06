"""OD-11-D3-2-b — PydanticAILLMComparator tests.

실 LLM 호출은 `@pytest.mark.integration` 으로 격리. 기본 스위트는 Fake agent 로 완결.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from backend.modeling.gap_detection.gap_engine import LLMComparator
from backend.modeling.gap_detection.gap_models import ScanConfig
from backend.modeling.gap_detection.llm_comparator import (
    LLMComparisonResult,
    PydanticAILLMComparator,
    _render_user_message,
)
from backend.modeling.manuals.manual_models import (
    GapMode,
    GapSeverity,
    ManualFragment,
    ManualFragmentKind,
)
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity


_NOW = datetime(2026, 4, 21, tzinfo=timezone.utc)


def _rule(statement: str = "안전재고는 100개 이상 확보한다") -> BusinessRule:
    return BusinessRule(
        qualified_name="inventory.rule.safety_stock",
        statement=statement,
        terms_ref=["safety_stock"],
        severity=RuleSeverity.HARD,
        source="code",
        confirmed=True,
        created_at=_NOW,
    )


def _fragment(text: str = "안전재고는 50개 이상 확보한다") -> ManualFragment:
    return ManualFragment(
        qualified_name="manual.spec#frag-1",
        section_fqn="manual.spec#sec-1",
        kind=ManualFragmentKind.TEXT,
        text=text,
        order_index=0,
        created_at=_NOW,
    )


def _config() -> ScanConfig:
    return ScanConfig(repo_id="demo", gap_mode=GapMode.HIERARCHICAL)


class _FakeAgent:
    """pydantic-ai Agent stub. ``run_sync`` returns a fake AgentRunResult or raises."""

    def __init__(self, output: Any = None, exc: Exception | None = None):
        self._output = output
        self._exc = exc
        self.calls: list[str] = []

    def run_sync(self, user_message: str):
        self.calls.append(user_message)
        if self._exc is not None:
            raise self._exc
        result = MagicMock()
        result.output = self._output
        return result


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------
def test_llm_comparison_result_accepts_four_severities():
    for label in ("low", "medium", "high", "critical"):
        out = LLMComparisonResult(severity=label, reasoning="ok")
        assert out.severity == label
        assert out.reasoning == "ok"


def test_llm_comparison_result_rejects_invalid_severity_literal():
    with pytest.raises(ValidationError):
        LLMComparisonResult(severity="apocalyptic", reasoning="bad")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_pydantic_ai_llm_comparator_implements_protocol():
    fake = _FakeAgent(
        output=LLMComparisonResult(severity="high", reasoning="quantity mismatch")
    )
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)
    assert isinstance(comp, LLMComparator)


# ---------------------------------------------------------------------------
# Successful compare
# ---------------------------------------------------------------------------
def test_compare_returns_severity_and_reasoning():
    fake = _FakeAgent(
        output=LLMComparisonResult(
            severity="high", reasoning="quantity diverges: 100 vs 50"
        )
    )
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)

    severity, reasoning = comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.HIGH,
        config=_config(),
    )
    assert severity == GapSeverity.HIGH
    assert reasoning == "quantity diverges: 100 vs 50"


def test_compare_handles_all_conflict_severity_levels():
    for label, expected in [
        ("low", GapSeverity.LOW),
        ("medium", GapSeverity.MEDIUM),
        ("high", GapSeverity.HIGH),
        ("critical", GapSeverity.CRITICAL),
    ]:
        fake = _FakeAgent(
            output=LLMComparisonResult(severity=label, reasoning="x")
        )
        comp = PydanticAILLMComparator(agent_factory=lambda f=fake: f)
        sev, _ = comp.compare(
            rule=_rule(),
            fragment=_fragment(),
            prior_severity=GapSeverity.MEDIUM,
            config=_config(),
        )
        assert sev == expected


# ---------------------------------------------------------------------------
# Graceful error handling
# ---------------------------------------------------------------------------
def test_agent_validation_error_falls_back_to_prior_severity():
    exc = ValidationError.from_exception_data("LLMComparisonResult", [])
    fake = _FakeAgent(exc=exc)
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)

    severity, reasoning = comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.HIGH,
        config=_config(),
    )
    assert severity == GapSeverity.HIGH  # prior preserved
    assert "LLM error" in reasoning
    assert "ValidationError" in reasoning


def test_agent_timeout_falls_back_to_prior_severity():
    fake = _FakeAgent(exc=TimeoutError("simulated timeout"))
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)

    severity, reasoning = comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.MEDIUM,
        config=_config(),
    )
    assert severity == GapSeverity.MEDIUM
    assert "LLM error" in reasoning
    assert "TimeoutError" in reasoning


def test_agent_arbitrary_exception_falls_back_to_prior_severity():
    fake = _FakeAgent(exc=RuntimeError("network down"))
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)
    severity, reasoning = comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.LOW,
        config=_config(),
    )
    assert severity == GapSeverity.LOW
    assert "RuntimeError" in reasoning


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------
def test_user_message_includes_rule_fragment_prior():
    message = _render_user_message(
        rule=_rule("안전재고는 100개 이상 확보한다"),
        fragment=_fragment("안전재고는 50개 이상 확보한다"),
        prior_severity=GapSeverity.HIGH,
    )
    assert "100개" in message
    assert "50개" in message
    # prior severity 가 프롬프트에 노출되어 LLM 이 인지 가능해야 함
    assert "high" in message.lower()


def test_agent_receives_rendered_message():
    fake = _FakeAgent(
        output=LLMComparisonResult(severity="medium", reasoning="ok")
    )
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)
    comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.MEDIUM,
        config=_config(),
    )
    assert len(fake.calls) == 1
    assert "100개" in fake.calls[0]
    assert "50개" in fake.calls[0]


# ---------------------------------------------------------------------------
# Defensive: unexpected enum category (belt-and-suspenders)
# ---------------------------------------------------------------------------
def test_defensive_invalid_category_falls_back_to_medium():
    """Literal 을 우회한 raw output (e.g. mocked) 가 MISSING_IN 카테고리(hard/soft)
    또는 임의 문자열을 반환해도 CONFLICTS_WITH severity (LOW/MEDIUM/HIGH/CRITICAL)
    만 허용되도록 방어한다."""

    @dataclass
    class _RawOutput:
        severity: str
        reasoning: str

    fake = _FakeAgent(output=_RawOutput(severity="hard", reasoning="wrong category"))
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)
    severity, reasoning = comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.HIGH,
        config=_config(),
    )
    # "hard" 는 GapSeverity 엔텀엔 있지만 CONFLICTS_WITH 카테고리가 아님
    assert severity == GapSeverity.MEDIUM
    assert "invalid" in reasoning.lower()


def test_defensive_unknown_severity_string_falls_back_to_medium():
    @dataclass
    class _RawOutput:
        severity: str
        reasoning: str

    fake = _FakeAgent(
        output=_RawOutput(severity="apocalyptic", reasoning="unknown")
    )
    comp = PydanticAILLMComparator(agent_factory=lambda: fake)
    severity, reasoning = comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.HIGH,
        config=_config(),
    )
    assert severity == GapSeverity.MEDIUM
    assert "invalid" in reasoning.lower()


# ---------------------------------------------------------------------------
# Integration smoke (skipped unless `pytest -m integration`)
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("ONTONG_LLM_INTEGRATION"),
    reason="set ONTONG_LLM_INTEGRATION=1 + OPENAI_API_KEY (or equivalent) to run",
)
def test_real_llm_returns_valid_severity():
    """실 LLM 호출 — 기본 스킵. `ONTONG_LLM_INTEGRATION=1 pytest -m integration` 으로 실행."""
    comp = PydanticAILLMComparator()
    severity, reasoning = comp.compare(
        rule=_rule(),
        fragment=_fragment(),
        prior_severity=GapSeverity.MEDIUM,
        config=_config(),
    )
    assert severity in {
        GapSeverity.LOW,
        GapSeverity.MEDIUM,
        GapSeverity.HIGH,
        GapSeverity.CRITICAL,
    }
    assert isinstance(reasoning, str)
    assert len(reasoning) > 0
