"""Wiki REST API endpoints."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from backend.application.wiki.wiki_service import WikiService, index_status
from backend.application.trust.confidence_service import ConfidenceService
from backend.application.trust.scoring_config import SCORING
from backend.core.auth import User, get_current_user
from backend.core.auth.permission import require_read, require_write
from backend.core.schemas import WikiFile, WikiTreeNode

# Path traversal / injection patterns
_DANGEROUS_PATH_RE = re.compile(r"\.\.|//|\\|[\x00-\x1f]")
MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB


def _validate_path(path: str) -> None:
    """Reject paths with traversal patterns or control characters."""
    if _DANGEROUS_PATH_RE.search(path):
        raise HTTPException(status_code=400, detail=f"Invalid path: {path}")

router = APIRouter(prefix="/api/wiki", tags=["wiki"], dependencies=[Depends(get_current_user)])

# Injected at startup via main.py
_wiki_service: WikiService | None = None
_confidence_service: ConfidenceService | None = None
_digest_service = None  # DocumentDigestService, set via init()
_feedback_tracker = None  # FeedbackTracker, set via init()


def init(wiki_service: WikiService, confidence_service: ConfidenceService | None = None, digest_service=None, feedback_tracker=None) -> None:
    global _wiki_service, _confidence_service, _digest_service, _feedback_tracker
    _wiki_service = wiki_service
    _confidence_service = confidence_service
    _digest_service = digest_service
    _feedback_tracker = feedback_tracker


def _svc() -> WikiService:
    if _wiki_service is None:
        raise RuntimeError("WikiService not initialized")
    return _wiki_service


class SaveRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_content_size(cls, v: str) -> str:
        if len(v.encode("utf-8")) > MAX_CONTENT_SIZE:
            raise ValueError(f"Content exceeds maximum size of {MAX_CONTENT_SIZE} bytes")
        return v


class MoveRequest(BaseModel):
    new_path: str


@router.get("/tree", response_model=list[WikiTreeNode])
async def get_tree(request: Request, response: Response, depth: int = 1):
    """Get wiki file tree. depth=0 returns full tree, depth=1 returns top-level only.
    Supports ETag caching for large trees."""
    if depth == 1:
        # Optimized: scan only root directory (no full tree build)
        tree = await _svc().get_subtree("")
    else:
        tree = await _svc().get_tree()

    # ETag caching
    import json
    tree_json = json.dumps([n.model_dump() for n in tree], sort_keys=True)
    etag = hashlib.md5(tree_json.encode()).hexdigest()
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    if depth > 1:
        return _truncate_tree(tree, depth)
    return tree


def _truncate_tree(nodes: list[WikiTreeNode], max_depth: int, current: int = 1) -> list[WikiTreeNode]:
    """Truncate tree to max_depth, replacing deep children with empty lists."""
    result = []
    for node in nodes:
        if node.is_dir and current >= max_depth:
            result.append(WikiTreeNode(
                name=node.name, path=node.path, is_dir=True,
                children=[], has_children=bool(node.children),
            ))
        else:
            if node.is_dir and node.children:
                truncated_children = _truncate_tree(node.children, max_depth, current + 1)
                result.append(WikiTreeNode(
                    name=node.name, path=node.path, is_dir=True, children=truncated_children
                ))
            else:
                result.append(node)
    return result


@router.get("/tree/{path:path}", response_model=list[WikiTreeNode])
async def get_subtree(path: str, user: User = Depends(require_read)):
    """Get children of a specific folder (for lazy loading).
    Returns one level of children with has_children flag for subdirectories."""
    _validate_path(path)
    children = await _svc().get_subtree(path)
    if not children and not await _svc().storage.exists(path):
        raise HTTPException(status_code=404, detail=f"Folder not found: {path}")
    return children


@router.get("/search-path")
async def search_path(q: str = "", limit: int = 20):
    """Lazy path search for autocomplete (e.g., related docs picker).

    Uses lightweight list_file_paths() instead of building the full tree,
    which is O(n) scan vs O(n) recursive tree build with WikiTreeNode allocation.
    """
    paths = await _svc().storage.list_file_paths()

    if q:
        q_lower = q.lower()
        # Early termination: stop once we have enough matches
        matches: list[str] = []
        for p in paths:
            if q_lower in p.lower():
                matches.append(p)
                if len(matches) >= limit:
                    break
    else:
        matches = paths[:limit]
    return {"paths": matches}


@router.get("/file/{path:path}", response_model=WikiFile)
async def get_file(path: str, user: User = Depends(require_read)):
    """Read a wiki file by path."""
    _validate_path(path)
    wiki_file = await _svc().get_file(path)
    if wiki_file is None:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return wiki_file


@router.put("/file/{path:path}", response_model=WikiFile)
async def save_file(path: str, body: SaveRequest, user: User = Depends(require_write)):
    """Create or update a wiki file (with synchronous re-indexing)."""
    _validate_path(path)
    try:
        result = await _svc().save_file(path, body.content, user_name=user.name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Invalidate persona cache when a user edits their ontong.local.md
    if "_personas/@" in path and path.endswith("ontong.local.md"):
        try:
            from backend.application.agent.rag_agent import invalidate_persona_cache
            invalidate_persona_cache(user.name)
        except Exception:
            pass

    return result


@router.patch("/file/{path:path}")
async def move_file(path: str, body: MoveRequest):
    """Rename or move a wiki file."""
    result = await _svc().move_file(path, body.new_path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return {"old_path": path, "new_path": body.new_path}


@router.delete("/file/{path:path}")
async def delete_file(path: str, force: bool = False, user: User = Depends(require_write)):
    """Delete a wiki file. If referenced by other docs and force=False, returns 409."""
    _validate_path(path)
    svc = _svc()
    if not force:
        refs = svc.get_referencing_files(path)
        if refs:
            raise HTTPException(
                status_code=409,
                detail={"message": f"File is referenced by {len(refs)} document(s)", "referenced_by": refs},
            )
    deleted = await svc.delete_file(path)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return {"deleted": path}


class CreateNewVersionRequest(BaseModel):
    old_path: str
    new_path: str


@router.post("/create-new-version")
async def create_new_version(body: CreateNewVersionRequest, user: User = Depends(require_write)):
    """Create a new version of an existing document.

    - Validates: not deprecated, not already superseded
    - Reads the old document's metadata (domain, process, tags)
    - Creates new doc with supersedes=old_path and inherited metadata
    - Updates old doc's superseded_by to point to new doc
    - Auto-deprecates old doc
    """
    _validate_path(body.old_path)
    _validate_path(body.new_path)
    svc = _svc()

    old_file = await svc.get_file(body.old_path)
    if not old_file:
        raise HTTPException(status_code=404, detail="원본 문서를 찾을 수 없습니다")

    om = old_file.metadata

    # Block: deprecated docs cannot spawn new versions
    if om.status == "deprecated":
        raise HTTPException(status_code=422, detail="폐기된 문서에서는 새 버전을 만들 수 없습니다")

    # Block: already has a successor
    if om.superseded_by:
        successor_name = om.superseded_by.split("/")[-1]
        raise HTTPException(
            status_code=422,
            detail=f"이미 새 버전이 존재합니다: {successor_name}",
        )

    # Check new path doesn't already exist
    existing = await svc.get_file(body.new_path)
    if existing:
        new_name = body.new_path.split("/")[-1]
        raise HTTPException(status_code=409, detail=f"같은 이름의 문서가 이미 존재합니다: {new_name}")

    # Build new document frontmatter inheriting from old
    fm_lines = ["---"]
    fm_lines.append(f"supersedes: {body.old_path}")
    if om.domain:
        fm_lines.append(f"domain: {om.domain}")
    if om.process:
        fm_lines.append(f"process: {om.process}")
    if om.tags:
        fm_lines.append("tags:")
        for t in om.tags:
            fm_lines.append(f"  - {t}")
    fm_lines.append("---")

    title = body.new_path.split("/")[-1].replace(".md", "")
    content = "\n".join(fm_lines) + f"\n\n# {title}\n\n"

    try:
        new_file = await svc.save_file(body.new_path, content, user_name=user.name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Auto-deprecate old doc, storing previous status for potential restoration
    try:
        await svc.update_status(body.old_path, "deprecated", user_name=user.name, prev_status=om.status)
    except Exception as e:
        logger.warning(f"Auto-deprecate failed for {body.old_path}: {e}")

    return {
        "new_path": body.new_path,
        "old_path": body.old_path,
        "old_status": "deprecated",
        "inherited": {
            "domain": om.domain,
            "process": om.process,
            "tags": om.tags,
        },
    }


@router.post("/folder/{path:path}")
async def create_folder(path: str):
    """Create a folder inside the wiki directory."""
    created = await _svc().create_folder(path)
    if not created:
        raise HTTPException(status_code=409, detail=f"Folder already exists: {path}")
    return {"created": path}


@router.patch("/folder/{path:path}")
async def move_folder(path: str, body: MoveRequest):
    """Rename or move a folder."""
    result = await _svc().move_folder(path, body.new_path)
    if not result:
        raise HTTPException(status_code=400, detail=f"Cannot move folder: {path}")
    return {"old_path": path, "new_path": body.new_path}


@router.delete("/folder/{path:path}")
async def delete_folder(path: str):
    """Delete an empty folder from the wiki directory."""
    deleted = await _svc().delete_folder(path)
    if not deleted:
        raise HTTPException(status_code=400, detail=f"Folder not found or not empty: {path}")
    return {"deleted": path}


@router.post("/reindex")
async def reindex(force: bool = False):
    """Trigger reindex of wiki files. With force=true, reindex all regardless of hash."""
    count = await _svc().reindex_all(force=force)
    return {"total_chunks": count}


@router.get("/index-status")
async def get_index_status():
    """Return list of files pending indexing."""
    pending = index_status.get_pending()
    return {
        "pending_count": len(pending),
        "pending": [
            {"path": path, "queued_at": ts}
            for path, ts in sorted(pending.items(), key=lambda x: x[1])
        ],
    }


@router.post("/reindex/{path:path}")
async def reindex_file(path: str):
    """Reindex a specific file (queue for background indexing)."""
    _validate_path(path)
    svc = _svc()
    wiki_file = await svc.get_file(path)
    if not wiki_file:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    index_status.mark_pending(path)
    import asyncio
    asyncio.create_task(svc._bg_index(wiki_file))
    return {"queued": path}


REINDEX_BATCH_LIMIT = 100  # max concurrent reindex tasks per call


@router.post("/reindex-pending")
async def reindex_pending():
    """Reindex pending (stale) files, capped at REINDEX_BATCH_LIMIT per call.

    At 100K+ scale, creating unbounded async tasks would exhaust memory.
    Returns remaining count so caller can re-invoke if needed.
    """
    pending = index_status.get_pending()
    if not pending:
        return {"queued": 0, "remaining": 0}
    svc = _svc()
    count = 0
    import asyncio
    for path in list(pending.keys())[:REINDEX_BATCH_LIMIT]:
        wiki_file = await svc.get_file(path)
        if wiki_file:
            asyncio.create_task(svc._bg_index(wiki_file))
            count += 1
    remaining = max(0, len(pending) - REINDEX_BATCH_LIMIT)
    return {"queued": count, "remaining": remaining}


@router.get("/lineage/{path:path}")
async def get_lineage(path: str):
    """Return lineage info: supersedes, superseded_by, related documents."""
    svc = _svc()
    wiki_file = await svc.get_file(path)
    if not wiki_file:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    meta = wiki_file.metadata
    lineage: dict = {
        "path": path,
        "supersedes": None,
        "superseded_by": None,
        "related": [],
    }

    # Resolve supersedes (this doc is newer version of)
    if meta.supersedes:
        older = await svc.get_file(meta.supersedes)
        if older:
            lineage["supersedes"] = {
                "path": older.path,
                "title": older.title,
                "status": older.metadata.status,
                "updated": older.metadata.updated,
            }

    # Resolve superseded_by (this doc is older, replaced by)
    if meta.superseded_by:
        newer = await svc.get_file(meta.superseded_by)
        if newer:
            lineage["superseded_by"] = {
                "path": newer.path,
                "title": newer.title,
                "status": newer.metadata.status,
                "updated": newer.metadata.updated,
            }

    # Resolve related documents (exclude those already in lineage)
    lineage_paths = {meta.supersedes, meta.superseded_by} - {""}
    for rp in meta.related:
        if rp in lineage_paths:
            continue
        rel = await svc.get_file(rp)
        if rel:
            lineage["related"].append({
                "path": rel.path,
                "title": rel.title,
                "status": rel.metadata.status,
                "updated": rel.metadata.updated,
            })

    return lineage


@router.get("/version-chain/{path:path}")
async def get_version_chain(path: str):
    """Walk the full supersedes/superseded_by chain in both directions.

    Returns {chain: [{path, title, status, created, updated, created_by}], current_index, branches}.
    Uses MetadataIndex for O(1) lookups (no file I/O per node).
    """
    svc = _svc()
    meta_index = svc._meta_index

    # Walk backward (older versions via supersedes)
    backward: list[dict] = []
    current_entry = meta_index.get_file_entry(path) if meta_index else None
    if not current_entry:
        wiki_file = await svc.get_file(path)
        if not wiki_file:
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        current_entry = {
            "domain": wiki_file.metadata.domain,
            "status": wiki_file.metadata.status,
            "supersedes": wiki_file.metadata.supersedes,
            "superseded_by": wiki_file.metadata.superseded_by,
            "created": wiki_file.metadata.created,
            "updated": wiki_file.metadata.updated,
            "created_by": wiki_file.metadata.created_by,
        }

    visited = {path}
    cursor = current_entry.get("supersedes", "")
    while cursor and cursor not in visited and len(backward) < 50:
        visited.add(cursor)
        entry = meta_index.get_file_entry(cursor) if meta_index else None
        if not entry:
            backward.append({"path": cursor, "title": cursor.rsplit("/", 1)[-1].replace(".md", ""),
                             "status": "", "created": "", "updated": "", "created_by": ""})
            break
        backward.append({
            "path": cursor,
            "title": cursor.rsplit("/", 1)[-1].replace(".md", ""),
            "status": entry.get("status", ""),
            "created": entry.get("created", ""),
            "updated": entry.get("updated", ""),
            "created_by": entry.get("created_by", ""),
        })
        cursor = entry.get("supersedes", "")

    backward.reverse()

    # Current node
    current_node = {
        "path": path,
        "title": path.rsplit("/", 1)[-1].replace(".md", ""),
        "status": current_entry.get("status", ""),
        "created": current_entry.get("created", ""),
        "updated": current_entry.get("updated", ""),
        "created_by": current_entry.get("created_by", ""),
    }

    # Walk forward (newer versions via superseded_by)
    forward: list[dict] = []
    cursor = current_entry.get("superseded_by", "")
    while cursor and cursor not in visited and len(forward) < 50:
        visited.add(cursor)
        entry = meta_index.get_file_entry(cursor) if meta_index else None
        if not entry:
            forward.append({"path": cursor, "title": cursor.rsplit("/", 1)[-1].replace(".md", ""),
                            "status": "", "created": "", "updated": "", "created_by": ""})
            break
        forward.append({
            "path": cursor,
            "title": cursor.rsplit("/", 1)[-1].replace(".md", ""),
            "status": entry.get("status", ""),
            "created": entry.get("created", ""),
            "updated": entry.get("updated", ""),
            "created_by": entry.get("created_by", ""),
        })
        cursor = entry.get("superseded_by", "")

    chain = backward + [current_node] + forward
    current_index = len(backward)

    # Detect branches: other docs that also supersede the same target
    branches: list[dict] = []
    if meta_index and current_entry.get("supersedes"):
        competitors = meta_index.get_supersedes_reverse(current_entry["supersedes"])
        for comp in competitors:
            if comp != path:
                comp_entry = meta_index.get_file_entry(comp) or {}
                branches.append({
                    "path": comp,
                    "title": comp.rsplit("/", 1)[-1].replace(".md", ""),
                    "status": comp_entry.get("status", ""),
                })

    return {"chain": chain, "current_index": current_index, "branches": branches}


@router.get("/compare")
async def compare_documents(path_a: str, path_b: str):
    """Return two documents side-by-side for diff comparison."""
    svc = _svc()
    file_a = await svc.get_file(path_a)
    file_b = await svc.get_file(path_b)

    if not file_a:
        raise HTTPException(status_code=404, detail=f"File not found: {path_a}")
    if not file_b:
        raise HTTPException(status_code=404, detail=f"File not found: {path_b}")

    return {
        "file_a": {
            "path": file_a.path,
            "title": file_a.title,
            "content": file_a.content,
            "metadata": file_a.metadata.model_dump(),
        },
        "file_b": {
            "path": file_b.path,
            "title": file_b.title,
            "content": file_b.content,
            "metadata": file_b.metadata.model_dump(),
        },
    }


# ── Confidence Score Endpoints ──────────────────────────────────────

@router.get("/confidence/{path:path}")
async def get_confidence(path: str, user: User = Depends(require_read)):
    """Get confidence score for a single document."""
    _validate_path(path)
    if _confidence_service is None:
        raise HTTPException(status_code=503, detail="Confidence service not available")
    result = _confidence_service.get_confidence(path)
    return result.model_dump()


@router.get("/confidence-batch")
async def get_confidence_batch(paths: str = "", user: User = Depends(require_read)):
    """Get confidence scores for multiple documents.
    Pass comma-separated paths: ?paths=a.md,b.md"""
    if _confidence_service is None:
        raise HTTPException(status_code=503, detail="Confidence service not available")
    path_list = [p.strip() for p in paths.split(",") if p.strip()]
    if not path_list:
        return {}
    results = _confidence_service.get_confidence_batch(path_list)
    return {k: v.model_dump() for k, v in results.items()}


@router.get("/scoring-config")
async def get_scoring_config(user: User = Depends(require_read)):
    """Return all scoring parameters with human-readable explanations.
    Intended for developer debugging and tuning transparency."""
    return SCORING.explain()


@router.get("/digest")
async def get_maintenance_digest(
    user_filter: str = "",
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_read),
):
    """Return documents needing attention: stale, low confidence, unresolved conflicts.

    Pagination applies per-section: each section returns at most `limit` items starting from `offset`.
    """
    if _digest_service is None:
        raise HTTPException(status_code=503, detail="Digest service not available")
    full = await _digest_service.generate_digest(username=user_filter)
    # Return a paginated copy (don't mutate cached original)
    return {
        "user": full.user,
        "total": full.total,
        "total_stale": full.total_stale,
        "total_low_confidence": full.total_low_confidence,
        "total_unresolved_conflicts": full.total_unresolved_conflicts,
        "stale": full.stale[offset:offset + limit],
        "low_confidence": full.low_confidence[offset:offset + limit],
        "unresolved_conflicts": full.unresolved_conflicts[offset:offset + limit],
    }


# ── Document Feedback Endpoints ───────────────────────────────────


def _refresh_document_timestamp(path: str, user_name: str) -> None:
    """Update the document's `updated` frontmatter field without changing content.

    This makes the freshness signal treat the document as recently verified.
    """
    import yaml
    from pathlib import Path
    from backend.core.config import settings

    svc = _svc()
    file_path = Path(settings.wiki_dir) / path
    if not file_path.exists():
        return

    try:
        raw = file_path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            return

        parts = raw.split("---", 2)
        if len(parts) < 3:
            return

        fm = yaml.safe_load(parts[1]) or {}
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        fm["updated"] = now_iso
        fm["updated_by"] = user_name

        new_raw = "---\n" + yaml.dump(fm, allow_unicode=True, default_flow_style=False) + "---" + parts[2]
        file_path.write_text(new_raw, encoding="utf-8")

        # Update metadata index
        svc._meta_index.on_file_saved(
            path,
            domain=fm.get("domain", ""),
            process=fm.get("process", ""),
            tags=fm.get("tags", []) or [],
            updated=now_iso,
            updated_by=user_name,
            created_by=fm.get("created_by", ""),
            related=fm.get("related", []) or [],
            status=fm.get("status", ""),
            supersedes=fm.get("supersedes", ""),
            superseded_by=fm.get("superseded_by", ""),
        )
    except Exception:
        pass  # best-effort: don't fail the feedback request


class FeedbackRequest(BaseModel):
    action: str  # "verified" | "needs_update" | "thumbs_up" | "thumbs_down"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid = {"verified", "needs_update", "thumbs_up", "thumbs_down"}
        if v not in valid:
            raise ValueError(f"action must be one of {valid}")
        return v


@router.post("/feedback/{path:path}")
async def post_feedback(path: str, body: FeedbackRequest, user: User = Depends(require_write)):
    """Record user feedback on a document."""
    _validate_path(path)
    if _feedback_tracker is None:
        raise HTTPException(status_code=503, detail="Feedback service not available")

    summary = _feedback_tracker.record_feedback(path, user.name, body.action)

    # "verified" refreshes the document's freshness (updates `updated` frontmatter)
    if body.action == "verified":
        _refresh_document_timestamp(path, user.name)

    # Invalidate confidence cache so score reflects fresh feedback
    if _confidence_service:
        _confidence_service.invalidate(path)

    return {"ok": True, "feedback": summary.model_dump()}


@router.get("/feedback/{path:path}")
async def get_feedback(path: str, user: User = Depends(require_read)):
    """Get feedback summary for a document."""
    _validate_path(path)
    if _feedback_tracker is None:
        raise HTTPException(status_code=503, detail="Feedback service not available")

    summary = _feedback_tracker.get_feedback_summary(path)
    return summary.model_dump()


# ── Metadata Inheritance ─────────────────────────────────────────────

@router.get("/predecessor-context/{path:path}")
async def get_predecessor_context(path: str, user: User = Depends(require_read)):
    """Return metadata from the predecessor (supersedes target) for inheritance.

    Used when creating a new version of a document to pre-fill metadata fields.
    Returns domain, process, tags, related (excluding deprecated docs).
    """
    _validate_path(path)
    svc = _svc()
    wiki_file = await svc.get_file(path)
    if not wiki_file:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    predecessor_path = wiki_file.metadata.supersedes
    if not predecessor_path:
        return {"has_predecessor": False}

    pred_file = await svc.get_file(predecessor_path)
    if not pred_file:
        return {"has_predecessor": False}

    # Filter out deprecated docs from related
    active_related = []
    if svc._meta_index:
        for rp in pred_file.metadata.related:
            entry = svc._meta_index.get_file_entry(rp)
            if entry and entry.get("status") != "deprecated":
                active_related.append(rp)
    else:
        active_related = pred_file.metadata.related

    return {
        "has_predecessor": True,
        "predecessor_path": predecessor_path,
        "domain": pred_file.metadata.domain,
        "process": pred_file.metadata.process,
        "tags": pred_file.metadata.tags,
        "related": active_related,
        "created_by": pred_file.metadata.created_by,
    }


# ── Bulk Status Change ───────────────────────────────────────────────

class BulkStatusRequest(BaseModel):
    paths: list[str]
    status: str  # draft | approved | deprecated

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("draft", "approved", "deprecated"):
            raise ValueError(f"Invalid status: {v}. Must be draft|approved|deprecated")
        return v

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, v: list[str]) -> list[str]:
        if len(v) > 500:
            raise ValueError("Maximum 500 paths per request")
        return v


@router.post("/bulk-status")
async def bulk_status_change(body: BulkStatusRequest, user: User = Depends(require_write)):
    """Change status for multiple documents at once.

    Max 500 paths. Triggers deprecation side effects for each path set to deprecated.
    """
    import yaml as _yaml

    svc = _svc()
    results: list[dict] = []

    for path in body.paths:
        try:
            _validate_path(path)
            wiki_file = await svc.get_file(path)
            if not wiki_file:
                results.append({"path": path, "ok": False, "error": "not found"})
                continue

            # Update status in frontmatter
            raw = wiki_file.raw_content
            if not raw.startswith("---"):
                results.append({"path": path, "ok": False, "error": "no frontmatter"})
                continue

            parts = raw.split("---", 2)
            if len(parts) < 3:
                results.append({"path": path, "ok": False, "error": "invalid frontmatter"})
                continue

            fm = _yaml.safe_load(parts[1]) or {}
            fm["status"] = body.status

            new_raw = "---\n" + _yaml.dump(fm, allow_unicode=True, default_flow_style=False) + "---" + parts[2]
            await svc.save_file(path, new_raw, user_name=user.name)
            results.append({"path": path, "ok": True})
        except Exception as e:
            results.append({"path": path, "ok": False, "error": str(e)})

    success_count = sum(1 for r in results if r["ok"])
    return {"total": len(body.paths), "success": success_count, "results": results}
