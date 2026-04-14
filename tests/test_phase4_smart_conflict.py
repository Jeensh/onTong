"""Phase 4 — Smart Conflict Resolution tests.

Tests:
- ConflictStore update_analysis / resolve_pair
- TypedConflict / ConflictAnalysis model validation
- StoredConflict canonical ordering
"""

import time
import pytest
from backend.application.conflict.conflict_store import (
    InMemoryConflictStore,
    StoredConflict,
    _canonical_key,
)
from backend.core.schemas import TypedConflict
from backend.application.agent.models import ConflictAnalysis


# ── ConflictStore: update_analysis / resolve_pair ──────────────────

class TestConflictStoreAnalysis:
    def _make_store(self):
        store = InMemoryConflictStore()
        sc = StoredConflict(
            file_a="docs/a.md",
            file_b="docs/b.md",
            similarity=0.95,
            detected_at=time.time(),
        )
        store.replace_for_file("docs/a.md", [sc])
        return store

    def test_update_analysis(self):
        store = self._make_store()
        ok = store.update_analysis("docs/a.md", "docs/b.md", {
            "conflict_type": "factual_contradiction",
            "severity": "high",
            "summary_ko": "TTL 값이 다릅니다",
            "claim_a": "TTL은 30분",
            "claim_b": "TTL은 1시간",
            "suggested_resolution": "merge",
            "resolution_detail": "하나로 통합하세요",
            "analyzed_at": 1234567890.0,
        })
        assert ok is True
        pair = store.get_all_pairs()[0]
        assert pair.conflict_type == "factual_contradiction"
        assert pair.severity == "high"
        assert pair.summary_ko == "TTL 값이 다릅니다"
        assert pair.analyzed_at == 1234567890.0

    def test_update_analysis_not_found(self):
        store = self._make_store()
        ok = store.update_analysis("nonexistent.md", "docs/b.md", {"conflict_type": "temporal"})
        assert ok is False

    def test_resolve_pair(self):
        store = self._make_store()
        ok = store.resolve_pair("docs/a.md", "docs/b.md", "admin", "dismiss")
        assert ok is True
        pair = store.get_all_pairs()[0]
        assert pair.resolved is True
        assert pair.resolved_by == "admin"
        assert pair.resolved_action == "dismiss"

    def test_resolve_pair_not_found(self):
        store = self._make_store()
        ok = store.resolve_pair("x.md", "y.md", "admin", "dismiss")
        assert ok is False

    def test_canonical_key_ordering(self):
        """update/resolve should work regardless of argument order."""
        store = self._make_store()
        # Store canonical: (docs/a.md, docs/b.md)
        # Call with reversed order
        ok = store.update_analysis("docs/b.md", "docs/a.md", {"conflict_type": "temporal"})
        assert ok is True
        ok = store.resolve_pair("docs/b.md", "docs/a.md", "user", "version_chain")
        assert ok is True

    def test_stored_conflict_extended_fields(self):
        """All new StoredConflict fields have proper defaults."""
        sc = StoredConflict(file_a="a.md", file_b="b.md", similarity=0.9, detected_at=0.0)
        assert sc.conflict_type == ""
        assert sc.severity == ""
        assert sc.summary_ko == ""
        assert sc.resolved is False
        assert sc.analyzed_at == 0.0


# ── TypedConflict / ConflictAnalysis models ──────────────────────

