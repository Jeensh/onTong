"""OD-11-D3-3 : GapScanner orchestrator unit tests.

`GapScanner` 는 D3-1 `MissingInDetector` + D3-2 `GapEngine` 를 묶어서 한 번의
scan 으로 MISSING_IN / CONFLICTS_WITH 를 같이 돌린다. fragments 가 비면
`ManualRegistry` 에서 자동으로 당겨와서 API 호출자의 부담을 줄인다 (Q1=A
partial hybrid — rules / described_in 은 store 없어서 body 필수).

unified result :
    code_only + manual_only   ← MissingInDetector
    conflicts                 ← GapEngine.detect_conflicts

Spec : `toClaude/modeling/HANDOFF.md` §D3-3, `backend/modeling/gap_detection/*`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.modeling.gap_detection.embedding_drifter import CosineDrifter
from backend.modeling.gap_detection.gap_engine import (
    HierarchicalGapEngine,
    create_gap_engine,
)
from backend.modeling.gap_detection.gap_models import ScanConfig
from backend.modeling.gap_detection.gap_scanner import (
    GapScanner,
    UnifiedScanResult,
)
from backend.modeling.gap_detection.gap_store import InMemoryGapStore
from backend.modeling.gap_detection.missing_in_detector import MissingInDetector
from backend.modeling.gap_detection.rule_ast_differ import RuleASTDiffer
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manuals.manual_models import (
    DescribedInBinding,
    DescribedInTargetKind,
    GapDetectedBy,
    GapDirection,
    GapMode,
    GapSeverity,
    ManualDocument,
    ManualFormat,
    ManualFragment,
    ManualFragmentKind,
    ManualSection,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
class _ControlledEmbedder:
    """Deterministic 2D embedder — drift/no-drift 는 동일 벡터 여부로 조절."""

    def __init__(self, mapping: dict[str, list[float]]):
        self._map = mapping

    def embed(self, text: str) -> list[float]:
        return list(self._map[text])


def _term(fqn: str, confirmed: bool = True) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=fqn,
        canonical_label=fqn.split(".")[-1],
        aliases=[],
        source=BusinessTermSource.MANUAL,
        confirmed=confirmed,
        created_at=_CLOCK_TS,
    )


def _rule(fqn: str, statement: str) -> BusinessRule:
    return BusinessRule(
        qualified_name=fqn,
        statement=statement,
        severity=RuleSeverity.HARD,
        confirmed=True,
        created_at=_CLOCK_TS,
    )


def _fragment(
    fqn: str, text: str, kind: ManualFragmentKind = ManualFragmentKind.TEXT
) -> ManualFragment:
    return ManualFragment(
        qualified_name=fqn,
        section_fqn=fqn.rsplit("#", 1)[0] + "#sec",
        kind=kind,
        text=text,
        created_at=_CLOCK_TS,
    )


def _described(source_fqn: str, target_fqn: str) -> DescribedInBinding:
    return DescribedInBinding(
        source_fqn=source_fqn,
        target_fqn=target_fqn,
        target_kind=DescribedInTargetKind.MANUAL_FRAGMENT,
        confidence=1.0,
        source="manual",
        created_at=_CLOCK_TS,
    )


def _config(**kw: object) -> ScanConfig:
    base = dict(
        repo_id="prod",
        gap_mode=GapMode.HIERARCHICAL,
        detected_by=GapDetectedBy.HIERARCHICAL,
    )
    base.update(kw)
    return ScanConfig(**base)  # type: ignore[arg-type]


def _registry_with(fragments: list[ManualFragment]) -> InMemoryManualRegistry:
    """Single-doc registry seeded with the given fragments."""
    reg = InMemoryManualRegistry()
    doc = ManualDocument(
        qualified_name="doc",
        title="Doc",
        source_path="/tmp/doc.md",
        format=ManualFormat.MARKDOWN,
        version="",
        checksum="a" * 64,
        authoritative=True,
        created_at=_CLOCK_TS,
    )
    section = ManualSection(
        qualified_name="doc#sec",
        doc_fqn="doc",
        title="sec",
        heading_path=["Root"],
        order_index=0,
        created_at=_CLOCK_TS,
    )
    reg.add(doc, sections=[section], fragments=fragments)
    return reg


def _build_scanner(
    *,
    gap_store: InMemoryGapStore | None = None,
    registry: InMemoryManualRegistry | None = None,
    embeddings: dict[str, list[float]] | None = None,
) -> tuple[GapScanner, InMemoryGapStore, InMemoryManualRegistry]:
    store = gap_store or InMemoryGapStore()
    reg = registry or InMemoryManualRegistry()
    embedder = _ControlledEmbedder(embeddings or {})
    detector = MissingInDetector(gap_store=store, clock=_clock)
    engine = create_gap_engine(
        mode=GapMode.HIERARCHICAL,
        rule_differ=RuleASTDiffer(clock=_clock),
        drifter=CosineDrifter(embedder=embedder, clock=_clock, cutoff=0.65),
        llm_comparator=None,
        gap_store=store,
        clock=_clock,
    )
    scanner = GapScanner(
        missing_detector=detector,
        gap_engine=engine,
        fragment_source=reg,
    )
    return scanner, store, reg


# ---------------------------------------------------------------------------
# Result shape + orchestration
# ---------------------------------------------------------------------------
def test_scan_returns_unified_scan_result() -> None:
    scanner, _, _ = _build_scanner()
    result = scanner.scan(
        config=_config(),
        business_terms=[],
        business_rules=[],
        described_in=[],
        fragments=[],
    )
    assert isinstance(result, UnifiedScanResult)
    assert list(result.code_only) == []
    assert list(result.manual_only) == []
    assert list(result.conflicts) == []
    assert list(result.errors) == []


def test_scan_runs_missing_in_and_conflicts_together() -> None:
    # MISSING_IN code_only : term without DESCRIBED_IN.
    # CONFLICTS_WITH       : rule with DESCRIBED_IN + fragment with numeric drift.
    scanner, _, _ = _build_scanner(
        embeddings={"재고 10 이상": [1.0, 0.0], "재고 20 이상": [1.0, 0.0]},
    )
    term = _term("inv.safety_stock")
    rule = _rule("rule.safety", "재고 10 이상")
    frag = _fragment("doc#sec#f0", "재고 20 이상")
    result = scanner.scan(
        config=_config(),
        business_terms=[term],
        business_rules=[rule],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        fragments=[frag],
    )
    code_only_targets = {g.target_fqn for g in result.code_only}
    conflict_targets = {g.target_fqn for g in result.conflicts}
    assert code_only_targets == {"inv.safety_stock"}
    assert conflict_targets == {"rule.safety"}
    assert result.conflicts[0].severity is GapSeverity.HIGH   # rule_ast hit


def test_scan_unified_all_combines_three_buckets() -> None:
    scanner, _, _ = _build_scanner(
        embeddings={"재고 10 이상": [1.0, 0.0], "재고 20 이상": [1.0, 0.0]},
    )
    term = _term("inv.safety_stock")
    rule = _rule("rule.safety", "재고 10 이상")
    frag_conflict = _fragment("doc#sec#f0", "재고 20 이상")
    frag_manual_only = _fragment("doc#sec#f1", "**미지의용어** 를 매일 사용")
    result = scanner.scan(
        config=_config(),
        business_terms=[term],
        business_rules=[rule],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        fragments=[frag_conflict, frag_manual_only],
    )
    all_gaps = list(result.all)
    assert len(all_gaps) == (
        len(result.code_only) + len(result.manual_only) + len(result.conflicts)
    )
    directions = {g.direction for g in all_gaps}
    assert GapDirection.CODE_ONLY in directions
    assert GapDirection.MANUAL_ONLY in directions
    # CONFLICTS_WITH 는 direction=None.
    assert None in directions


# ---------------------------------------------------------------------------
# Auto-pull from ManualRegistry
# ---------------------------------------------------------------------------
def test_scan_auto_pulls_fragments_when_none() -> None:
    # Registry 에 **미지의용어** 담긴 fragment 하나. body fragments=None → auto-pull.
    frag = _fragment("doc#sec#f0", "**미지의용어** 을 매일 사용")
    scanner, _, _ = _build_scanner(registry=_registry_with([frag]))
    result = scanner.scan(
        config=_config(),
        business_terms=[],
        business_rules=[],
        described_in=[],
        fragments=None,   # auto-pull
    )
    manual_targets = {g.target_fqn for g in result.manual_only}
    assert manual_targets == {"미지의용어"}


def test_scan_uses_body_fragments_when_provided() -> None:
    # Registry 에 다른 fragment (A) 있어도 body 가 있으면 body (B) 만 사용.
    registry_frag = _fragment("doc#sec#fA", "**레지스트리만의용어** 등장")
    body_frag = _fragment("doc#sec#fB", "**바디만의용어** 등장")
    scanner, _, _ = _build_scanner(
        registry=_registry_with([registry_frag]),
    )
    result = scanner.scan(
        config=_config(),
        business_terms=[],
        business_rules=[],
        described_in=[],
        fragments=[body_frag],
    )
    manual_targets = {g.target_fqn for g in result.manual_only}
    assert manual_targets == {"바디만의용어"}


def test_scan_empty_registry_and_none_fragments_yields_no_manual_only() -> None:
    scanner, _, _ = _build_scanner()   # empty registry
    result = scanner.scan(
        config=_config(),
        business_terms=[],
        business_rules=[],
        described_in=[],
        fragments=None,
    )
    assert list(result.manual_only) == []
    assert list(result.conflicts) == []


# ---------------------------------------------------------------------------
# GapStore persistence
# ---------------------------------------------------------------------------
def test_scan_persists_all_candidates_to_shared_gap_store() -> None:
    store = InMemoryGapStore()
    scanner, _, _ = _build_scanner(
        gap_store=store,
        embeddings={"재고 10 이상": [1.0, 0.0], "재고 20 이상": [1.0, 0.0]},
    )
    term = _term("inv.safety_stock")
    rule = _rule("rule.safety", "재고 10 이상")
    frag = _fragment("doc#sec#f0", "재고 20 이상")
    scanner.scan(
        config=_config(),
        business_terms=[term],
        business_rules=[rule],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        fragments=[frag],
    )
    pending = list(store.list_pending())
    assert len(pending) >= 2   # 1 code_only + 1 conflict (at minimum)
    directions = {g.direction for g in pending}
    assert GapDirection.CODE_ONLY in directions
    assert None in directions   # CONFLICTS_WITH


def test_scan_rescan_preserves_human_confirmation() -> None:
    store = InMemoryGapStore()
    scanner, _, _ = _build_scanner(gap_store=store)
    term = _term("inv.safety_stock")
    scanner.scan(
        config=_config(),
        business_terms=[term],
        business_rules=[],
        described_in=[],
        fragments=[],
    )
    pending = list(store.list_pending())
    assert len(pending) == 1
    store.confirm(pending[0].id)
    # rescan — same input
    scanner.scan(
        config=_config(),
        business_terms=[term],
        business_rules=[],
        described_in=[],
        fragments=[],
    )
    assert store.list_pending() == []
    confirmed = store.get(pending[0].id)
    assert confirmed is not None
    assert confirmed.confirmed is True


# ---------------------------------------------------------------------------
# Error surface — fragment_source is optional, scanner tolerates missing registry
# ---------------------------------------------------------------------------
def test_scan_without_registry_and_fragments_none_uses_empty_list() -> None:
    # fragment_source=None 이면 auto-pull 대신 빈 리스트.
    store = InMemoryGapStore()
    detector = MissingInDetector(gap_store=store, clock=_clock)
    engine = HierarchicalGapEngine(
        rule_differ=RuleASTDiffer(clock=_clock),
        drifter=CosineDrifter(
            embedder=_ControlledEmbedder({}), clock=_clock, cutoff=0.65
        ),
        llm_comparator=None,
        gap_store=store,
        clock=_clock,
    )
    scanner = GapScanner(
        missing_detector=detector,
        gap_engine=engine,
        fragment_source=None,   # explicit None allowed
    )
    result = scanner.scan(
        config=_config(),
        business_terms=[],
        business_rules=[],
        described_in=[],
        fragments=None,
    )
    assert list(result.manual_only) == []


# ---------------------------------------------------------------------------
# Progress callbacks — SSE stage hooks
# ---------------------------------------------------------------------------
def test_scan_emits_progress_events_in_order() -> None:
    scanner, _, _ = _build_scanner(
        embeddings={"재고 10 이상": [1.0, 0.0], "재고 20 이상": [1.0, 0.0]},
    )
    events: list[str] = []

    def on_progress(stage: str) -> None:
        events.append(stage)

    scanner.scan(
        config=_config(),
        business_terms=[_term("inv.x")],
        business_rules=[_rule("rule.safety", "재고 10 이상")],
        described_in=[_described("rule.safety", "doc#sec#f0")],
        fragments=[_fragment("doc#sec#f0", "재고 20 이상")],
        on_progress=on_progress,
    )
    # Expected stage sequence for HIERARCHICAL mode.
    expected_prefix = ["scanning", "stage1_missing_in", "stage2_conflicts", "complete"]
    assert events == expected_prefix
