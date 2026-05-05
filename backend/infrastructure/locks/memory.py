"""In-memory lock backend (single process)."""
from __future__ import annotations

import logging
from .lock_protocol import LockBackend, LockInfo, DEFAULT_TTL

logger = logging.getLogger(__name__)


class InMemoryLockBackend(LockBackend):
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
