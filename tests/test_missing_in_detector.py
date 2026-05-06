"""OD-11-D3-1 : MissingInDetector unit tests (Q6=A bidirectional)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.modeling.gap_detection.gap_models import ScanConfig
from backend.modeling.gap_detection.gap_store import InMemoryGapStore
from backend.modeling.gap_detection.missing_in_detector import (
    MissingInDetector,
    SimpleHeuristicExtractor,
)
from backend.modeling.manuals.manual_models import (
    DescribedInBinding,
    DescribedInTargetKind,
    GapDetectedBy,
    GapDirection,
    GapMode,
    GapSeverity,
    ManualFragment,
    ManualFragmentKind,
)
from backend.modeling.mapping.mapping_models import (
    BusinessRule,
    BusinessTerm,
    BusinessTermSource,
    RuleSeverity,
)


_CLOCK_TS = datetime(2026, 4, 21, 10, tzinfo=timezone.utc)


def _clock() -> datetime:
    return _CLOCK_TS


def _term(name: str, aliases: list[str] | None = None, confirmed: bool = True) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=name,
        canonical_label=name.split(".")[-1],
        aliases=aliases or [],
        source=BusinessTermSource.MANUAL,
        confirmed=confirmed,
        created_at=_CLOCK_TS,
    )


def _rule(fqn: str, statement: str, confirmed: bool = True) -> BusinessRule:
    return BusinessRule(
        qualified_name=fqn,
        statement=statement,
        severity=RuleSeverity.HARD,
        confirmed=confirmed,
        created_at=_CLOCK_TS,
    )


def _fragment(
    fqn: str,
    text: str,
    kind: ManualFragmentKind = ManualFragmentKind.TEXT,
) -> ManualFragment:
    return ManualFragment(
        qualified_name=fqn,
        section_fqn=fqn.rsplit("/", 1)[0],
        kind=kind,
        text=text,
        created_at=_CLOCK_TS,
    )


def _described_in(source_fqn: str, target_fqn: str) -> DescribedInBinding:
    return DescribedInBinding(
        source_fqn=source_fqn,
        target_fqn=target_fqn,
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
# Extractor unit tests
# ---------------------------------------------------------------------------
def test_heuristic_extractor_picks_bold_code_and_korean_quote() -> None:
    frag = _fragment(
        "doc#s/1:f0",
        "본문에 **안전재고** 와 `reorder_point` 및 「서비스수준」 을 설명.",
    )
    candidates = SimpleHeuristicExtractor().extract(frag)
    assert set(candidates) == {"안전재고", "reorder_point", "서비스수준"}


def test_heuristic_extractor_skips_image_fragments() -> None:
    frag = _fragment(
        "doc#s/1:f0",
        "**ignored**",
        kind=ManualFragmentKind.IMAGE,
    )
    assert SimpleHeuristicExtractor().extract(frag) == []


def test_heuristic_extractor_dedup_within_fragment() -> None:
    frag = _fragment("doc#s/1:f0", "**용어** 와 **용어** 반복")
    assert SimpleHeuristicExtractor().extract(frag) == ["용어"]


# ---------------------------------------------------------------------------
# code_only direction — BusinessTerm/Rule w/o DESCRIBED_IN
# ---------------------------------------------------------------------------
def test_code_only_term_without_described_in_emits_soft_gap() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    result = detector.scan(
        business_terms=[_term("inv.safety_stock")],
        business_rules=[],
        fragments=[],
        described_in=[],
        config=_config(),
    )
    assert len(result.code_only) == 1
    gap = result.code_only[0]
    assert gap.direction is GapDirection.CODE_ONLY
    assert gap.target_fqn == "inv.safety_stock"
    assert gap.severity is GapSeverity.SOFT
    assert gap.detected_by is GapDetectedBy.HIERARCHICAL
    assert gap.gap_mode is GapMode.HIERARCHICAL


def test_code_only_term_with_described_in_skipped() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    result = detector.scan(
        business_terms=[_term("inv.safety_stock")],
        business_rules=[],
        fragments=[],
        described_in=[_described_in("inv.safety_stock", "doc#s/1:f0")],
        config=_config(),
    )
    assert result.code_only == []


def test_code_only_rule_without_described_in_emits_soft_gap() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    result = detector.scan(
        business_terms=[],
        business_rules=[_rule("inv.ss_rule", "SS = z × σ × √L")],
        fragments=[],
        described_in=[],
        config=_config(),
    )
    assert len(result.code_only) == 1
    assert result.code_only[0].target_fqn == "inv.ss_rule"
    assert result.code_only[0].severity is GapSeverity.SOFT


def test_code_only_skips_unconfirmed_term_by_default() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    result = detector.scan(
        business_terms=[_term("inv.tentative", confirmed=False)],
        business_rules=[],
        fragments=[],
        described_in=[],
        config=_config(),
    )
    assert result.code_only == []


def test_code_only_includes_unconfirmed_when_flag_set() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    result = detector.scan(
        business_terms=[_term("inv.tentative", confirmed=False)],
        business_rules=[],
        fragments=[],
        described_in=[],
        config=_config(include_unconfirmed_terms=True),
    )
    assert len(result.code_only) == 1


# ---------------------------------------------------------------------------
# manual_only direction — Fragment phrase w/o BusinessTerm
# ---------------------------------------------------------------------------
def test_manual_only_unmatched_bold_phrase_emits_hard_gap() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    frag = _fragment("doc#s/1:f0", "**발주점** 을 매일 계산한다.")
    result = detector.scan(
        business_terms=[],
        business_rules=[],
        fragments=[frag],
        described_in=[],
        config=_config(),
    )
    assert len(result.manual_only) == 1
    gap = result.manual_only[0]
    assert gap.direction is GapDirection.MANUAL_ONLY
    assert gap.severity is GapSeverity.HARD
    assert gap.target_fqn == "발주점"
    assert gap.counterpart_fqn == "doc#s/1:f0"


def test_manual_only_matched_canonical_label_skipped() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    term = _term("inv.발주점")
    frag = _fragment("doc#s/1:f0", "**발주점** 을 매일 계산한다.")
    result = detector.scan(
        business_terms=[term],
        business_rules=[],
        fragments=[frag],
        described_in=[],
        config=_config(),
    )
    assert result.manual_only == []


def test_manual_only_matched_alias_case_insensitive() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    term = _term("inv.reorder_point", aliases=["발주점", "Reorder Point"])
    frag = _fragment("doc#s/1:f0", "**REORDER POINT** 와 **발주점** 을 관리.")
    result = detector.scan(
        business_terms=[term],
        business_rules=[],
        fragments=[frag],
        described_in=[],
        config=_config(),
    )
    assert result.manual_only == []


def test_manual_only_min_occurrence_threshold_filters_singletons() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    frags = [
        _fragment("doc#s/1:f0", "**단일어** 만 한 번"),
        _fragment("doc#s/1:f1", "**반복어** 첫째"),
        _fragment("doc#s/2:f0", "**반복어** 둘째"),
    ]
    result = detector.scan(
        business_terms=[],
        business_rules=[],
        fragments=frags,
        described_in=[],
        config=_config(min_occurrence_for_manual_only=2),
    )
    assert len(result.manual_only) == 1
    assert result.manual_only[0].target_fqn == "반복어"


def test_manual_only_image_fragments_ignored() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    frag = _fragment(
        "doc#s/1:f0",
        "**무시됨**",
        kind=ManualFragmentKind.IMAGE,
    )
    result = detector.scan(
        business_terms=[],
        business_rules=[],
        fragments=[frag],
        described_in=[],
        config=_config(),
    )
    assert result.manual_only == []


# ---------------------------------------------------------------------------
# GapStore integration + dedup
# ---------------------------------------------------------------------------
def test_scan_persists_candidates_to_gap_store() -> None:
    store = InMemoryGapStore()
    detector = MissingInDetector(gap_store=store, clock=_clock)
    detector.scan(
        business_terms=[_term("inv.safety_stock")],
        business_rules=[],
        fragments=[_fragment("doc#s/1:f0", "**발주점** 설명")],
        described_in=[],
        config=_config(),
    )
    pending = list(store.list_pending())
    assert len(pending) == 2
    directions = {g.direction for g in pending}
    assert directions == {GapDirection.CODE_ONLY, GapDirection.MANUAL_ONLY}


def test_rescan_with_same_inputs_is_idempotent() -> None:
    store = InMemoryGapStore()
    detector = MissingInDetector(gap_store=store, clock=_clock)
    kwargs = dict(
        business_terms=[_term("inv.safety_stock")],
        business_rules=[],
        fragments=[_fragment("doc#s/1:f0", "**발주점** 설명")],
        described_in=[],
        config=_config(),
    )
    detector.scan(**kwargs)  # type: ignore[arg-type]
    first_pending = list(store.list_pending())
    detector.scan(**kwargs)  # type: ignore[arg-type]
    second_pending = list(store.list_pending())
    assert {g.id for g in first_pending} == {g.id for g in second_pending}
    assert len(second_pending) == len(first_pending)


def test_rescan_preserves_human_confirmation() -> None:
    store = InMemoryGapStore()
    detector = MissingInDetector(gap_store=store, clock=_clock)
    kwargs = dict(
        business_terms=[_term("inv.safety_stock")],
        business_rules=[],
        fragments=[],
        described_in=[],
        config=_config(),
    )
    detector.scan(**kwargs)  # type: ignore[arg-type]
    pending = list(store.list_pending())
    assert len(pending) == 1
    store.confirm(pending[0].id)
    detector.scan(**kwargs)  # type: ignore[arg-type]
    assert store.list_pending() == []
    confirmed = store.get(pending[0].id)
    assert confirmed is not None
    assert confirmed.confirmed is True


def test_gap_mode_llm_only_propagates_to_candidates() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    result = detector.scan(
        business_terms=[_term("inv.safety_stock")],
        business_rules=[],
        fragments=[_fragment("doc#s/1:f0", "**발주점** 설명")],
        described_in=[],
        config=_config(
            gap_mode=GapMode.LLM_ONLY,
            detected_by=GapDetectedBy.LLM_ONLY,
        ),
    )
    for gap in (*result.code_only, *result.manual_only):
        assert gap.gap_mode is GapMode.LLM_ONLY
        assert gap.detected_by is GapDetectedBy.LLM_ONLY


def test_scan_result_all_property_combines_both_directions() -> None:
    detector = MissingInDetector(gap_store=InMemoryGapStore(), clock=_clock)
    result = detector.scan(
        business_terms=[_term("inv.safety_stock")],
        business_rules=[],
        fragments=[_fragment("doc#s/1:f0", "**발주점** 설명")],
        described_in=[],
        config=_config(),
    )
    all_gaps = list(result.all)
    assert len(all_gaps) == 2
    assert len(all_gaps) == len(result.code_only) + len(result.manual_only)
