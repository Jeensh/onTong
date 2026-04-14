"""Tests for document status field.

Validates:
1. DocumentMetadata status field (simplified: draft | approved | deprecated)
2. SourceRef extended fields
3. Frontmatter parsing/serialization of status
4. Status normalization (review/"" → draft)
"""

import pytest
from backend.core.schemas import DocumentMetadata, SourceRef
from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter, _normalize_status


class TestDocumentMetadataStatus:
    """Status field on DocumentMetadata."""

    def test_default_draft(self):
        meta = DocumentMetadata()
        assert meta.status == "draft"

    def test_valid_statuses(self):
        for s in ["draft", "approved", "deprecated"]:
            meta = DocumentMetadata(status=s)
            assert meta.status == s

    def test_serialization(self):
        meta = DocumentMetadata(status="approved", domain="IT")
        data = meta.model_dump()
        assert data["status"] == "approved"


class TestStatusNormalization:
    """Status normalization: review/empty → draft."""

    def test_review_to_draft(self):
        assert _normalize_status("review") == "draft"

    def test_empty_to_draft(self):
        assert _normalize_status("") == "draft"

    def test_none_to_draft(self):
        assert _normalize_status(None) == "draft"

    def test_approved_unchanged(self):
        assert _normalize_status("approved") == "approved"

    def test_deprecated_unchanged(self):
        assert _normalize_status("deprecated") == "deprecated"

    def test_draft_unchanged(self):
        assert _normalize_status("draft") == "draft"

    def test_unknown_to_draft(self):
        assert _normalize_status("garbage") == "draft"


class TestSourceRefExtended:
    """SourceRef with updated, updated_by, status fields."""

    def test_new_fields(self):
        s = SourceRef(
            doc="test.md",
            relevance=0.85,
            updated="2026-03-28",
            updated_by="홍길동",
            status="approved",
        )
        data = s.model_dump()
        assert data["updated"] == "2026-03-28"
        assert data["updated_by"] == "홍길동"
        assert data["status"] == "approved"

    def test_backward_compat(self):
        """Old-style SourceRef without new fields should still work."""
        s = SourceRef(doc="test.md", relevance=0.5)
        assert s.updated == ""
        assert s.status == ""


class TestFrontmatterStatusParsing:
    """Frontmatter parsing includes status with normalization."""

    def test_parse_status(self):
        raw = "---\ndomain: IT\nstatus: approved\n---\nContent"
        meta, body = _parse_frontmatter(raw)
        assert meta.status == "approved"
        assert body == "Content"

    def test_parse_no_status_defaults_to_draft(self):
        raw = "---\ndomain: HR\n---\nContent"
        meta, body = _parse_frontmatter(raw)
        assert meta.status == "draft"

    def test_parse_review_normalized_to_draft(self):
        raw = "---\nstatus: review\n---\nContent"
        meta, body = _parse_frontmatter(raw)
        assert meta.status == "draft"

    def test_serialize_status(self):
        meta = DocumentMetadata(domain="IT", status="deprecated")
        result = _serialize_frontmatter(meta, "Body")
        assert "status: deprecated" in result

    def test_serialize_draft_status(self):
        """Draft status should appear in frontmatter."""
        meta = DocumentMetadata(domain="IT", status="draft")
        result = _serialize_frontmatter(meta, "Body")
        assert "status: draft" in result

    def test_roundtrip(self):
        meta = DocumentMetadata(domain="SCM", status="approved", created_by="김철수")
        serialized = _serialize_frontmatter(meta, "Hello")
        parsed_meta, body = _parse_frontmatter(serialized)
        assert parsed_meta.status == "approved"
        assert parsed_meta.domain == "SCM"
        assert body == "Hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
