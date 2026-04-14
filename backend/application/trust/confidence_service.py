"""Confidence Service — orchestrates scoring with cache and metadata lookups.

Provides high-level API for computing confidence for single files or batches.
Depends on MetadataIndex for metadata and backlink counts, and wiki_service
for owner activity checks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import numpy as np

from backend.application.trust.confidence import (
    ConfidenceResult, NewerAlternative, compute_confidence,
)
from backend.application.trust.confidence_cache import ConfidenceCache
from backend.application.trust.scoring_config import SCORING

logger = logging.getLogger(__name__)

OWNER_ACTIVE_DAYS = 90
_NEWER_ALT_SCORE_THRESHOLD = SCORING.confidence.thresholds.medium_min  # 50 → show alternatives for low+medium-low


class ConfidenceService:
    """Compute and cache document confidence scores."""

    def __init__(self, meta_index: Any, wiki_dir: str) -> None:
        self._meta_index = meta_index
        self._wiki_dir = wiki_dir
        self._cache = ConfidenceCache()
        self._citation_tracker: Any = None
        self._chroma: Any = None
        self._feedback_tracker: Any = None

    def set_citation_tracker(self, tracker: Any) -> None:
        self._citation_tracker = tracker

    def set_chroma(self, chroma: Any) -> None:
        self._chroma = chroma

    def set_feedback_tracker(self, tracker: Any) -> None:
        self._feedback_tracker = tracker

    def get_confidence(self, path: str) -> ConfidenceResult:
        """Get confidence for a single document path."""
        cached = self._cache.get(path)
        if cached is not None:
            # Citation count is always fresh (not cached) since it changes frequently
            if self._citation_tracker:
                try:
                    cached.citation_count = self._citation_tracker.get_count(path)
                except Exception:
                    pass
            return cached

        meta = self._get_file_meta(path)
        backlink_count = self._get_backlink_count(path)
        owner_active = self._is_owner_active(meta.get("created_by", ""), path)
        fb_verified, fb_needs_update = self._get_feedback_counts(path)

        result = compute_confidence(
            meta, backlink_count, owner_active,
            feedback_verified=fb_verified,
            feedback_needs_update=fb_needs_update,
        )

        # Enrich with citation count (always fresh)
        if self._citation_tracker:
            try:
                result.citation_count = self._citation_tracker.get_count(path)
            except Exception:
                pass

        # Find newer alternatives for low-confidence docs
        if result.score < _NEWER_ALT_SCORE_THRESHOLD and self._chroma:
            try:
                result.newer_alternatives = self._find_newer_alternatives(path, result.score)
            except Exception as e:
                logger.debug(f"Failed to find alternatives for {path}: {e}")

        self._cache.put(path, result)
        return result

    def get_confidence_batch(self, paths: list[str]) -> dict[str, ConfidenceResult]:
        """Get confidence for multiple documents."""
        results: dict[str, ConfidenceResult] = {}
        for p in paths:
            results[p] = self.get_confidence(p)
        return results

    def invalidate(self, path: str) -> None:
        """Invalidate cache for a file (called on save/delete)."""
        self._cache.invalidate(path)

    def invalidate_all(self) -> None:
        """Invalidate entire cache (called on reindex)."""
        self._cache.invalidate_all()

    # ── Internal helpers ─────────────────────────────────────────────

    def _find_newer_alternatives(self, path: str, current_score: int) -> list[NewerAlternative]:
        """Find similar documents with higher confidence scores."""
        if not self._chroma:
            return []

        # Get this document's average embedding
        file_data = self._chroma.get_file_embeddings(path)
        embeddings = file_data.get("embeddings", [])
        if embeddings is None or len(embeddings) == 0:
            return []

        avg_emb = np.mean(embeddings, axis=0).tolist()

        # Query similar documents
        results = self._chroma.collection.query(
            query_embeddings=[avg_emb],
            n_results=SCORING.related.hnsw_candidates,
            include=["metadatas", "embeddings"],
        )

        if not results or not results.get("metadatas") or not results["metadatas"][0]:
            return []

        # Collect unique files with their similarity
        seen_files: set[str] = set()
        candidates: list[NewerAlternative] = []

        for meta in results["metadatas"][0]:
            fp = meta.get("file_path", "")
            if not fp or fp == path or fp in seen_files:
                continue
            if fp.startswith("_skills/") or fp.startswith("_personas/"):
                continue
            seen_files.add(fp)

            # Compute this candidate's confidence
            try:
                cand_result = self._get_confidence_no_alternatives(fp)
                if cand_result.score > current_score:
                    title = meta.get("heading", "") or fp.split("/")[-1].replace(".md", "")
                    candidates.append(NewerAlternative(
                        path=fp,
                        title=title,
                        confidence_score=cand_result.score,
                        confidence_tier=cand_result.tier,
                    ))
            except Exception:
                continue

        # Sort by confidence desc, take top 3
        candidates.sort(key=lambda c: -c.confidence_score)
        return candidates[:3]

    def _get_confidence_no_alternatives(self, path: str) -> ConfidenceResult:
        """Compute confidence without newer_alternatives (avoids recursion)."""
        meta = self._get_file_meta(path)
        backlink_count = self._get_backlink_count(path)
        owner_active = self._is_owner_active(meta.get("created_by", ""), path)
        fb_verified, fb_needs_update = self._get_feedback_counts(path)
        return compute_confidence(
            meta, backlink_count, owner_active,
            feedback_verified=fb_verified,
            feedback_needs_update=fb_needs_update,
        )

    def _get_file_meta(self, path: str) -> dict[str, Any]:
        """Read metadata for a file from MetadataIndex."""
        try:
            data = self._meta_index._load()
            files = data.get("files", {})
            entry = files.get(path, {})
            return self._enrich_meta(path, entry)
        except Exception as e:
            logger.debug(f"Failed to read meta for {path}: {e}")
            return {}

    def _enrich_meta(self, path: str, index_entry: dict) -> dict:
        """Enrich index metadata with fields from the actual file frontmatter."""
        from pathlib import Path
        import yaml

        result = dict(index_entry)
        file_path = Path(self._wiki_dir) / path
        if not file_path.exists():
            return result

        try:
            raw = file_path.read_text(encoding="utf-8")
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1]) or {}
                    for key in ("status", "updated", "created", "created_by", "updated_by",
                                "supersedes", "superseded_by"):
                        if key in fm and fm[key]:
                            result[key] = str(fm[key])
        except Exception:
            pass
        return result

    def _get_backlink_count(self, path: str) -> int:
        """Count backlinks pointing to this file from MetadataIndex data.

        Counts how many other documents list `path` in their `related` field.
        """
        try:
            data = self._meta_index._load()
            files = data.get("files", {})
            count = 0
            for fp, entry in files.items():
                if fp == path:
                    continue
                related = entry.get("related") or []
                if path in related:
                    count += 1
            return count
        except Exception:
            return 0

    def _is_owner_active(self, created_by: str, exclude_path: str) -> bool:
        """Check if the owner has edited any document in the last 90 days.

        Scans MetadataIndex for files where `updated_by` matches `created_by`
        and `updated` timestamp is within OWNER_ACTIVE_DAYS.
        """
        if not created_by:
            return False
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=OWNER_ACTIVE_DAYS)
            data = self._meta_index._load()
            files = data.get("files", {})
            for fp, entry in files.items():
                if fp == exclude_path:
                    continue
                if entry.get("updated_by") != created_by:
                    continue
                updated_str = entry.get("updated", "")
                if not updated_str:
                    continue
                updated_dt = self._parse_date(updated_str)
                if updated_dt and updated_dt >= cutoff:
                    return True
            return False
        except Exception:
            return False

    def _get_feedback_counts(self, path: str) -> tuple[int, int]:
        """Return (verified_count, needs_update_count) from feedback tracker."""
        if not self._feedback_tracker:
            return 0, 0
        try:
            summary = self._feedback_tracker.get_feedback_summary(path)
            return summary.verified_count, summary.needs_update_count
        except Exception:
            return 0, 0

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Parse ISO date string to timezone-aware datetime."""
        try:
            from dateutil.parser import parse as dateutil_parse
            dt = dateutil_parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
