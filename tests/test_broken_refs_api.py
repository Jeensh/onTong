"""GET /api/wiki/broken-refs tests."""
from __future__ import annotations

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_refs(tmp_path, monkeypatch):
    """Mini FastAPI app with the broken-refs endpoint and a tmp wiki."""
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    backend.core.config.settings.wiki_dir = tmp_path
    (tmp_path / ".ontong").mkdir(parents=True, exist_ok=True)

    from backend.core.backends import _reset_for_test
    _reset_for_test()

    # Build app with ONLY the wiki router (avoid full main.py side effects)
    from backend.api import wiki as wiki_api
    from backend.core.auth import get_current_user, User

    app = FastAPI()
    app.include_router(wiki_api.router)
    # Override auth
    app.dependency_overrides[get_current_user] = lambda: User(id="demo", name="demo", roles=["read", "write"])

    yield app, tmp_path

    _reset_for_test()


def _seed_index(wiki_dir):
    """Seed the RefIndex with broken + good refs."""
    from backend.application.refindex.sqlite_backend import SqliteRefIndex
    from backend.application.refindex.extractor import Reference, RefKind

    db = wiki_dir / ".ontong" / "refs.db"
    idx = SqliteRefIndex(str(db))
    # alpha.md has refs to beta.md (good) and missing.md (broken)
    idx.upsert_for_source("alpha.md", [
        Reference("alpha.md", "beta.md", RefKind.BODY_MD_LINK,
                  {"offset": 10, "length": 7, "raw": "beta.md"}),
        Reference("alpha.md", "missing.md", RefKind.BODY_MD_LINK,
                  {"offset": 30, "length": 10, "raw": "missing.md"}),
    ])
    # beta.md exists as a source, so beta.md is NOT broken
    idx.upsert_for_source("beta.md", [
        Reference("beta.md", "alpha.md", RefKind.BODY_WIKILINK,
                  {"offset": 5, "length": 5, "raw": "alpha"}),
    ])


def test_broken_refs_endpoint_returns_dangling(app_with_refs):
    app, wiki_dir = app_with_refs
    _seed_index(wiki_dir)
    client = TestClient(app)
    r = client.get("/api/wiki/broken-refs")
    assert r.status_code == 200
    body = r.json()
    targets = sorted(item["target_path"] for item in body["items"])
    assert "missing.md" in targets
    # beta.md is a source, NOT broken
    assert "beta.md" not in targets


def test_broken_refs_filtered_by_kind(app_with_refs):
    app, wiki_dir = app_with_refs
    _seed_index(wiki_dir)
    client = TestClient(app)
    r = client.get("/api/wiki/broken-refs?kind=5")  # BODY_MD_LINK
    body = r.json()
    assert all(item["kind"] == 5 for item in body["items"])


def test_broken_refs_pagination(app_with_refs):
    app, wiki_dir = app_with_refs
    # Seed 5 broken refs
    from backend.application.refindex.sqlite_backend import SqliteRefIndex
    from backend.application.refindex.extractor import Reference, RefKind
    idx = SqliteRefIndex(str(wiki_dir / ".ontong" / "refs.db"))
    refs = [
        Reference("a.md", f"missing-{i}.md", RefKind.BODY_MD_LINK,
                  {"offset": i * 10, "length": 5, "raw": f"missing-{i}.md"})
        for i in range(5)
    ]
    idx.upsert_for_source("a.md", refs)

    client = TestClient(app)
    # Page 1
    r1 = client.get("/api/wiki/broken-refs?limit=2&offset=0")
    assert r1.json()["count"] == 2
    # Page 2
    r2 = client.get("/api/wiki/broken-refs?limit=2&offset=2")
    assert r2.json()["count"] == 2
    # Page 3 (last)
    r3 = client.get("/api/wiki/broken-refs?limit=2&offset=4")
    assert r3.json()["count"] == 1


def test_broken_refs_empty_when_no_db(app_with_refs):
    """If RefIndex hasn't been built yet, return empty + warning."""
    app, wiki_dir = app_with_refs
    # No _seed_index call — DB doesn't exist
    client = TestClient(app)
    r = client.get("/api/wiki/broken-refs")
    body = r.json()
    assert body["items"] == []
    assert "warning" in body
