"""Tests for MetadataIndex enrichment (Phase 3).

Validates:
1. status/supersedes/superseded_by stored in file entries
2. supersedes_index reverse index (who supersedes whom)
3. related_index reverse index (who references whom)
4. status_files index (files grouped by status)
5. Query APIs: get_file_entry, get_supersedes_reverse, get_related_reverse, get_files_by_status, get_all_statuses
6. Incremental save/delete maintains all indexes
7. Full rebuild populates all indexes
"""

import json
import pytest
import tempfile
from pathlib import Path

from backend.application.metadata.metadata_index import MetadataIndex


@pytest.fixture
def idx(tmp_path):
    """Create a MetadataIndex in a temp directory."""
    return MetadataIndex(str(tmp_path))


class TestEnrichedFieldStorage:
    """status/supersedes/superseded_by are stored in file entries."""

    def test_on_file_saved_stores_new_fields(self, idx):
        idx.on_file_saved(
            "doc/a.md", "IT", "", ["tag1"],
            status="approved",
            supersedes="doc/old.md",
            superseded_by="",
        )
        entry = idx.get_file_entry("doc/a.md")
        assert entry is not None
        assert entry["status"] == "approved"
        assert entry["supersedes"] == "doc/old.md"
        assert entry["superseded_by"] == ""

    def test_rebuild_stores_new_fields(self, idx):
        idx.rebuild(extended=[
            {
                "path": "doc/v2.md",
                "domain": "IT",
                "process": "",
                "tags": [],
                "status": "deprecated",
                "supersedes": "",
                "superseded_by": "doc/v3.md",
            }
        ])
        entry = idx.get_file_entry("doc/v2.md")
        assert entry["status"] == "deprecated"
        assert entry["superseded_by"] == "doc/v3.md"


class TestSupersedesIndex:
    """supersedes_index tracks who supersedes whom."""

    def test_basic_supersedes(self, idx):
        idx.on_file_saved("doc/v2.md", "IT", "", [], supersedes="doc/v1.md")
        assert idx.get_supersedes_reverse("doc/v1.md") == ["doc/v2.md"]

    def test_multiple_supersede_same_target(self, idx):
        idx.on_file_saved("doc/v2a.md", "IT", "", [], supersedes="doc/v1.md")
        idx.on_file_saved("doc/v2b.md", "IT", "", [], supersedes="doc/v1.md")
        result = idx.get_supersedes_reverse("doc/v1.md")
        assert sorted(result) == ["doc/v2a.md", "doc/v2b.md"]

    def test_supersedes_removed_on_delete(self, idx):
        idx.on_file_saved("doc/v2.md", "IT", "", [], supersedes="doc/v1.md")
        idx.on_file_deleted("doc/v2.md")
        assert idx.get_supersedes_reverse("doc/v1.md") == []

    def test_supersedes_updated_on_resave(self, idx):
        idx.on_file_saved("doc/v2.md", "IT", "", [], supersedes="doc/v1.md")
        # Change supersedes target
        idx.on_file_saved("doc/v2.md", "IT", "", [], supersedes="doc/v0.md")
        assert idx.get_supersedes_reverse("doc/v1.md") == []
        assert idx.get_supersedes_reverse("doc/v0.md") == ["doc/v2.md"]

    def test_no_supersedes_returns_empty(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [])
        assert idx.get_supersedes_reverse("doc/a.md") == []


class TestRelatedIndex:
    """related_index tracks who references whom in their related field."""

    def test_basic_related(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [], related=["doc/b.md", "doc/c.md"])
        assert idx.get_related_reverse("doc/b.md") == ["doc/a.md"]
        assert idx.get_related_reverse("doc/c.md") == ["doc/a.md"]

    def test_related_removed_on_delete(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [], related=["doc/b.md"])
        idx.on_file_deleted("doc/a.md")
        assert idx.get_related_reverse("doc/b.md") == []

    def test_related_updated_on_resave(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [], related=["doc/b.md"])
        idx.on_file_saved("doc/a.md", "IT", "", [], related=["doc/c.md"])
        assert idx.get_related_reverse("doc/b.md") == []
        assert idx.get_related_reverse("doc/c.md") == ["doc/a.md"]


class TestStatusFiles:
    """status_files groups files by status."""

    def test_basic_status_grouping(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [], status="approved")
        idx.on_file_saved("doc/b.md", "HR", "", [], status="deprecated")
        idx.on_file_saved("doc/c.md", "IT", "", [], status="approved")
        assert sorted(idx.get_files_by_status("approved")) == ["doc/a.md", "doc/c.md"]
        assert idx.get_files_by_status("deprecated") == ["doc/b.md"]
        assert idx.get_files_by_status("draft") == []

    def test_status_change_updates_index(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [], status="draft")
        idx.on_file_saved("doc/a.md", "IT", "", [], status="approved")
        assert idx.get_files_by_status("draft") == []
        assert idx.get_files_by_status("approved") == ["doc/a.md"]

    def test_status_removed_on_delete(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [], status="approved")
        idx.on_file_deleted("doc/a.md")
        assert idx.get_files_by_status("approved") == []


class TestGetAllStatuses:
    """get_all_statuses returns {path: status} for all files."""

    def test_all_statuses(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "", [], status="approved")
        idx.on_file_saved("doc/b.md", "HR", "", [], status="draft")
        idx.on_file_saved("doc/c.md", "IT", "", [])  # no status
        result = idx.get_all_statuses()
        assert result == {"doc/a.md": "approved", "doc/b.md": "draft"}


class TestGetFileEntry:
    """get_file_entry returns the full entry or None."""

    def test_existing_file(self, idx):
        idx.on_file_saved("doc/a.md", "IT", "P1", ["tag1"], status="approved")
        entry = idx.get_file_entry("doc/a.md")
        assert entry["domain"] == "IT"
        assert entry["process"] == "P1"
        assert entry["status"] == "approved"

    def test_nonexistent_file(self, idx):
        assert idx.get_file_entry("doc/nonexist.md") is None


class TestRebuildWithAllIndexes:
    """Full rebuild populates supersedes/related/status indexes."""

    def test_rebuild_indexes(self, idx):
        idx.rebuild(extended=[
            {
                "path": "doc/v1.md",
                "domain": "IT", "process": "", "tags": [],
                "status": "deprecated",
                "superseded_by": "doc/v2.md",
            },
            {
                "path": "doc/v2.md",
                "domain": "IT", "process": "", "tags": [],
                "status": "approved",
                "supersedes": "doc/v1.md",
                "related": ["doc/guide.md"],
            },
            {
                "path": "doc/guide.md",
                "domain": "IT", "process": "", "tags": ["guide"],
                "status": "draft",
            },
        ])
        # Status index
        assert idx.get_files_by_status("deprecated") == ["doc/v1.md"]
        assert idx.get_files_by_status("approved") == ["doc/v2.md"]
        assert idx.get_files_by_status("draft") == ["doc/guide.md"]

        # Supersedes index
        assert idx.get_supersedes_reverse("doc/v1.md") == ["doc/v2.md"]

        # Related index
        assert idx.get_related_reverse("doc/guide.md") == ["doc/v2.md"]

        # All statuses
        statuses = idx.get_all_statuses()
        assert len(statuses) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
