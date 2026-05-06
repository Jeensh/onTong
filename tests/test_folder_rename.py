"""Phase 4 — folder rename + bulk lock + batched processing."""
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
    # Reset lock service singleton for test isolation
    import backend.application.lock_service as _ls_mod
    _ls_mod._lock_service = None

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
    app.dependency_overrides[get_current_user] = lambda: User(id="alice", name="alice", roles=["read","write","admin"])

    yield app, svc, tmp_path
    _reset_for_test()
    _ls_mod._lock_service = None


def _seed(svc, path: str, raw: str):
    asyncio.get_event_loop().run_until_complete(svc.save_file(path, raw, user_name="alice"))


def test_folder_preview_aggregates_inbound(app_with_wiki):
    app, svc, _ = app_with_wiki
    _seed(svc, "myfolder/a.md", "---\n---\n# A\n")
    _seed(svc, "myfolder/b.md", "---\n---\n# B\n[link](myfolder/a.md)\n")
    _seed(svc, "outside.md", "---\n---\n# Outside\n[ref](myfolder/a.md)\n[ref](myfolder/b.md)\n")

    client = TestClient(app)
    r = client.get("/api/wiki/folder-rename-preview/myfolder?to=newfolder")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["file_count"] == 2  # a.md + b.md
    assert body["inbound_count"] >= 3  # b→a, outside→a, outside→b
    sources = sorted(it["source_path"] for it in body["impact_items"])
    assert "outside.md" in sources or "myfolder/b.md" in sources


def test_folder_rename_moves_all_children_and_patches(app_with_wiki):
    app, svc, tmp_path = app_with_wiki
    _seed(svc, "myfolder/a.md", "---\n---\n# A\n")
    _seed(svc, "myfolder/b.md", "---\n---\n# B\n[ref](myfolder/a.md)\n")
    _seed(svc, "outside.md", "---\nrelated:\n  - myfolder/a.md\n---\n# Outside\n")

    client = TestClient(app)
    r = client.patch("/api/wiki/folder/myfolder", json={"new_path": "newfolder"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("success", "partial")
    assert body["total_files"] == 2

    # Files moved
    assert (tmp_path / "newfolder" / "a.md").exists()
    assert (tmp_path / "newfolder" / "b.md").exists()
    assert not (tmp_path / "myfolder" / "a.md").exists()

    # Inbound patched
    outside = (tmp_path / "outside.md").read_text(encoding="utf-8")
    assert "newfolder/a.md" in outside
    assert "myfolder/a.md" not in outside

    b_content = (tmp_path / "newfolder" / "b.md").read_text(encoding="utf-8")
    assert "newfolder/a.md" in b_content


def test_folder_rename_with_subdirectory(app_with_wiki):
    app, svc, tmp_path = app_with_wiki
    _seed(svc, "parent/a.md", "---\n---\n# A\n")
    _seed(svc, "parent/sub/b.md", "---\n---\n# B\n")
    _seed(svc, "parent/sub/c.md", "---\n---\n# C\n")

    client = TestClient(app)
    r = client.patch("/api/wiki/folder/parent", json={"new_path": "renamed_parent"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_files"] == 3
    assert (tmp_path / "renamed_parent" / "a.md").exists()
    assert (tmp_path / "renamed_parent" / "sub" / "b.md").exists()
    assert (tmp_path / "renamed_parent" / "sub" / "c.md").exists()


def test_folder_rename_empty_folder_fails(app_with_wiki):
    app, svc, _ = app_with_wiki
    client = TestClient(app)
    r = client.patch("/api/wiki/folder/nonexistent", json={"new_path": "doesntmatter"})
    assert r.status_code == 409
    assert "마크다운" in r.json()["detail"]["error"] or "폴더" in r.json()["detail"]["error"]


def test_bulk_lock_blocks_concurrent_folder_op(app_with_wiki):
    """If alice already holds bulk lock, second alice request blocks."""
    app, svc, _ = app_with_wiki
    _seed(svc, "f1/a.md", "---\n---\n# A\n")
    _seed(svc, "f2/b.md", "---\n---\n# B\n")

    # Manually grab bulk lock for alice using the same lock-user the orchestrator uses
    from backend.application.lock_service import get_lock_service
    get_lock_service().acquire("ontong:lock:bulk:alice", "bulk_active", ttl=1800)

    client = TestClient(app)
    r = client.patch("/api/wiki/folder/f1", json={"new_path": "renamed_f1"})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "bulk" in detail.get("error", "").lower() or "진행 중" in detail.get("error", "")


def test_swap_prefix_pure_function():
    """_swap_prefix doesn't rely on raw.replace, handles ambiguous prefixes correctly."""
    from backend.application.rename.folder_orchestrator import _swap_prefix
    assert _swap_prefix("데모/sub/c.md", "데모", "데모2") == "데모2/sub/c.md"
    assert _swap_prefix("데모/a.md", "데모", "데모2") == "데모2/a.md"
    # Ambiguous: 'foo' vs 'foobar' — should NOT replace foobar/x as foo prefix
    assert _swap_prefix("foobar/x.md", "foo", "FOO") == "foobar/x.md"
    # Exact match (file IS the folder name itself, edge case)
    assert _swap_prefix("foo", "foo", "FOO") == "FOO"


def test_progress_events_emitted(app_with_wiki):
    """SSE folder_rename_started/progress/finished should be published."""
    app, svc, _ = app_with_wiki
    _seed(svc, "fold/a.md", "---\n---\n# A\n")
    _seed(svc, "fold/b.md", "---\n---\n# B\n")

    received: list[tuple[str, dict]] = []
    from backend.infrastructure.events.event_bus import event_bus
    event_bus.on("folder_rename_started", lambda d: received.append(("started", d)))
    event_bus.on("folder_rename_progress", lambda d: received.append(("progress", d)))
    event_bus.on("folder_rename_finished", lambda d: received.append(("finished", d)))

    client = TestClient(app)
    r = client.patch("/api/wiki/folder/fold", json={"new_path": "fold_new"})
    assert r.status_code == 200

    types = [t for t, _ in received]
    assert "started" in types
    assert "finished" in types
