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


def get_kv_store(profile: Profile, namespace: str, *, redis_url: str = ""):
    """Return a KVStore for the given namespace (e.g. 'hash', 'pending').

    Each namespace gets its own singleton.
    """
    cache_key = f"kv:{namespace}"
    cached = _singletons.get(cache_key)
    if cached is not None:
        cached_name, cached_obj = cached
        if cached_name != profile.kv_backend:
            raise RuntimeError(
                f"Profile changed mid-process: cached kv backend for {namespace!r} is {cached_name!r}, "
                f"requested {profile.kv_backend!r}. Call _reset_for_test() between switches."
            )
        return cached_obj

    if profile.kv_backend == "memory":
        from backend.infrastructure.kv.memory import MemoryKVStore
        store = MemoryKVStore()
    elif profile.kv_backend == "redis":
        from backend.infrastructure.kv.redis import RedisKVStore
        if not redis_url:
            raise RuntimeError("redis_url required for Redis KV store")
        store = RedisKVStore(redis_url, namespace=namespace)
    else:
        raise ValueError(f"unknown kv backend: {profile.kv_backend}")

    _singletons[cache_key] = (profile.kv_backend, store)
    return store


def get_metadata_index_backend(profile: Profile, *, legacy_path=None, redis_url: str = ""):
    """Return a MetadataBackend matching the profile."""
    cached = _singletons.get("metadata_index")
    if cached is not None:
        cached_name, cached_obj = cached
        if cached_name != profile.metadata_index_backend:
            raise RuntimeError(
                f"Profile changed mid-process: cached metadata_index backend is {cached_name!r}, "
                f"requested {profile.metadata_index_backend!r}. Call _reset_for_test() between switches."
            )
        return cached_obj

    if profile.metadata_index_backend == "json_file":
        from backend.application.metadata.backends.json_file import JsonFileBackend
        if legacy_path is None:
            raise RuntimeError("legacy_path required for json_file backend")
        backend = JsonFileBackend(legacy_path)
    elif profile.metadata_index_backend == "redis_hash":
        from backend.application.metadata.backends.redis_hash import RedisHashBackend
        if not redis_url:
            raise RuntimeError("redis_url required for redis_hash backend")
        backend = RedisHashBackend(redis_url)
    else:
        raise ValueError(f"unknown metadata_index backend: {profile.metadata_index_backend}")

    _singletons["metadata_index"] = (profile.metadata_index_backend, backend)
    logger.info(f"MetadataIndex backend initialized: {profile.metadata_index_backend}")
    return backend


def get_task_queue(profile: Profile, *, redis_url: str = ""):
    """Return a TaskQueue matching the profile."""
    cached = _singletons.get("task_queue")
    if cached is not None:
        cached_name, cached_obj = cached
        if cached_name != profile.task_queue_backend:
            raise RuntimeError(
                f"Profile changed mid-process: cached task_queue backend is {cached_name!r}, "
                f"requested {profile.task_queue_backend!r}. Call _reset_for_test() between switches."
            )
        return cached_obj

    if profile.task_queue_backend == "asyncio":
        from backend.infrastructure.queue.asyncio_queue import AsyncioTaskQueue
        q = AsyncioTaskQueue()
    elif profile.task_queue_backend == "arq":
        from backend.infrastructure.queue.arq_queue import ArqTaskQueue
        if not redis_url:
            raise RuntimeError("redis_url required for arq backend")
        q = ArqTaskQueue(redis_url)
    else:
        raise ValueError(f"unknown task_queue backend: {profile.task_queue_backend}")

    _singletons["task_queue"] = (profile.task_queue_backend, q)
    logger.info(f"TaskQueue backend initialized: {profile.task_queue_backend}")
    return q


def get_ref_index(profile: Profile, *, sqlite_path: str | None = None, postgres_dsn: str = ""):
    """Return a RefIndex matching the profile."""
    cached = _singletons.get("ref_index")
    if cached is not None:
        cached_name, cached_obj = cached
        if cached_name != profile.ref_index_backend:
            raise RuntimeError(
                f"Profile changed mid-process: cached ref_index backend is {cached_name!r}, "
                f"requested {profile.ref_index_backend!r}. Call _reset_for_test() between switches."
            )
        return cached_obj

    if profile.ref_index_backend == "sqlite":
        from backend.application.refindex.sqlite_backend import SqliteRefIndex
        if sqlite_path is None:
            raise RuntimeError("sqlite_path required for sqlite ref_index backend")
        index = SqliteRefIndex(sqlite_path)
    elif profile.ref_index_backend == "postgres":
        from backend.application.refindex.postgres_backend import PostgresRefIndex
        if not postgres_dsn:
            raise RuntimeError("postgres_dsn required for postgres ref_index backend")
        index = PostgresRefIndex(postgres_dsn)
    else:
        raise ValueError(f"unknown ref_index backend: {profile.ref_index_backend}")

    _singletons["ref_index"] = (profile.ref_index_backend, index)
    logger.info(f"RefIndex backend initialized: {profile.ref_index_backend}")
    return index
