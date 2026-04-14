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


DEFAULT_DOMAIN_PROCESSES: dict[str, list[str]] = {
    "SCM": ["주문", "품질", "진행", "공정", "물류"],
    "ERP": ["마스터데이터", "모듈관리", "인터페이스", "리포트"],
    "MES": ["생산계획", "실적관리", "설비보전", "품질관리"],
    "인프라": ["서버", "네트워크", "보안", "모니터링"],
    "기획": ["예산", "프로젝트", "KPI", "전략"],
    "재무": ["회계", "결산", "세무", "원가"],
    "인사": ["채용", "평가", "교육", "급여"],
}

DEFAULT_TAG_PRESETS: list[str] = ["장애대응", "SOP", "FAQ", "가이드", "정책", "양식"]


def _load_templates() -> dict:
    """Load templates from JSON file, with defaults if missing."""
    if TEMPLATES_FILE.exists():
        try:
            data = json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
            # Migrate legacy flat format → hierarchical
            if "domains" in data and "domain_processes" not in data:
                data = _migrate_flat_to_hierarchical(data)
                _save_templates(data)
            return data
        except Exception:
            pass
    return {
        "domain_processes": DEFAULT_DOMAIN_PROCESSES,
        "tag_presets": DEFAULT_TAG_PRESETS,
    }


def _migrate_flat_to_hierarchical(data: dict) -> dict:
    """Convert legacy {domains[], processes[]} → {domain_processes: {}}."""
    domains = data.get("domains", [])
    processes = data.get("processes", [])
    domain_processes: dict[str, list[str]] = {}
    for d in domains:
        # Assign all processes to first domain as fallback; user can reassign
        domain_processes[d] = []
    if domains and processes:
        domain_processes[domains[0]] = processes
    return {
        "domain_processes": domain_processes,
        "tag_presets": data.get("tag_presets", DEFAULT_TAG_PRESETS),
    }


def _save_templates(data: dict) -> None:
    """Save templates to JSON file."""
    TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# Injected at startup
_wiki_service = None
_meta_index = None


def init(wiki_service, meta_index=None) -> None:
    global _wiki_service, _meta_index
    _wiki_service = wiki_service
    _meta_index = meta_index


async def _ensure_index_built() -> None:
    """Rebuild metadata index if it's empty but wiki has files."""
    if not _meta_index or not _wiki_service:
        return
    stats = _meta_index.get_stats()
    if stats.get("domains") or stats.get("tags"):
        return  # Already populated
    entries = await _wiki_service.get_all_metadata()
    if entries:
        _meta_index.rebuild(extended=[
            {
                "path": e.path,
                "domain": e.metadata.domain,
                "process": e.metadata.process,
                "tags": e.metadata.tags,
                "updated": e.metadata.updated,
                "updated_by": e.metadata.updated_by,
                "created_by": e.metadata.created_by,
                "related": e.metadata.related,
                "status": e.metadata.status,
                "supersedes": e.metadata.supersedes,
                "superseded_by": e.metadata.superseded_by,
            }
            for e in entries
        ])


@router.get("/tags")
async def get_all_tags():
    """Return all unique metadata values across wiki files (index-backed)."""
    if _meta_index:
        await _ensure_index_built()
        stats = _meta_index.get_stats()
        return {
            "domains": sorted(stats.get("domains", {}).keys()),
            "processes": sorted({p for procs in stats.get("domain_processes", {}).values() for p in procs}),
            "error_codes": [],  # error_codes not tracked in index; rarely needed here
            "tags": sorted(stats.get("tags", {}).keys()),
        }

    # Fallback: full scan (first run before index is built)
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


@router.get("/tags/search")
async def search_tags(q: str = "", offset: int = 0, limit: int = 30):
    """Lazy tag search — prefix match on indexed tag names, paginated with counts."""
    if _meta_index:
        await _ensure_index_built()
        return _meta_index.search_tags_paginated(q, offset, limit)
    # Fallback
    all_tags_data = await get_all_tags()
    filtered = [t for t in all_tags_data["tags"] if q.lower() in t.lower()] if q else all_tags_data["tags"]
    total = len(filtered)
    page = filtered[offset : offset + limit]
    return {"tags": [{"name": t, "count": 0} for t in page], "total": total}


