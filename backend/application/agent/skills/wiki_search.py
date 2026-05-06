"""WikiSearchSkill — hybrid vector + BM25 search with RRF, filtering, reranking."""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import settings
from backend.application.agent.skill import SkillResult
from backend.application.agent.filter_extractor import extract_metadata_filter, extract_path_filter
from backend.application.agent.filter_compiler import (
    compile_to_chroma_where,
    compile_to_bm25_predicate,
)
from backend.infrastructure.search.bm25 import bm25_index
from backend.infrastructure.search.hybrid import reciprocal_rank_fusion
from backend.infrastructure.search.reranker import rerank
from backend.infrastructure.cache.query_cache import query_cache
from backend.core.auth.acl_store import acl_store
from backend.core.auth.scope import build_scope_where_clause

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
        filters: dict | None = None,
        exclude_deprecated: bool = True,
        user_roles: list[str] | None = None,
        path_preference: str | None = None,
        user_scope: list[str] | None = None,
    ) -> SkillResult:
        chroma = ctx.chroma

        # FilterSpec (structured or DSL) → Chroma where + BM25 predicate
        spec_where = compile_to_chroma_where(filters)
        spec_bm25_pred = compile_to_bm25_predicate(filters)

        # Auto-extract metadata filter from query
        base_filter = metadata_filter or extract_metadata_filter(query)

        # Merge explicit FilterSpec on top of auto-extracted/LLM filter
        if spec_where:
            base_filter = _merge_where_filters(base_filter, spec_where)

        # L2: Path filter — explicit preference (from L3 disambiguation) or auto-extracted
        path_filter = None
        if path_preference:
            path_filter = {"path_depth_1": path_preference}
        else:
            path_filter = extract_path_filter(query)
        if path_filter:
            base_filter = _merge_where_filters(base_filter, path_filter)

        deprecated_filter = {"status": {"$ne": "deprecated"}} if exclude_deprecated else None
        effective_filter = _merge_where_filters(base_filter, deprecated_filter)

        # Add access_read scope filter if user_scope is provided
        resolved_scope = user_scope or getattr(ctx, "user_scope", None)
        if resolved_scope:
            scope_filter = build_scope_where_clause(resolved_scope)
            if scope_filter:
                effective_filter = _merge_where_filters(effective_filter, scope_filter)

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

            # BM25 keyword search (with metadata post-filter when FilterSpec present)
            bm25_filter_fn = None
            meta_index_for_bm25 = getattr(ctx, "meta_index", None)
            if spec_bm25_pred and meta_index_for_bm25:
                from backend.application.wiki.wiki_indexer import _extract_path_depths

                def bm25_filter_fn(bm25_doc):  # noqa: E306
                    entry = dict(meta_index_for_bm25.get_file_entry(bm25_doc.file_path) or {})
                    entry.update(_extract_path_depths(bm25_doc.file_path))
                    return spec_bm25_pred(entry)
            bm25_results = bm25_index.search(
                query, n_results=n_results, filter_predicate=bm25_filter_fn
            )

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
        # BM25-only results lack status metadata; look up from MetadataIndex
        meta_index = getattr(ctx, "meta_index", None)
        deprecated_paths: list[str] = []
        if documents and exclude_deprecated:
            filtered = []
            for doc, meta, dist in zip(documents, metadatas, distances):
                status = meta.get("status", "")
                if not status and meta_index:
                    fp = meta.get("path") or meta.get("file_path", "")
                    entry = meta_index.get_file_entry(fp) if fp else None
                    if entry:
                        status = entry.get("status", "")
                        meta["status"] = status
                if status == "deprecated":
                    deprecated_paths.append(meta.get("path", meta.get("file_path", "unknown")))
                else:
                    filtered.append((doc, meta, dist))
            if filtered:
                documents, metadatas, distances = map(list, zip(*filtered))
            else:
                documents, metadatas, distances = [], [], []

        # ACL filter
        user = getattr(ctx, "user", None)
        if documents and user:
            acl_filtered = [
                (doc, meta, dist)
                for doc, meta, dist in zip(documents, metadatas, distances)
                if acl_store.check_permission(meta.get("path", meta.get("file_path", "")), user, "read")
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

        feedback = ""
        if deprecated_paths:
            unique_paths = list(dict.fromkeys(deprecated_paths))  # dedupe, preserve order
            logger.info(f"Excluded deprecated docs: {unique_paths}")
            if len(unique_paths) <= 3:
                feedback = f"폐기된 문서 {len(unique_paths)}건 제외: {', '.join(p.rsplit('/', 1)[-1] for p in unique_paths)}"
            else:
                shown = ', '.join(p.rsplit('/', 1)[-1] for p in unique_paths[:2])
                feedback = f"폐기된 문서 {len(unique_paths)}건 제외: {shown} 외 {len(unique_paths) - 2}건"

        # 0-result fallback: if no active documents found, retry including deprecated
        if not documents and exclude_deprecated:
            logger.info("No active documents found, retrying with deprecated included")
            fallback = await self.execute(
                ctx, query=query, n_results=n_results,
                metadata_filter=metadata_filter,
                filters=filters,
                exclude_deprecated=False,
                user_roles=user_roles,
                path_preference=path_preference,
                user_scope=user_scope,
            )
            if fallback.data.get("documents"):
                fallback.feedback = "활성 문서에서 결과를 찾지 못했습니다. 폐기된 문서에서 관련 내용을 찾았습니다."
                return fallback

        return SkillResult(
            data={
                "documents": documents,
                "metadatas": metadatas,
                "distances": distances,
                "search_mode": search_mode,
            },
            feedback=feedback,
        )

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "검색 쿼리 (키워드/자연어)"},
                        "n_results": {"type": "integer", "description": "검색 결과 수", "default": 8},
                        "filters": {
                            "type": "object",
                            "description": (
                                "메타데이터 검색 조건. 사용자가 특정 폴더/태그/작성자/기간/타입/상태를 "
                                "명시하거나 문맥상 한정할 필요가 있을 때 설정. 구조화 필드 또는 boolean DSL 사용."
                            ),
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "경로 글롭, 예: 'wiki/ERP/**'",
                                },
                                "folders": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "폴더 목록 (중첩 가능: 'ERP/마스터데이터'). 여러 개는 OR.",
                                },
                                "tags": {
                                    "type": "object",
                                    "description": "태그 필터",
                                    "properties": {
                                        "include": {"type": "array", "items": {"type": "string"}},
                                        "exclude": {"type": "array", "items": {"type": "string"}},
                                        "mode": {"type": "string", "enum": ["AND", "OR"], "default": "OR"},
                                    },
                                },
                                "authors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "작성자 멘션(@이름) 목록. OR 결합.",
                                },
                                "types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "문서 유형 (예: sop, spec, incident). OR 결합.",
                                },
                                "mtime_from": {
                                    "type": "string",
                                    "description": "수정일 시작 (ISO 8601, 예: 2026-01-01)",
                                },
                                "mtime_to": {
                                    "type": "string",
                                    "description": "수정일 끝 (ISO 8601)",
                                },
                                "statuses": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "상태 목록 (active, review, deprecated 등). OR 결합.",
                                },
                                "acl": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "ACL 스코프 (public, team:mes 등). OR 결합.",
                                },
                                "boolean": {
                                    "type": "string",
                                    "description": (
                                        "Boolean DSL 표현. 설정 시 위 구조화 필드보다 우선. "
                                        "예: '(tag:재고 OR tag:주문) AND author:@동해 AND !status:draft'"
                                    ),
                                },
                            },
                        },
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
