"""Phase 5-C: edit-lock blocking."""
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
    (tmp_path / ".ontong").mkdir()

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
    app.dependency_overrides[get_current_user] = lambda: User(id="alice", name="alice", roles=["read", "write", "admin"])

    asyncio.get_event_loop().run_until_complete(
        svc.save_file("target.md", "---\n---\n# T\n", user_name="alice")
    )

    yield app, svc
    _reset_for_test()
    # Reset lock_service singleton so lock state does not bleed across tests
    import backend.application.lock_service as _ls_mod
    _ls_mod._lock_service = None


def test_rename_blocked_when_other_user_editing(app_with_wiki):
    app, _ = app_with_wiki
    # Bob acquires edit lock on the file
    from backend.application.lock_service import get_lock_service
    get_lock_service().acquire("target.md", "bob", ttl=300)

    client = TestClient(app)
    # Alice tries to rename — should be blocked because bob holds edit lock
    r = client.get("/api/wiki/rename-preview/target.md?to=renamed.md")
    assert r.status_code == 409
    body = r.json()["detail"]
    assert body["blocked"] is True
    assert "bob" in body["error"]


def test_rename_succeeds_when_no_lock(app_with_wiki):
    app, _ = app_with_wiki
    client = TestClient(app)
    r = client.get("/api/wiki/rename-preview/target.md?to=renamed.md")
    assert r.status_code == 200


def test_rename_succeeds_when_actor_holds_own_lock(app_with_wiki):
    """User can rename a file they themselves are editing."""
    app, _ = app_with_wiki
    from backend.application.lock_service import get_lock_service
    get_lock_service().acquire("target.md", "alice", ttl=300)
    client = TestClient(app)
    r = client.get("/api/wiki/rename-preview/target.md?to=renamed.md")
    assert r.status_code == 200


def test_patch_blocked_when_other_user_editing(app_with_wiki):
    app, _ = app_with_wiki
    from backend.application.lock_service import get_lock_service
    get_lock_service().acquire("target.md", "bob", ttl=300)

    client = TestClient(app)
    r = client.patch("/api/wiki/file/target.md", json={"new_path": "renamed.md"})
    assert r.status_code == 409
    body = r.json()["detail"]
    assert body.get("blocked") is True
