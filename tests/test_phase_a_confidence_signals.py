"""Phase A — Confidence signal bug fixes tests.

Tests:
- _get_backlink_count returns > 0 when related fields reference the target
- _is_owner_active returns True when the owner has recent edits
- MetadataIndex stores extended fields (updated, updated_by, created_by, related)
"""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from backend.application.metadata.metadata_index import MetadataIndex
from backend.application.trust.confidence_service import ConfidenceService


# ── MetadataIndex extended fields ────────────────────────────────

class TestMetadataIndexExtended:
    """MetadataIndex should store and return extended fields."""

    def _make_index(self, tmp_path):
        idx = MetadataIndex(str(tmp_path))
        return idx

    def test_on_file_saved_stores_extended_fields(self, tmp_path):
        idx = self._make_index(tmp_path)
        idx.on_file_saved(
            "docs/a.md", "infra", "deploy", ["cache", "redis"],
            updated="2026-04-10",
            updated_by="admin",
            created_by="admin",
            related=["docs/b.md"],
        )
        data = idx._load()
        entry = data["files"]["docs/a.md"]
        assert entry["updated"] == "2026-04-10"
        assert entry["updated_by"] == "admin"
        assert entry["created_by"] == "admin"
        assert entry["related"] == ["docs/b.md"]

    def test_on_file_saved_preserves_created_by(self, tmp_path):
        """created_by should be preserved from previous entry if not provided."""
        idx = self._make_index(tmp_path)
        idx.on_file_saved(
            "docs/a.md", "infra", "deploy", ["cache"],
            created_by="original_author",
        )
        # Second save without created_by
        idx.on_file_saved("docs/a.md", "infra", "deploy", ["cache", "redis"])
        entry = idx._load()["files"]["docs/a.md"]
        assert entry["created_by"] == "original_author"

    def test_rebuild_extended(self, tmp_path):
        idx = self._make_index(tmp_path)
        idx.rebuild(extended=[
            {
                "path": "docs/a.md",
                "domain": "infra",
                "process": "deploy",
                "tags": ["cache"],
                "updated": "2026-04-10",
                "updated_by": "admin",
                "created_by": "admin",
                "related": ["docs/b.md"],
            },
            {
                "path": "docs/b.md",
                "domain": "infra",
                "process": "",
                "tags": [],
                "updated": "2026-04-09",
                "updated_by": "user1",
                "created_by": "user1",
                "related": [],
            },
        ])
        data = idx._load()
        assert data["files"]["docs/a.md"]["updated_by"] == "admin"
        assert data["files"]["docs/b.md"]["created_by"] == "user1"

    def test_rebuild_legacy_format(self, tmp_path):
        """Legacy tuple format should still work."""
        idx = self._make_index(tmp_path)
        idx.rebuild([
            ("docs/a.md", "infra", "deploy", ["cache"]),
        ])
        entry = idx._load()["files"]["docs/a.md"]
        assert entry["domain"] == "infra"
        assert entry["updated"] == ""  # default
        assert entry["related"] == []  # default


# ── Backlink count fix ──────────────────────────────────────────

class TestBacklinkCount:
    """_get_backlink_count should count documents referencing the target in their related field."""

    def _make_service(self, tmp_path, files_data: dict):
        idx = MetadataIndex(str(tmp_path))
        # Manually inject data
        idx._data = {"files": files_data, "domains": {}, "tags": {}, "untagged": []}
        svc = ConfidenceService(meta_index=idx, wiki_dir=str(tmp_path))
        return svc

    def test_backlink_count_basic(self, tmp_path):
        """doc_b references doc_a → doc_a backlink count = 1."""
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"domain": "infra", "process": "", "tags": [], "related": []},
            "docs/b.md": {"domain": "infra", "process": "", "tags": [], "related": ["docs/a.md"]},
        })
        count = svc._get_backlink_count("docs/a.md")
        assert count == 1

    def test_backlink_count_multiple(self, tmp_path):
        """Multiple documents reference the target."""
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"domain": "infra", "process": "", "tags": [], "related": []},
            "docs/b.md": {"domain": "infra", "process": "", "tags": [], "related": ["docs/a.md"]},
            "docs/c.md": {"domain": "infra", "process": "", "tags": [], "related": ["docs/a.md", "docs/b.md"]},
        })
        count = svc._get_backlink_count("docs/a.md")
        assert count == 2

    def test_backlink_count_zero(self, tmp_path):
        """No documents reference the target."""
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"domain": "infra", "process": "", "tags": [], "related": []},
            "docs/b.md": {"domain": "infra", "process": "", "tags": [], "related": []},
        })
        count = svc._get_backlink_count("docs/a.md")
        assert count == 0

    def test_backlink_count_self_excluded(self, tmp_path):
        """A document's own related list should not count as a backlink to itself."""
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"domain": "", "process": "", "tags": [], "related": ["docs/a.md"]},
        })
        count = svc._get_backlink_count("docs/a.md")
        assert count == 0


# ── Owner activity fix ──────────────────────────────────────────

class TestOwnerActivity:
    """_is_owner_active should return True when the owner has recent edits."""

    def _make_service(self, tmp_path, files_data: dict):
        idx = MetadataIndex(str(tmp_path))
        idx._data = {"files": files_data, "domains": {}, "tags": {}, "untagged": []}
        svc = ConfidenceService(meta_index=idx, wiki_dir=str(tmp_path))
        return svc

    def test_owner_active_recent_edit(self, tmp_path):
        """Owner edited another doc within 90 days → active."""
        recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"updated_by": "admin", "updated": recent_date, "created_by": "admin"},
            "docs/b.md": {"updated_by": "admin", "updated": recent_date, "created_by": "admin"},
        })
        assert svc._is_owner_active("admin", "docs/a.md") is True

    def test_owner_inactive_old_edit(self, tmp_path):
        """Owner's last edit was > 90 days ago → inactive."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"updated_by": "admin", "updated": old_date, "created_by": "admin"},
            "docs/b.md": {"updated_by": "admin", "updated": old_date, "created_by": "admin"},
        })
        assert svc._is_owner_active("admin", "docs/a.md") is False

    def test_owner_active_excludes_self(self, tmp_path):
        """The current document should not count toward the owner's activity."""
        recent_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        old_date = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"updated_by": "admin", "updated": recent_date, "created_by": "admin"},
            "docs/b.md": {"updated_by": "other", "updated": old_date, "created_by": "other"},
        })
        # Only doc a.md was recently edited by admin, but it's the excluded path
        assert svc._is_owner_active("admin", "docs/a.md") is False

    def test_owner_active_empty_created_by(self, tmp_path):
        """Empty created_by → always False."""
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"updated_by": "admin", "updated": "2026-04-10"},
        })
        assert svc._is_owner_active("", "docs/a.md") is False

    def test_owner_active_no_updated_field(self, tmp_path):
        """Missing updated field → skip, return False."""
        svc = self._make_service(tmp_path, {
            "docs/a.md": {"updated_by": "admin", "created_by": "admin"},
            "docs/b.md": {"updated_by": "admin"},
        })
        assert svc._is_owner_active("admin", "docs/a.md") is False


# ── Parse date utility ──────────────────────────────────────────

class TestParseDate:
    def test_iso_with_tz(self):
        dt = ConfidenceService._parse_date("2026-04-10T12:00:00+09:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_iso_without_tz(self):
        dt = ConfidenceService._parse_date("2026-04-10")
        assert dt is not None
        assert dt.tzinfo is not None  # should be set to UTC

    def test_invalid(self):
        dt = ConfidenceService._parse_date("not-a-date")
        assert dt is None
