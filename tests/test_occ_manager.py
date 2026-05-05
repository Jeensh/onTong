"""OCC manager + version store tests."""
from __future__ import annotations

import pytest
from backend.application.occ.manager import OCCManager, VersionConflict


@pytest.fixture
def store(tmp_path):
    from backend.application.occ.sqlite_store import SqliteVersionStore
    return SqliteVersionStore(str(tmp_path / "versions.db"))


def test_issue_creates_version(store):
    occ = OCCManager(store)
    v1 = occ.issue("a.md", updated_by="alice")
    assert v1
    assert occ.current("a.md") == v1


def test_advance_changes_version(store):
    occ = OCCManager(store)
    v1 = occ.issue("a.md")
    v2 = occ.advance("a.md")
    assert v2 != v1
    assert occ.current("a.md") == v2


def test_check_passes_when_match(store):
    occ = OCCManager(store)
    v1 = occ.issue("a.md")
    occ.check_or_raise("a.md", v1)  # no exception


def test_check_raises_on_mismatch(store):
    occ = OCCManager(store)
    v1 = occ.issue("a.md")
    occ.advance("a.md")  # server moved on
    with pytest.raises(VersionConflict) as exc:
        occ.check_or_raise("a.md", v1, server_content="server body", server_updated_by="bob")
    p = exc.value.payload
    assert p.base_version == v1
    assert p.server_version == occ.current("a.md")
    assert p.server_content == "server body"
    assert p.server_updated_by == "bob"


def test_check_passes_for_fresh_file(store):
    occ = OCCManager(store)
    occ.check_or_raise("never-existed.md", "ignored")  # no row, no expectation


def test_check_skipped_when_expected_none(store):
    occ = OCCManager(store)
    occ.issue("a.md")
    occ.advance("a.md")
    occ.check_or_raise("a.md", None)  # legacy caller


def test_lazy_version_for_existing(store):
    occ = OCCManager(store)
    v1 = occ.issue("a.md")
    assert occ.lazy_version_for("a.md") == v1


def test_lazy_version_for_missing_with_mtime(store):
    occ = OCCManager(store)
    v = occ.lazy_version_for("never-saved.md", mtime_fallback=1700000000.0)
    v2 = occ.lazy_version_for("another-never-saved.md", mtime_fallback=1700000000.0)
    # Different paths but same mtime — different paths get persisted independently
    assert v == occ.current("never-saved.md")
    assert v2 == occ.current("another-never-saved.md")


def test_rename_updates_key(store):
    occ = OCCManager(store)
    v1 = occ.issue("old.md")
    store.rename("old.md", "new.md")
    assert occ.current("old.md") is None
    assert occ.current("new.md") == v1


def test_rename_collision_raises(store):
    occ = OCCManager(store)
    occ.issue("a.md")
    occ.issue("b.md")
    with pytest.raises(ValueError):
        store.rename("a.md", "b.md")


def test_delete_removes_row(store):
    occ = OCCManager(store)
    occ.issue("a.md")
    store.delete("a.md")
    assert occ.current("a.md") is None


def test_factory_dev_returns_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.backends import get_version_store, _reset_for_test
    _reset_for_test()
    from backend.core.config import settings
    profile = settings.resolve_profile()
    assert profile.version_store_backend == "sqlite"
    store = get_version_store(profile, sqlite_path=str(tmp_path / "v.db"))
    from backend.application.occ.sqlite_store import SqliteVersionStore
    assert isinstance(store, SqliteVersionStore)
    _reset_for_test()


def test_profile_team_uses_postgres():
    from backend.core.profile import resolve_profile
    p = resolve_profile("team", {})
    assert p.version_store_backend == "postgres"
