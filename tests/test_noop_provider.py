"""Tests for NoOpAuthProvider — multi-user dev mode.

Covers:
- User loading from users.json config
- X-User-Id header routing
- Default user fallback (unknown/missing header)
- Group resolution via group_store
- Missing config file fallback to _DEFAULT_USER

Note: async methods are exercised via asyncio.run() since pytest-asyncio
is not installed in this project (only anyio is available as async support).
"""

from __future__ import annotations

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from starlette.requests import Request


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_request(headers: dict | None = None) -> Request:
    """Build a minimal Starlette Request with given headers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in (headers or {}).items()
        ],
        "query_string": b"",
    }
    return Request(scope)


def _make_users_file(tmp_path: Path) -> Path:
    """Write sample users.json and return its path."""
    users = {
        "users": [
            {
                "id": "donghae",
                "name": "동해",
                "email": "donghae@ontong.local",
                "roles": ["admin"],
            },
            {
                "id": "kim",
                "name": "김팀원",
                "email": "kim@ontong.local",
                "roles": [],
            },
            {
                "id": "lee",
                "name": "이팀원",
                "email": "lee@ontong.local",
                "roles": [],
            },
        ]
    }
    p = tmp_path / "users.json"
    p.write_text(json.dumps(users), encoding="utf-8")
    return p


def _make_provider(tmp_path: Path, group_store=None):
    """Synchronously create and start a NoOpAuthProvider."""
    from backend.core.auth.noop_provider import NoOpAuthProvider

    p = _make_users_file(tmp_path)
    prov = NoOpAuthProvider(users_path=p, group_store=group_store)
    asyncio.run(prov.on_startup())
    return prov


def _make_provider_no_file(tmp_path: Path):
    """NoOpAuthProvider where users.json does NOT exist."""
    from backend.core.auth.noop_provider import NoOpAuthProvider

    prov = NoOpAuthProvider(users_path=tmp_path / "nonexistent.json")
    asyncio.run(prov.on_startup())
    return prov


# ── Tests: User Loading ───────────────────────────────────────────────────────


class TestUserLoading:
    """on_startup correctly parses users.json."""

    def test_loads_all_users(self, tmp_path):
        prov = _make_provider(tmp_path)
        assert len(prov._users) == 3

    def test_user_ids_correct(self, tmp_path):
        prov = _make_provider(tmp_path)
        assert "donghae" in prov._users
        assert "kim" in prov._users
        assert "lee" in prov._users

    def test_user_fields(self, tmp_path):
        prov = _make_provider(tmp_path)
        u = prov._users["donghae"]
        assert u.name == "동해"
        assert u.email == "donghae@ontong.local"
        assert "admin" in u.roles

    def test_fallback_when_no_file(self, tmp_path):
        """Missing file → _DEFAULT_USER is used."""
        prov = _make_provider_no_file(tmp_path)
        assert "dev-user" in prov._users

    def test_fallback_user_is_admin(self, tmp_path):
        prov = _make_provider_no_file(tmp_path)
        u = prov._users["dev-user"]
        assert "admin" in u.roles


# ── Tests: authenticate() ─────────────────────────────────────────────────────


class TestAuthenticate:
    """authenticate() routes requests to the correct user."""

    def test_known_user_header(self, tmp_path):
        prov = _make_provider(tmp_path)
        req = _make_request({"X-User-Id": "kim"})
        user = asyncio.run(prov.authenticate(req))
        assert user.id == "kim"
        assert user.name == "김팀원"

    def test_another_known_user_header(self, tmp_path):
        prov = _make_provider(tmp_path)
        req = _make_request({"X-User-Id": "lee"})
        user = asyncio.run(prov.authenticate(req))
        assert user.id == "lee"

    def test_unknown_header_defaults_to_first_user(self, tmp_path):
        """X-User-Id that doesn't exist → first user in config."""
        prov = _make_provider(tmp_path)
        req = _make_request({"X-User-Id": "nobody"})
        user = asyncio.run(prov.authenticate(req))
        # First user defined is 'donghae'
        assert user.id == "donghae"

    def test_missing_header_defaults_to_first_user(self, tmp_path):
        """No X-User-Id header → first user in config."""
        prov = _make_provider(tmp_path)
        req = _make_request({})
        user = asyncio.run(prov.authenticate(req))
        assert user.id == "donghae"

    def test_fallback_provider_returns_dev_user(self, tmp_path):
        prov = _make_provider_no_file(tmp_path)
        req = _make_request({})
        user = asyncio.run(prov.authenticate(req))
        assert user.id == "dev-user"


