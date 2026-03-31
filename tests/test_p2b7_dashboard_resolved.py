"""Tests for Phase 2-B Step 7: Conflict dashboard resolved state.

Validates:
1. DuplicatePair resolved field and auto-detection logic
2. API filter parameter (unresolved/resolved/all)
3. Resolved = bidirectional lineage exists between the pair
"""

import pytest
from backend.application.conflict.conflict_service import (
    ConflictDetectionService,
    DuplicatePair,
    is_pair_resolved,
)


class TestResolvedDetection:
    """P2B-7-1: auto-detect resolved pairs."""

    def test_resolved_when_superseded_by_matches(self):
        """Pair is resolved when A.superseded_by == B or B.superseded_by == A."""
        meta_a = {"file_path": "old.md", "status": "deprecated", "superseded_by": "new.md"}
        meta_b = {"file_path": "new.md", "status": "approved", "supersedes": "old.md"}
        assert is_pair_resolved("old.md", "new.md", meta_a, meta_b) is True

    def test_resolved_reverse_direction(self):
        """Resolved even when B is deprecated pointing to A."""
        meta_a = {"file_path": "new.md", "status": "approved"}
        meta_b = {"file_path": "old.md", "status": "deprecated", "superseded_by": "new.md"}
        assert is_pair_resolved("new.md", "old.md", meta_a, meta_b) is True

    def test_unresolved_no_lineage(self):
        """No lineage between pair = unresolved."""
        meta_a = {"file_path": "a.md", "status": ""}
        meta_b = {"file_path": "b.md", "status": ""}
        assert is_pair_resolved("a.md", "b.md", meta_a, meta_b) is False

    def test_unresolved_deprecated_but_different_target(self):
        """A is deprecated but superseded_by points to C, not B."""
        meta_a = {"file_path": "a.md", "status": "deprecated", "superseded_by": "c.md"}
        meta_b = {"file_path": "b.md", "status": ""}
        assert is_pair_resolved("a.md", "b.md", meta_a, meta_b) is False

    def test_resolved_both_deprecated_with_lineage(self):
        """Both deprecated but one points to the other."""
        meta_a = {"file_path": "a.md", "status": "deprecated", "superseded_by": "b.md"}
        meta_b = {"file_path": "b.md", "status": "deprecated", "superseded_by": "c.md"}
        assert is_pair_resolved("a.md", "b.md", meta_a, meta_b) is True


class TestDuplicatePairResolved:
    """P2B-7-1: DuplicatePair model has resolved field."""

    def test_duplicate_pair_has_resolved_field(self):
        pair = DuplicatePair(
            file_a="a.md", file_b="b.md", similarity=0.9, resolved=True
        )
        assert pair.resolved is True

    def test_duplicate_pair_default_unresolved(self):
        pair = DuplicatePair(file_a="a.md", file_b="b.md", similarity=0.9)
        assert pair.resolved is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
