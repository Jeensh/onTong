"""OCC conflict detection — end-to-end via API."""
from __future__ import annotations

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_wiki(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    backend.core.config.settings.wiki_dir = tmp_path
    (tmp_path / ".ontong").mkdir(parents=True, exist_ok=True)

    from backend.core.backends import _reset_for_test
    _reset_for_test()

    from backend.infrastructure.storage.local_fs import LocalFSAdapter
    from backend.application.wiki.wiki_service import WikiService

    class _NoopIndexer:
        async def index_file(self, *a, **kw): return 0
        async def remove_file(self, *a, **kw): pass
        async def reindex_all(self, *a, **kw): return 0

    storage = LocalFSAdapter(tmp_path)
    svc = WikiService(storage, _NoopIndexer(), None)

    from backend.api import wiki as wiki_api
    wiki_api.init(svc)

    from backend.core.auth import get_current_user, User

    app = FastAPI()
    app.include_router(wiki_api.router)
    app.dependency_overrides[get_current_user] = lambda: User(id="demo", name="demo", roles=["read", "write", "admin"])

    yield app, tmp_path, svc
    _reset_for_test()


def test_get_file_returns_etag_header(app_with_wiki):
    app, tmp_path, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# Hello\n", user_name="alice")
    )
    client = TestClient(app)
    r = client.get("/api/wiki/file/a.md")
    assert r.status_code == 200
    assert "etag" in r.headers


def test_save_with_matching_if_match_succeeds(app_with_wiki):
    app, tmp_path, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v1\n", user_name="alice")
    )
    client = TestClient(app)
    r = client.get("/api/wiki/file/a.md")
    etag = r.headers.get("etag", "").strip('"')
    assert etag

    r2 = client.put(
        "/api/wiki/file/a.md",
        json={"content": "---\n---\n# v2\n"},
        headers={"If-Match": f'"{etag}"'},
    )
    assert r2.status_code == 200


def test_save_with_stale_if_match_returns_409(app_with_wiki):
    app, tmp_path, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v1\n", user_name="alice")
    )
    client = TestClient(app)
    r = client.get("/api/wiki/file/a.md")
    stale_etag = r.headers.get("etag", "").strip('"')

    # Server moves on (bob saves directly via service — bypasses If-Match)
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\n---\n# v2 by bob\n", user_name="bob")
    )

    # Alice's stale save
    r2 = client.put(
        "/api/wiki/file/a.md",
        json={"content": "---\n---\n# v3 by alice\n"},
        headers={"If-Match": f'"{stale_etag}"'},
    )
    assert r2.status_code == 409
    body = r2.json()["detail"]
    assert body["conflict"] is True
    assert body["base_version"] == stale_etag
    assert body["server_version"] != stale_etag
    assert "v2 by bob" in body["server_content"]


def test_save_without_if_match_succeeds_legacy(app_with_wiki):
    """Legacy callers without If-Match still work."""
    app, _, _ = app_with_wiki
    client = TestClient(app)
    r = client.put("/api/wiki/file/a.md", json={"content": "---\n---\n# new\n"})
    assert r.status_code == 200