# ── Tests: Group Resolution ───────────────────────────────────────────────────


class TestGroupResolution:
    """resolve_groups() uses group_store when provided."""

    def test_no_group_store_returns_empty(self, tmp_path):
        prov = _make_provider(tmp_path)
        groups = asyncio.run(prov.resolve_groups("donghae"))
        assert groups == []

    def test_group_store_called(self, tmp_path):
        """When group_store is set, groups are resolved from it."""
        from backend.core.auth.group_store import Group

        mock_store = MagicMock()
        mock_store.get_user_groups.return_value = [
            Group(id="grp-1", name="인프라팀", type="department", members=["kim"]),
            Group(id="grp-2", name="DevOps", type="custom", members=["kim"]),
        ]

        prov = _make_provider(tmp_path, group_store=mock_store)
        groups = asyncio.run(prov.resolve_groups("kim"))
        assert "인프라팀" in groups
        assert "DevOps" in groups
        mock_store.get_user_groups.assert_called_once_with("kim")

    def test_groups_attached_to_authenticated_user(self, tmp_path):
        """authenticate() attaches resolved groups to the User object."""
        from backend.core.auth.group_store import Group

        mock_store = MagicMock()
        mock_store.get_user_groups.return_value = [
            Group(id="grp-1", name="인프라팀", type="department", members=["kim"]),
        ]

        prov = _make_provider(tmp_path, group_store=mock_store)
        req = _make_request({"X-User-Id": "kim"})
        user = asyncio.run(prov.authenticate(req))
        assert "인프라팀" in user.groups

    def test_empty_group_store_result(self, tmp_path):
        """If group_store returns empty list, user.groups is []."""
        mock_store = MagicMock()
        mock_store.get_user_groups.return_value = []

        prov = _make_provider(tmp_path, group_store=mock_store)
        req = _make_request({"X-User-Id": "lee"})
        user = asyncio.run(prov.authenticate(req))
        assert user.groups == []


# ── Tests: Invalid JSON ───────────────────────────────────────────────────────


class TestInvalidUsersJson:
    """Gracefully handles malformed users.json."""

    def test_malformed_json_falls_back_to_default(self, tmp_path):
        from backend.core.auth.noop_provider import NoOpAuthProvider

        bad_file = tmp_path / "users.json"
        bad_file.write_text("{ this is not valid json }", encoding="utf-8")

        prov = NoOpAuthProvider(users_path=bad_file)
        asyncio.run(prov.on_startup())
        assert "dev-user" in prov._users

    def test_empty_users_list_falls_back_to_default(self, tmp_path):
        from backend.core.auth.noop_provider import NoOpAuthProvider

        empty_file = tmp_path / "users.json"
        empty_file.write_text(json.dumps({"users": []}), encoding="utf-8")

        prov = NoOpAuthProvider(users_path=empty_file)
        asyncio.run(prov.on_startup())
        assert "dev-user" in prov._users


# ── Tests: Lifecycle ──────────────────────────────────────────────────────────


class TestLifecycle:
    """on_startup / on_shutdown don't raise."""

    def test_on_shutdown_noop(self, tmp_path):
        prov = _make_provider(tmp_path)
        # Should not raise
        asyncio.run(prov.on_shutdown())
