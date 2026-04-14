"""Feedback Tracker — records user feedback on document quality.

Tracks "verified" (user confirms content is correct) and "needs_update"
(user flags content as outdated/incorrect) actions per document.
Used by confidence scoring and TrustBanner.

Storage: Redis (persistent) with InMemory fallback.
Follows CitationTracker pattern.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict

from pydantic import BaseModel

logger = logging.getLogger(__name__)

REDIS_PREFIX = "ontong:feedback:"
VALID_ACTIONS = {"verified", "needs_update", "thumbs_up", "thumbs_down"}


class FeedbackSummary(BaseModel):
    verified_count: int = 0
    needs_update_count: int = 0
    thumbs_up_count: int = 0
    thumbs_down_count: int = 0
    last_verified_at: float = 0.0
    last_verified_by: str = ""


class FeedbackStore(ABC):
    @abstractmethod
    def record(self, path: str, user: str, action: str) -> None: ...

    @abstractmethod
    def get_summary(self, path: str) -> FeedbackSummary: ...

    @abstractmethod
    def get_batch(self, paths: list[str]) -> dict[str, FeedbackSummary]: ...


class InMemoryFeedbackStore(FeedbackStore):
    def __init__(self) -> None:
        self._counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._last_verified: dict[str, tuple[float, str]] = {}

    def record(self, path: str, user: str, action: str) -> None:
        self._counts[path][action] += 1
        if action == "verified":
            self._last_verified[path] = (time.time(), user)

    def get_summary(self, path: str) -> FeedbackSummary:
        counts = self._counts.get(path, {})
        last = self._last_verified.get(path, (0.0, ""))
        return FeedbackSummary(
            verified_count=counts.get("verified", 0),
            needs_update_count=counts.get("needs_update", 0),
            thumbs_up_count=counts.get("thumbs_up", 0),
            thumbs_down_count=counts.get("thumbs_down", 0),
            last_verified_at=last[0],
            last_verified_by=last[1],
        )

    def get_batch(self, paths: list[str]) -> dict[str, FeedbackSummary]:
        return {p: self.get_summary(p) for p in paths}


class RedisFeedbackStore(FeedbackStore):
    def __init__(self, redis_url: str) -> None:
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        logger.info("Redis feedback store connected")

    def _key(self, path: str) -> str:
        return f"{REDIS_PREFIX}{path}"

    def record(self, path: str, user: str, action: str) -> None:
        key = self._key(path)
        self._redis.hincrby(key, action, 1)
        if action == "verified":
            self._redis.hset(key, "last_verified_at", str(time.time()))
            self._redis.hset(key, "last_verified_by", user)

    def get_summary(self, path: str) -> FeedbackSummary:
        data = self._redis.hgetall(self._key(path))
        if not data:
            return FeedbackSummary()
        return FeedbackSummary(
            verified_count=int(data.get("verified", 0)),
            needs_update_count=int(data.get("needs_update", 0)),
            thumbs_up_count=int(data.get("thumbs_up", 0)),
            thumbs_down_count=int(data.get("thumbs_down", 0)),
            last_verified_at=float(data.get("last_verified_at", 0)),
            last_verified_by=data.get("last_verified_by", ""),
        )

    def get_batch(self, paths: list[str]) -> dict[str, FeedbackSummary]:
        pipe = self._redis.pipeline()
        for p in paths:
            pipe.hgetall(self._key(p))
        results = pipe.execute()
        out: dict[str, FeedbackSummary] = {}
        for p, data in zip(paths, results):
            if not data:
                out[p] = FeedbackSummary()
            else:
                out[p] = FeedbackSummary(
                    verified_count=int(data.get("verified", 0)),
                    needs_update_count=int(data.get("needs_update", 0)),
                    thumbs_up_count=int(data.get("thumbs_up", 0)),
                    thumbs_down_count=int(data.get("thumbs_down", 0)),
                    last_verified_at=float(data.get("last_verified_at", 0)),
                    last_verified_by=data.get("last_verified_by", ""),
                )
        return out


class FeedbackTracker:
    """Facade for feedback recording — auto-selects Redis or InMemory."""

    def __init__(self, store: FeedbackStore) -> None:
        self._store = store

    def record_feedback(self, path: str, user: str, action: str) -> FeedbackSummary:
        """Record a feedback action and return updated summary."""
        if action not in VALID_ACTIONS:
            raise ValueError(f"Invalid action: {action}. Must be one of {VALID_ACTIONS}")
        self._store.record(path, user, action)
        return self._store.get_summary(path)

    def get_feedback_summary(self, path: str) -> FeedbackSummary:
        return self._store.get_summary(path)

    def get_batch(self, paths: list[str]) -> dict[str, FeedbackSummary]:
        return self._store.get_batch(paths)


def create_feedback_tracker() -> FeedbackTracker:
    """Create FeedbackTracker with appropriate backend."""
    from backend.core.config import settings
    if settings.redis_url:
        try:
            store = RedisFeedbackStore(settings.redis_url)
            return FeedbackTracker(store)
        except Exception as e:
            logger.warning(f"Redis feedback store failed, falling back to in-memory: {e}")
    return FeedbackTracker(InMemoryFeedbackStore())
