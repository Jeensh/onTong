"""Tests for Group CRUD API and ACL API extensions.

Uses FastAPI TestClient with isolated in-memory/temp stores.

Usage:
    cd /path/to/onTong
    .venv/bin/python -m pytest tests/test_group_api.py -v
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import group as group_api
from backend.api import acl as acl_api
from backend.core.auth import User, get_current_user
from backend.core.auth.group_store import JSONGroupStore, Group
from backend.core.auth.acl_store import ACLStore


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(uid: str = "alice", roles: list[str] | None = None) -> User:
    return User(id=uid, name=uid.capitalize(), roles=roles or [], groups=[])


def _admin_user() -> User:
    return _make_user("admin", roles=["admin"])


def _regular_user() -> User:
    return _make_user("alice", roles=[])


def _make_app(user: User, group_store: JSONGroupStore, acl_store_inst: ACLStore) -> FastAPI:
    """Build a minimal FastAPI app with group + acl routers, fixed auth user."""
    app = FastAPI()

    # Override auth dependency
    app.dependency_overrides[get_current_user] = lambda: user

    # Initialize group store
    group_api.init(group_store)

    # Inject test acl_store into api modules (bypass lazy singleton)
    import backend.api.group as _group_mod
    import backend.api.acl as _acl_mod
    _group_mod.acl_store = acl_store_inst  # type: ignore[assignment]
    _acl_mod.acl_store = acl_store_inst  # type: ignore[assignment]

    app.include_router(group_api.router)
    app.include_router(acl_api.router)

    return app


@pytest.fixture()
def tmp_group_store(tmp_path: Path) -> JSONGroupStore:
    return JSONGroupStore(path=tmp_path / "groups.json")


@pytest.fixture()
def tmp_acl_store(tmp_path: Path) -> ACLStore:
    return ACLStore(acl_path=tmp_path / ".acl.json")


# ── Group API Tests ───────────────────────────────────────────────────────────


class TestGroupListAndCreate:
    def test_list_empty(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        resp = client.get("/api/groups")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_custom_group_by_regular_user(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_regular_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        resp = client.post("/api/groups", json={
            "id": "grp-proj-x",
            "name": "Project X",
            "type": "custom",
            "members": ["alice", "bob"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "grp-proj-x"
        assert data["name"] == "Project X"
        assert data["type"] == "custom"
        assert "alice" in data["members"]
        assert data["created_by"] == "alice"

    def test_create_department_group_by_regular_user_forbidden(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_regular_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        resp = client.post("/api/groups", json={
            "id": "grp-infra",
            "name": "인프라팀",
            "type": "department",
        })
        assert resp.status_code == 403

    def test_create_department_group_by_admin(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        resp = client.post("/api/groups", json={
            "id": "grp-infra",
            "name": "인프라팀",
            "type": "department",
        })
        assert resp.status_code == 201
        assert resp.json()["type"] == "department"

    def test_create_duplicate_id_conflict(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        payload = {"id": "grp-x", "name": "X", "type": "custom"}
        client.post("/api/groups", json=payload)
        resp = client.post("/api/groups", json=payload)
        assert resp.status_code == 409

    def test_list_after_create(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        client.post("/api/groups", json={"id": "g1", "name": "G1", "type": "custom"})
        client.post("/api/groups", json={"id": "g2", "name": "G2", "type": "custom"})
        resp = client.get("/api/groups")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGroupGetAndMembers:
    def test_get_existing_group(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        client.post("/api/groups", json={"id": "grp-1", "name": "Team A", "type": "custom"})
        resp = client.get("/api/groups/grp-1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Team A"

    def test_get_nonexistent_group(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        resp = client.get("/api/groups/does-not-exist")
        assert resp.status_code == 404

    def test_add_remove_members_by_manager(self, tmp_group_store, tmp_acl_store):
        # alice creates the group, so alice is in managed_by
        app = _make_app(_regular_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        client.post("/api/groups", json={"id": "grp-a", "name": "A", "type": "custom"})
        # add carol
        resp = client.put("/api/groups/grp-a/members", json={"add": ["carol"], "remove": []})
        assert resp.status_code == 200
        assert "carol" in resp.json()["members"]
        # remove carol
        resp = client.put("/api/groups/grp-a/members", json={"add": [], "remove": ["carol"]})
        assert resp.status_code == 200
        assert "carol" not in resp.json()["members"]

    def test_update_members_forbidden_for_non_manager(self, tmp_group_store, tmp_acl_store):
        # admin creates group, managed_by = ["admin"]
        app_admin = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        admin_client = TestClient(app_admin)
        admin_client.post("/api/groups", json={"id": "grp-b", "name": "B", "type": "custom"})

        # alice (non-manager) tries to update members
        app_alice = _make_app(_regular_user(), tmp_group_store, tmp_acl_store)
        alice_client = TestClient(app_alice)
        resp = alice_client.put("/api/groups/grp-b/members", json={"add": ["eve"], "remove": []})
        assert resp.status_code == 403


class TestGroupRenameAndDelete:
    def test_rename_group_updates_acl(self, tmp_group_store, tmp_acl_store):
        # Set up ACL with old group name
        tmp_acl_store.set_acl("wiki/hr/", read=["인프라팀"], write=["인프라팀"], manage=["admin"])

        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        client.post("/api/groups", json={"id": "grp-infra", "name": "인프라팀", "type": "department"})

        resp = client.put("/api/groups/grp-infra", json={"name": "인프라운영팀"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "인프라운영팀"

        # ACL reference should be updated
        acl = tmp_acl_store.get_all()
        assert "인프라운영팀" in acl["wiki/hr/"]["read"]
        assert "인프라팀" not in acl["wiki/hr/"]["read"]

    def test_rename_forbidden_for_non_admin(self, tmp_group_store, tmp_acl_store):
        app_admin = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        TestClient(app_admin).post("/api/groups", json={"id": "grp-c", "name": "C", "type": "custom"})

        app_alice = _make_app(_regular_user(), tmp_group_store, tmp_acl_store)
        resp = TestClient(app_alice).put("/api/groups/grp-c", json={"name": "C2"})
        assert resp.status_code == 403

    def test_delete_group_removes_acl_refs(self, tmp_group_store, tmp_acl_store):
        tmp_acl_store.set_acl("wiki/hr/", read=["ProjectX"], write=["ProjectX"], manage=["admin"])

        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        client.post("/api/groups", json={"id": "grp-proj-x", "name": "ProjectX", "type": "custom"})

        resp = client.delete("/api/groups/grp-proj-x")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "grp-proj-x"

        # Group should be gone
        assert tmp_group_store.get("grp-proj-x") is None

        # ACL references should be cleaned
        acl = tmp_acl_store.get_all()
        assert "ProjectX" not in acl["wiki/hr/"]["read"]

    def test_delete_nonexistent_group(self, tmp_group_store, tmp_acl_store):
        app = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        client = TestClient(app)
        resp = client.delete("/api/groups/ghost")
        assert resp.status_code == 404

    def test_delete_forbidden_for_non_admin(self, tmp_group_store, tmp_acl_store):
        app_admin = _make_app(_admin_user(), tmp_group_store, tmp_acl_store)
        TestClient(app_admin).post("/api/groups", json={"id": "grp-d", "name": "D", "type": "custom"})

        app_alice = _make_app(_regular_user(), tmp_group_store, tmp_acl_store)
        resp = TestClient(app_alice).delete("/api/groups/grp-d")
        assert resp.status_code == 403


# ── ACL API Tests ─────────────────────────────────────────────────────────────


class TestACLApi:
    def _acl_app(self, user: User, acl_store_inst: ACLStore) -> TestClient:
        app = FastAPI()
        app.dependency_overrides[get_current_user] = lambda: user

        # Inject test acl_store directly into the api module
        import backend.api.acl as _acl_mod
        _acl_mod.acl_store = acl_store_inst  # type: ignore[assignment]

        app.include_router(acl_api.router)
        return TestClient(app)

    def test_get_all_acl_admin_only(self, tmp_acl_store):
        client = self._acl_app(_regular_user(), tmp_acl_store)
        resp = client.get("/api/acl")
        assert resp.status_code == 403

    def test_get_all_acl_admin_succeeds(self, tmp_acl_store):
        tmp_acl_store.set_acl("wiki/hr/", read=["hr-team"], write=["hr-team"])
        client = self._acl_app(_admin_user(), tmp_acl_store)
        resp = client.get("/api/acl")
        assert resp.status_code == 200
        assert "wiki/hr/" in resp.json()

    def test_get_acl_for_path_direct_entry(self, tmp_acl_store):
        tmp_acl_store.set_acl("wiki/hr/doc.md", read=["hr-team"], write=["hr-team"], inherited=False)
        client = self._acl_app(_regular_user(), tmp_acl_store)
        resp = client.get("/api/acl/wiki/hr/doc.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "wiki/hr/doc.md"
        assert "hr-team" in data["read"]

    def test_get_acl_for_path_no_entry_returns_404(self, tmp_acl_store):
        client = self._acl_app(_regular_user(), tmp_acl_store)
        resp = client.get("/api/acl/wiki/nowhere/doc.md")
        assert resp.status_code == 404

    def test_set_acl_admin_succeeds(self, tmp_acl_store):
        client = self._acl_app(_admin_user(), tmp_acl_store)
        resp = client.put("/api/acl/wiki/hr/", json={
            "read": ["hr-team", "admin"],
            "write": ["hr-team"],
            "manage": ["admin"],
            "owner": "hr-admin",
            "inherited": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "wiki/hr/"
        assert data["owner"] == "hr-admin"
        assert "hr-team" in data["read"]

    def test_set_acl_non_admin_without_manage_permission_forbidden(self, tmp_acl_store):
        # No ACL set, default-deny → alice has no manage permission
        client = self._acl_app(_regular_user(), tmp_acl_store)
        resp = client.put("/api/acl/wiki/secret/", json={"read": ["all"], "write": []})
        assert resp.status_code == 403

    def test_set_acl_preserves_existing_owner(self, tmp_acl_store):
        # Set initial ACL with owner
        tmp_acl_store.set_acl("wiki/hr/", read=["hr-team"], write=["hr-team"], owner="hr-admin")
        client = self._acl_app(_admin_user(), tmp_acl_store)
        # Update without specifying owner
        resp = client.put("/api/acl/wiki/hr/", json={
            "read": ["hr-team", "all"],
            "write": ["hr-team"],
        })
        assert resp.status_code == 200
        # owner should be preserved from existing entry
        assert resp.json()["owner"] == "hr-admin"

    def test_delete_acl_admin_only(self, tmp_acl_store):
        tmp_acl_store.set_acl("wiki/hr/", read=["hr-team"], write=["hr-team"])
        client_admin = self._acl_app(_admin_user(), tmp_acl_store)
        resp = client_admin.delete("/api/acl?path=wiki/hr/")
        assert resp.status_code == 200
        assert resp.json()["removed"] == "wiki/hr/"

    def test_delete_acl_non_admin_forbidden(self, tmp_acl_store):
        tmp_acl_store.set_acl("wiki/hr/", read=["hr-team"], write=["hr-team"])
        client = self._acl_app(_regular_user(), tmp_acl_store)
        resp = client.delete("/api/acl?path=wiki/hr/")
        assert resp.status_code == 403

    def test_delete_acl_nonexistent_404(self, tmp_acl_store):
        client = self._acl_app(_admin_user(), tmp_acl_store)
        resp = client.delete("/api/acl?path=wiki/nowhere/")
        assert resp.status_code == 404
