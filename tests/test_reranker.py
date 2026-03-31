"""Reranker A/B comparison test.

Compares search results with and without LLM reranking.

Usage:
    cd /path/to/onTong
    source venv/bin/activate
    python -m tests.test_reranker
"""

from __future__ import annotations

import asyncio
import time

from backend.infrastructure.vectordb.chroma import ChromaWrapper
from backend.infrastructure.search.reranker import rerank


async def main() -> None:
    chroma = ChromaWrapper()
    chroma.connect()

    print("=" * 72)
    print("  Reranker A/B Comparison Test")
    print("=" * 72)

    if chroma.count() == 0:
        print("\n  ⚠ ChromaDB is empty. Run reindex first:")
        print("    curl -X POST http://localhost:8001/api/wiki/reindex?force=true")
        return

    test_queries = [
        "출장 경비 규정",
        "캐시 장애 대응",
        "신규입사자 온보딩",
        "재고관리 프로세스",
    ]

    for query in test_queries:
        print(f"\n--- Query: {query}")

        # Get raw search results
        results = chroma.query(query_text=query, n_results=5)
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        if not docs:
            print("  No results found")
            continue

        # Without reranking
        print("  Without reranking:")
        for i, (meta, dist) in enumerate(zip(metas, dists)):
            rel = max(0, 1 - dist)
            print(f"    {i+1}. {meta.get('file_path', '?'):40s} rel={rel:.0%}")

        # With reranking
        t0 = time.perf_counter()
        r_docs, r_metas, r_dists = await rerank(
            query=query, documents=docs, metadatas=metas,
            distances=dists, top_k=5, enabled=True,
        )
        elapsed = (time.perf_counter() - t0) * 1000

        print(f"  With reranking ({elapsed:.0f}ms):")
        for i, (meta, dist) in enumerate(zip(r_metas, r_dists)):
            rel = max(0, 1 - dist)
            print(f"    {i+1}. {meta.get('file_path', '?'):40s} rel={rel:.0%}")

        # Check if order changed
        orig_paths = [m.get("file_path") for m in metas[:5]]
        reranked_paths = [m.get("file_path") for m in r_metas[:5]]
        changed = orig_paths != reranked_paths
        print(f"  Order changed: {'Yes' if changed else 'No'}")

    print(f"\n{'=' * 72}")
    print("  Done.")


if __name__ == "__main__":
    asyncio.run(main())
