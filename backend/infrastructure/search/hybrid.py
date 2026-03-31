"""Hybrid search: merge vector (ChromaDB) + BM25 results via Reciprocal Rank Fusion."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

RRF_K = 60  # Standard RRF constant


@dataclass
class HybridResult:
    id: str
    file_path: str
    heading: str
    content: str
    metadata: dict
    vector_distance: float  # lower = more similar (cosine distance)
    bm25_score: float
    rrf_score: float


def reciprocal_rank_fusion(
    vector_results: dict,
    bm25_results: list[tuple],  # list of (BM25Document, score)
    n_results: int = 8,
    vector_weight: float = 1.0,
    bm25_weight: float = 1.0,
) -> dict:
    """Merge vector and BM25 results using Reciprocal Rank Fusion (RRF).

    Returns a dict matching ChromaDB query format:
        {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    RRF score = sum( weight / (k + rank) ) across both result sets.
    """
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}  # id -> {content, metadata, distance, bm25}

    # Process vector results
    if vector_results and vector_results.get("ids") and vector_results["ids"][0]:
        ids = vector_results["ids"][0]
        docs = vector_results["documents"][0]
        metas = vector_results["metadatas"][0]
        dists = vector_results["distances"][0]

        for rank, (doc_id, doc, meta, dist) in enumerate(zip(ids, docs, metas, dists)):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + vector_weight / (RRF_K + rank + 1)
            doc_map[doc_id] = {
                "content": doc,
                "metadata": meta,
                "distance": dist,
                "bm25_score": 0.0,
            }

    # Process BM25 results
    for rank, (bm25_doc, score) in enumerate(bm25_results):
        doc_id = bm25_doc.id
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + bm25_weight / (RRF_K + rank + 1)
        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "content": bm25_doc.content,
                "metadata": {"file_path": bm25_doc.file_path, "heading": bm25_doc.heading},
                "distance": 0.8,  # default distance for BM25-only results
                "bm25_score": score,
            }
        else:
            doc_map[doc_id]["bm25_score"] = score

    # Sort by RRF score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:n_results]

    # Convert back to ChromaDB format
    result_ids = []
    result_docs = []
    result_metas = []
    result_dists = []

    for doc_id in sorted_ids:
        info = doc_map[doc_id]
        result_ids.append(doc_id)
        result_docs.append(info["content"])
        result_metas.append(info["metadata"])
        # Convert RRF score to distance-like metric (lower = better)
        # Invert RRF score to maintain distance semantics
        rrf = rrf_scores[doc_id]
        max_rrf = max(rrf_scores.values()) if rrf_scores else 1
        normalized_dist = info["distance"] * (1 - 0.3 * (rrf / max_rrf)) if max_rrf > 0 else info["distance"]
        result_dists.append(normalized_dist)

    logger.debug(
        f"Hybrid search: {len(vector_results.get('ids', [[]])[0]) if vector_results.get('ids') else 0} vector + "
        f"{len(bm25_results)} BM25 → {len(result_ids)} merged"
    )

    return {
        "ids": [result_ids],
        "documents": [result_docs],
        "metadatas": [result_metas],
        "distances": [result_dists],
    }
