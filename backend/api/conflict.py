"""Conflict detection API — duplicate documents, deprecation, and full scan."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query

from backend.application.conflict.conflict_service import (
    ConflictDetectionService,
    DuplicatePair,
    SIMILARITY_THRESHOLD,
)
from backend.application.wiki.wiki_service import WikiService
from backend.core.auth import get_current_user
from backend.infrastructure.storage.local_fs import _serialize_frontmatter
from backend.infrastructure.vectordb.chroma import chroma
from backend.infrastructure.events.event_bus import event_bus

router = APIRouter(
    prefix="/api/conflict",
    tags=["conflict"],
    dependencies=[Depends(get_current_user)],
)

_wiki_service: WikiService | None = None
_conflict_svc: ConflictDetectionService | None = None


def init(wiki_service: WikiService, conflict_svc: ConflictDetectionService) -> None:
    global _wiki_service, _conflict_svc
    _wiki_service = wiki_service
    _conflict_svc = conflict_svc


def _svc() -> WikiService:
    if _wiki_service is None:
        raise RuntimeError("WikiService not initialized")
    return _wiki_service


def _conflict() -> ConflictDetectionService:
    if _conflict_svc is None:
        raise RuntimeError("ConflictDetectionService not initialized")
    return _conflict_svc


@router.get("/duplicates", response_model=list[DuplicatePair])
async def get_duplicates(
    threshold: float = Query(default=SIMILARITY_THRESHOLD, ge=0.5, le=1.0),
    filter: str = Query(default="unresolved", pattern="^(unresolved|resolved|all)$"),
):
    """Read conflict pairs from store (instant, no computation)."""
    svc = _conflict()
    return svc.get_pairs(filter_mode=filter, threshold=threshold)


@router.post("/full-scan")
async def trigger_full_scan(
    threshold: float = Query(default=SIMILARITY_THRESHOLD, ge=0.5, le=1.0),
):
    """Trigger a background full scan to populate the conflict store."""
    svc = _conflict()
    state = svc.get_scan_state()
    if state.get("running"):
        return {"status": "already_running", "progress": state["progress"], "total": state["total"]}

    async def _run_scan():
        def on_progress(current: int, total: int):
            event_bus.publish("conflict_scan", {"progress": current, "total": total})

        await asyncio.to_thread(svc.full_scan, threshold, on_progress)
        event_bus.publish("conflict_scan", {"progress": -1, "total": -1, "done": True})

    asyncio.create_task(_run_scan())
    return {"status": "started"}


@router.get("/scan-status")
async def scan_status():
    """Return current full scan progress."""
    svc = _conflict()
    return svc.get_scan_state()


@router.post("/deprecate")
async def deprecate_document(
    path: str = Query(..., description="File path to deprecate"),
    superseded_by: str = Query(default="", description="Path of the newer document"),
):
    """Set a document's status to 'deprecated' and optionally set lineage."""
    svc = _svc()
    conflict_svc = _conflict()
    wiki_file = await svc.get_file(path)
    if not wiki_file:
        return {"error": f"File not found: {path}"}

    wiki_file.metadata.status = "deprecated"
    if superseded_by:
        wiki_file.metadata.superseded_by = superseded_by
    full_content = _serialize_frontmatter(wiki_file.metadata, wiki_file.content)
    saved = await svc.save_file(path, full_content)
    # Force reindex to ensure ChromaDB metadata is in sync
    await svc.indexer.index_file(saved, force=True)

    # Update conflict store metadata so resolved status reflects immediately
    conflict_svc.update_metadata(path, {
        "status": "deprecated",
        "superseded_by": superseded_by,
        "supersedes": getattr(wiki_file.metadata, "supersedes", ""),
    })

    # Also update the newer document to reference this one
    if superseded_by:
        newer = await svc.get_file(superseded_by)
        if newer:
            newer.metadata.supersedes = path
            newer_content = _serialize_frontmatter(newer.metadata, newer.content)
            saved_newer = await svc.save_file(superseded_by, newer_content)
            await svc.indexer.index_file(saved_newer, force=True)
            conflict_svc.update_metadata(superseded_by, {
                "status": getattr(newer.metadata, "status", ""),
                "superseded_by": getattr(newer.metadata, "superseded_by", ""),
                "supersedes": path,
            })

    return {"status": "ok", "path": path, "new_status": "deprecated", "superseded_by": superseded_by}
