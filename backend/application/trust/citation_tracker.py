"""Citation Tracker — counts how many times each document is cited in AI answers.

Used by TrustBanner to show "AI 답변에서 N회 인용됨" and by confidence
scoring as a positive quality signal.

Storage: Redis (persistent) with InMemory fallback.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict

logger = logging.getLogger(__name__)

REDIS_PREFIX = "ontong:citations:"


class CitationStore(ABC):
    @abstractmethod
    def record(self, path: str) -> None: ...

    @abstractmethod
    def get_count(self, path: str) -> int: ...

    @abstractmethod
    def get_batch(self, paths: list[str]) -> dict[str, int]: ...


class InMemoryCitationStore(CitationStore):
    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)

    def record(self, path: str) -> None:
        self._counts[path] += 1

    def get_count(self, path: str) -> int:
        return self._counts.get(path, 0)

    def get_batch(self, paths: list[str]) -> dict[str, int]:
        return {p: self._counts.get(p, 0) for p in paths}


class RedisCitationStore(CitationStore):
    def __init__(self, redis_url: str) -> None:
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        logger.info("Redis citation store connected")

    def record(self, path: str) -> None:
        self._redis.incr(f"{REDIS_PREFIX}{path}")

    def get_count(self, path: str) -> int:
        val = self._redis.get(f"{REDIS_PREFIX}{path}")
        return int(val) if val else 0

    def get_batch(self, paths: list[str]) -> dict[str, int]:
        if not paths:
            return {}
        keys = [f"{REDIS_PREFIX}{p}" for p in paths]
        values = self._redis.mget(keys)
        return {p: int(v) if v else 0 for p, v in zip(paths, values)}


class CitationTracker:
    """Facade for citation counting — auto-selects Redis or InMemory."""

    def __init__(self, store: CitationStore) -> None:
        self._store = store

    def record_citation(self, path: str) -> None:
        """Increment citation count for a document."""
        self._store.record(path)

    def record_citations(self, paths: list[str]) -> None:
        """Increment citation count for multiple documents."""
        for p in paths:
            self._store.record(p)

    def get_count(self, path: str) -> int:
        return self._store.get_count(path)

    def get_batch(self, paths: list[str]) -> dict[str, int]:
        return self._store.get_batch(paths)


def create_citation_tracker() -> CitationTracker:
    """Create CitationTracker with appropriate backend."""
    from backend.core.config import settings
    if settings.redis_url:
        try:
            store = RedisCitationStore(settings.redis_url)
            return CitationTracker(store)
        except Exception as e:
            logger.warning(f"Redis citation store failed, falling back to in-memory: {e}")
    return CitationTracker(InMemoryCitationStore())
