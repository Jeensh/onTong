"""Singleton factory for infrastructure backends. Resolved once per process."""
from __future__ import annotations

import logging
from typing import Any

from backend.core.profile import Profile

logger = logging.getLogger(__name__)

_singletons: dict[str, Any] = {}


def _reset_for_test() -> None:
    """Clear cached backends — test-only helper."""
    _singletons.clear()


def get_lock_backend(profile: Profile, *, redis_url: str = ""):
    """Return a LockBackend matching the profile."""
    if "lock" in _singletons:
        return _singletons["lock"]

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

    _singletons["lock"] = backend
    logger.info(f"Lock backend initialized: {profile.lock_backend}")
    return backend
