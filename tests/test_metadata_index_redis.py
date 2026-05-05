"""MetadataIndex backend equivalence tests."""
from __future__ import annotations

import pytest


def _build_json_file(tmp_path):
    from backend.application.metadata.backends.json_file import JsonFileBackend
    return JsonFileBackend(tmp_path / "metadata_index.json")


def _build_redis(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.application.metadata.backends.redis_hash._build_client",
        lambda url: fake,
    )
    from backend.application.metadata.backends.redis_hash import RedisHashBackend
    return RedisHashBackend(redis_url="redis://fake")


@pytest.fixture(params=["json_file", "redis"])
def backend(request, tmp_path, monkeypatch):
    if request.param == "json_file":
        return _build_json_file(tmp_path)
    return _build_redis(monkeypatch)


def test_save_load_round_trip(backend):
    data = {
        "files": {"a.md": {"domain": "ops", "tags": ["x"]}},
        "tags": {"x": 1},
    }
    backend.save(data)
    loaded = backend.load()
    assert loaded == data


def test_load_empty_returns_default(backend):
    loaded = backend.load()
    # Both backends return the empty default shape
    assert loaded.get("files") == {}
