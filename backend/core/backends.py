"""Singleton factory for infrastructure backends. Resolved once per process."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.core.profile import Profile

if TYPE_CHECKING:
    from backend.infrastructure.locks.base import LockBackend

logger = logging.getLogger(__name__)

_singletons: dict[str, Any] = {}


def _reset_for_test() -> None:
    """Clear cached backends — test-only helper."""
    _singletons.clear()


def get_lock_backend(profile: Profile, *, redis_url: str = "") -> "LockBackend":
    """Return a LockBackend matching the profile."""
    cached = _singletons.get("lock")
    if cached is not None:
        cached_name, cached_obj = cached
        if cached_name != profile.lock_backend:
            raise RuntimeError(
                f"Profile changed mid-process: cached lock backend is {cached_name!r}, "
                f"requested {profile.lock_backend!r}. Call _reset_for_test() between switches."
            )
        return cached_obj

    if profile.lock_backend == "memory":
        from backend.infrastructure.locks.memory import InMemoryLockBackend
        backend = InMemoryLockBackend()
    elif profile.lock_backend == "redis":
        from backend.infrastructure.locks.redis import RedisLockBackend
        if not redis_url:
            raise RuntimeError("redis_url required for Redis lock backend")
        backend = RedisLockBackend(redis_url)
    else:
        raise ValueError(f"unknown lock backend: {profile.lock_backend}")

    _singletons["lock"] = (profile.lock_backend, backend)
    logger.info(f"Lock backend initialized: {profile.lock_backend}")
    return backend
