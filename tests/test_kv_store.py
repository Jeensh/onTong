"""KVStore tests — both memory and Redis backends behave identically."""
from __future__ import annotations

import pytest


def _build_memory():
    from backend.infrastructure.kv.memory import MemoryKVStore
    return MemoryKVStore()


def _build_redis(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.kv.redis._build_client",
        lambda url: fake,
    )
    from backend.infrastructure.kv.redis import RedisKVStore
    return RedisKVStore(redis_url="redis://fake", namespace="test")


@pytest.fixture(params=["memory", "redis"])
def kv(request, monkeypatch):
    if request.param == "memory":
        return _build_memory()
    return _build_redis(monkeypatch)


def test_set_get(kv):
    kv.set("a", "1")
    assert kv.get("a") == "1"


def test_get_missing_returns_none(kv):
    assert kv.get("nope") is None


def test_delete(kv):
    kv.set("a", "1")
    kv.delete("a")
    assert kv.get("a") is None


def test_keys_with_prefix(kv):
    kv.set("foo:1", "a")
    kv.set("foo:2", "b")
    kv.set("bar:1", "c")
    assert sorted(kv.keys(prefix="foo:")) == ["foo:1", "foo:2"]


def test_clear(kv):
    kv.set("a", "1")
    kv.set("b", "2")
    kv.clear()
    assert kv.get("a") is None
    assert kv.get("b") is None
