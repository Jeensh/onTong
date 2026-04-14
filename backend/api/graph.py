"""Knowledge Graph API — relationship queries and statistics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.core.auth import get_current_user
from backend.core.auth.permission import require_read
from backend.core.schemas import GraphResult, GraphStats
from backend.application.graph.graph_store import GraphStore

router = APIRouter(prefix="/api/graph", tags=["graph"], dependencies=[Depends(get_current_user)])

_graph_store: GraphStore | None = None
_graph_builder = None  # GraphBuilder


def init(graph_store: GraphStore, graph_builder=None) -> None:
    global _graph_store, _graph_builder
    _graph_store = graph_store
    _graph_builder = graph_builder


def _store() -> GraphStore:
    if _graph_store is None:
        raise RuntimeError("GraphStore not initialized")
    return _graph_store


@router.get("/stats", response_model=GraphStats)
async def graph_stats(user=Depends(require_read)):
    """Return aggregate knowledge graph statistics."""
    return _store().stats()


@router.get("/{path:path}", response_model=GraphResult)
async def graph_query(path: str, depth: int = 1, rel_type: str = "", user=Depends(require_read)):
    """Query knowledge graph centered on a document.

    Args:
        path: document file path
        depth: BFS traversal depth (1 = direct neighbors only)
        rel_type: filter by relationship type (empty = all)
    """
    if depth < 1:
        depth = 1
    if depth > 3:
        depth = 3  # cap to prevent expensive traversals

    result = _store().get_graph(path, depth=depth)

    # Filter by rel_type if specified
    if rel_type:
        result.relationships = [r for r in result.relationships if r.rel_type == rel_type]

    return result
