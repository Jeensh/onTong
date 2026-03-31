"""WikiSearchSkill — hybrid vector + BM25 search with RRF, filtering, reranking."""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import settings
from backend.application.agent.skill import SkillResult
from backend.application.agent.filter_extractor import extract_metadata_filter
from backend.infrastructure.search.bm25 import bm25_index
from backend.infrastructure.search.hybrid import reciprocal_rank_fusion
from backend.infrastructure.search.reranker import rerank
from backend.infrastructure.cache.query_cache import query_cache
from backend.core.auth.acl_store import acl_store

logger = logging.getLogger(__name__)


class WikiSearchSkill:
    name = "wiki_search"
    description = "Wiki 문서를 하이브리드 검색 (벡터 + 키워드)"

    async def execute(
        self,
        ctx: Any,
        *,
        query: str = "",
        n_results: int = 8,
        metadata_filter: dict | None = None,
        exclude_deprecated: bool = True,
        user_roles: list[str] | None = None,
    ) -> SkillResult:
        chroma = ctx.chroma
        roles = user_roles or getattr(ctx, "user_roles", ["admin"])

        # Auto-extract metadata filter from query
        base_filter = metadata_filter or extract_metadata_filter(query)
        deprecated_filter = {"status": {"$ne": "deprecated"}} if exclude_deprecated else None
        effective_filter = _merge_where_filters(base_filter, deprecated_filter)

        # Cache check
        cached = query_cache.get(query, effective_filter)
        if cached:
            results = cached
            search_mode = "캐시"
        else:
            # Vector search
            if effective_filter:
                vector_results = chroma.query_with_filter(
                    query_text=query, n_results=n_results, where=effective_filter
                )
            else:
                vector_results = chroma.query(query_text=query, n_results=n_results)

            # Fallback: if filtered search returns 0, retry without filter
            v_docs = vector_results.get("documents", [[]])[0]
            if effective_filter and not v_docs:
                logger.info("Filtered search returned 0 results, retrying without filter")
                vector_results = chroma.query(query_text=query, n_results=n_results)
                effective_filter = None

            # BM25 keyword search
            bm25_results = bm25_index.search(query, n_results=n_results)

            if bm25_results:
                results = reciprocal_rank_fusion(vector_results, bm25_results, n_results=n_results)
                search_mode = "하이브리드"
            else:
                results = vector_results
                search_mode = "벡터"

            query_cache.put(query, results, effective_filter)

        documents = results.get("documents", [[]])[0] or []
        metadatas = results.get("metadatas", [[]])[0] or []
        distances = results.get("distances", [[]])[0] or []

        # Post-RRF: remove deprecated docs that may have entered via BM25
        if documents and exclude_deprecated:
            filtered = [
                (doc, meta, dist)
                for doc, meta, dist in zip(documents, metadatas, distances)
                if meta.get("status") != "deprecated"
            ]
            if filtered:
                documents, metadatas, distances = map(list, zip(*filtered))
            else:
                documents, metadatas, distances = [], [], []

        # ACL filter
        if documents and roles:
            acl_filtered = [
                (doc, meta, dist)
                for doc, meta, dist in zip(documents, metadatas, distances)
                if acl_store.check_permission(meta.get("path", meta.get("file_path", "")), roles, "read")
            ]
            if acl_filtered:
                documents, metadatas, distances = map(list, zip(*acl_filtered))
            else:
                documents, metadatas, distances = [], [], []

        # Cross-encoder reranking (optional)
        if documents and settings.enable_reranker:
            documents, metadatas, distances = await rerank(
                query=query,
                documents=documents,
                metadatas=metadatas,
                distances=distances,
                top_k=min(n_results, len(documents)),
                enabled=settings.enable_reranker,
            )

        return SkillResult(data={
            "documents": documents,
            "metadatas": metadatas,
            "distances": distances,
            "search_mode": search_mode,
        })

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "검색 쿼리"},
                        "n_results": {"type": "integer", "description": "검색 결과 수", "default": 8},
                    },
                    "required": ["query"],
                },
            },
        }


def _merge_where_filters(filter_a: dict | None, filter_b: dict | None) -> dict | None:
    if not filter_a and not filter_b:
        return None
    if not filter_a:
        return filter_b
    if not filter_b:
        return filter_a
    return {"$and": [filter_a, filter_b]}
