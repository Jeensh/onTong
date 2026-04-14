"""Conflict Detection Service — incremental per-save detection via ChromaDB HNSW.

Instead of loading all embeddings and computing O(n²) similarity,
each document save queries ChromaDB's HNSW index (~50ms) and stores
results in a persistent conflict store (Redis or InMemory).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

import numpy as np
from pydantic import BaseModel

from backend.infrastructure.vectordb.chroma import ChromaWrapper
from .conflict_store import ConflictStore, StoredConflict
from backend.core.auth.scope import build_scope_where_clause

logger = logging.getLogger(__name__)

from backend.application.trust.scoring_config import SCORING as _SCORING

SIMILARITY_THRESHOLD = _SCORING.conflict.similarity_threshold
HNSW_N_RESULTS = _SCORING.conflict.hnsw_n_results
MAX_RESULTS = _SCORING.conflict.max_results


class DuplicatePair(BaseModel):
    """A pair of documents with high embedding similarity."""
    file_a: str
    file_b: str
    similarity: float
    meta_a: dict = {}
    meta_b: dict = {}
    resolved: bool = False


def is_pair_resolved(
    file_a: str, file_b: str, meta_a: dict, meta_b: dict
) -> bool:
    """Check if a duplicate pair is resolved via superseded_by lineage."""
    a_superseded_by = meta_a.get("superseded_by", "")
    b_superseded_by = meta_b.get("superseded_by", "")
    a_supersedes = meta_a.get("supersedes", "")
    b_supersedes = meta_b.get("supersedes", "")

    if a_superseded_by == file_b or b_superseded_by == file_a:
        return True
    if a_supersedes == file_b or b_supersedes == file_a:
        return True
    return False


class ConflictDetectionService:
    """Detects duplicate/similar documents incrementally on save."""

    def __init__(self, chroma: ChromaWrapper, store: ConflictStore) -> None:
        self.chroma = chroma
        self.store = store
        self._scan_state: dict = {"running": False, "progress": 0, "total": 0}

    def check_file(
        self,
        file_path: str,
        threshold: float = SIMILARITY_THRESHOLD,
        user_scope: list[str] | None = None,
    ) -> list[StoredConflict]:
        """Check one file against all others via ChromaDB HNSW query.

        Called after indexing completes for a file.
        HNSW returns chunk-level results, so we use it to find candidate files,
        then compute avg-to-avg cosine similarity for accurate file-level comparison.

        Args:
            file_path: The file to check against all others.
            threshold: Cosine similarity threshold for conflict detection.
            user_scope: Optional ACL scope list for filtering candidates.
                        If provided, only candidates readable by this scope are considered.
        """
        try:
            data = self.chroma.get_file_embeddings(file_path)
            embeddings = data.get("embeddings", [])
            metadatas = data.get("metadatas", [])

            if embeddings is None or len(embeddings) == 0:
                self.store.replace_for_file(file_path, [])
                return []

            # Compute average embedding for this file
            avg_embedding = np.mean(embeddings, axis=0)

            # Build scope where clause for HNSW candidate query
            scope_where: dict | None = None
            if user_scope:
                scope_where = build_scope_where_clause(user_scope)

            # Query HNSW for similar chunks (candidate discovery)
            results = self.chroma.query_by_embedding(
                avg_embedding.tolist(), n_results=HNSW_N_RESULTS, where=scope_where
            )

            result_metadatas = results.get("metadatas", [[]])[0]

            if not result_metadatas:
                self.store.replace_for_file(file_path, [])
                return []

            # Collect unique candidate file paths from HNSW results
            candidate_files: set[str] = set()
            candidate_meta: dict[str, dict] = {}
            for meta in result_metadatas:
                fp = meta.get("file_path", "")
                if fp and fp != file_path:
                    candidate_files.add(fp)
                    if fp not in candidate_meta:
                        candidate_meta[fp] = meta

            # For each candidate, get its average embedding and compute accurate similarity
            avg_norm = np.linalg.norm(avg_embedding)
            if avg_norm == 0:
                self.store.replace_for_file(file_path, [])
                return []

            now = time.time()
            file_meta = metadatas[0] if metadatas else {}

            pairs: list[StoredConflict] = []
            for other_path in candidate_files:
                other_data = self.chroma.get_file_embeddings(other_path)
                other_embs = other_data.get("embeddings", [])
                if other_embs is None or len(other_embs) == 0:
                    continue

                other_avg = np.mean(other_embs, axis=0)
                other_norm = np.linalg.norm(other_avg)
                if other_norm == 0:
                    continue

                # Cosine similarity between file averages
                sim = float(np.dot(avg_embedding, other_avg) / (avg_norm * other_norm))

                if sim >= threshold:
                    other_meta = candidate_meta.get(other_path, other_data.get("metadatas", [{}])[0])
                    pairs.append(StoredConflict(
                        file_a=file_path,
                        file_b=other_path,
                        similarity=round(sim, 4),
                        detected_at=now,
                        meta_a=file_meta,
                        meta_b=other_meta,
                    ))

            self.store.replace_for_file(file_path, pairs)
            if pairs:
                logger.info(f"Conflict check: {file_path} → {len(pairs)} conflicts found")
            return pairs

        except Exception as e:
            logger.warning(f"Conflict check failed for {file_path}: {e}")
            return []

    def remove_file(self, file_path: str) -> None:
        """Remove all conflicts referencing a file (on delete/move)."""
        try:
            self.store.remove_for_file(file_path)
            logger.debug(f"Conflicts removed for: {file_path}")
        except Exception as e:
            logger.warning(f"Conflict removal failed for {file_path}: {e}")

    def update_metadata(self, file_path: str, new_meta: dict) -> None:
        """Update stored metadata for a file (on deprecation)."""
        try:
            self.store.update_metadata(file_path, new_meta)
        except Exception as e:
            logger.warning(f"Conflict metadata update failed for {file_path}: {e}")

    def full_scan(
        self,
        threshold: float = SIMILARITY_THRESHOLD,
        progress_callback=None,
    ) -> list[StoredConflict]:
        """Scan all files and populate the conflict store.

        Used for initial population or recovery.
        """
        self._scan_state = {"running": True, "progress": 0, "total": 0}
        try:
            # Get all unique file paths from ChromaDB
            data = self.chroma.get_all_embeddings()
            metadatas = data.get("metadatas", [])
            file_paths = list({m.get("file_path", "") for m in metadatas if m.get("file_path")})
            self._scan_state["total"] = len(file_paths)

            for i, fp in enumerate(file_paths):
                self.check_file(fp, threshold)
                self._scan_state["progress"] = i + 1
                if progress_callback:
                    progress_callback(i + 1, len(file_paths))

            all_pairs = self.store.get_all_pairs()
            logger.info(f"Full scan complete: {len(file_paths)} files, {len(all_pairs)} conflicts")
            return all_pairs
        except Exception as e:
            logger.error(f"Full scan failed: {e}")
            return []
        finally:
            self._scan_state = {"running": False, "progress": 0, "total": 0}

    def get_scan_state(self) -> dict:
        return dict(self._scan_state)

    def get_pairs(
        self,
        filter_mode: str = "unresolved",
        threshold: float | None = None,
    ) -> list[DuplicatePair]:
        """Read stored conflicts and return as DuplicatePairs.

        Computes resolved status from stored metadata (no ChromaDB query).
        """
        stored = self.store.get_all_pairs()

        pairs: list[DuplicatePair] = []
        for sc in stored:
            if threshold and sc.similarity < threshold:
                continue

            resolved = is_pair_resolved(sc.file_a, sc.file_b, sc.meta_a, sc.meta_b)

            if filter_mode == "unresolved" and resolved:
                continue
            if filter_mode == "resolved" and not resolved:
                continue

            pairs.append(DuplicatePair(
                file_a=sc.file_a,
                file_b=sc.file_b,
                similarity=sc.similarity,
                meta_a=sc.meta_a,
                meta_b=sc.meta_b,
                resolved=resolved,
            ))

        if len(pairs) > MAX_RESULTS:
            pairs = pairs[:MAX_RESULTS]

        return pairs

    def get_typed_pairs(
        self,
        filter_mode: str = "unresolved",
    ) -> list[dict]:
        """Return stored conflicts as TypedConflict-compatible dicts.

        Only returns pairs that have been semantically analyzed (analyzed_at > 0).
        """
        stored = self.store.get_all_pairs()
        results: list[dict] = []
        for sc in stored:
            if filter_mode == "unresolved" and sc.resolved:
                continue
            if filter_mode == "resolved" and not sc.resolved:
                continue
            results.append({
                "file_a": sc.file_a,
                "file_b": sc.file_b,
                "conflict_type": sc.conflict_type or "none",
                "severity": sc.severity or "low",
                "summary_ko": sc.summary_ko,
                "claim_a": sc.claim_a,
                "claim_b": sc.claim_b,
                "suggested_resolution": sc.suggested_resolution or "dismiss",
                "resolution_detail": sc.resolution_detail,
                "analyzed_at": sc.analyzed_at,
                "resolved": sc.resolved,
                "resolved_by": sc.resolved_by,
                "resolved_action": sc.resolved_action,
                "similarity": sc.similarity,
            })
        return results

    def resolve_pair(self, file_a: str, file_b: str, resolved_by: str, action: str) -> bool:
        """Mark a conflict pair as resolved."""
        return self.store.resolve_pair(file_a, file_b, resolved_by, action)

    def update_analysis(self, file_a: str, file_b: str, analysis: dict) -> bool:
        """Update semantic analysis for a conflict pair."""
        return self.store.update_analysis(file_a, file_b, analysis)

    async def trigger_deep_analysis(self, file_path: str, max_pairs: int = 3) -> int:
        """Run LLM semantic analysis on top conflict pairs for a file.

        Called asynchronously after check_file(). Returns number of pairs analyzed.
        """
        stored = self.store.get_all_pairs()
        # Filter to pairs involving this file, high similarity, not yet analyzed
        candidates = [
            sc for sc in stored
            if (sc.file_a == file_path or sc.file_b == file_path)
            and sc.similarity >= 0.9
            and sc.analyzed_at == 0.0
        ]
        candidates.sort(key=lambda s: s.similarity, reverse=True)
        candidates = candidates[:max_pairs]

        if not candidates:
            return 0

        from backend.application.agent.skills.conflict_check import ConflictCheckSkill

        analyzed = 0
        for sc in candidates:
            try:
                # Load document contents
                content_a = self._load_doc_content(sc.file_a)
                content_b = self._load_doc_content(sc.file_b)
                if not content_a or not content_b:
                    continue

                result = await ConflictCheckSkill.analyze_pair(
                    sc.file_a, content_a, sc.meta_a,
                    sc.file_b, content_b, sc.meta_b,
                )
                if result:
                    self.store.update_analysis(sc.file_a, sc.file_b, result)
                    analyzed += 1
                    logger.info(
                        f"Deep analysis: {sc.file_a} vs {sc.file_b} → {result.get('conflict_type', '?')}"
                    )
            except Exception as e:
                logger.warning(f"Deep analysis failed for {sc.file_a} vs {sc.file_b}: {e}")

        return analyzed

    def _load_doc_content(self, file_path: str) -> str:
        """Load document content from wiki storage (sync, for thread use)."""
        try:
            from pathlib import Path
            from backend.core.config import settings
            full_path = Path(settings.wiki_dir) / file_path
            if full_path.exists():
                return full_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to load {file_path}: {e}")
        return ""

    # Keep backward compatibility for old batch approach
    def find_duplicates(self, threshold: float = SIMILARITY_THRESHOLD) -> list[DuplicatePair]:
        """Legacy method — reads from store instead of computing."""
        return self.get_pairs(filter_mode="all", threshold=threshold)
