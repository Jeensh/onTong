"""BM25 adapter conforming to FullTextSearch protocol.

Wraps the global bm25_index singleton so that get_fulltext_search() can return
a proper FullTextSearch subclass for the bm25_inmem profile.
"""
from __future__ import annotations

from .fulltext_protocol import FullTextSearch, SearchHit
from .bm25 import bm25_index, BM25Document, tokenize


class BM25SearchAdapter(FullTextSearch):
    """Wrap the global bm25_index to conform to FullTextSearch protocol."""

    def add_documents(self, docs: list) -> int:
        """Add chunk documents. Converts dict-like inputs to BM25Document if needed.

        If a dict / object input has no `tokens`, the adapter tokenizes its
        content automatically — callers (e.g. WikiIndexer) don't need to know
        BM25 specifics.

        Returns count added.
        """
        bm25_docs: list[BM25Document] = []
        for d in docs:
            if isinstance(d, BM25Document):
                bm25_docs.append(d)
                continue
            if isinstance(d, dict):
                content = d.get("content", "")
                tokens = d.get("tokens") or tokenize(content)
                bm25_docs.append(BM25Document(
                    id=d.get("id", ""),
                    file_path=d.get("file_path", ""),
                    heading=d.get("heading", ""),
                    content=content,
                    tokens=tokens,
                ))
                continue
            # object with attributes (e.g. WikiChunk)
            content = getattr(d, "content", "")
            tokens = getattr(d, "tokens", None) or tokenize(content)
            bm25_docs.append(BM25Document(
                id=getattr(d, "id", ""),
                file_path=getattr(d, "file_path", ""),
                heading=getattr(d, "heading", ""),
                content=content,
                tokens=tokens,
            ))
        bm25_index.add_documents(bm25_docs)
        return len(bm25_docs)

    def remove_by_file(self, file_path: str) -> int:
        """Remove all chunks for a file. Returns count removed."""
        before = bm25_index.size
        bm25_index.remove_by_file(file_path)
        return max(0, before - bm25_index.size)

    def has_file(self, file_path: str) -> bool:
        """True iff bm25_index has at least one chunk for file_path."""
        with bm25_index._lock:
            return any(d.file_path == file_path for d in bm25_index._documents)

    def search(
        self, query: str, limit: int = 10, *, file_predicate=None
    ) -> list[SearchHit]:
        """Full-text search. file_predicate filters before limit."""
        # Over-fetch when filtering client-side
        raw_limit = limit * 5 if file_predicate else limit
        # bm25_index.search signature: search(query, n_results=8)
        results = bm25_index.search(query, n_results=raw_limit)
        hits: list[SearchHit] = []
        for item in results:
            # BM25Index.search returns list[tuple[BM25Document, float]]
            if isinstance(item, tuple):
                doc, score = item
            else:
                doc = item
                score = float(getattr(item, "score", 0.0))
            if file_predicate and not file_predicate(doc.file_path):
                continue
            hits.append(SearchHit(
                file_path=doc.file_path,
                chunk_id=doc.id,
                heading=doc.heading,
                content=doc.content,
                score=float(score),
            ))
            if len(hits) >= limit:
                break
        return hits

    def clear(self) -> None:
        bm25_index.clear()

    @property
    def size(self) -> int:
        return bm25_index.size