@router.get("/stats")
async def get_metadata_stats():
    """Return metadata statistics from index (O(1))."""
    if _meta_index:
        await _ensure_index_built()
        return _meta_index.get_stats()
    # Fallback
    all_tags = await get_all_tags()
    return {
        "domains": {d: 0 for d in all_tags["domains"]},
        "tags": {t: 0 for t in all_tags["tags"]},
        "untagged_count": 0,
    }


@router.get("/statuses")
async def get_all_statuses():
    """Return {path: status} map for all files with a non-empty status. Lightweight endpoint for TreeNav."""
    if _meta_index:
        await _ensure_index_built()
        return _meta_index.get_all_statuses()
    return {}


@router.get("/tags/similar")
async def find_similar_tags(tag: str, top_k: int = 5):
    """Find semantically similar existing tags (for Smart Friction UI)."""
    from backend.application.metadata.tag_registry import tag_registry
    if not tag_registry.is_connected:
        return {"similar": []}
    results = tag_registry.find_similar(tag, top_k=top_k)
    # Exclude exact match, only return truly different tags
    filtered = [r for r in results if r["tag"] != tag and r["distance"] < 0.60]
    return {"similar": filtered}


@router.get("/tags/similar-groups")
async def get_similar_tag_groups(threshold: float = 0.55):
    """Find groups of similar tags for admin merge dashboard."""
    from backend.application.metadata.tag_registry import tag_registry
    if not tag_registry.is_connected:
        return {"groups": []}
    groups = tag_registry.find_similar_groups(threshold)
    return {"groups": groups}


@router.post("/tags/merge")
async def merge_tags(source: str, target: str):
    """Merge source tag into target tag across all documents."""
    from backend.application.metadata.tag_registry import tag_registry
    if not _wiki_service:
        raise HTTPException(500, "Wiki service not initialized")

    entries = await _wiki_service.get_all_metadata()
    updated_count = 0
    for e in entries:
        if source in e.metadata.tags:
            new_tags = [target if t == source else t for t in e.metadata.tags]
            # Deduplicate
            seen = set()
            deduped = []
            for t in new_tags:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)

            wiki_file = await _wiki_service.get_file(e.path)
            if wiki_file:
                raw = wiki_file.raw_content or wiki_file.content
                new_meta = wiki_file.metadata.model_copy()
                new_meta.tags = deduped
                await _wiki_service.save_file(e.path, raw, metadata=new_meta)
                updated_count += 1

    # Remove source tag from registry
    if tag_registry.is_connected:
        tag_registry.delete_tag(source)

    _invalidate_meta_cache()
    return {"merged": source, "into": target, "updated_documents": updated_count}


@router.get("/tags/orphans")
async def get_orphan_tags(min_docs: int = 1):
    """Find tags used by very few documents (candidates for cleanup)."""
    if not _meta_index:
        return {"orphans": []}
    d = _meta_index._load()
    tags = d.get("tags", {})
    orphans = [{"name": t, "count": c} for t, c in tags.items() if c <= min_docs]
    orphans.sort(key=lambda x: (x["count"], x["name"]))
    return {"orphans": orphans, "total": len(orphans)}


@router.get("/files-by-tag")
async def get_files_by_tag(field: str, value: str, offset: int = 0, limit: int = 50):
    """Return paginated file paths matching a metadata field value (index-backed)."""
    if _meta_index:
        await _ensure_index_built()
        return _meta_index.get_files_by_field(field, value, offset, limit)

    # Fallback: full scan (should rarely happen)
    cache_key = f"files_by_tag:{field}:{value}"
    cached = _get_meta_cache(cache_key)
    if cached:
        all_files = cached
    else:
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
        all_files = sorted(matched)
        _set_meta_cache(cache_key, all_files)

    page = all_files[offset : offset + limit]
    return {"files": page, "total": len(all_files), "offset": offset, "limit": limit}


