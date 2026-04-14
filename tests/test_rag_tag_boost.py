"""B4: RAG tag-boost evaluation.

Compares hit@5 / MRR for vector search on eval queries with and without
the tag boost rerank from rag_agent._tag_boost_rerank. Uses the real
ChromaDB collection and tag_registry (requires ChromaDB + backend
services running — the test skips if chroma isn't reachable).

Result is written to tests/fixtures/rag_eval_baseline.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.application.agent.filter_extractor import extract_query_tags
from backend.application.agent.rag_agent import RAGAgent
from backend.infrastructure.vectordb.chroma import chroma

FIXTURES = Path(__file__).resolve().parent / "fixtures"
QUERIES_FILE = FIXTURES / "rag_eval_queries.json"
RESULT_FILE = FIXTURES / "rag_eval_baseline.json"

TOP_K = 5


def _ensure_connected() -> bool:
    if not chroma.is_connected:
        try:
            chroma.connect()
        except Exception:
            return False
    return chroma.is_connected


def _doc_path(meta: dict) -> str | None:
    if not meta:
        return None
    p = meta.get("file_path") or meta.get("path")
    if p and not p.startswith("wiki/"):
        p = f"wiki/{p}"
    return p


def _dedupe_by_path(
    documents: list, metadatas: list, distances: list
) -> tuple[list, list, list]:
    """Chroma returns chunk-level results; collapse to one entry per doc."""
    seen: set[str] = set()
    out_d, out_m, out_dist = [], [], []
    for doc, meta, dist in zip(documents, metadatas, distances):
        p = _doc_path(meta)
        if not p or p in seen:
            continue
        seen.add(p)
        out_d.append(doc)
        out_m.append(meta)
        out_dist.append(dist)
    return out_d, out_m, out_dist


def _rank_of_expected(paths: list[str], expected: list[str]) -> int | None:
    exp = set(expected)
    for i, p in enumerate(paths):
        if p in exp:
            return i + 1  # 1-indexed
    return None


def _evaluate(boost_weight: float) -> dict:
    data = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    queries = data["queries"]

    per_query = []
    hits = 0
    rr_sum = 0.0

    for item in queries:
        q = item["query"]
        expected = item["expected"]

        result = chroma.query_with_filter(q, n_results=TOP_K * 3)
        documents = result["documents"][0] if result["documents"] else []
        metadatas = result["metadatas"][0] if result["metadatas"] else []
        distances = result["distances"][0] if result["distances"] else []

        if boost_weight > 0 and documents:
            try:
                qtags = extract_query_tags(q, top_k=5)
            except Exception:
                qtags = []
            if qtags:
                documents, metadatas, distances = RAGAgent._tag_boost_rerank(
                    documents, metadatas, distances, qtags, weight=boost_weight
                )

        documents, metadatas, distances = _dedupe_by_path(
            documents, metadatas, distances
        )
        top_paths = [_doc_path(m) for m in metadatas[:TOP_K]]
        rank = _rank_of_expected(top_paths, expected)

        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank

        per_query.append(
            {
                "query": q,
                "expected": expected,
                "top5": top_paths,
                "rank": rank,
            }
        )

    n = len(queries)
    return {
        "boost_weight": boost_weight,
        "n_queries": n,
        "hit@5": round(hits / n, 3) if n else 0,
        "mrr": round(rr_sum / n, 3) if n else 0,
        "per_query": per_query,
    }


@pytest.mark.skipif(not _ensure_connected(), reason="ChromaDB not reachable")
def test_rag_tag_boost_eval():
    baseline = _evaluate(boost_weight=0.0)
    with_boost = _evaluate(boost_weight=0.05)

    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(
        json.dumps(
            {"baseline": baseline, "with_boost": with_boost},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"\nBaseline  : hit@5={baseline['hit@5']}  mrr={baseline['mrr']}"
    )
    print(
        f"With boost: hit@5={with_boost['hit@5']}  mrr={with_boost['mrr']}"
    )

    # Sanity: baseline should already be reasonable on these easy queries.
    assert baseline["hit@5"] >= 0.5, (
        f"baseline hit@5 too low: {baseline['hit@5']}"
    )
    # Boost should not regress more than 10%p vs baseline.
    assert with_boost["hit@5"] >= baseline["hit@5"] - 0.1, (
        f"boost regressed: {with_boost['hit@5']} vs {baseline['hit@5']}"
    )
