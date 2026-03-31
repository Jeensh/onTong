"""Search API endpoints — server-side search with BM25 + vector hybrid."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from fastapi import APIRouter, Depends, Query

from backend.application.wiki.wiki_service import WikiService
from backend.application.wiki.wiki_search import WikiSearchService
from backend.core.schemas import (
    BacklinkMap, SearchIndexEntry, TagIndex,
    HybridSearchResult, GraphNode, GraphEdge, GraphData,
)
from backend.infrastructure.search.bm25 import bm25_index
from backend.infrastructure.search.hybrid import reciprocal_rank_fusion
from backend.infrastructure.vectordb.chroma import ChromaWrapper

from backend.core.auth import get_current_user

logger = logging.getLogger(__name__)

# ── In-memory TTL cache for heavy endpoints ──────────────────────────
_endpoint_cache: dict[str, tuple[object, float]] = {}
_ENDPOINT_CACHE_TTL = 60  # seconds


def _get_endpoint_cache(key: str):
    entry = _endpoint_cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > _ENDPOINT_CACHE_TTL:
        del _endpoint_cache[key]
        return None
    return result


def _set_endpoint_cache(key: str, value: object) -> None:
    _endpoint_cache[key] = (value, time.time())


def invalidate_endpoint_cache() -> None:
    """Called when files change to clear stale cache."""
    _endpoint_cache.clear()

router = APIRouter(prefix="/api/search", tags=["search"], dependencies=[Depends(get_current_user)])

_wiki_service: WikiService | None = None
_search_service: WikiSearchService | None = None
_chroma: ChromaWrapper | None = None


def init(wiki_service: WikiService, search_service: WikiSearchService, chroma: ChromaWrapper | None = None) -> None:
    global _wiki_service, _search_service, _chroma
    _wiki_service = wiki_service
    _search_service = search_service
    _chroma = chroma


def _wiki() -> WikiService:
    if _wiki_service is None:
        raise RuntimeError("WikiService not initialized")
    return _wiki_service


def _search() -> WikiSearchService:
    if _search_service is None:
        raise RuntimeError("WikiSearchService not initialized")
    return _search_service


@router.get("/index", response_model=list[SearchIndexEntry])
async def get_search_index(
    offset: int = Query(0, ge=0, description="Skip first N entries"),
    limit: int = Query(0, ge=0, description="Max entries (0=all)"),
):
    """Return search index for frontend MiniSearch. Supports pagination for large datasets."""
    files = await _wiki().get_all_files()
    entries = _search().build_search_index(files)
    if limit > 0:
        return entries[offset:offset + limit]
    return entries


@router.get("/backlinks", response_model=BacklinkMap)
async def get_backlinks():
    """Return forward and backward link maps."""
    cached = _get_endpoint_cache("backlinks")
    if cached:
        return cached
    files = await _wiki().get_all_files()
    result = _search().build_backlink_map(files)
    _set_endpoint_cache("backlinks", result)
    return result


@router.get("/tags", response_model=TagIndex)
async def get_tags():
    """Return tag → file paths index."""
    cached = _get_endpoint_cache("tags")
    if cached:
        return cached
    files = await _wiki().get_all_files()
    result = _search().build_tag_index(files)
    _set_endpoint_cache("tags", result)
    return result


@router.get("/quick", response_model=list[HybridSearchResult])
async def quick_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
):
    """Fast BM25-only keyword search (no vector search). Used for real-time search UI."""
    bm25_results = bm25_index.search(q, n_results=limit)
    if not bm25_results:
        return []

    results: list[HybridSearchResult] = []
    for doc, score in bm25_results:
        title = doc.heading if doc.heading else doc.file_path.split("/")[-1].replace(".md", "")
        snippet = (doc.content[:150] + "...") if len(doc.content) > 150 else doc.content
        results.append(HybridSearchResult(
            path=doc.file_path,
            title=title,
            snippet=snippet,
            score=round(score, 4),
            tags=[],
            status="",
        ))
    return results


@router.get("/resolve-link")
async def resolve_link(
    target: str = Query(..., min_length=1, description="Wiki link target (stem name)"),
):
    """Resolve a wiki-link target to a full file path."""
    normalized = target.lower().replace(".md", "")

    files = await _wiki().get_all_files()

    # Exact stem match
    for f in files:
        stem = f.path.split("/")[-1].replace(".md", "")
        if stem.lower() == normalized:
            return {"path": f.path}

    # Title match
    for f in files:
        if f.title.lower() == normalized:
            return {"path": f.path}

    # Partial stem match
    for f in files:
        stem = f.path.split("/")[-1].replace(".md", "")
        if normalized in stem.lower():
            return {"path": f.path}

    return {"path": None}


@router.get("/hybrid", response_model=list[HybridSearchResult])
async def hybrid_search(
    q: str = Query(..., min_length=1, description="Search query"),
    n: int = Query(10, ge=1, le=50, description="Number of results"),
):
    """User-facing hybrid search combining BM25 + vector similarity.
    Vector and BM25 searches run in parallel for lower latency."""

    async def _vector_search() -> dict:
        if not _chroma:
            return {}
        try:
            return await asyncio.to_thread(_chroma.query, q, n_results=n)
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return {}

    # Run vector (I/O bound) and BM25 (CPU bound) in parallel
    vector_task = asyncio.create_task(_vector_search())
    bm25_results = bm25_index.search(q, n_results=n)  # CPU-bound, fast (~5ms)
    vector_results = await vector_task

    # Merge via RRF
    if not vector_results and not bm25_results:
        return []

    merged = reciprocal_rank_fusion(vector_results or {}, bm25_results, n_results=n)

    # Build results
    results: list[HybridSearchResult] = []
    ids = merged.get("ids", [[]])[0]
    docs = merged.get("documents", [[]])[0]
    metas = merged.get("metadatas", [[]])[0]
    dists = merged.get("distances", [[]])[0]

    for doc_id, content, meta, dist in zip(ids, docs, metas, dists):
        file_path = meta.get("file_path", doc_id)
        heading = meta.get("heading", "")
        title = heading if heading else file_path.split("/")[-1].replace(".md", "")

        # Build snippet: first 150 chars of content
        snippet = (content[:150] + "...") if len(content) > 150 else content

        # Parse tags from pipe-delimited format
        raw_tags = meta.get("tags", "")
        tags = [t for t in raw_tags.strip("|").split("|") if t] if isinstance(raw_tags, str) and raw_tags else []

        results.append(HybridSearchResult(
            path=file_path,
            title=title,
            snippet=snippet,
            score=round(1.0 - dist, 4),  # Convert distance to relevance score
            tags=tags,
            status=meta.get("status", ""),
        ))

    return results


@router.get("/graph", response_model=GraphData)
async def get_graph_data(
    center_path: str = Query(..., description="Center document path for BFS"),
    include_similar: bool = Query(False, description="Include similarity-based edges"),
    similarity_threshold: float = Query(0.85, ge=0.5, le=1.0),
):
    """Return focused document graph centered on a specific file.

    Traverses ALL reachable nodes from center_path (no depth limit).
    Each node includes its BFS distance from center for visual encoding.
    """
    files = await _wiki().get_all_files()
    file_map = {f.path: f for f in files}

    if center_path not in file_map:
        return GraphData(nodes=[], edges=[])

    backlinks = _search().build_backlink_map(files)

    # Collect all edges
    edges: list[GraphEdge] = []
    edge_set: set[tuple[str, str, str]] = set()

    def add_edge(src: str, tgt: str, etype: str) -> None:
        key = (src, tgt, etype)
        if key not in edge_set and src in file_map and tgt in file_map:
            edge_set.add(key)
            edges.append(GraphEdge(source=src, target=tgt, type=etype))

    # 1. Wiki-links (from backlink map)
    for src, targets in backlinks.forward.items():
        for tgt in targets:
            add_edge(src, tgt, "wiki-link")

    # 2. Lineage (supersedes/superseded_by) + Related
    for f in files:
        meta = f.metadata
        if meta.supersedes and meta.supersedes in file_map:
            add_edge(meta.supersedes, f.path, "supersedes")
        if meta.superseded_by and meta.superseded_by in file_map:
            add_edge(f.path, meta.superseded_by, "supersedes")
        for rel in meta.related:
            if rel in file_map:
                add_edge(f.path, rel, "related")

    # 3. Similarity edges (from conflict store, instant)
    if include_similar:
        try:
            from backend.api.conflict import _conflict
            conflict_svc = _conflict()
            pairs = conflict_svc.get_pairs(
                filter_mode="all", threshold=similarity_threshold
            )
            for pair in pairs:
                add_edge(pair.file_a, pair.file_b, "similar")
        except Exception as e:
            logger.warning(f"Similarity edge retrieval failed: {e}")

    # BFS from center_path — no depth limit, track distance
    adj: dict[str, set[str]] = {}
    for edge in edges:
        adj.setdefault(edge.source, set()).add(edge.target)
        adj.setdefault(edge.target, set()).add(edge.source)

    node_depth: dict[str, int] = {center_path: 0}
    queue: deque[tuple[str, int]] = deque([(center_path, 0)])
    while queue:
        node, d = queue.popleft()
        for neighbor in adj.get(node, set()):
            if neighbor not in node_depth:
                node_depth[neighbor] = d + 1
                queue.append((neighbor, d + 1))

    # Filter edges and nodes to visited set
    edges = [e for e in edges if e.source in node_depth and e.target in node_depth]

    # Build nodes with depth
    nodes: list[GraphNode] = []
    for path, d in node_depth.items():
        f = file_map.get(path)
        if f:
            nodes.append(GraphNode(
                id=f.path,
                title=f.title,
                status=f.metadata.status,
                tags=f.metadata.tags,
                domain=f.metadata.domain,
                depth=d,
                node_type="skill" if f.path.startswith("_skills/") else "document",
            ))

    return GraphData(nodes=nodes, edges=edges)
