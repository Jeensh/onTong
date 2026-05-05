"""End-to-end snapshot integration via WikiService + API."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_wiki(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib
    import backend.core.config
    importlib.reload(backend.core.config)
    backend.core.config.settings.wiki_dir = tmp_path
    (tmp_path / ".ontong").mkdir(parents=True, exist_ok=True)
    from backend.core.backends import _reset_for_test
    _reset_for_test()

    from backend.infrastructure.storage.local_fs import LocalFSAdapter
    from backend.application.wiki.wiki_service import WikiService

    class _NoopIndexer:
        async def index_file(self, *a, **kw):
            return 0

        async def remove_file(self, *a, **kw):
            pass

        async def reindex_all(self, *a, **kw):
            return 0

    storage = LocalFSAdapter(tmp_path)
    svc = WikiService(storage, _NoopIndexer(), None)

    from backend.api import wiki as wiki_api
    wiki_api.init(svc)

    from backend.core.auth import get_current_user, User

    app = FastAPI()
    app.include_router(wiki_api.router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="demo", name="demo", roles=["read", "write", "admin"]
    )

    yield app, tmp_path, svc
    _reset_for_test()


def test_save_creates_snapshot_of_old_content(app_with_wiki):
    app, _, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v1\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v2\n", user_name="alice")
    )
    client = TestClient(app)
    r = client.get("/api/wiki/snapshots/a.md")
    body = r.json()
    # 1 snapshot expected: v1 captured before v2 was written.
    assert body["count"] == 1
    assert body["items"][0]["reason"] == "save"


def test_get_snapshot_content_returns_old_body(app_with_wiki):
    app, _, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v1 body\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v2 body\n", user_name="alice")
    )
    client = TestClient(app)
    r = client.get("/api/wiki/snapshots/a.md")
    snap_meta = r.json()["items"][0]
    version = snap_meta["version"]
    r2 = client.get(f"/api/wiki/snapshots/a.md?version={version}")
    assert r2.status_code == 200
    assert "v1 body" in r2.json()["content"]


def test_restore_snapshot_brings_back_old_content(app_with_wiki):
    app, tmp_path, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v1\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v2\n", user_name="alice")
    )
    client = TestClient(app)
    snap_list = client.get("/api/wiki/snapshots/a.md").json()
    target_version = snap_list["items"][0]["version"]
    r = client.post(f"/api/wiki/snapshots/a.md/restore?version={target_version}")
    assert r.status_code == 200

    # File on disk now contains v1 body again
    content = (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "# v1" in content


def test_delete_creates_pre_delete_snapshot(app_with_wiki):
    app, _, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("doomed.md", "---\n---\n# byebye\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        svc.delete_file("doomed.md")
    )
    client = TestClient(app)
    r = client.get("/api/wiki/snapshots/doomed.md")
    body = r.json()
    reasons = [s["reason"] for s in body["items"]]
    assert "pre_delete" in reasons


def test_save_does_not_snapshot_first_write(app_with_wiki):
    app, _, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("fresh.md", "---\n---\n# new\n", user_name="alice")
    )
    client = TestClient(app)
    r = client.get("/api/wiki/snapshots/fresh.md")
    # First save has no prior content to snapshot → 0 snapshots
    assert r.json()["count"] == 0


def test_snapshot_warning_when_db_missing(tmp_path, monkeypatch):
    """When no saves have occurred yet, the snapshot DB doesn't exist — response is empty."""
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib
    import backend.core.config
    importlib.reload(backend.core.config)
    backend.core.config.settings.wiki_dir = tmp_path
    from backend.core.backends import _reset_for_test
    _reset_for_test()

    from backend.infrastructure.storage.local_fs import LocalFSAdapter
    from backend.application.wiki.wiki_service import WikiService

    class _NoopIndexer:
        async def index_file(self, *a, **kw):
            return 0

        async def remove_file(self, *a, **kw):
            pass

        async def reindex_all(self, *a, **kw):
            return 0

    storage = LocalFSAdapter(tmp_path)
    svc = WikiService(storage, _NoopIndexer(), None)
    from backend.api import wiki as wiki_api
    wiki_api.init(svc)
    from backend.core.auth import get_current_user, User
    app = FastAPI()
    app.include_router(wiki_api.router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="demo", name="demo", roles=["read", "write", "admin"]
    )
    client = TestClient(app)
    r = client.get("/api/wiki/snapshots/never-saved.md")
    body = r.json()
    assert body["items"] == []
    assert "warning" in body or body["count"] == 0
    _reset_for_test()
