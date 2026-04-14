"""Persistent conflict store — dual backend (InMemory + Redis).

Stores detected conflict pairs so the dashboard reads instantly
without recomputing similarity on every request.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StoredConflict:
    file_a: str  # canonical: min(a, b)
    file_b: str  # canonical: max(a, b)
    similarity: float
    detected_at: float
    meta_a: dict = field(default_factory=dict)
    meta_b: dict = field(default_factory=dict)
    # Phase 4: semantic analysis fields (populated by LLM analyze_pair)
    conflict_type: str = ""       # "factual_contradiction" | "scope_overlap" | "temporal" | "none"
    severity: str = ""            # "high" | "medium" | "low"
    summary_ko: str = ""
    claim_a: str = ""
    claim_b: str = ""
    suggested_resolution: str = ""  # "merge" | "scope_clarify" | "version_chain" | "dismiss"
    resolution_detail: str = ""
    analyzed_at: float = 0.0      # 0 = not yet analyzed
    resolved: bool = False
    resolved_by: str = ""
    resolved_action: str = ""


def _canonical_key(a: str, b: str) -> tuple[str, str]:
    return (min(a, b), max(a, b))


class ConflictStore(ABC):
    @abstractmethod
    def replace_for_file(self, file_path: str, pairs: list[StoredConflict]) -> None:
        """Delete all existing conflicts for file_path, then store new pairs."""

    @abstractmethod
    def remove_for_file(self, file_path: str) -> None:
        """Remove all conflicts referencing file_path."""

    @abstractmethod
    def get_all_pairs(self) -> list[StoredConflict]:
        """Return all stored conflict pairs sorted by similarity desc."""

    @abstractmethod
    def update_metadata(self, file_path: str, new_meta: dict) -> None:
        """Update stored metadata for all pairs involving file_path."""

    @abstractmethod
    def update_analysis(self, file_a: str, file_b: str, analysis: dict) -> bool:
        """Update semantic analysis fields for a conflict pair. Returns True if found."""

    @abstractmethod
    def resolve_pair(self, file_a: str, file_b: str, resolved_by: str, action: str) -> bool:
        """Mark a conflict pair as resolved. Returns True if found."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored conflicts."""


SIMILARITY_CHANGE_THRESHOLD = 0.05  # if similarity changes by more than this, reset resolved status


class InMemoryConflictStore(ConflictStore):
    def __init__(self) -> None:
        self._conflicts: dict[tuple[str, str], StoredConflict] = {}
        self._file_index: dict[str, set[tuple[str, str]]] = {}

    def replace_for_file(self, file_path: str, pairs: list[StoredConflict]) -> None:
        # Snapshot existing resolved/analyzed state before removal
        old_state: dict[tuple[str, str], StoredConflict] = {}
        for key in self._file_index.get(file_path, set()):
            old = self._conflicts.get(key)
            if old and (old.resolved or old.analyzed_at > 0):
                old_state[key] = old

        self.remove_for_file(file_path)
        for pair in pairs:
            key = _canonical_key(pair.file_a, pair.file_b)
            pair.file_a, pair.file_b = key

            # Restore resolved/analyzed state if content hasn't changed significantly
            prev = old_state.get(key)
            if prev:
                sim_delta = abs(pair.similarity - prev.similarity)
                if sim_delta < SIMILARITY_CHANGE_THRESHOLD:
                    # Content is essentially the same — preserve state
                    pair.resolved = prev.resolved
                    pair.resolved_by = prev.resolved_by
                    pair.resolved_action = prev.resolved_action
                    pair.conflict_type = prev.conflict_type
                    pair.severity = prev.severity
                    pair.summary_ko = prev.summary_ko
                    pair.claim_a = prev.claim_a
                    pair.claim_b = prev.claim_b
                    pair.suggested_resolution = prev.suggested_resolution
                    pair.resolution_detail = prev.resolution_detail
                    pair.analyzed_at = prev.analyzed_at
                # else: content changed significantly → fresh detection

            self._conflicts[key] = pair
            self._file_index.setdefault(pair.file_a, set()).add(key)
            self._file_index.setdefault(pair.file_b, set()).add(key)

    def remove_for_file(self, file_path: str) -> None:
        keys = self._file_index.pop(file_path, set()).copy()
        for key in keys:
            conflict = self._conflicts.pop(key, None)
            if conflict:
                other = conflict.file_b if conflict.file_a == file_path else conflict.file_a
                other_keys = self._file_index.get(other)
                if other_keys:
                    other_keys.discard(key)
                    if not other_keys:
                        del self._file_index[other]

    def get_all_pairs(self) -> list[StoredConflict]:
        pairs = list(self._conflicts.values())
        pairs.sort(key=lambda p: p.similarity, reverse=True)
        return pairs

    def update_metadata(self, file_path: str, new_meta: dict) -> None:
        keys = self._file_index.get(file_path, set())
        for key in keys:
            conflict = self._conflicts.get(key)
            if conflict:
                if conflict.file_a == file_path:
                    conflict.meta_a = new_meta
                else:
                    conflict.meta_b = new_meta

    def update_analysis(self, file_a: str, file_b: str, analysis: dict) -> bool:
        key = _canonical_key(file_a, file_b)
        conflict = self._conflicts.get(key)
        if not conflict:
            return False
        for field in ("conflict_type", "severity", "summary_ko", "claim_a", "claim_b",
                      "suggested_resolution", "resolution_detail", "analyzed_at"):
            if field in analysis:
                setattr(conflict, field, analysis[field])
        return True

    def resolve_pair(self, file_a: str, file_b: str, resolved_by: str, action: str) -> bool:
        key = _canonical_key(file_a, file_b)
        conflict = self._conflicts.get(key)
        if not conflict:
            return False
        conflict.resolved = True
        conflict.resolved_by = resolved_by
        conflict.resolved_action = action
        return True

    def clear(self) -> None:
        self._conflicts.clear()
        self._file_index.clear()


