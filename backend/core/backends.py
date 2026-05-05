"""Singleton factory for infrastructure backends. Resolved once per process."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.core.profile import Profile

if TYPE_CHECKING:
    from backend.infrastructure.locks.base import LockBackend
    from backend.infrastructure.events.event_bus_inproc import InProcessEventBus
    from backend.infrastructure.events.event_bus_redis import RedisEventBus
    EventBusLike = "InProcessEventBus | RedisEventBus"

logger = logging.getLogger(__name__)

_singletons: dict[str, Any] = {}


def _reset_for_test() -> None:
    """Clear cached backends — test-only helper.

    Also resets the event_bus proxy's _impl so subsequent attribute access
    re-resolves through this factory.
    """
    _singletons.clear()
    try:
        from backend.infrastructure.events.event_bus import event_bus
        event_bus._impl = None
    except Exception:
        # Module not loaded yet — nothing to reset
        pass


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


def get_event_bus(profile: Profile, *, redis_url: str = "") -> "EventBusLike":
    """Return an EventBus matching the profile."""
    cached = _singletons.get("event_bus")
    if cached is not None:
        cached_name, cached_obj = cached
        if cached_name != profile.event_bus_backend:
            raise RuntimeError(
                f"Profile changed mid-process: cached event_bus backend is {cached_name!r}, "
                f"requested {profile.event_bus_backend!r}. Call _reset_for_test() between switches."
            )
        return cached_obj

    if profile.event_bus_backend == "inproc":
        from backend.infrastructure.events.event_bus_inproc import InProcessEventBus
        bus = InProcessEventBus()
    elif profile.event_bus_backend == "redis_pubsub":
        from backend.infrastructure.events.event_bus_redis import RedisEventBus
        if not redis_url:
            raise RuntimeError("redis_url required for redis_pubsub event bus")
        bus = RedisEventBus(redis_url)
    else:
        raise ValueError(f"unknown event bus backend: {profile.event_bus_backend}")

    _singletons["event_bus"] = (profile.event_bus_backend, bus)
    logger.info(f"EventBus backend initialized: {profile.event_bus_backend}")
    return bus
