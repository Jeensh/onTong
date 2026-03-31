"""Cross-encoder reranker for search result refinement.

Uses LLM-based relevance scoring to rerank search results.
Lightweight approach: uses the existing LiteLLM model instead of a dedicated cross-encoder.
"""

from __future__ import annotations

import logging
import time

import litellm

from backend.core.config import settings

logger = logging.getLogger(__name__)


async def rerank(
    query: str,
    documents: list[str],
    metadatas: list[dict],
    distances: list[float],
    top_k: int = 5,
    enabled: bool = True,
) -> tuple[list[str], list[dict], list[float]]:
    """Rerank search results using LLM-based relevance scoring.

    Returns reordered (documents, metadatas, distances) tuples.
    If reranking fails or is disabled, returns the original order.
    """
    if not enabled or len(documents) <= 1:
        return documents, metadatas, distances

    t0 = time.perf_counter()

    # Build candidate summaries for LLM
    candidates = []
    for i, (doc, meta) in enumerate(zip(documents, metadatas)):
        file_path = meta.get("file_path", "")
        heading = meta.get("heading", "")
        snippet = doc[:200].replace("\n", " ").strip()
        candidates.append(f"[{i}] {file_path} — {heading}: {snippet}")

    candidates_text = "\n".join(candidates)

    try:
        response = await litellm.acompletion(
            model=settings.litellm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a search result ranker. Given a query and search results, "
                        "return the indices of the most relevant results in order of relevance.\n"
                        "Output ONLY comma-separated indices (e.g., '2,0,4,1,3'). Nothing else."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nResults:\n{candidates_text}",
                },
            ],
            max_tokens=30,
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        # Parse indices
        indices = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part)
                if 0 <= idx < len(documents) and idx not in indices:
                    indices.append(idx)

        # Add any missing indices at the end
        for i in range(len(documents)):
            if i not in indices:
                indices.append(i)

        # Limit to top_k
        indices = indices[:top_k]

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(f"Reranked {len(documents)} → {len(indices)} results in {elapsed:.0f}ms")

        reranked_docs = [documents[i] for i in indices]
        reranked_metas = [metadatas[i] for i in indices]
        reranked_dists = [distances[i] for i in indices]

        return reranked_docs, reranked_metas, reranked_dists

    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        logger.warning(f"Reranking failed ({elapsed:.0f}ms): {e}, using original order")
        return documents[:top_k], metadatas[:top_k], distances[:top_k]
