"""Hybrid search quality test — BM25 + Vector vs Vector-only.

Usage:
    cd /path/to/onTong
    source venv/bin/activate
    python -m tests.test_hybrid_search
"""

from __future__ import annotations

import asyncio
import time

from backend.infrastructure.vectordb.chroma import ChromaWrapper
from backend.infrastructure.search.bm25 import bm25_index, BM25Document, tokenize
from backend.infrastructure.search.hybrid import reciprocal_rank_fusion
from backend.application.wiki.wiki_indexer import WikiIndexer


async def main() -> None:
    chroma = ChromaWrapper()
    chroma.connect()

    print("=" * 72)
    print("  Hybrid Search Quality Test")
    print("=" * 72)

    # Check index status
    chroma_count = chroma.count()
    bm25_count = bm25_index.size
    print(f"\n  ChromaDB documents: {chroma_count}")
    print(f"  BM25 documents:    {bm25_count}")

    if chroma_count == 0:
        print("\n  ⚠ ChromaDB is empty. Run reindex first:")
        print("    curl -X POST http://localhost:8001/api/wiki/reindex")
        return

    if bm25_count == 0:
        print("\n  BM25 index is empty — building from ChromaDB...")
        # Bootstrap BM25 from ChromaDB
        result = chroma._collection.get(limit=chroma_count + 100, include=["documents", "metadatas"])
        if result and result.get("ids"):
            docs = []
            for doc_id, content, meta in zip(result["ids"], result["documents"], result["metadatas"]):
                docs.append(BM25Document(
                    id=doc_id,
                    file_path=meta.get("file_path", ""),
                    heading=meta.get("heading", ""),
                    content=content,
                    tokens=tokenize(content),
                ))
            bm25_index.add_documents(docs)
            print(f"  BM25 bootstrapped: {bm25_index.size} documents")

    test_queries = [
        "출장 경비 규정",
        "DG320 에러",
        "캐시 장애 대응",
        "신규입사자 온보딩",
        "재고관리 프로세스",
        "김태헌",
    ]

    for query in test_queries:
        print(f"\n--- Query: {query}")

        # Vector only
        t0 = time.perf_counter()
        vector_results = chroma.query(query_text=query, n_results=5)
        vector_ms = (time.perf_counter() - t0) * 1000

        # BM25 only
        t0 = time.perf_counter()
        bm25_results = bm25_index.search(query, n_results=5)
        bm25_ms = (time.perf_counter() - t0) * 1000

        # Hybrid
        t0 = time.perf_counter()
        hybrid_results = reciprocal_rank_fusion(vector_results, bm25_results, n_results=5)
        hybrid_ms = (time.perf_counter() - t0) * 1000

        # Print vector results
        v_docs = vector_results["documents"][0] if vector_results["documents"][0] else []
        v_metas = vector_results["metadatas"][0] if vector_results["metadatas"][0] else []
        v_dists = vector_results["distances"][0] if vector_results["distances"][0] else []
        print(f"  Vector ({vector_ms:.1f}ms):")
        for i, (meta, dist) in enumerate(zip(v_metas[:3], v_dists[:3])):
            rel = max(0, 1 - dist)
            print(f"    {i+1}. {meta.get('file_path', '?'):40s} rel={rel:.0%}")

        # Print BM25 results
        print(f"  BM25 ({bm25_ms:.1f}ms):")
        for i, (doc, score) in enumerate(bm25_results[:3]):
            print(f"    {i+1}. {doc.file_path:40s} score={score:.2f}")

        # Print hybrid results
        h_metas = hybrid_results["metadatas"][0] if hybrid_results["metadatas"][0] else []
        h_dists = hybrid_results["distances"][0] if hybrid_results["distances"][0] else []
        print(f"  Hybrid ({hybrid_ms:.1f}ms):")
        for i, (meta, dist) in enumerate(zip(h_metas[:3], h_dists[:3])):
            rel = max(0, 1 - dist)
            print(f"    {i+1}. {meta.get('file_path', '?'):40s} rel={rel:.0%}")

    print(f"\n{'=' * 72}")
    print("  Done.")


if __name__ == "__main__":
    asyncio.run(main())