class TestModels:
    def test_typed_conflict_defaults(self):
        tc = TypedConflict(file_a="a.md", file_b="b.md")
        assert tc.conflict_type == "none"
        assert tc.severity == "low"
        assert tc.resolved is False

    def test_typed_conflict_full(self):
        tc = TypedConflict(
            file_a="a.md", file_b="b.md",
            conflict_type="factual_contradiction",
            severity="high",
            summary_ko="테스트",
            suggested_resolution="merge",
        )
        assert tc.conflict_type == "factual_contradiction"

    def test_conflict_analysis_defaults(self):
        ca = ConflictAnalysis()
        assert ca.conflict_type == "none"
        assert ca.severity == "low"
        assert ca.suggested_resolution == "dismiss"

    def test_conflict_analysis_valid_literals(self):
        ca = ConflictAnalysis(
            conflict_type="scope_overlap",
            severity="medium",
            suggested_resolution="scope_clarify",
        )
        assert ca.conflict_type == "scope_overlap"

    def test_conflict_analysis_serialization(self):
        ca = ConflictAnalysis(
            conflict_type="temporal",
            severity="medium",
            summary_ko="버전 차이",
            claim_a="v1 내용",
            claim_b="v2 내용",
            suggested_resolution="version_chain",
            resolution_detail="supersedes 설정 필요",
        )
        d = ca.model_dump()
        assert d["conflict_type"] == "temporal"
        assert d["resolution_detail"] == "supersedes 설정 필요"


# ── Resolved state preservation across re-detection ──────────────

class TestResolvedStatePreservation:
    """When check_file re-detects a pair, resolved/analyzed state should survive
    if content hasn't changed significantly (similarity delta < 0.05)."""

    def test_resolved_preserved_on_reindex(self):
        store = InMemoryConflictStore()
        # Initial detection
        store.replace_for_file("a.md", [
            StoredConflict(file_a="a.md", file_b="b.md", similarity=0.95, detected_at=1.0),
        ])
        # Resolve it
        store.resolve_pair("a.md", "b.md", "user1", "scope_clarify")
        assert store.get_all_pairs()[0].resolved is True

        # Re-detect with nearly identical similarity (content unchanged)
        store.replace_for_file("a.md", [
            StoredConflict(file_a="a.md", file_b="b.md", similarity=0.94, detected_at=2.0),
        ])
        pair = store.get_all_pairs()[0]
        assert pair.resolved is True, "Resolved status should survive re-detection"
        assert pair.resolved_action == "scope_clarify"

    def test_resolved_reset_on_content_change(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict(file_a="a.md", file_b="b.md", similarity=0.95, detected_at=1.0),
        ])
        store.resolve_pair("a.md", "b.md", "user1", "dismiss")
        assert store.get_all_pairs()[0].resolved is True

        # Re-detect with significantly different similarity (content changed)
        store.replace_for_file("a.md", [
            StoredConflict(file_a="a.md", file_b="b.md", similarity=0.85, detected_at=2.0),
        ])
        pair = store.get_all_pairs()[0]
        assert pair.resolved is False, "Content changed → resolved should reset"
        assert pair.resolved_action == ""

    def test_analyzed_preserved_on_reindex(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict(file_a="a.md", file_b="b.md", similarity=0.95, detected_at=1.0),
        ])
        store.update_analysis("a.md", "b.md", {
            "conflict_type": "temporal",
            "severity": "medium",
            "summary_ko": "시간차 충돌",
            "analyzed_at": 100.0,
        })
        assert store.get_all_pairs()[0].conflict_type == "temporal"

        # Re-detect, same similarity
        store.replace_for_file("a.md", [
            StoredConflict(file_a="a.md", file_b="b.md", similarity=0.96, detected_at=2.0),
        ])
        pair = store.get_all_pairs()[0]
        assert pair.conflict_type == "temporal", "Analysis should survive re-detection"
        assert pair.summary_ko == "시간차 충돌"

    def test_pair_disappears_when_not_redetected(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict(file_a="a.md", file_b="b.md", similarity=0.95, detected_at=1.0),
        ])
        store.resolve_pair("a.md", "b.md", "user1", "dismiss")

        # Re-detect with NO pairs (documents are now different)
        store.replace_for_file("a.md", [])
        assert len(store.get_all_pairs()) == 0, "Pair should be gone if not re-detected"


# ── Canonical key ─────────────────────────────────────────────────

class TestCanonicalKey:
    def test_order(self):
        assert _canonical_key("b.md", "a.md") == ("a.md", "b.md")
        assert _canonical_key("a.md", "b.md") == ("a.md", "b.md")

    def test_same(self):
        assert _canonical_key("x.md", "x.md") == ("x.md", "x.md")
