"""Tests for Phase 2-B Step 5: Document lineage system.

Validates:
1. DocumentMetadata lineage fields (supersedes, superseded_by, related)
2. Frontmatter roundtrip with lineage
3. Superseded document penalty in RAG context
"""

import pytest
from backend.core.schemas import DocumentMetadata
from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter


class TestLineageFields:
    """P2B-5-1: lineage fields on DocumentMetadata."""

    def test_default_empty(self):
        meta = DocumentMetadata()
        assert meta.supersedes == ""
        assert meta.superseded_by == ""
        assert meta.related == []

    def test_set_fields(self):
        meta = DocumentMetadata(
            supersedes="wiki/old-doc.md",
            superseded_by="wiki/new-doc.md",
            related=["wiki/related-a.md", "wiki/related-b.md"],
        )
        assert meta.supersedes == "wiki/old-doc.md"
        assert meta.superseded_by == "wiki/new-doc.md"
        assert len(meta.related) == 2


class TestLineageFrontmatter:
    """P2B-5-1: Frontmatter parsing/serialization with lineage."""

    def test_parse_supersedes(self):
        raw = "---\ndomain: IT\nsupersedes: wiki/v1.md\n---\nContent"
        meta, body = _parse_frontmatter(raw)
        assert meta.supersedes == "wiki/v1.md"

    def test_parse_superseded_by(self):
        raw = "---\nsuperseded_by: wiki/v3.md\nstatus: deprecated\n---\nOld"
        meta, body = _parse_frontmatter(raw)
        assert meta.superseded_by == "wiki/v3.md"
        assert meta.status == "deprecated"

    def test_parse_related(self):
        raw = "---\nrelated:\n  - wiki/a.md\n  - wiki/b.md\n---\nContent"
        meta, body = _parse_frontmatter(raw)
        assert meta.related == ["wiki/a.md", "wiki/b.md"]

    def test_serialize_lineage(self):
        meta = DocumentMetadata(
            domain="SCM",
            supersedes="wiki/old.md",
            superseded_by="wiki/new.md",
        )
        result = _serialize_frontmatter(meta, "Body")
        assert "supersedes: wiki/old.md" in result
        assert "superseded_by: wiki/new.md" in result

    def test_serialize_related(self):
        meta = DocumentMetadata(related=["a.md", "b.md"])
        result = _serialize_frontmatter(meta, "Body")
        assert "related:" in result
        assert "  - a.md" in result
        assert "  - b.md" in result

    def test_serialize_empty_lineage(self):
        """Empty lineage fields should not appear in frontmatter."""
        meta = DocumentMetadata(domain="IT")
        result = _serialize_frontmatter(meta, "Body")
        assert "supersedes" not in result
        assert "superseded_by" not in result
        assert "related" not in result

    def test_roundtrip(self):
        meta = DocumentMetadata(
            domain="IT",
            supersedes="wiki/v1.md",
            related=["wiki/ref.md"],
            status="approved",
        )
        serialized = _serialize_frontmatter(meta, "Hello")
        parsed, body = _parse_frontmatter(serialized)
        assert parsed.supersedes == "wiki/v1.md"
        assert parsed.related == ["wiki/ref.md"]
        assert parsed.status == "approved"
        assert body == "Hello"


class TestSupersededPenalty:
    """P2B-5-2: Deprecated docs get distance penalty."""

    def test_penalty_applied(self):
        from backend.application.agent.rag_agent import RAGAgent

        documents = ["Doc content"]
        metadatas = [{"file_path": "old.md", "status": "deprecated", "superseded_by": "new.md"}]
        distances = [0.2]

        # Build context should include warning
        context = RAGAgent._build_context_with_metadata(documents, metadatas, distances)
        assert "폐기됨" in context or "deprecated" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
