"""OD-11-D3-2-a : RuleASTDiffer unit tests.

BusinessRule.statement / ManualFragment.text 에서 수량 표현 (숫자/비교연산자/단위)
만 추출해 mismatch 여부만 판정. 자연어 의미 비교는 embedding/llm 단계 책임.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.modeling.gap_detection.gap_models import ScanConfig
from backend.modeling.gap_detection.rule_ast_differ import (
    RuleASTDiffer,
    RuleStatementTokens,
    extract_quantities,
)
from backend.modeling.manuals.manual_models import (
    DescribedInBinding,
    DescribedInTargetKind,
    GapDetectedBy,
    GapMode,
    GapSeverity,
    ManualFragment,
    ManualFragmentKind,
)
from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity


_CLOCK_TS = datetime(2026, 4, 21, 10, tzinfo=timezone.utc)


def _rule(fqn: str, statement: str) -> BusinessRule:
    return BusinessRule(
        qualified_name=fqn,
        statement=statement,
        severity=RuleSeverity.HARD,
        confirmed=True,
        created_at=_CLOCK_TS,
    )


def _fragment(fqn: str, text: str) -> ManualFragment:
    return ManualFragment(
        qualified_name=fqn,
        section_fqn=fqn.rsplit("#", 1)[0] + "#sec",
        kind=ManualFragmentKind.TEXT,
        text=text,
        created_at=_CLOCK_TS,
    )


def _described_in(rule_fqn: str, frag_fqn: str) -> DescribedInBinding:
    return DescribedInBinding(
        source_fqn=rule_fqn,
        target_fqn=frag_fqn,
        target_kind=DescribedInTargetKind.MANUAL_FRAGMENT,
        confidence=1.0,
        source="manual",
        created_at=_CLOCK_TS,
    )


def _config() -> ScanConfig:
    return ScanConfig(
        repo_id="prod",
        gap_mode=GapMode.HIERARCHICAL,
        detected_by=GapDetectedBy.HIERARCHICAL,
    )


# ---------------------------------------------------------------------------
# extract_quantities
# ---------------------------------------------------------------------------
def test_extract_quantities_picks_numbers_and_units() -> None:
    tokens = extract_quantities("안전재고는 10 개 이상 유지")
    assert tokens.numbers == (10.0,)
    assert "개" in tokens.units
    assert "이상" in tokens.comparators


def test_extract_quantities_recognizes_ascii_operators() -> None:
    tokens = extract_quantities("재고 >= 20%")
    assert tokens.numbers == (20.0,)
    assert "%" in tokens.units
    assert ">=" in tokens.comparators or "≥" in tokens.comparators


def test_extract_quantities_handles_decimal_and_range() -> None:
    tokens = extract_quantities("마진 1.5 ~ 3.0 % 범위")
    assert 1.5 in tokens.numbers
    assert 3.0 in tokens.numbers
    assert "%" in tokens.units


def test_extract_quantities_returns_empty_for_pure_prose() -> None:
    tokens = extract_quantities("고객이 불만을 제기하면 즉시 대응한다")
    assert tokens.numbers == ()
    assert tokens.units == ()
    assert tokens.comparators == ()


# ---------------------------------------------------------------------------
# RuleASTDiffer.compare
# ---------------------------------------------------------------------------
def test_compare_no_mismatch_when_tokens_identical() -> None:
    differ = RuleASTDiffer()
    left = RuleStatementTokens(numbers=(10.0,), comparators=("이상",), units=("개",))
    right = RuleStatementTokens(numbers=(10.0,), comparators=("이상",), units=("개",))
    outcome = differ.compare(left, right)
    assert outcome.has_mismatch is False


def test_compare_detects_numeric_mismatch() -> None:
    differ = RuleASTDiffer()
    left = RuleStatementTokens(numbers=(10.0,), comparators=("이상",), units=("개",))
    right = RuleStatementTokens(numbers=(20.0,), comparators=("이상",), units=("개",))
    outcome = differ.compare(left, right)
    assert outcome.has_mismatch is True
    assert outcome.numeric_mismatch == ((10.0, 20.0),)


def test_compare_detects_comparator_flip() -> None:
    differ = RuleASTDiffer()
    left = RuleStatementTokens(numbers=(10.0,), comparators=("이상",), units=("개",))
    right = RuleStatementTokens(numbers=(10.0,), comparators=("이하",), units=("개",))
    outcome = differ.compare(left, right)
    assert outcome.has_mismatch is True
    assert outcome.comparator_mismatch  # not empty


def test_compare_detects_unit_mismatch() -> None:
    differ = RuleASTDiffer()
    left = RuleStatementTokens(numbers=(10.0,), comparators=("이상",), units=("개",))
    right = RuleStatementTokens(numbers=(10.0,), comparators=("이상",), units=("%",))
    outcome = differ.compare(left, right)
    assert outcome.has_mismatch is True
    assert outcome.unit_mismatch  # not empty


def test_compare_both_empty_is_not_mismatch() -> None:
    differ = RuleASTDiffer()
    empty = RuleStatementTokens(numbers=(), comparators=(), units=())
    assert differ.compare(empty, empty).has_mismatch is False


# ---------------------------------------------------------------------------
# find_conflicts (상위 API)
# ---------------------------------------------------------------------------
def test_find_conflicts_requires_described_in_mapping() -> None:
    """described_in 매핑 없는 rule 은 skip (missing_in 영역)."""
    differ = RuleASTDiffer(clock=lambda: _CLOCK_TS)
    rule = _rule("rule.safety", "재고 10 개 이상")
    frag = _fragment("doc#sec#f0", "재고 20 개 이상")   # 매핑 안 됨
    conflicts = differ.find_conflicts(
        rules=[rule], fragments=[frag], described_in=[], config=_config(),
    )
    assert conflicts == []


def test_find_conflicts_emits_candidate_on_numeric_mismatch() -> None:
    differ = RuleASTDiffer(clock=lambda: _CLOCK_TS)
    rule = _rule("rule.safety", "재고 10 개 이상 유지")
    frag = _fragment("doc#sec#f0", "재고 20 개 이상")
    conflicts = differ.find_conflicts(
        rules=[rule],
        fragments=[frag],
        described_in=[_described_in("rule.safety", "doc#sec#f0")],
        config=_config(),
    )
    assert len(conflicts) == 1
    c = conflicts[0]
    # CONFLICTS_WITH 는 direction=None, target=rule_fqn, counterpart=frag_fqn.
    assert c.direction is None
    assert c.target_fqn == "rule.safety"
    assert c.counterpart_fqn == "doc#sec#f0"
    # rule_ast hit 은 즉시 HIGH — LLM 이 재평가해 CRITICAL 로 올릴 수 있음.
    assert c.severity is GapSeverity.HIGH


def test_find_conflicts_skips_when_tokens_empty() -> None:
    """수량 표현이 전혀 없는 rule/fragment 는 rule_ast 단계에서 skip."""
    differ = RuleASTDiffer(clock=lambda: _CLOCK_TS)
    rule = _rule("rule.process", "고객 불만 대응 프로세스")
    frag = _fragment("doc#sec#f0", "고객이 불만 제기 시 대응한다")
    conflicts = differ.find_conflicts(
        rules=[rule],
        fragments=[frag],
        described_in=[_described_in("rule.process", "doc#sec#f0")],
        config=_config(),
    )
    assert conflicts == []


def test_find_conflicts_stable_id_for_rescan() -> None:
    differ = RuleASTDiffer(clock=lambda: _CLOCK_TS)
    rule = _rule("rule.safety", "재고 10 이상")
    frag = _fragment("doc#sec#f0", "재고 20 이상")
    described = [_described_in("rule.safety", "doc#sec#f0")]
    first = differ.find_conflicts(
        rules=[rule], fragments=[frag], described_in=described, config=_config(),
    )
    second = differ.find_conflicts(
        rules=[rule], fragments=[frag], described_in=described, config=_config(),
    )
    assert first[0].id == second[0].id


def test_find_conflicts_ignores_image_fragments() -> None:
    differ = RuleASTDiffer(clock=lambda: _CLOCK_TS)
    rule = _rule("rule.safety", "재고 10 이상")
    img = ManualFragment(
        qualified_name="doc#sec#img0",
        section_fqn="doc#sec",
        kind=ManualFragmentKind.IMAGE,
        text="재고 20 이상",   # OCR 전 원본 — 비교 대상 아님
        image_ref="x.png",
        created_at=_CLOCK_TS,
    )
    conflicts = differ.find_conflicts(
        rules=[rule],
        fragments=[img],
        described_in=[_described_in("rule.safety", "doc#sec#img0")],
        config=_config(),
    )
    assert conflicts == []
