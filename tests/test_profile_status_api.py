"""Profile status endpoint test."""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import wiki as wiki_api
from backend.core.auth import User, get_current_user


def _make_app(user: User) -> FastAPI:
    """Build a minimal FastAPI app with just the wiki router, fixed auth user."""
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: user
    app.include_router(wiki_api.router)
    return app


def test_profile_status_dev(monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib
    import backend.core.config
    importlib.reload(backend.core.config)

    user = User(id="test", name="test", roles=[], groups=[])
    app = _make_app(user)
    client = TestClient(app)

    r = client.get("/api/wiki/profile-status", headers={"X-User": "test"})
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] == "dev"
    assert body["backends"]["lock"]["name"] == "memory"
    assert body["backends"]["lock"]["healthy"] is True
