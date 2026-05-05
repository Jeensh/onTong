"""Lock backend integration with Profile."""
from __future__ import annotations

import pytest
from backend.core.profile import Profile
from backend.core.backends import get_lock_backend, _reset_for_test


@pytest.fixture(autouse=True)
def reset_backends():
    _reset_for_test()
    yield
    _reset_for_test()


def test_dev_profile_returns_inmemory_lock():
    p = Profile(
        name="dev", lock_backend="memory", event_bus_backend="inproc",
        metadata_index_backend="json_file", kv_backend="memory",
        task_queue_backend="asyncio", fulltext_backend="bm25_inmem",
    )
    backend = get_lock_backend(p)
    from backend.infrastructure.locks.memory import InMemoryLockBackend
    assert isinstance(backend, InMemoryLockBackend)


def test_team_profile_returns_redis_lock(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.locks.redis._build_client",
        lambda url: fake,
    )
    p = Profile(
        name="team", lock_backend="redis", event_bus_backend="redis_pubsub",
        metadata_index_backend="redis_hash", kv_backend="redis",
        task_queue_backend="arq", fulltext_backend="bm25_inmem",
    )
    backend = get_lock_backend(p, redis_url="redis://fake")
    from backend.infrastructure.locks.redis import RedisLockBackend
    assert isinstance(backend, RedisLockBackend)


def test_acquire_release_via_factory():
    p = Profile(
        name="dev", lock_backend="memory", event_bus_backend="inproc",
        metadata_index_backend="json_file", kv_backend="memory",
        task_queue_backend="asyncio", fulltext_backend="bm25_inmem",
    )
    backend = get_lock_backend(p)
    lock = backend.acquire("test/path", "alice", ttl=5)
    assert lock is not None
    assert lock.user == "alice"
    assert backend.release("test/path", "alice") is True
