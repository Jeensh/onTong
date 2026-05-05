"""G7 Delete blocking tests — covers all 5 RefKind cases."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_wiki(tmp_path, monkeypatch):
    """FastAPI app with the wiki router + tmp wiki + WikiService set up."""
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


def _seed(svc, path: str, raw: str):
    """Save a file via the WikiService to ensure RefIndex is updated."""
    import asyncio
    asyncio.get_event_loop().run_until_complete(svc.save_file(path, raw, user_name="demo"))


def test_delete_blocked_by_frontmatter_related(app_with_wiki):
    app, wiki_dir, svc = app_with_wiki
    _seed(svc, "target.md", "---\n---\n# Target\n")
    _seed(svc, "source.md", "---\nrelated:\n  - target.md\n---\n# Src\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/target.md")
    assert r.status_code == 409
    body = r.json()["detail"]
    assert body["blocked"] is True
    assert body["policy"] == "G7"
    assert "source.md" in body["unique_sources"]


def test_delete_blocked_by_frontmatter_supersedes(app_with_wiki):
    app, wiki_dir, svc = app_with_wiki
    _seed(svc, "old.md", "---\n---\n# Old\n")
    _seed(svc, "new.md", "---\nsupersedes: old.md\n---\n# New\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/old.md")
    assert r.status_code == 409
    assert "new.md" in r.json()["detail"]["unique_sources"]


def test_delete_blocked_by_body_markdown_link(app_with_wiki):
    app, wiki_dir, svc = app_with_wiki
    _seed(svc, "target.md", "---\n---\n# Target\n")
    _seed(svc, "source.md", "---\n---\n# Src\n[goto](target.md)\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/target.md")
    assert r.status_code == 409
    body = r.json()["detail"]
    assert "source.md" in body["unique_sources"]


def test_delete_blocked_by_body_wikilink_stem_match(app_with_wiki):
    app, wiki_dir, svc = app_with_wiki
    # target stem is 'target', wikilink is [[target]]
    _seed(svc, "target.md", "---\n---\n# Target\n")
    _seed(svc, "source.md", "---\n---\n# Src\nSee [[target]].\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/target.md")
    assert r.status_code == 409
    assert "source.md" in r.json()["detail"]["unique_sources"]


def test_no_force_override(app_with_wiki):
    """G7 policy: ?force=true must NOT bypass."""
    app, wiki_dir, svc = app_with_wiki
    _seed(svc, "target.md", "---\n---\n# Target\n")
    _seed(svc, "source.md", "---\nrelated:\n  - target.md\n---\n# Src\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/target.md?force=true")
    assert r.status_code == 409  # still blocked
    assert "source.md" in r.json()["detail"]["unique_sources"]


def test_delete_succeeds_when_no_inbound(app_with_wiki):
    """A document with no inbound refs deletes cleanly."""
    app, wiki_dir, svc = app_with_wiki
    _seed(svc, "lonely.md", "---\n---\n# Lonely — no one points here\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/lonely.md")
    assert r.status_code == 200
    assert r.json() == {"deleted": "lonely.md"}


def test_delete_404_when_missing(app_with_wiki):
    """Deleting a never-existed path returns 404."""
    app, wiki_dir, svc = app_with_wiki
    client = TestClient(app)
    r = client.delete("/api/wiki/file/never-existed.md")
    # If RefIndex has no record AND file doesn't exist on disk, svc.delete_file returns False → 404.
    assert r.status_code == 404


def test_response_includes_by_kind_breakdown(app_with_wiki):
    """The response separates inbound by kind for UI grouping."""
    app, wiki_dir, svc = app_with_wiki
    _seed(svc, "shared.md", "---\n---\n# Shared\n")
    _seed(svc, "src1.md", "---\nrelated:\n  - shared.md\n---\n# S1\n")
    _seed(svc, "src2.md", "---\n---\n# S2\n[link](shared.md)\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/shared.md")
    assert r.status_code == 409
    by_kind = r.json()["detail"]["by_kind"]
    # FM_RELATED = 3, BODY_MD_LINK = 5
    assert "3" in by_kind
    assert "5" in by_kind


def test_inbound_count_matches_total_refs(app_with_wiki):
    """If one source has multiple refs to the same target, all are counted."""
    app, wiki_dir, svc = app_with_wiki
    _seed(svc, "target.md", "---\n---\n# Target\n")
    _seed(svc, "source.md", "---\nrelated:\n  - target.md\n---\n# Src\n[link](target.md)\n[[target]]\n")

    client = TestClient(app)
    r = client.delete("/api/wiki/file/target.md")
    detail = r.json()["detail"]
    # source.md has 3 refs to target: FM_RELATED, BODY_MD_LINK, BODY_WIKILINK (stem-match)
    assert detail["inbound_count"] >= 3
    assert detail["unique_sources"] == ["source.md"]