def _redis_conflict_key(file_a: str, file_b: str) -> str:
    """SHA256 hash key to avoid separator collision with file paths."""
    a, b = _canonical_key(file_a, file_b)
    raw = f"{a}\x00{b}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"ontong:conflict:{h}"


class RedisConflictStore(ConflictStore):
    INDEX_PREFIX = "ontong:conflict_idx:"

    def __init__(self, redis_url: str) -> None:
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        logger.info("Redis conflict store connected")

    def _serialize(self, c: StoredConflict) -> str:
        return json.dumps({
            "file_a": c.file_a,
            "file_b": c.file_b,
            "similarity": c.similarity,
            "detected_at": c.detected_at,
            "meta_a": c.meta_a,
            "meta_b": c.meta_b,
            "conflict_type": c.conflict_type,
            "severity": c.severity,
            "summary_ko": c.summary_ko,
            "claim_a": c.claim_a,
            "claim_b": c.claim_b,
            "suggested_resolution": c.suggested_resolution,
            "resolution_detail": c.resolution_detail,
            "analyzed_at": c.analyzed_at,
            "resolved": c.resolved,
            "resolved_by": c.resolved_by,
            "resolved_action": c.resolved_action,
        })

    def _deserialize(self, raw: str) -> StoredConflict:
        d = json.loads(raw)
        return StoredConflict(**d)

    def replace_for_file(self, file_path: str, pairs: list[StoredConflict]) -> None:
        pipe = self._redis.pipeline()

        # 1. Snapshot existing resolved/analyzed state before removal
        idx_key = f"{self.INDEX_PREFIX}{file_path}"
        old_keys = self._redis.smembers(idx_key)
        old_state: dict[tuple[str, str], dict] = {}
        for old_key in old_keys:
            raw = self._redis.get(old_key)
            if raw:
                data = json.loads(raw)
                if data.get("resolved") or data.get("analyzed_at", 0) > 0:
                    ckey = _canonical_key(data["file_a"], data["file_b"])
                    old_state[ckey] = data

        # 2. Delete old conflict keys and remove from other file's index
        for old_key in old_keys:
            raw = self._redis.get(old_key)
            if raw:
                data = json.loads(raw)
                other = data["file_b"] if data["file_a"] == file_path else data["file_a"]
                pipe.srem(f"{self.INDEX_PREFIX}{other}", old_key)
            pipe.delete(old_key)
        pipe.delete(idx_key)

        # 3. Store new pairs, preserving state for unchanged pairs
        for pair in pairs:
            a, b = _canonical_key(pair.file_a, pair.file_b)
            pair.file_a, pair.file_b = a, b

            prev = old_state.get((a, b))
            if prev:
                sim_delta = abs(pair.similarity - prev.get("similarity", 0))
                if sim_delta < SIMILARITY_CHANGE_THRESHOLD:
                    for field in ("resolved", "resolved_by", "resolved_action",
                                  "conflict_type", "severity", "summary_ko",
                                  "claim_a", "claim_b", "suggested_resolution",
                                  "resolution_detail", "analyzed_at"):
                        if field in prev:
                            setattr(pair, field, prev[field])

            rkey = _redis_conflict_key(a, b)
            pipe.set(rkey, self._serialize(pair))
            pipe.sadd(f"{self.INDEX_PREFIX}{a}", rkey)
            pipe.sadd(f"{self.INDEX_PREFIX}{b}", rkey)

        pipe.execute()

    def remove_for_file(self, file_path: str) -> None:
        idx_key = f"{self.INDEX_PREFIX}{file_path}"
        conflict_keys = self._redis.smembers(idx_key)
        if not conflict_keys:
            return

        pipe = self._redis.pipeline()
        for ckey in conflict_keys:
            raw = self._redis.get(ckey)
            if raw:
                data = json.loads(raw)
                other = data["file_b"] if data["file_a"] == file_path else data["file_a"]
                pipe.srem(f"{self.INDEX_PREFIX}{other}", ckey)
            pipe.delete(ckey)
        pipe.delete(idx_key)
        pipe.execute()

    def get_all_pairs(self) -> list[StoredConflict]:
        pairs: list[StoredConflict] = []
        seen: set[str] = set()
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match="ontong:conflict:*", count=100)
            for key in keys:
                if key.startswith(self.INDEX_PREFIX):
                    continue
                if key in seen:
                    continue
                seen.add(key)
                raw = self._redis.get(key)
                if raw:
                    pairs.append(self._deserialize(raw))
            if cursor == 0:
                break
        pairs.sort(key=lambda p: p.similarity, reverse=True)
        return pairs

    def update_metadata(self, file_path: str, new_meta: dict) -> None:
        idx_key = f"{self.INDEX_PREFIX}{file_path}"
        conflict_keys = self._redis.smembers(idx_key)
        if not conflict_keys:
            return

        pipe = self._redis.pipeline()
        for ckey in conflict_keys:
            raw = self._redis.get(ckey)
            if raw:
                data = json.loads(raw)
                if data["file_a"] == file_path:
                    data["meta_a"] = new_meta
                else:
                    data["meta_b"] = new_meta
                pipe.set(ckey, json.dumps(data))
        pipe.execute()

    def update_analysis(self, file_a: str, file_b: str, analysis: dict) -> bool:
        rkey = _redis_conflict_key(file_a, file_b)
        raw = self._redis.get(rkey)
        if not raw:
            return False
        data = json.loads(raw)
        for field in ("conflict_type", "severity", "summary_ko", "claim_a", "claim_b",
                      "suggested_resolution", "resolution_detail", "analyzed_at"):
            if field in analysis:
                data[field] = analysis[field]
        self._redis.set(rkey, json.dumps(data))
        return True

    def resolve_pair(self, file_a: str, file_b: str, resolved_by: str, action: str) -> bool:
        rkey = _redis_conflict_key(file_a, file_b)
        raw = self._redis.get(rkey)
        if not raw:
            return False
        data = json.loads(raw)
        data["resolved"] = True
        data["resolved_by"] = resolved_by
        data["resolved_action"] = action
        self._redis.set(rkey, json.dumps(data))
        return True

    def clear(self) -> None:
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match="ontong:conflict*", count=100)
            if keys:
                self._redis.delete(*keys)
            if cursor == 0:
                break


def create_conflict_store() -> ConflictStore:
    """Create conflict store with appropriate backend based on config."""
    from backend.core.config import settings
    if settings.redis_url:
        try:
            store = RedisConflictStore(settings.redis_url)
            return store
        except Exception as e:
            logger.warning(f"Redis conflict store failed, falling back to in-memory: {e}")
    return InMemoryConflictStore()
