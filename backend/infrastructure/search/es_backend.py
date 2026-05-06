"""Elasticsearch-backed FullTextSearch — enterprise profile.

Uses elasticsearch-py 8.x sync client. Korean text uses the nori analyzer
(requires the analysis-nori plugin installed in the cluster). For dev/test,
the index is created with default standard analyzer if nori unavailable.

Index naming: ontong-wiki-chunks. Alias-swap migration handled by
cmd_fulltext_export (Phase 6 Task 6-5).
"""
from __future__ import annotations

import logging
from typing import Any
from .fulltext_protocol import FullTextSearch, SearchHit

logger = logging.getLogger(__name__)

INDEX_ALIAS = "ontong-wiki-chunks"  # alias the app reads from
INDEX_PREFIX = "ontong-wiki-chunks-"  # actual index names: prefix + timestamp

NORI_ANALYZER_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "korean_default": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase", "nori_part_of_speech"],
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "file_path": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "heading": {"type": "text", "analyzer": "korean_default"},
            "content": {"type": "text", "analyzer": "korean_default"},
            "tags": {"type": "keyword"},
            "domain": {"type": "keyword"},
            "process": {"type": "keyword"},
            "mtime_epoch": {"type": "long"},
        }
    },
}

# Fallback if nori plugin not installed (dev/test)
STANDARD_MAPPING = {
    "mappings": NORI_ANALYZER_MAPPING["mappings"],
}


def _build_client(url: str):
    """Factory — monkey-patchable in tests."""
    from elasticsearch import Elasticsearch
    return Elasticsearch(url, request_timeout=10)


class ESSearchBackend(FullTextSearch):
    def __init__(self, es_url: str, *, use_nori: bool = True) -> None:
        self._es = _build_client(es_url)
        self._use_nori = use_nori
        self._ensure_index()

    def _ensure_index(self) -> None:
        """Create the alias if missing, pointing to a fresh index."""
        if not self._es.indices.exists_alias(name=INDEX_ALIAS):
            # Create initial index
            import time
            initial_name = f"{INDEX_PREFIX}{int(time.time())}"
            mapping = NORI_ANALYZER_MAPPING if self._use_nori else STANDARD_MAPPING
            try:
                self._es.indices.create(index=initial_name, body=mapping)
            except Exception as e:
                # Possibly nori not installed — fallback to standard
                logger.warning(
                    f"Failed to create index with nori, falling back to standard: {e}"
                )
                self._es.indices.create(index=initial_name, body=STANDARD_MAPPING)
            self._es.indices.put_alias(index=initial_name, name=INDEX_ALIAS)
            logger.info(f"Created index {initial_name} aliased to {INDEX_ALIAS}")

    def add_documents(self, docs: list) -> int:
        """Bulk index via elasticsearch helpers."""
        from elasticsearch.helpers import bulk
        actions = []
        for d in docs:
            # d is BM25Document or dict-like; extract fields
            actions.append({
                "_index": INDEX_ALIAS,
                "_id": getattr(d, "id", None) or d.get("id"),
                "_source": {
                    "file_path": getattr(d, "file_path", None) or d.get("file_path"),
                    "chunk_id": getattr(d, "id", None) or d.get("id"),
                    "heading": getattr(d, "heading", None) or d.get("heading", ""),
                    "content": getattr(d, "content", None) or d.get("content", ""),
                    "tags": (
                        d.get("tags", []) if isinstance(d, dict) else getattr(d, "tags", [])
                    ),
                    "domain": (
                        d.get("domain", "") if isinstance(d, dict) else getattr(d, "domain", "")
                    ),
                    "process": (
                        d.get("process", "") if isinstance(d, dict) else getattr(d, "process", "")
                    ),
                    "mtime_epoch": (
                        d.get("mtime_epoch", 0)
                        if isinstance(d, dict)
                        else getattr(d, "mtime_epoch", 0)
                    ),
                },
            })
        success, errors = bulk(self._es, actions, raise_on_error=False)
        if errors:
            logger.warning(
                f"ES bulk had {len(errors) if isinstance(errors, list) else errors} errors"
            )
        return success

    def remove_by_file(self, file_path: str) -> int:
        """Delete all chunks where file_path matches."""
        result = self._es.delete_by_query(
            index=INDEX_ALIAS,
            body={"query": {"term": {"file_path": file_path}}},
        )
        deleted = result.get("deleted", 0)
        logger.info(f"ES removed {deleted} chunks for {file_path}")
        return deleted

    def search(
        self, query: str, limit: int = 10, *, file_predicate=None
    ) -> list[SearchHit]:
        """BM25-style search via ES match query."""
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["heading^2", "content"],
                    "type": "best_fields",
                }
            },
            # Over-fetch if filtering client-side
            "size": limit * 5 if file_predicate else limit,
        }
        result = self._es.search(index=INDEX_ALIAS, body=body)
        hits = []
        for hit in result["hits"]["hits"]:
            src = hit["_source"]
            fp = src.get("file_path", "")
            if file_predicate and not file_predicate(fp):
                continue
            hits.append(SearchHit(
                file_path=fp,
                chunk_id=src.get("chunk_id", hit["_id"]),
                heading=src.get("heading", ""),
                content=src.get("content", ""),
                score=hit["_score"],
            ))
            if len(hits) >= limit:
                break
        return hits

    def clear(self) -> None:
        try:
            self._es.delete_by_query(
                index=INDEX_ALIAS,
                body={"query": {"match_all": {}}},
            )
        except Exception as e:
            logger.warning(f"ES clear failed: {e}")

    @property
    def size(self) -> int:
        try:
            r = self._es.count(index=INDEX_ALIAS)
            return int(r.get("count", 0))
        except Exception:
            return 0

    def alias_swap(self, new_index_name: str) -> None:
        """Atomically swap the alias to point to a new index, removing old.

        Used by cmd_fulltext_export to swap-in a freshly built index.
        """
        actions = []
        # Remove from all current targets
        try:
            current = self._es.indices.get_alias(name=INDEX_ALIAS)
            for old_name in current.keys():
                actions.append({"remove": {"index": old_name, "alias": INDEX_ALIAS}})
        except Exception:
            pass
        actions.append({"add": {"index": new_index_name, "alias": INDEX_ALIAS}})
        self._es.indices.update_aliases(body={"actions": actions})
        logger.info(f"Alias {INDEX_ALIAS} swapped to {new_index_name}")
