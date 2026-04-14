"""Knowledge Graph Builder — converts existing data sources into Relationships.

Sources:
1. MetadataIndex: related, supersedes/superseded_by fields → "related", "supersedes"
2. ConflictStore: conflict pairs → "conflicts"
3. CitationTracker: citation counts → "cites" (from AI answers)
4. FeedbackTracker: not a relationship source (feeds into confidence)

The builder can do a full rebuild or incremental updates for a single file.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.core.schemas import Relationship
from backend.application.graph.graph_store import GraphStore

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Populates GraphStore from existing data sources."""

    def __init__(
        self,
        graph_store: GraphStore,
        meta_index: Any,
        conflict_store: Any = None,
        citation_tracker: Any = None,
    ) -> None:
        self._store = graph_store
        self._meta_index = meta_index
        self._conflict_store = conflict_store
        self._citation_tracker = citation_tracker

    def rebuild_all(self) -> int:
        """Full rebuild: clear store and re-extract all relationships.

        Returns the number of relationships created.
        """
        self._store.clear()
        count = 0
        count += self._build_from_metadata()
        count += self._build_from_conflicts()
        logger.info(f"Graph rebuild complete: {count} relationships")
        return count

    def rebuild_file(self, path: str) -> int:
        """Incremental: remove all relationships for this file and re-extract.

        Returns the number of relationships created for this file.
        """
        self._store.remove_all(path)
        count = 0
        count += self._build_metadata_for_file(path)
        count += self._build_conflicts_for_file(path)
        return count

    # ── Metadata source ──────────────────────────────────────────────

    def _build_from_metadata(self) -> int:
        """Extract related + supersedes relationships from MetadataIndex."""
        try:
            data = self._meta_index._load()
        except Exception:
            return 0

        files = data.get("files", {})
        count = 0
        now = time.time()

        for path, entry in files.items():
            count += self._extract_metadata_rels(path, entry, now)

        return count

    def _build_metadata_for_file(self, path: str) -> int:
        """Extract metadata relationships for a single file."""
        try:
            data = self._meta_index._load()
        except Exception:
            return 0

        entry = data.get("files", {}).get(path)
        if not entry:
            return 0

        return self._extract_metadata_rels(path, entry, time.time())

    def _extract_metadata_rels(self, path: str, entry: dict, now: float) -> int:
        count = 0
        created_by = entry.get("updated_by") or entry.get("created_by") or "system"

        # related field → bidirectional "related" relationships
        for target in entry.get("related") or []:
            self._store.add(Relationship(
                source=path,
                target=target,
                rel_type="related",
                strength=1.0,
                created_by=f"user:{created_by}",
                created_at=now,
            ))
            count += 1

        # supersedes field (from frontmatter via _enrich or index)
        supersedes = entry.get("supersedes", "")
        if supersedes:
            self._store.add(Relationship(
                source=path,
                target=supersedes,
                rel_type="supersedes",
                strength=1.0,
                created_by=f"user:{created_by}",
                created_at=now,
            ))
            count += 1

        return count

    # ── Conflict source ──────────────────────────────────────────────

    def _build_from_conflicts(self) -> int:
        """Extract conflict pairs from ConflictStore."""
        if not self._conflict_store:
            return 0

        try:
            pairs = self._conflict_store.get_all_pairs()
        except Exception:
            return 0

        count = 0
        for pair in pairs:
            if pair.resolved:
                continue  # skip resolved conflicts
            self._store.add(Relationship(
                source=pair.file_a,
                target=pair.file_b,
                rel_type="conflicts",
                strength=pair.similarity,
                created_by="ai:conflict_check",
                created_at=pair.detected_at or time.time(),
                metadata={
                    "conflict_type": pair.conflict_type,
                    "severity": pair.severity,
                },
            ))
            count += 1

        return count

    def _build_conflicts_for_file(self, path: str) -> int:
        """Extract conflict relationships involving a specific file."""
        if not self._conflict_store:
            return 0

        try:
            pairs = self._conflict_store.get_all_pairs()
        except Exception:
            return 0

        count = 0
        for pair in pairs:
            if pair.resolved:
                continue
            if pair.file_a == path or pair.file_b == path:
                self._store.add(Relationship(
                    source=pair.file_a,
                    target=pair.file_b,
                    rel_type="conflicts",
                    strength=pair.similarity,
                    created_by="ai:conflict_check",
                    created_at=pair.detected_at or time.time(),
                    metadata={
                        "conflict_type": pair.conflict_type,
                        "severity": pair.severity,
                    },
                ))
                count += 1

        return count