class SuggestRequest(BaseModel):
    content: str
    existing_tags: list[str] = []
    path: str | None = None
    related: list[str] = []


@router.post("/suggest", response_model=MetadataSuggestion)
async def suggest_tags(req: SuggestRequest):
    """Use LLM to suggest metadata tags for document content."""
    return await suggest_metadata(
        req.content,
        req.existing_tags,
        path=req.path,
        related=req.related,
    )


# ── Template CRUD ─────────────────────────────────────────────────────

@router.get("/templates")
async def get_templates():
    """Return metadata templates {domain_processes, tag_presets}."""
    return _load_templates()


@router.get("/templates/domains")
async def get_domains():
    """Return flat domain list (convenience)."""
    data = _load_templates()
    return {"domains": sorted(data.get("domain_processes", {}).keys())}


@router.get("/templates/processes/{domain}")
async def get_processes_for_domain(domain: str):
    """Return processes for a specific domain."""
    data = _load_templates()
    dp = data.get("domain_processes", {})
    if domain not in dp:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")
    return {"domain": domain, "processes": dp[domain]}


class TemplateUpdate(BaseModel):
    domain_processes: dict[str, list[str]] | None = None
    tag_presets: list[str] | None = None


@router.put("/templates")
async def update_templates(req: TemplateUpdate):
    """Update metadata templates (full replace of provided fields)."""
    data = _load_templates()
    if req.domain_processes is not None:
        data["domain_processes"] = req.domain_processes
    if req.tag_presets is not None:
        data["tag_presets"] = req.tag_presets
    _save_templates(data)
    _invalidate_meta_cache()
    return data


# ── Domain CRUD ──────────────────────────────────────────────────────

class AddDomainRequest(BaseModel):
    name: str
    processes: list[str] = []


@router.post("/templates/domain")
async def add_domain(req: AddDomainRequest):
    """Add a new domain with optional initial processes."""
    data = _load_templates()
    dp: dict = data.setdefault("domain_processes", {})
    if req.name in dp:
        raise HTTPException(status_code=409, detail=f"Domain already exists: {req.name}")
    dp[req.name] = req.processes
    _save_templates(data)
    _invalidate_meta_cache()
    return data


@router.delete("/templates/domain/{domain}")
async def remove_domain(domain: str):
    """Remove a domain and all its processes."""
    data = _load_templates()
    dp: dict = data.get("domain_processes", {})
    if domain not in dp:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")
    del dp[domain]
    _save_templates(data)
    _invalidate_meta_cache()
    return data


# ── Process CRUD (under domain) ─────────────────────────────────────

class AddProcessRequest(BaseModel):
    name: str


@router.post("/templates/domain/{domain}/process")
async def add_process(domain: str, req: AddProcessRequest):
    """Add a process under an existing domain."""
    data = _load_templates()
    dp: dict = data.get("domain_processes", {})
    if domain not in dp:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")
    procs: list[str] = dp[domain]
    if req.name in procs:
        raise HTTPException(status_code=409, detail=f"Process already exists: {req.name}")
    procs.append(req.name)
    _save_templates(data)
    _invalidate_meta_cache()
    return data


@router.delete("/templates/domain/{domain}/process/{process}")
async def remove_process(domain: str, process: str):
    """Remove a process from a domain."""
    data = _load_templates()
    dp: dict = data.get("domain_processes", {})
    if domain not in dp:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain}")
    procs: list[str] = dp[domain]
    if process not in procs:
        raise HTTPException(status_code=404, detail=f"Process not found: {process}")
    procs.remove(process)
    _save_templates(data)
    _invalidate_meta_cache()
    return data


# ── Tag preset CRUD ──────────────────────────────────────────────────

class TagPresetRequest(BaseModel):
    value: str


@router.post("/templates/tag-preset")
async def add_tag_preset(req: TagPresetRequest):
    """Add a tag preset."""
    data = _load_templates()
    presets: list[str] = data.setdefault("tag_presets", [])
    if req.value not in presets:
        presets.append(req.value)
        _save_templates(data)
        _invalidate_meta_cache()
    return data


