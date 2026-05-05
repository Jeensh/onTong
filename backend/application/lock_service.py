"""Document lock service — facade over LockBackend.

Backend selection is driven by ONTONG_PROFILE / ONTONG_LOCK_BACKEND.
See backend.infrastructure.locks for concrete implementations.
"""
from __future__ import annotations

import logging
from backend.infrastructure.locks.lock_protocol import LockInfo, LockBackend, DEFAULT_TTL

logger = logging.getLogger(__name__)


class LockService:
    """Lock service facade — delegates to backend selected by Profile."""

    def __init__(self, backend=None) -> None:
        if backend is None:
            from backend.core.config import settings
            from backend.core.backends import get_lock_backend
            profile = settings.resolve_profile()
            backend = get_lock_backend(profile, redis_url=settings.redis_url)
        self._backend = backend

    def acquire(self, path: str, user: str, ttl: int = DEFAULT_TTL):
        return self._backend.acquire(path, user, ttl)

    def release(self, path: str, user: str) -> bool:
        return self._backend.release(path, user)

    def status(self, path: str):
        return self._backend.status(path)

    def refresh(self, path: str, user: str) -> bool:
        return self._backend.refresh(path, user)

    def release_all_by_user(self, user: str) -> int:
        return self._backend.release_all_by_user(user)

    def batch_refresh(self, paths: list[str], user: str) -> int:
        return self._backend.batch_refresh(paths, user)


_lock_service: LockService | None = None


def get_lock_service() -> LockService:
    global _lock_service
    if _lock_service is None:
        _lock_service = LockService()
    return _lock_service
