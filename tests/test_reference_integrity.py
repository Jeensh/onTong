"""Tests for reference integrity (Phase 7).

Validates:
1. get_referencing_files finds all references to a path
2. MetadataIndex reverse lookups work for supersedes/superseded_by/related
3. Delete with references check (via get_referencing_files)
"""

import pytest
from backend.application.metadata.metadata_index import MetadataIndex


@pytest.fixture
def idx(tmp_path):
    """MetadataIndex with cross-references."""
    idx = MetadataIndex(str(tmp_path))
    idx.rebuild(extended=[
        {
            "path": "doc/v1.md", "domain": "IT", "process": "", "tags": [],
            "status": "deprecated", "superseded_by": "doc/v2.md",
        },
        {
            "path": "doc/v2.md", "domain": "IT", "process": "", "tags": [],
            "status": "approved", "supersedes": "doc/v1.md",
            "related": ["doc/guide.md"],
        },
        {
            "path": "doc/guide.md", "domain": "IT", "process": "", "tags": [],
            "status": "draft", "related": ["doc/v2.md"],
        },
    ])
    return idx


class TestReferenceLookup:
    """Find all files that reference a given path."""

    def test_supersedes_reverse(self, idx):
        # v2 supersedes v1
        assert idx.get_supersedes_reverse("doc/v1.md") == ["doc/v2.md"]

    def test_related_reverse(self, idx):
        # v2 references guide in related, guide references v2 in related
        assert idx.get_related_reverse("doc/guide.md") == ["doc/v2.md"]
        assert idx.get_related_reverse("doc/v2.md") == ["doc/guide.md"]

    def test_superseded_by_lookup(self, idx):
        """Files whose superseded_by points to a given path."""
        files = idx._load().get("files", {})
        refs = [p for p, e in files.items() if e.get("superseded_by") == "doc/v2.md"]
        assert refs == ["doc/v1.md"]

    def test_no_references(self, idx):
        assert idx.get_supersedes_reverse("doc/nonexist.md") == []
        assert idx.get_related_reverse("doc/nonexist.md") == []


class TestCombinedReferences:
    """Combining all reference types for a comprehensive check."""

    def test_all_references_to_v2(self, idx):
        """doc/v2.md is referenced by: v1 (superseded_by) and guide (related)."""
        refs: set[str] = set()
        refs.update(idx.get_supersedes_reverse("doc/v2.md"))
        refs.update(idx.get_related_reverse("doc/v2.md"))
        # Also check superseded_by
        for p, entry in idx._load().get("files", {}).items():
            if entry.get("superseded_by") == "doc/v2.md":
                refs.add(p)
        assert sorted(refs) == ["doc/guide.md", "doc/v1.md"]


class TestDeleteWithReferences:
    """Verify that references are detectable before deletion."""

    def test_detect_before_delete(self, idx):
        """guide.md is referenced by v2 — should be detectable."""
        refs = idx.get_related_reverse("doc/guide.md")
        assert len(refs) > 0  # Should warn before deleting guide.md

    def test_unreferenced_safe_to_delete(self, tmp_path):
        """A file with no references should be safe to delete."""
        idx = MetadataIndex(str(tmp_path))
        idx.rebuild(extended=[
            {"path": "doc/solo.md", "domain": "IT", "process": "", "tags": [], "status": "draft"},
        ])
        assert idx.get_supersedes_reverse("doc/solo.md") == []
        assert idx.get_related_reverse("doc/solo.md") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
