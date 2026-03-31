"""Metadata API: tag aggregation, AI auto-suggest, and template management."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.schemas import DocumentMetadata, MetadataSuggestion, WikiFile
from backend.application.metadata.metadata_service import suggest_metadata

from backend.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metadata", tags=["metadata"], dependencies=[Depends(get_current_user)])

TEMPLATES_FILE = Path(settings.wiki_dir) / ".ontong" / "metadata_templates.json"

# ── TTL cache for metadata endpoints ─────────────────────────────────
_meta_cache: dict[str, tuple[object, float]] = {}
_META_CACHE_TTL = 60  # seconds


def _get_meta_cache(key: str):
    entry = _meta_cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > _META_CACHE_TTL:
        del _meta_cache[key]
        return None
    return result


def _set_meta_cache(key: str, value: object) -> None:
    _meta_cache[key] = (value, time.time())


def _invalidate_meta_cache() -> None:
    _meta_cache.clear()


def _load_templates() -> dict:
    """Load templates from JSON file, with defaults if missing."""
    if TEMPLATES_FILE.exists():
        try:
            return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "domains": ["SCM", "QC", "생산", "물류", "영업", "회계", "IT", "HR"],
        "processes": ["주문처리", "입고", "출고", "검수", "재고관리", "배송", "정산"],
        "tag_presets": [],
    }


def _save_templates(data: dict) -> None:
    """Save templates to JSON file."""
    TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# Injected at startup
_wiki_service = None


def init(wiki_service) -> None:
    global _wiki_service
    _wiki_service = wiki_service


@router.get("/tags")
async def get_all_tags():
    """Return all unique metadata values across wiki files."""
    cached = _get_meta_cache("tags")
    if cached:
        return cached

    entries = await _wiki_service.get_all_metadata()

    domains: set[str] = set()
    processes: set[str] = set()
    error_codes: set[str] = set()
    tags: set[str] = set()

    for e in entries:
        meta: DocumentMetadata = e.metadata
        if meta.domain:
            domains.add(meta.domain)
        if meta.process:
            processes.add(meta.process)
        for ec in meta.error_codes:
            error_codes.add(ec)
        for t in meta.tags:
            tags.add(t)

    result = {
        "domains": sorted(domains),
        "processes": sorted(processes),
        "error_codes": sorted(error_codes),
        "tags": sorted(tags),
    }
    _set_meta_cache("tags", result)
    return result


@router.get("/files-by-tag")
async def get_files_by_tag(field: str, value: str):
    """Return file paths matching a metadata field value."""
    cache_key = f"files_by_tag:{field}:{value}"
    cached = _get_meta_cache(cache_key)
    if cached:
        return cached

    entries = await _wiki_service.get_all_metadata()
    matched: list[str] = []

    for e in entries:
        meta: DocumentMetadata = e.metadata
        if field == "domain" and meta.domain == value:
            matched.append(e.path)
        elif field == "process" and meta.process == value:
            matched.append(e.path)
        elif field == "tags" and value in meta.tags:
            matched.append(e.path)
        elif field == "error_codes" and value in meta.error_codes:
            matched.append(e.path)

    result = sorted(matched)
    _set_meta_cache(cache_key, result)
    return result


class SuggestRequest(BaseModel):
    content: str
    existing_tags: list[str] = []


@router.post("/suggest", response_model=MetadataSuggestion)
async def suggest_tags(req: SuggestRequest):
    """Use LLM to suggest metadata tags for document content."""
    return await suggest_metadata(req.content, req.existing_tags)


# ── Template CRUD ─────────────────────────────────────────────────────

@router.get("/templates")
async def get_templates():
    """Return metadata templates (domains, processes, tag_presets)."""
    return _load_templates()


class TemplateUpdate(BaseModel):
    domains: list[str] | None = None
    processes: list[str] | None = None
    tag_presets: list[str] | None = None


@router.put("/templates")
async def update_templates(req: TemplateUpdate):
    """Update metadata templates. Only provided fields are replaced."""
    data = _load_templates()
    if req.domains is not None:
        data["domains"] = req.domains
    if req.processes is not None:
        data["processes"] = req.processes
    if req.tag_presets is not None:
        data["tag_presets"] = req.tag_presets
    _save_templates(data)
    return data


class AddItemRequest(BaseModel):
    field: str  # "domains" | "processes" | "tag_presets"
    value: str


@router.post("/templates/add")
async def add_template_item(req: AddItemRequest):
    """Add a single item to a template field."""
    data = _load_templates()
    if req.field not in ("domains", "processes", "tag_presets"):
        raise HTTPException(status_code=400, detail=f"Invalid field: {req.field}")
    items: list[str] = data.get(req.field, [])
    if req.value not in items:
        items.append(req.value)
        data[req.field] = items
        _save_templates(data)
    return data


class RemoveItemRequest(BaseModel):
    field: str
    value: str


@router.post("/templates/remove")
async def remove_template_item(req: RemoveItemRequest):
    """Remove a single item from a template field."""
    data = _load_templates()
    if req.field not in ("domains", "processes", "tag_presets"):
        raise HTTPException(status_code=400, detail=f"Invalid field: {req.field}")
    items: list[str] = data.get(req.field, [])
    if req.value in items:
        items.remove(req.value)
        data[req.field] = items
        _save_templates(data)
    return data


# ── Untagged documents ────────────────────────────────────────────────

# ── Tag normalization / merge suggestions ─────────────────────────────

def _suggest_merges(tags: list[str]) -> list[dict]:
    """Detect similar tags and suggest merges."""
    import unicodedata

    def normalize(s: str) -> str:
        s = s.lower().strip()
        s = unicodedata.normalize("NFC", s)
        # Map common Korean variants
        replacements = {
            "캐쉬": "캐시", "케시": "캐시", "cache": "캐시",
            "서버": "서버", "server": "서버",
            "에러": "에러", "error": "에러",
            "프로세스": "프로세스", "process": "프로세스",
        }
        return replacements.get(s, s)

    groups: dict[str, list[str]] = {}
    for t in tags:
        key = normalize(t)
        groups.setdefault(key, []).append(t)

    suggestions = []
    for key, members in groups.items():
        if len(members) > 1:
            suggestions.append({
                "canonical": members[0],
                "variants": members[1:],
                "all": members,
            })
    return suggestions


@router.get("/tag-merge-suggestions")
async def get_tag_merge_suggestions():
    """Suggest tag merges for similar/duplicate tags."""
    cached = _get_meta_cache("tag_merges")
    if cached:
        return cached

    entries = await _wiki_service.get_all_metadata()
    all_tags: set[str] = set()
    for e in entries:
        for t in e.metadata.tags:
            all_tags.add(t)
    result = {"suggestions": _suggest_merges(sorted(all_tags))}
    _set_meta_cache("tag_merges", result)
    return result


@router.get("/untagged")
async def get_untagged_documents():
    """Return documents with no tags, no domain, and no process."""
    cached = _get_meta_cache("untagged")
    if cached:
        return cached

    entries = await _wiki_service.get_all_metadata()
    untagged = []
    for e in entries:
        meta = e.metadata
        if not meta.domain and not meta.process and not meta.tags:
            untagged.append({"path": e.path, "title": e.path.split("/")[-1]})
    result = {"files": untagged, "count": len(untagged)}
    _set_meta_cache("untagged", result)
    return result
