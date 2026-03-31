"""Wiki REST API endpoints."""

from __future__ import annotations

import hashlib
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from backend.application.wiki.wiki_service import WikiService, index_status
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


def init(wiki_service: WikiService) -> None:
    global _wiki_service
    _wiki_service = wiki_service


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
    return await _svc().save_file(path, body.content, user_name=user.name)


@router.patch("/file/{path:path}")
async def move_file(path: str, body: MoveRequest):
    """Rename or move a wiki file."""
    result = await _svc().move_file(path, body.new_path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return {"old_path": path, "new_path": body.new_path}


@router.delete("/file/{path:path}")
async def delete_file(path: str, user: User = Depends(require_write)):
    """Delete a wiki file."""
    _validate_path(path)
    deleted = await _svc().delete_file(path)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return {"deleted": path}


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


@router.post("/reindex-pending")
async def reindex_pending():
    """Reindex all pending (stale) files."""
    pending = index_status.get_pending()
    if not pending:
        return {"queued": 0}
    svc = _svc()
    count = 0
    import asyncio
    for path in pending:
        wiki_file = await svc.get_file(path)
        if wiki_file:
            asyncio.create_task(svc._bg_index(wiki_file))
            count += 1
    return {"queued": count}


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

    # Resolve related documents
    for rp in meta.related:
        rel = await svc.get_file(rp)
        if rel:
            lineage["related"].append({
                "path": rel.path,
                "title": rel.title,
                "status": rel.metadata.status,
                "updated": rel.metadata.updated,
            })

    return lineage


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
