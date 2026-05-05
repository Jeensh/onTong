"""Snapshot store tests, parametrized over sqlite (postgres requires running DB — skip in CI)."""
from __future__ import annotations

import time

import pytest


@pytest.fixture(params=["sqlite"])
def store(request, tmp_path):
    from backend.application.snapshot.sqlite_store import SqliteSnapshotStore
    return SqliteSnapshotStore(str(tmp_path / "snap.db"))


def test_append_and_list(store):
    store.append("a.md", "v1 body", "01H000", "alice", "save")
    items = store.list("a.md")
    assert len(items) == 1
    assert items[0].version == "01H000"


def test_get_content_round_trip(store):
    store.append("a.md", "hello world", "01H000", "alice", "save")
    assert store.get_content("a.md", "01H000") == "hello world"


def test_get_missing_returns_none(store):
    assert store.get_content("a.md", "nope") is None


def test_list_most_recent_first(store):
    store.append("a.md", "v1", "01H001", "alice", "save")
    time.sleep(0.01)
    store.append("a.md", "v2", "01H002", "bob", "save")
    items = store.list("a.md")
    assert items[0].version == "01H002"
    assert items[1].version == "01H001"


def test_sliding_window_keeps_only_N(store):
    """N=20 retention enforced automatically."""
    for i in range(25):
        store.append("a.md", f"v{i}", f"01H{i:03d}", "alice", "save")
    items = store.list("a.md", limit=100)
    assert len(items) == 20
    versions = [s.version for s in items]
    # Most recent 20 retained → indices 24..5
    assert versions[0] == "01H024"
    assert versions[-1] == "01H005"


def test_delete_for_path(store):
    store.append("a.md", "v1", "01H001", "alice", "save")
    store.append("b.md", "v1", "01H002", "alice", "save")
    n = store.delete_for_path("a.md")
    assert n == 1
    assert store.list("a.md") == []
    assert len(store.list("b.md")) == 1


def test_unicode_content(store):
    store.append("doc.md", "한글 내용", "01H100", "alice", "save")
    assert store.get_content("doc.md", "01H100") == "한글 내용"


def test_factory_dev(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib
    import backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.backends import get_snapshot_store, _reset_for_test
    _reset_for_test()
    from backend.core.config import settings
    profile = settings.resolve_profile()
    assert profile.snapshot_backend == "sqlite"
    store = get_snapshot_store(profile, sqlite_path=str(tmp_path / "x.db"))
    from backend.application.snapshot.sqlite_store import SqliteSnapshotStore
    assert isinstance(store, SqliteSnapshotStore)
    _reset_for_test()
