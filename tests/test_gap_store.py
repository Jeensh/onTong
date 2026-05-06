"""OD-11-D3-1 : InMemoryGapStore unit tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.modeling.gap_detection.gap_models import GapCandidate
from backend.modeling.gap_detection.gap_store import (
    GapStore,
    InMemoryGapStore,
)
from backend.modeling.manuals.manual_models import (
    GapDetectedBy,
    GapDirection,
    GapMode,
    GapSeverity,
)


def _make_gap(
    gap_id: str = "abc123",
    direction: GapDirection = GapDirection.CODE_ONLY,
    target: str = "inventory.safety_stock",
    counterpart: str | None = None,
    severity: GapSeverity = GapSeverity.SOFT,
    confirmed: bool = False,
) -> GapCandidate:
    return GapCandidate(
        id=gap_id,
        direction=direction,
        target_fqn=target,
        counterpart_fqn=counterpart,
        severity=severity,
        detected_by=GapDetectedBy.HIERARCHICAL,
        gap_mode=GapMode.HIERARCHICAL,
        description="stub",
        confirmed=confirmed,
        created_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
    )


def test_inmemory_gap_store_implements_protocol() -> None:
    store = InMemoryGapStore()
    assert isinstance(store, GapStore)


def test_upsert_and_get_roundtrip() -> None:
    store = InMemoryGapStore()
    gap = _make_gap()
    store.upsert(gap)
    fetched = store.get(gap.id)
    assert fetched == gap


def test_upsert_replaces_existing_pending_gap() -> None:
    store = InMemoryGapStore()
    first = _make_gap(target="a", confirmed=False)
    second = _make_gap(target="a", confirmed=False, severity=GapSeverity.HARD)
    store.upsert(first)
    store.upsert(second)
    fetched = store.get(first.id)
    assert fetched is not None
    assert fetched.severity is GapSeverity.HARD


def test_upsert_does_not_overwrite_confirmed_gap() -> None:
    store = InMemoryGapStore()
    confirmed = _make_gap(confirmed=True, severity=GapSeverity.HARD)
    store.upsert(confirmed)
    rescan = _make_gap(confirmed=False, severity=GapSeverity.SOFT)
    store.upsert(rescan)
    fetched = store.get(confirmed.id)
    assert fetched is not None
    assert fetched.confirmed is True
    assert fetched.severity is GapSeverity.HARD


def test_list_pending_excludes_confirmed() -> None:
    store = InMemoryGapStore()
    store.upsert(_make_gap(gap_id="1", confirmed=False))
    store.upsert(_make_gap(gap_id="2", confirmed=True))
    pending = list(store.list_pending())
    assert len(pending) == 1
    assert pending[0].id == "1"


def test_list_by_direction() -> None:
    store = InMemoryGapStore()
    store.upsert(_make_gap(gap_id="1", direction=GapDirection.CODE_ONLY))
    store.upsert(_make_gap(gap_id="2", direction=GapDirection.MANUAL_ONLY))
    store.upsert(_make_gap(gap_id="3", direction=GapDirection.CODE_ONLY))
    code_only = list(store.list_by_direction(GapDirection.CODE_ONLY))
    assert {g.id for g in code_only} == {"1", "3"}


def test_confirm_flips_flag_and_returns_updated_gap() -> None:
    store = InMemoryGapStore()
    gap = _make_gap()
    store.upsert(gap)
    updated = store.confirm(gap.id)
    assert updated.confirmed is True
    assert store.get(gap.id) == updated


def test_confirm_missing_raises_key_error() -> None:
    store = InMemoryGapStore()
    with pytest.raises(KeyError):
        store.confirm("nonexistent")


def test_remove_deletes_entry() -> None:
    store = InMemoryGapStore()
    gap = _make_gap()
    store.upsert(gap)
    store.remove(gap.id)
    assert store.get(gap.id) is None


def test_remove_missing_is_noop() -> None:
    store = InMemoryGapStore()
    store.remove("nonexistent")
