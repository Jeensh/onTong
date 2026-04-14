"""Document Maintenance Digest — surfaces docs needing attention.

Groups documents by: stale (>12 months), low confidence (<40), unresolved conflicts.

Designed for 100K+ document scale:
- File scanning runs in a thread pool (non-blocking)
- Result caching with TTL to avoid repeated scans
- MAX_FILES_SCAN cap as safety net
- Only reads frontmatter (first ~500 bytes), not full file content
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MAX_FILES_SCAN = 100_000  # safety cap
DIGEST_CACHE_TTL = 300  # 5 minutes — digest doesn't change often
MAX_FRONTMATTER_BYTES = 1024  # only read first KB for frontmatter


class DigestItem(BaseModel):
    path: str
    title: str
    reason: str  # "stale" | "low_confidence" | "unresolved_conflict"
    detail: str  # human-readable Korean detail
    confidence_score: int = -1
    stale_months: int = 0


class DigestResult(BaseModel):
    user: str
    total: int = 0
    stale: list[DigestItem] = Field(default_factory=list)
    low_confidence: list[DigestItem] = Field(default_factory=list)
    unresolved_conflicts: list[DigestItem] = Field(default_factory=list)
    # Totals before pagination (for UI display)
    total_stale: int = 0
    total_low_confidence: int = 0
    total_unresolved_conflicts: int = 0


class DocumentDigestService:
    """Generate maintenance digest for a user's documents."""

    def __init__(
        self,
        confidence_svc: Any,
        conflict_svc: Any,
        wiki_dir: str,
    ) -> None:
        self._confidence_svc = confidence_svc
        self._conflict_svc = conflict_svc
        self._wiki_dir = wiki_dir
        self._cache: dict[str, tuple[DigestResult, float]] = {}

    async def generate_digest(self, username: str = "") -> DigestResult:
        """Generate digest of documents needing attention.

        Uses result caching to avoid repeated filesystem scans.
        File scanning runs in a thread to avoid blocking the event loop.
        """
        cache_key = username or "__all__"
        cached = self._cache.get(cache_key)
        if cached:
            result, ts = cached
            if time.time() - ts < DIGEST_CACHE_TTL:
                return result

        result = await asyncio.to_thread(self._scan_documents, username)

        # Add unresolved conflicts
        if self._conflict_svc:
            await self._add_conflicts(result, username)

        result.total_stale = len(result.stale)
        result.total_low_confidence = len(result.low_confidence)
        result.total_unresolved_conflicts = len(result.unresolved_conflicts)
        result.total = result.total_stale + result.total_low_confidence + result.total_unresolved_conflicts

        self._cache[cache_key] = (result, time.time())
        return result

    def invalidate_cache(self) -> None:
        """Clear digest cache (call on tree_change events)."""
        self._cache.clear()

    def _scan_documents(self, username: str) -> DigestResult:
        """Synchronous file scan — runs in thread pool."""
        from pathlib import Path
        import yaml

        result = DigestResult(user=username or "all")
        wiki_path = Path(self._wiki_dir)

        scanned = 0
        for md_file in wiki_path.rglob("*.md"):
            if scanned >= MAX_FILES_SCAN:
                logger.warning("Digest scan hit MAX_FILES_SCAN=%d cap", MAX_FILES_SCAN)
                break
            scanned += 1

            rel = str(md_file.relative_to(wiki_path))
            if rel.startswith(("_skills/", "_personas/", ".")):
                continue

            # Read only frontmatter (first KB is enough)
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    header = f.read(MAX_FRONTMATTER_BYTES)
                fm: dict = {}
                if header.startswith("---"):
                    parts = header.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1]) or {}
            except Exception:
                continue

            # Filter by user if specified
            if username:
                created_by = fm.get("created_by", "")
                updated_by = fm.get("updated_by", "")
                if username not in (created_by, updated_by):
                    continue

            title = fm.get("title", "") or rel.split("/")[-1].replace(".md", "")

            # Get confidence
            try:
                conf = self._confidence_svc.get_confidence(rel)
            except Exception:
                continue

            # Check stale
            if conf.stale and conf.stale_months >= 12:
                result.stale.append(DigestItem(
                    path=rel,
                    title=title,
                    reason="stale",
                    detail=f"{conf.stale_months}개월 동안 수정되지 않았습니다",
                    confidence_score=conf.score,
                    stale_months=conf.stale_months,
                ))

            # Check low confidence
            if conf.score < 40:
                result.low_confidence.append(DigestItem(
                    path=rel,
                    title=title,
                    reason="low_confidence",
                    detail=f"신뢰도 {conf.score}점 — 메타데이터 보강 또는 내용 검증이 필요합니다",
                    confidence_score=conf.score,
                ))

        return result

    async def _add_conflicts(self, result: DigestResult, username: str) -> None:
        """Add unresolved conflict items to digest."""
        from pathlib import Path
        import yaml

        wiki_path = Path(self._wiki_dir)
        seen_conflict_paths: set[str] = set()

        try:
            typed_pairs = self._conflict_svc.get_typed_pairs(filter_mode="unresolved")
            for pair in typed_pairs:
                for fp in (pair["file_a"], pair["file_b"]):
                    if fp in seen_conflict_paths:
                        continue
                    if username:
                        try:
                            fm_path = wiki_path / fp
                            with open(fm_path, "r", encoding="utf-8") as f:
                                header = f.read(MAX_FRONTMATTER_BYTES)
                            if header.startswith("---"):
                                parts = header.split("---", 2)
                                if len(parts) >= 3:
                                    fm = yaml.safe_load(parts[1]) or {}
                                    if username not in (fm.get("created_by", ""), fm.get("updated_by", "")):
                                        continue
                        except Exception:
                            continue

                    seen_conflict_paths.add(fp)
                    other = pair["file_b"] if fp == pair["file_a"] else pair["file_a"]
                    detail = pair.get("summary_ko", "") or f"{other}와 유사도 {round(pair.get('similarity', 0) * 100)}%"
                    result.unresolved_conflicts.append(DigestItem(
                        path=fp,
                        title=fp.split("/")[-1].replace(".md", ""),
                        reason="unresolved_conflict",
                        detail=detail,
                    ))
        except Exception as e:
            logger.warning(f"Failed to get conflict pairs for digest: {e}")
