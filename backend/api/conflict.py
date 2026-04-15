"""Conflict detection API — duplicate documents, deprecation, and full scan."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel

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


@router.get("/grouped")
async def get_grouped_duplicates(
    threshold: float = Query(default=SIMILARITY_THRESHOLD, ge=0.5, le=1.0),
    filter: str = Query(default="unresolved", pattern="^(unresolved|resolved|all)$"),
):
    """Return conflicts grouped by file: 'A conflicts with [B, C]'."""
    svc = _conflict()
    return svc.get_grouped_pairs(filter_mode=filter, threshold=threshold)


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


@router.post("/undeprecate")
async def undeprecate_document(
    path: str = Query(..., description="File path to restore from deprecated"),
):
    """Restore a deprecated document: set status to 'draft', clear lineage links."""
    svc = _svc()
    conflict_svc = _conflict()
    wiki_file = await svc.get_file(path)
    if not wiki_file:
        return {"error": f"File not found: {path}"}

    if wiki_file.metadata.status != "deprecated":
        return {"error": f"File is not deprecated: {path} (status={wiki_file.metadata.status})"}

    # Remember counterpart before clearing
    counterpart_path = wiki_file.metadata.superseded_by

    # Restore this document — use prev_status if available, else draft
    restored_status = wiki_file.metadata.prev_status or "draft"
    wiki_file.metadata.status = restored_status
    wiki_file.metadata.prev_status = ""
    wiki_file.metadata.superseded_by = ""
    full_content = _serialize_frontmatter(wiki_file.metadata, wiki_file.content)
    saved = await svc.save_file(path, full_content)
    await svc.indexer.index_file(saved, force=True)
    conflict_svc.update_metadata(path, {
        "status": restored_status,
        "superseded_by": "",
        "supersedes": getattr(wiki_file.metadata, "supersedes", ""),
    })

    # Clear counterpart's supersedes reference
    if counterpart_path:
        newer = await svc.get_file(counterpart_path)
        if newer and newer.metadata.supersedes == path:
            newer.metadata.supersedes = ""
            newer_content = _serialize_frontmatter(newer.metadata, newer.content)
            saved_newer = await svc.save_file(counterpart_path, newer_content)
            await svc.indexer.index_file(saved_newer, force=True)
            conflict_svc.update_metadata(counterpart_path, {
                "status": getattr(newer.metadata, "status", ""),
                "superseded_by": getattr(newer.metadata, "superseded_by", ""),
                "supersedes": "",
            })

    return {"status": "ok", "path": path, "new_status": restored_status}


# ── Typed conflict endpoints ─────────────────────────────────────────


class ResolveRequest(BaseModel):
    file_a: str
    file_b: str
    action: str  # "merge" | "scope_clarify" | "version_chain" | "dismiss"
    resolved_by: str = ""


@router.get("/typed")
async def get_typed_conflicts(
    filter: str = Query(default="unresolved", pattern="^(unresolved|resolved|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Return semantically analyzed conflict pairs with pagination."""
    svc = _conflict()
    all_pairs = svc.get_typed_pairs(filter_mode=filter)
    total = len(all_pairs)
    items = all_pairs[offset:offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/resolve")
async def resolve_conflict(req: ResolveRequest):
    """Resolve a conflict pair with a specific action.

    Actions:
    - dismiss: mark as false positive
    - version_chain: set supersedes/superseded_by lineage
    - scope_clarify: add mutual related links
    - merge: placeholder (future LLM merge)
    """
    svc = _conflict()
    wiki = _svc()

    if req.action == "dismiss":
        ok = svc.resolve_pair(req.file_a, req.file_b, req.resolved_by, "dismiss")
        if not ok:
            return {"error": "Conflict pair not found"}
        return {"status": "ok", "action": "dismiss"}

    elif req.action == "version_chain":
        # Deprecate older doc (file_a) in favor of newer (file_b)
        wiki_file_a = await wiki.get_file(req.file_a)
        if not wiki_file_a:
            return {"error": f"File not found: {req.file_a}"}

        wiki_file_a.metadata.status = "deprecated"
        wiki_file_a.metadata.superseded_by = req.file_b
        full_a = _serialize_frontmatter(wiki_file_a.metadata, wiki_file_a.content)
        saved_a = await wiki.save_file(req.file_a, full_a)
        await wiki.indexer.index_file(saved_a, force=True)

        # Update newer doc to reference the old one
        wiki_file_b = await wiki.get_file(req.file_b)
        if wiki_file_b:
            wiki_file_b.metadata.supersedes = req.file_a
            full_b = _serialize_frontmatter(wiki_file_b.metadata, wiki_file_b.content)
            saved_b = await wiki.save_file(req.file_b, full_b)
            await wiki.indexer.index_file(saved_b, force=True)

        svc.resolve_pair(req.file_a, req.file_b, req.resolved_by, "version_chain")
        return {"status": "ok", "action": "version_chain", "deprecated": req.file_a, "newer": req.file_b}

    elif req.action == "scope_clarify":
        # Add mutual related links
        for src, dst in [(req.file_a, req.file_b), (req.file_b, req.file_a)]:
            wiki_file = await wiki.get_file(src)
            if wiki_file and dst not in wiki_file.metadata.related:
                wiki_file.metadata.related.append(dst)
                full = _serialize_frontmatter(wiki_file.metadata, wiki_file.content)
                saved = await wiki.save_file(src, full)
                await wiki.indexer.index_file(saved, force=True)

        svc.resolve_pair(req.file_a, req.file_b, req.resolved_by, "scope_clarify")
        return {"status": "ok", "action": "scope_clarify"}

    elif req.action == "merge":
        # For now, just mark as resolved with merge action
        # Future: LLM merge draft → approval flow
        svc.resolve_pair(req.file_a, req.file_b, req.resolved_by, "merge")
        return {"status": "ok", "action": "merge", "note": "Merge draft not yet implemented"}

    return {"error": f"Unknown action: {req.action}"}


@router.post("/analyze-pair")
async def analyze_pair(
    file_a: str = Query(...),
    file_b: str = Query(...),
):
    """Trigger LLM semantic analysis for a specific conflict pair."""
    svc = _conflict()
    from backend.application.agent.skills.conflict_check import ConflictCheckSkill

    content_a = svc._load_doc_content(file_a)
    content_b = svc._load_doc_content(file_b)
    if not content_a or not content_b:
        return {"error": "Could not load document content"}

    # Get stored metadata
    stored = svc.store.get_all_pairs()
    meta_a, meta_b = {}, {}
    for sc in stored:
        if (sc.file_a == file_a and sc.file_b == file_b) or (sc.file_a == file_b and sc.file_b == file_a):
            meta_a, meta_b = sc.meta_a, sc.meta_b
            break

    result = await ConflictCheckSkill.analyze_pair(
        file_a, content_a, meta_a,
        file_b, content_b, meta_b,
    )
    if not result:
        return {"error": "Analysis failed"}

    svc.update_analysis(file_a, file_b, result)
    return {"status": "ok", "analysis": result}
