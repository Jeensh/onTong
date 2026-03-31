"""Document lock service for preventing concurrent edits.

Supports two backends:
- In-memory dict (default, for development / single worker)
- Redis (for production multi-worker, survives restarts)

Each lock has a TTL (default 5 minutes) and auto-expires.
Locks are per file path, held by a user identifier.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes


@dataclass
class LockInfo:
    path: str
    user: str
    acquired_at: float = field(default_factory=time.time)
    ttl: int = DEFAULT_TTL

    @property
    def is_expired(self) -> bool:
        return time.time() - self.acquired_at > self.ttl

    @property
    def remaining(self) -> int:
        r = self.ttl - (time.time() - self.acquired_at)
        return max(0, int(r))

    def refresh(self) -> None:
        self.acquired_at = time.time()

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "user": self.user,
            "acquired_at": self.acquired_at,
            "ttl": self.ttl,
            "remaining": self.remaining,
            "is_expired": self.is_expired,
        }


class LockBackend(ABC):
    @abstractmethod
    def acquire(self, path: str, user: str, ttl: int) -> LockInfo | None: ...

    @abstractmethod
    def release(self, path: str, user: str) -> bool: ...

    @abstractmethod
    def status(self, path: str) -> LockInfo | None: ...

    @abstractmethod
    def refresh(self, path: str, user: str) -> bool: ...

    @abstractmethod
    def release_all_by_user(self, user: str) -> int: ...

    def batch_refresh(self, paths: list[str], user: str) -> int:
        """Refresh multiple locks at once. Returns count refreshed."""
        count = 0
        for p in paths:
            if self.refresh(p, user):
                count += 1
        return count


class InMemoryLockBackend(LockBackend):
    """In-memory lock backend (single worker only)."""

    def __init__(self) -> None:
        self._locks: dict[str, LockInfo] = {}

    def acquire(self, path: str, user: str, ttl: int = DEFAULT_TTL) -> LockInfo | None:
        self._cleanup_expired()
        existing = self._locks.get(path)
        if existing and not existing.is_expired:
            if existing.user == user:
                existing.refresh()
                return existing
            return None
        lock = LockInfo(path=path, user=user, ttl=ttl)
        self._locks[path] = lock
        logger.info(f"Lock acquired: {path} by {user}")
        return lock

    def release(self, path: str, user: str) -> bool:
        existing = self._locks.get(path)
        if not existing:
            return True
        if existing.user != user and not existing.is_expired:
            return False
        del self._locks[path]
        logger.info(f"Lock released: {path} by {user}")
        return True

    def status(self, path: str) -> LockInfo | None:
        self._cleanup_expired()
        lock = self._locks.get(path)
        if lock and lock.is_expired:
            del self._locks[path]
            return None
        return lock

    def refresh(self, path: str, user: str) -> bool:
        lock = self._locks.get(path)
        if not lock or lock.is_expired:
            return False
        if lock.user != user:
            return False
        lock.refresh()
        return True

    def release_all_by_user(self, user: str) -> int:
        to_remove = [p for p, l in self._locks.items() if l.user == user]
        for path in to_remove:
            del self._locks[path]
        if to_remove:
            logger.info(f"Released {len(to_remove)} locks for user {user}")
        return len(to_remove)

    def _cleanup_expired(self) -> None:
        expired = [p for p, l in self._locks.items() if l.is_expired]
        for path in expired:
            logger.info(f"Lock expired: {path} (was held by {self._locks[path].user})")
            del self._locks[path]


class RedisLockBackend(LockBackend):
    """Redis-based lock backend (multi-worker, survives restarts)."""

    KEY_PREFIX = "ontong:lock:"
    USER_INDEX_PREFIX = "ontong:user_locks:"

    def __init__(self, redis_url: str) -> None:
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"Redis lock backend connected: {redis_url}")

    def _key(self, path: str) -> str:
        return f"{self.KEY_PREFIX}{path}"

    def acquire(self, path: str, user: str, ttl: int = DEFAULT_TTL) -> LockInfo | None:
        key = self._key(path)
        now = time.time()
        lock_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})

        # Try atomic SET NX (only if key doesn't exist)
        if self._redis.set(key, lock_data, nx=True, ex=ttl):
            # Track user's locks for release_all_by_user
            self._redis.sadd(f"{self.USER_INDEX_PREFIX}{user}", path)
            logger.info(f"Lock acquired (Redis): {path} by {user}")
            return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)

        # Key exists — check if same user (refresh) or different user (blocked)
        existing_raw = self._redis.get(key)
        if not existing_raw:
            # Race: key expired between SET NX and GET — retry
            if self._redis.set(key, lock_data, nx=True, ex=ttl):
                self._redis.sadd(f"{self.USER_INDEX_PREFIX}{user}", path)
                return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)
            return None

        existing = json.loads(existing_raw)
        if existing["user"] == user:
            # Same user — refresh
            self._redis.set(key, lock_data, ex=ttl)
            return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)

        # Held by another user
        return None

    def release(self, path: str, user: str) -> bool:
        key = self._key(path)
        existing_raw = self._redis.get(key)
        if not existing_raw:
            return True  # No lock

        existing = json.loads(existing_raw)
        if existing["user"] != user:
            return False  # Can't release someone else's lock

        self._redis.delete(key)
        self._redis.srem(f"{self.USER_INDEX_PREFIX}{user}", path)
        logger.info(f"Lock released (Redis): {path} by {user}")
        return True

    def status(self, path: str) -> LockInfo | None:
        raw = self._redis.get(self._key(path))
        if not raw:
            return None
        data = json.loads(raw)
        return LockInfo(
            path=path,
            user=data["user"],
            acquired_at=data["acquired_at"],
            ttl=data["ttl"],
        )

    def refresh(self, path: str, user: str) -> bool:
        key = self._key(path)
        raw = self._redis.get(key)
        if not raw:
            return False
        data = json.loads(raw)
        if data["user"] != user:
            return False
        now = time.time()
        ttl = data["ttl"]
        new_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})
        self._redis.set(key, new_data, ex=ttl)
        return True

    def release_all_by_user(self, user: str) -> int:
        index_key = f"{self.USER_INDEX_PREFIX}{user}"
        paths = self._redis.smembers(index_key)
        count = 0
        for path in paths:
            key = self._key(path)
            raw = self._redis.get(key)
            if raw:
                data = json.loads(raw)
                if data["user"] == user:
                    self._redis.delete(key)
                    count += 1
        self._redis.delete(index_key)
        if count:
            logger.info(f"Released {count} locks for user {user} (Redis)")
        return count

    def batch_refresh(self, paths: list[str], user: str) -> int:
        """Optimized batch refresh using Redis pipeline."""
        pipe = self._redis.pipeline()
        for path in paths:
            pipe.get(self._key(path))
        results = pipe.execute()

        now = time.time()
        refresh_pipe = self._redis.pipeline()
        count = 0
        for path, raw in zip(paths, results):
            if not raw:
                continue
            data = json.loads(raw)
            if data["user"] != user:
                continue
            ttl = data["ttl"]
            new_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})
            refresh_pipe.set(self._key(path), new_data, ex=ttl)
            count += 1
        if count:
            refresh_pipe.execute()
        return count


class LockService:
    """Lock service facade — delegates to backend (in-memory or Redis)."""

    def __init__(self, backend: LockBackend | None = None) -> None:
        self._backend = backend or InMemoryLockBackend()

    def acquire(self, path: str, user: str, ttl: int = DEFAULT_TTL) -> LockInfo | None:
        return self._backend.acquire(path, user, ttl)

    def release(self, path: str, user: str) -> bool:
        return self._backend.release(path, user)

    def status(self, path: str) -> LockInfo | None:
        return self._backend.status(path)

    def refresh(self, path: str, user: str) -> bool:
        return self._backend.refresh(path, user)

    def release_all_by_user(self, user: str) -> int:
        return self._backend.release_all_by_user(user)

    def batch_refresh(self, paths: list[str], user: str) -> int:
        return self._backend.batch_refresh(paths, user)


def create_lock_service() -> LockService:
    """Create lock service with appropriate backend based on config."""
    from backend.core.config import settings
    if settings.redis_url:
        try:
            backend = RedisLockBackend(settings.redis_url)
            logger.info("Using Redis lock backend")
            return LockService(backend)
        except Exception as e:
            logger.warning(f"Redis connection failed, falling back to in-memory: {e}")
    logger.info("Using in-memory lock backend")
    return LockService(InMemoryLockBackend())


# Singleton — created lazily
_lock_service: LockService | None = None


def get_lock_service() -> LockService:
    global _lock_service
    if _lock_service is None:
        _lock_service = create_lock_service()
    return _lock_service


# Backward compatibility
lock_service = property(lambda self: get_lock_service())
