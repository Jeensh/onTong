"""OD-11-D3-2-a : GapEngine Strategy skeleton unit tests.

HierarchicalGapEngine 은 3 단계 (rule_ast → embedding → llm) 를 직렬로 돌린다.
D3-2-a 단계에서는 llm_comparator 주입이 optional — 없으면 embedding drift 결과를
그대로 배출 (severity=MEDIUM). llm_comparator 는 D3-2-b 에서 본격 구현.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from backend.modeling.gap_detection.embedding_drifter import CosineDrifter
from backend.modeling.gap_detection.gap_engine import (
    HierarchicalGapEngine,
    LLMOnlyGapEngine,
    create_gap_engine,
)
from backend.modeling.gap_detection.gap_models import GapCandidate, ScanConfig
from backend.modeling.gap_detection.gap_store import InMemoryGapStore
from backend.modeling.gap_detection.rule_ast_differ import RuleASTDiffer
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


class _ControlledEmbedder:
    def __init__(self, mapping: dict[str, list[float]]):
        self._map = mapping

    def embed(self, text: str) -> list[float]:
        return list(self._map[text])


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


def _described(rule_fqn: str, frag_fqn: str) -> DescribedInBinding:
    return DescribedInBinding(
        source_fqn=rule_fqn,
        target_fqn=frag_fqn,
        target_kind=DescribedInTargetKind.MANUAL_FRAGMENT,
        confidence=1.0,
        source="manual",
        created_at=_CLOCK_TS,
    )


def _config(**kw: object) -> ScanConfig:
    base = dict(repo_id="prod", gap_mode=GapMode.HIERARCHICAL,
                detected_by=GapDetectedBy.HIERARCHICAL)
    base.update(kw)
    return ScanConfig(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# HierarchicalGapEngine
# ---------------------------------------------------------------------------
def test_hierarchical_rule_ast_hit_short_circuits() -> None:
    """rule_ast 가 numeric mismatch 잡으면 embedding 단계는 skip."""
    embedder = _ControlledEmbedder({
        "재고 10 이상": [1.0, 0.0],
        "재고 20 이상": [1.0, 0.0],   # cos=1.0 — drift 없음
    })
    engine = HierarchicalGapEngine(
        rule_differ=RuleASTDiffer(clock=lambda: _CLOCK_TS),
        drifter=CosineDrifter(embedder=embedder, clock=lambda: _CLOCK_TS),
        llm_comparator=None,
        clock=lambda: _CLOCK_TS,
    )
    rule = _rule("rule.safety", "재고 10 이상")
    frag = _fragment("doc#sec#f0", "재고 20 이상")
    results = engine.detect_conflicts(
        rules=[rule],
        fragments=[frag],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        config=_config(),
    )
    assert len(results) == 1
    assert results[0].severity is GapSeverity.HIGH   # rule_ast hit severity
    assert results[0].target_fqn == "rule.safety"


def test_hierarchical_embedding_drift_when_rule_ast_empty() -> None:
    """수량 토큰이 없으면 rule_ast skip, embedding drift 가 판정."""
    embedder = _ControlledEmbedder({
        "고객 불만 대응": [1.0, 0.0],
        "주문 취소 처리": [0.0, 1.0],   # cos=0
    })
    engine = HierarchicalGapEngine(
        rule_differ=RuleASTDiffer(clock=lambda: _CLOCK_TS),
        drifter=CosineDrifter(embedder=embedder, clock=lambda: _CLOCK_TS,
                              cutoff=0.65),
        llm_comparator=None,
        clock=lambda: _CLOCK_TS,
    )
    rule = _rule("rule.complaint", "고객 불만 대응")
    frag = _fragment("doc#sec#f0", "주문 취소 처리")
    results = engine.detect_conflicts(
        rules=[rule],
        fragments=[frag],
        described_in=[_described("rule.complaint", "doc#sec#f0")],
        config=_config(),
    )
    assert len(results) == 1
    assert results[0].severity is GapSeverity.MEDIUM   # drift 단계 기본


def test_hierarchical_no_mapping_no_conflict() -> None:
    engine = HierarchicalGapEngine(
        rule_differ=RuleASTDiffer(clock=lambda: _CLOCK_TS),
        drifter=CosineDrifter(embedder=_ControlledEmbedder({}),
                              clock=lambda: _CLOCK_TS),
        llm_comparator=None,
        clock=lambda: _CLOCK_TS,
    )
    rule = _rule("rule.x", "재고 10 이상")
    frag = _fragment("doc#sec#f0", "재고 20 이상")
    results = engine.detect_conflicts(
        rules=[rule], fragments=[frag], described_in=[], config=_config(),
    )
    assert results == []


def test_hierarchical_llm_override_severity() -> None:
    """llm_comparator 주입 시 drift/rule_ast 의 severity 를 재평가."""

    @dataclass
    class _FakeLLMComparator:
        def compare(self, *, rule, fragment, prior_severity, config):
            return GapSeverity.CRITICAL, f"LLM says critical: {rule.qualified_name}"

    embedder = _ControlledEmbedder({
        "재고 10 이상": [1.0, 0.0],
        "재고 20 이상": [1.0, 0.0],
    })
    engine = HierarchicalGapEngine(
        rule_differ=RuleASTDiffer(clock=lambda: _CLOCK_TS),
        drifter=CosineDrifter(embedder=embedder, clock=lambda: _CLOCK_TS),
        llm_comparator=_FakeLLMComparator(),
        clock=lambda: _CLOCK_TS,
    )
    rule = _rule("rule.safety", "재고 10 이상")
    frag = _fragment("doc#sec#f0", "재고 20 이상")
    results = engine.detect_conflicts(
        rules=[rule],
        fragments=[frag],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        config=_config(),
    )
    assert len(results) == 1
    assert results[0].severity is GapSeverity.CRITICAL
    assert "LLM says critical" in results[0].description


def test_hierarchical_persists_to_store_when_provided() -> None:
    embedder = _ControlledEmbedder({
        "재고 10 이상": [1.0, 0.0],
        "재고 20 이상": [1.0, 0.0],
    })
    store = InMemoryGapStore()
    engine = HierarchicalGapEngine(
        rule_differ=RuleASTDiffer(clock=lambda: _CLOCK_TS),
        drifter=CosineDrifter(embedder=embedder, clock=lambda: _CLOCK_TS),
        llm_comparator=None,
        gap_store=store,
        clock=lambda: _CLOCK_TS,
    )
    rule = _rule("rule.safety", "재고 10 이상")
    frag = _fragment("doc#sec#f0", "재고 20 이상")
    _ = engine.detect_conflicts(
        rules=[rule],
        fragments=[frag],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        config=_config(),
    )
    pending = store.list_pending()
    assert len(pending) == 1
    assert pending[0].target_fqn == "rule.safety"


# ---------------------------------------------------------------------------
# LLMOnlyGapEngine — D3-2-a skeleton (llm 없으면 빈 결과 + 경고)
# ---------------------------------------------------------------------------
def test_llm_only_without_comparator_returns_empty(caplog: pytest.LogCaptureFixture) -> None:
    engine = LLMOnlyGapEngine(llm_comparator=None, clock=lambda: _CLOCK_TS)
    results = engine.detect_conflicts(
        rules=[], fragments=[], described_in=[], config=_config(gap_mode=GapMode.LLM_ONLY),
    )
    assert results == []


def test_llm_only_with_comparator_runs_on_mapped_pairs() -> None:
    @dataclass
    class _FakeLLMComparator:
        def compare(self, *, rule, fragment, prior_severity, config):
            return GapSeverity.LOW, "trivial drift"

    engine = LLMOnlyGapEngine(
        llm_comparator=_FakeLLMComparator(), clock=lambda: _CLOCK_TS,
    )
    rule = _rule("rule.safety", "anything")
    frag = _fragment("doc#sec#f0", "whatever")
    results = engine.detect_conflicts(
        rules=[rule],
        fragments=[frag],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        config=_config(gap_mode=GapMode.LLM_ONLY, detected_by=GapDetectedBy.LLM_ONLY),
    )
    assert len(results) == 1
    assert results[0].severity is GapSeverity.LOW
    assert results[0].gap_mode is GapMode.LLM_ONLY


# ---------------------------------------------------------------------------
# create_gap_engine factory
# ---------------------------------------------------------------------------
def test_factory_returns_hierarchical_for_hierarchical_mode() -> None:
    engine = create_gap_engine(
        mode=GapMode.HIERARCHICAL,
        rule_differ=RuleASTDiffer(clock=lambda: _CLOCK_TS),
        drifter=CosineDrifter(embedder=_ControlledEmbedder({}),
                              clock=lambda: _CLOCK_TS),
        llm_comparator=None,
    )
    assert isinstance(engine, HierarchicalGapEngine)


def test_factory_returns_llm_only_for_llm_only_mode() -> None:
    engine = create_gap_engine(
        mode=GapMode.LLM_ONLY,
        rule_differ=RuleASTDiffer(clock=lambda: _CLOCK_TS),
        drifter=CosineDrifter(embedder=_ControlledEmbedder({}),
                              clock=lambda: _CLOCK_TS),
        llm_comparator=None,
    )
    assert isinstance(engine, LLMOnlyGapEngine)
