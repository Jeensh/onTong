"""Tests for Phase 2-B Step 6: RAG deprecated document filtering.

Validates:
1. ChromaDB search excludes deprecated documents by default
2. Superseded_by chain resolution (fallback to latest version)
3. Penalty logic removed — deprecated docs never appear in sources
"""

import pytest
from backend.core.schemas import DocumentMetadata


class TestDeprecatedFilterLogic:
    """P2B-6-1: deprecated docs excluded from search."""

    def test_build_deprecated_where_filter(self):
        """The where clause should exclude status='deprecated'."""
        from backend.application.agent.rag_agent import RAGAgent

        # RAGAgent should have a method or constant for the deprecated filter
        where = RAGAgent._build_status_filter()
        # Should filter out deprecated status
        assert where is not None
        assert "status" in str(where)

    def test_deprecated_doc_not_in_sources(self):
        """Deprecated documents should not appear in source list."""
        from backend.application.agent.rag_agent import RAGAgent

        documents = ["Doc A content", "Doc B deprecated content"]
        metadatas = [
            {"file_path": "a.md", "status": "approved"},
            {"file_path": "b.md", "status": "deprecated", "superseded_by": "a.md"},
        ]
        distances = [0.2, 0.3]

        sources = RAGAgent._build_sources(metadatas, distances, threshold=0.3)
        doc_paths = [s.doc for s in sources]
        assert "a.md" in doc_paths
        assert "b.md" not in doc_paths


class TestSupersededChainResolution:
    """P2B-6-2: follow superseded_by chain to find latest version."""

    def test_resolve_chain_single_hop(self):
        """v1 -> v2: should resolve to v2."""
        from backend.application.agent.rag_agent import RAGAgent

        chain = {"v1.md": "v2.md"}
        result = RAGAgent._resolve_superseded_chain("v1.md", chain, max_depth=5)
        assert result == "v2.md"

    def test_resolve_chain_multi_hop(self):
        """v1 -> v2 -> v3: should resolve to v3."""
        from backend.application.agent.rag_agent import RAGAgent

        chain = {"v1.md": "v2.md", "v2.md": "v3.md"}
        result = RAGAgent._resolve_superseded_chain("v1.md", chain, max_depth=5)
        assert result == "v3.md"

    def test_resolve_chain_no_supersede(self):
        """No superseded_by: should return None."""
        from backend.application.agent.rag_agent import RAGAgent

        chain = {}
        result = RAGAgent._resolve_superseded_chain("v1.md", chain, max_depth=5)
        assert result is None

    def test_resolve_chain_max_depth(self):
        """Circular reference protection: should stop at max_depth."""
        from backend.application.agent.rag_agent import RAGAgent

        chain = {"a.md": "b.md", "b.md": "a.md"}
        result = RAGAgent._resolve_superseded_chain("a.md", chain, max_depth=5)
        # Should not infinite loop, returns whatever it reached
        assert result is not None


class TestPenaltyRemoved:
    """P2B-6-3: +0.3 penalty logic should be removed."""

    def test_no_penalty_in_context_builder(self):
        """Context builder should not modify distances for deprecated docs."""
        from backend.application.agent.rag_agent import RAGAgent

        documents = ["Active content"]
        metadatas = [{"file_path": "active.md", "status": "approved"}]
        distances = [0.2]

        # Distances should not be modified
        original_dist = distances[0]
        context = RAGAgent._build_context_with_metadata(documents, metadatas, distances)
        assert distances[0] == original_dist  # not mutated


class TestMetadataChromaCompleteness:
    """Guard: ALL DocumentMetadata fields must be in _metadata_to_chroma()."""

    def test_all_fields_included(self):
        """Every DocumentMetadata field must appear in ChromaDB metadata.

        This test auto-detects new fields added to DocumentMetadata and
        fails if _metadata_to_chroma() doesn't include them.
        """
        from backend.application.wiki.wiki_indexer import WikiIndexer
        from backend.core.schemas import WikiFile, DocumentMetadata

        meta = DocumentMetadata(
            domain="test", process="test", status="approved",
            superseded_by="new.md", supersedes="old.md",
            tags=["tag1"], error_codes=["E001"], related=["other.md"],
            created="2026-01-01", updated="2026-01-02",
            created_by="tester", updated_by="tester",
        )
        wiki_file = WikiFile(path="test.md", title="Test", content="body", metadata=meta)
        chroma_meta = WikiIndexer._metadata_to_chroma(wiki_file)

        for field in DocumentMetadata.model_fields:
            assert field in chroma_meta, (
                f"DocumentMetadata.{field} is missing from _metadata_to_chroma(). "
                f"New fields must be synced to ChromaDB."
            )

    def test_list_fields_pipe_delimited(self):
        """list[str] fields should be serialized as pipe-delimited strings."""
        from backend.application.wiki.wiki_indexer import WikiIndexer
        from backend.core.schemas import WikiFile, DocumentMetadata

        meta = DocumentMetadata(tags=["a", "b"], error_codes=["E1"], related=["x.md"])
        wiki_file = WikiFile(path="t.md", title="T", content="c", metadata=meta)
        chroma_meta = WikiIndexer._metadata_to_chroma(wiki_file)

        assert chroma_meta["tags"] == "|a|b|"
        assert chroma_meta["error_codes"] == "|E1|"
        assert chroma_meta["related"] == "|x.md|"

    def test_empty_list_fields(self):
        """Empty lists should become empty strings, not '||'."""
        from backend.application.wiki.wiki_indexer import WikiIndexer
        from backend.core.schemas import WikiFile, DocumentMetadata

        meta = DocumentMetadata()
        wiki_file = WikiFile(path="t.md", title="T", content="c", metadata=meta)
        chroma_meta = WikiIndexer._metadata_to_chroma(wiki_file)

        assert chroma_meta["tags"] == ""
        assert chroma_meta["error_codes"] == ""
        assert chroma_meta["related"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
