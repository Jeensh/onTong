"""Phase 3 endpoint tests: preview + PATCH + undo."""
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

    # Seed
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("target.md", "---\n---\n# Target\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\nrelated:\n  - target.md\n---\n# A\n[link](target.md)\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("b.md", "---\n---\n# B\n[ref](target.md)\n", user_name="alice")
    )

    yield app, tmp_path, svc
    _reset_for_test()


def test_rename_preview_returns_impact(app_with_wiki):
    app, _, _ = app_with_wiki
    client = TestClient(app)
    r = client.get("/api/wiki/rename-preview/target.md?to=renamed.md")
    assert r.status_code == 200
    body = r.json()
    assert body["old_path"] == "target.md"
    assert body["new_path"] == "renamed.md"
    assert body["inbound_count"] >= 2
    assert body["unique_inbound_sources"] == 2
    sources = sorted(it["source_path"] for it in body["impact_items"])
    assert sources == ["a.md", "b.md"]


def test_patch_renames_and_patches_inbound(app_with_wiki):
    app, tmp_path, _ = app_with_wiki
    client = TestClient(app)
    r = client.patch("/api/wiki/file/target.md", json={"new_path": "renamed.md"})
    assert r.status_code == 200
    body = r.json()
    assert body["old_path"] == "target.md"
    assert body["new_path"] == "renamed.md"
    assert body["status"] in ("success", "partial")
    # File moved
    assert (tmp_path / "renamed.md").exists()
    assert not (tmp_path / "target.md").exists()
    # Inbound patched
    a = (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "renamed.md" in a and "target.md" not in a


def test_patch_returns_audit_id(app_with_wiki):
    app, _, _ = app_with_wiki
    client = TestClient(app)
    r = client.patch("/api/wiki/file/target.md", json={"new_path": "renamed.md"})
    assert "audit_id" in r.json()
    assert r.json()["audit_id"]


def test_undo_rename_within_window(app_with_wiki):
    app, tmp_path, _ = app_with_wiki
    client = TestClient(app)
    r1 = client.patch("/api/wiki/file/target.md", json={"new_path": "renamed.md"})
    audit_id = r1.json()["audit_id"]

    r2 = client.post(f"/api/wiki/audit/{audit_id}/undo")
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] in ("success", "partial")
    # File back at original
    assert (tmp_path / "target.md").exists()
    assert not (tmp_path / "renamed.md").exists()


def test_preview_does_not_modify(app_with_wiki):
    app, tmp_path, _ = app_with_wiki
    client = TestClient(app)
    client.get("/api/wiki/rename-preview/target.md?to=renamed.md")
    # Files unchanged
    assert (tmp_path / "target.md").exists()
    assert not (tmp_path / "renamed.md").exists()


def test_undo_outside_window_rejected(app_with_wiki):
    """Mock the audit's finished_at to be 10 min ago — undo refuses."""
    app, tmp_path, svc = app_with_wiki
    client = TestClient(app)
    r1 = client.patch("/api/wiki/file/target.md", json={"new_path": "renamed.md"})
    audit_id = r1.json()["audit_id"]

    # Reach in and manipulate the audit row's finished_at
    orch = svc.get_rename_orchestrator()
    # SQLite-direct UPDATE
    if hasattr(orch._audit, "_conn"):
        import time
        with orch._audit._lock, orch._audit._conn:
            orch._audit._conn.execute(
                "UPDATE wiki_audit SET finished_at=? WHERE id=?",
                (time.time() - 600, int(audit_id)),
            )
    r2 = client.post(f"/api/wiki/audit/{audit_id}/undo")
    assert r2.status_code == 400
    assert "window" in r2.json()["detail"]["error"].lower()


def test_patch_no_inbound_succeeds(app_with_wiki):
    app, tmp_path, svc = app_with_wiki
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("lonely.md", "---\n---\n# Lonely\n", user_name="alice")
    )
    client = TestClient(app)
    r = client.patch("/api/wiki/file/lonely.md", json={"new_path": "renamed_lonely.md"})
    assert r.status_code == 200
    assert (tmp_path / "renamed_lonely.md").exists()
