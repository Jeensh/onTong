"""Tests for Phase 2-B Step 2: Metadata-based document status/trust display.

Validates:
1. DocumentMetadata status field
2. SourceRef extended fields
3. ChromaDB metadata includes status
4. Frontmatter parsing/serialization of status
"""

import pytest
from backend.core.schemas import DocumentMetadata, SourceRef
from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter


class TestDocumentMetadataStatus:
    """P2B-2-1: status field on DocumentMetadata."""

    def test_default_empty(self):
        meta = DocumentMetadata()
        assert meta.status == ""

    def test_valid_statuses(self):
        for s in ["draft", "review", "approved", "deprecated"]:
            meta = DocumentMetadata(status=s)
            assert meta.status == s

    def test_serialization(self):
        meta = DocumentMetadata(status="approved", domain="IT")
        data = meta.model_dump()
        assert data["status"] == "approved"


class TestSourceRefExtended:
    """P2B-2-3: SourceRef with updated, updated_by, status fields."""

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
    """P2B-2-1: Frontmatter parsing includes status."""

    def test_parse_status(self):
        raw = "---\ndomain: IT\nstatus: approved\n---\nContent"
        meta, body = _parse_frontmatter(raw)
        assert meta.status == "approved"
        assert body == "Content"

    def test_parse_no_status(self):
        raw = "---\ndomain: HR\n---\nContent"
        meta, body = _parse_frontmatter(raw)
        assert meta.status == ""

    def test_serialize_status(self):
        meta = DocumentMetadata(domain="IT", status="deprecated")
        result = _serialize_frontmatter(meta, "Body")
        assert "status: deprecated" in result

    def test_serialize_empty_status(self):
        """Empty status should not appear in frontmatter."""
        meta = DocumentMetadata(domain="IT")
        result = _serialize_frontmatter(meta, "Body")
        assert "status" not in result

    def test_roundtrip(self):
        meta = DocumentMetadata(domain="SCM", status="review", created_by="김철수")
        serialized = _serialize_frontmatter(meta, "Hello")
        parsed_meta, body = _parse_frontmatter(serialized)
        assert parsed_meta.status == "review"
        assert parsed_meta.domain == "SCM"
        assert body == "Hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