@router.delete("/templates/tag-preset/{value}")
async def remove_tag_preset(value: str):
    """Remove a tag preset."""
    data = _load_templates()
    presets: list[str] = data.get("tag_presets", [])
    if value in presets:
        presets.remove(value)
        _save_templates(data)
        _invalidate_meta_cache()
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
async def get_untagged_documents(offset: int = 0, limit: int = 50):
    """Return paginated untagged documents (index-backed)."""
    if _meta_index:
        await _ensure_index_built()
        return _meta_index.get_untagged(offset, limit)

    # Fallback: full scan
    entries = await _wiki_service.get_all_metadata()
    untagged = []
    for e in entries:
        meta = e.metadata
        if not meta.domain and not meta.process and not meta.tags:
            untagged.append({"path": e.path, "title": e.path.split("/")[-1]})
    page = untagged[offset : offset + limit]
    return {"files": page, "count": len(untagged), "offset": offset, "limit": limit}


# ── Bulk auto-tag ────────────────────────────────────────────────────

class BulkSuggestRequest(BaseModel):
    paths: list[str]
    apply: bool = False  # If True, immediately save suggestions to files


class BulkSuggestResult(BaseModel):
    path: str
    suggestion: MetadataSuggestion | None = None
    applied: bool = False
    error: str = ""


@router.post("/suggest-bulk")
async def suggest_bulk(req: BulkSuggestRequest):
    """Auto-tag multiple documents. Parallel LLM calls (max 5 concurrent)."""
    import asyncio

    semaphore = asyncio.Semaphore(5)

    async def process_one(path: str) -> dict:
        async with semaphore:
            try:
                wiki_file = await _wiki_service.get_file(path)
                if not wiki_file:
                    return {"path": path, "error": "File not found", "applied": False}

                suggestion = await suggest_metadata(
                    wiki_file.content,
                    wiki_file.metadata.tags,
                    path=path,
                    related=wiki_file.metadata.related,
                )

                applied = False
                if req.apply and suggestion.confidence >= 0.5:
                    raw = wiki_file.raw_content or wiki_file.content
                    applied = await _apply_suggestion(path, raw, wiki_file.metadata, suggestion)

                return {
                    "path": path,
                    "suggestion": suggestion.model_dump(),
                    "applied": applied,
                }
            except Exception as e:
                logger.error(f"Bulk suggest failed for {path}: {e}")
                return {"path": path, "error": str(e), "applied": False}

    results = await asyncio.gather(*[process_one(p) for p in req.paths])

    _invalidate_meta_cache()
    return {"results": list(results), "total": len(results)}


async def _apply_suggestion(
    path: str,
    raw_content: str,
    current_meta: "DocumentMetadata",
    suggestion: MetadataSuggestion,
) -> bool:
    """Apply suggestion to file metadata and save."""
    try:
        import yaml

        # Parse frontmatter
        if raw_content.startswith("---"):
            parts = raw_content.split("---", 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1]) or {}
                body = parts[2]
            else:
                return False
        else:
            fm = {}
            body = raw_content

        # Apply suggestion (only fill empty fields)
        if suggestion.domain and not fm.get("domain"):
            fm["domain"] = suggestion.domain
        if suggestion.process and not fm.get("process"):
            fm["process"] = suggestion.process
        if suggestion.tags:
            existing_tags = fm.get("tags", []) or []
            new_tags = [t for t in suggestion.tags if t not in existing_tags]
            fm["tags"] = existing_tags + new_tags
        if suggestion.error_codes:
            existing_ec = fm.get("error_codes", []) or []
            new_ec = [e for e in suggestion.error_codes if e not in existing_ec]
            fm["error_codes"] = existing_ec + new_ec

        new_raw = "---\n" + yaml.dump(fm, allow_unicode=True, default_flow_style=False) + "---" + body
        await _wiki_service.save_file(path, new_raw, user_name="auto-tagger")
        return True
    except Exception as e:
        logger.error(f"Failed to apply suggestion to {path}: {e}")
        return False
