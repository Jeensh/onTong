"""Tests for ACL Store v2 — default-deny, owner/manage, inheritance, personal space.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.core.auth.models import User


def _make_store(acl_data: dict | None = None):
    """Create an ACLStore with a temp file and optional initial data."""
    from backend.core.auth.acl_store import ACLStore

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    if acl_data is not None:
        json.dump(acl_data, tmp, ensure_ascii=False)
    tmp.close()
    return ACLStore(acl_path=Path(tmp.name))


def _user(
    uid: str = "alice",
    name: str = "Alice",
    roles: list[str] | None = None,
    groups: list[str] | None = None,
) -> User:
    return User(
        id=uid,
        name=name,
        roles=roles or [],
        groups=groups or [],
    )


# ── Test Classes ────────────────────────────────────────────────────────


class TestDefaultDeny:
    """When no ACL entry exists anywhere, access should be denied (default-deny)."""

    def test_no_acl_denies_read(self):
        store = _make_store({})  # Empty ACL
        user = _user("bob", roles=["viewer"])
        assert store.check_permission("wiki/somepage.md", user, "read") is False

    def test_admin_always_allowed(self):
        store = _make_store({})  # Empty ACL
        admin = _user("admin1", roles=["admin"])
        assert store.check_permission("wiki/somepage.md", admin, "read") is True
        assert store.check_permission("wiki/somepage.md", admin, "write") is True
        assert store.check_permission("wiki/somepage.md", admin, "manage") is True


class TestPersonalSpace:
    """@username/ paths: only that user (and admin) can access."""

    def test_owner_can_access(self):
        store = _make_store({})
        alice = _user("alice")
        assert store.check_permission("@alice/notes.md", alice, "read") is True
        assert store.check_permission("@alice/notes.md", alice, "write") is True

    def test_other_user_denied(self):
        store = _make_store({})
        bob = _user("bob")
        assert store.check_permission("@alice/notes.md", bob, "read") is False
        assert store.check_permission("@alice/notes.md", bob, "write") is False

    def test_admin_can_access_personal(self):
        store = _make_store({})
        admin = _user("admin1", roles=["admin"])
        assert store.check_permission("@alice/notes.md", admin, "read") is True

    def test_nested_personal(self):
        store = _make_store({})
        alice = _user("alice")
        bob = _user("bob")
        assert store.check_permission("@alice/deep/nested/doc.md", alice, "read") is True
        assert store.check_permission("@alice/deep/nested/doc.md", bob, "read") is False


class TestFolderInheritance:
    """Child documents inherit parent folder permissions (inherited=True)."""

    def test_child_inherits_folder_read(self):
        acl = {
            "wiki/hr/": {
                "owner": "hr-admin",
                "read": ["hr-team"],
                "write": ["hr-team"],
                "manage": ["hr-admin"],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        user = _user("u1", groups=["hr-team"])
        assert store.check_permission("wiki/hr/policy.md", user, "read") is True

    def test_child_inherits_folder_write(self):
        acl = {
            "wiki/hr/": {
                "owner": "hr-admin",
                "read": ["hr-team"],
                "write": ["hr-team"],
                "manage": ["hr-admin"],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        user = _user("u1", groups=["hr-team"])
        assert store.check_permission("wiki/hr/policy.md", user, "write") is True

    def test_non_member_denied(self):
        acl = {
            "wiki/hr/": {
                "owner": "hr-admin",
                "read": ["hr-team"],
                "write": ["hr-team"],
                "manage": ["hr-admin"],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        outsider = _user("outsider", groups=["sales-team"])
        assert store.check_permission("wiki/hr/policy.md", outsider, "read") is False

    def test_nested_folder_inheritance(self):
        acl = {
            "wiki/eng/": {
                "owner": "",
                "read": ["eng-team"],
                "write": ["eng-team"],
                "manage": [],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        dev = _user("dev1", groups=["eng-team"])
        assert store.check_permission("wiki/eng/backend/api/readme.md", dev, "read") is True


class TestDocumentOverride:
    """Document-level ACL overrides inherited folder permissions."""

    def test_doc_override_narrows_access(self):
        """Folder gives broad access, but doc-level ACL restricts it."""
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["all"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            },
            "wiki/hr/salary.md": {
                "owner": "hr-admin",
                "read": ["hr-lead"],
                "write": ["hr-lead"],
                "manage": ["hr-admin"],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        # Normal user can read the folder
        normal = _user("someone", groups=["viewer"])
        assert store.check_permission("wiki/hr/policy.md", normal, "read") is True
        # But NOT the salary doc (narrowed)
        assert store.check_permission("wiki/hr/salary.md", normal, "read") is False

    def test_doc_override_widens_access(self):
        """Folder is restricted, but a specific doc is open to all."""
        acl = {
            "wiki/finance/": {
                "owner": "",
                "read": ["finance-team"],
                "write": ["finance-team"],
                "manage": [],
                "inherited": False,
            },
            "wiki/finance/public-report.md": {
                "owner": "",
                "read": ["all"],
                "write": [],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        outsider = _user("anyone", groups=["sales-team"])
        # Cannot read the folder
        assert store.check_permission("wiki/finance/budget.md", outsider, "read") is False
        # But CAN read the public doc
        assert store.check_permission("wiki/finance/public-report.md", outsider, "read") is True


class TestOwnerAccess:
    """Owner of a resource always has read + write + manage."""

    def test_owner_always_has_access(self):
        acl = {
            "wiki/secret/doc.md": {
                "owner": "alice",
                "read": [],
                "write": [],
                "manage": [],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        alice = _user("alice")
        assert store.check_permission("wiki/secret/doc.md", alice, "read") is True
        assert store.check_permission("wiki/secret/doc.md", alice, "write") is True
        assert store.check_permission("wiki/secret/doc.md", alice, "manage") is True

        # But another user cannot
        bob = _user("bob")
        assert store.check_permission("wiki/secret/doc.md", bob, "read") is False


class TestManagePermission:
    """Manage permission controls who can modify the ACL itself."""

    def test_manage_granted(self):
        acl = {
            "wiki/team/": {
                "owner": "",
                "read": ["all"],
                "write": ["team-a"],
                "manage": ["team-lead"],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        lead = _user("lead1", groups=["team-lead"])
        assert store.check_permission("wiki/team/", lead, "manage") is True

    def test_manage_denied(self):
        acl = {
            "wiki/team/": {
                "owner": "",
                "read": ["all"],
                "write": ["team-a"],
                "manage": ["team-lead"],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        member = _user("dev1", groups=["team-a"])
        assert store.check_permission("wiki/team/", member, "manage") is False


class TestAllKeyword:
    """The 'all' principal grants access to everyone."""

    def test_all_grants_read(self):
        acl = {
            "wiki/public/": {
                "owner": "",
                "read": ["all"],
                "write": [],
                "manage": [],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        anyone = _user("random", groups=[])
        assert store.check_permission("wiki/public/readme.md", anyone, "read") is True
        # But write is not granted
        assert store.check_permission("wiki/public/readme.md", anyone, "write") is False


class TestUserDirectGrant:
    """'@username' principal matches a specific user."""

    def test_user_direct_read(self):
        acl = {
            "wiki/shared/doc.md": {
                "owner": "",
                "read": ["@bob"],
                "write": [],
                "manage": [],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        bob = _user("bob")
        assert store.check_permission("wiki/shared/doc.md", bob, "read") is True

        # Other user not granted
        alice = _user("alice")
        assert store.check_permission("wiki/shared/doc.md", alice, "read") is False


class TestComputeAccessScope:
    """compute_access_scope returns principals for ChromaDB metadata."""

    def test_folder_scope(self):
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["hr-team", "admin"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        scope = store.compute_access_scope("wiki/hr/policy.md")
        assert scope["read"] == ["hr-team", "admin"]
        assert scope["write"] == ["hr-team"]

    def test_doc_override_scope(self):
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["all"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            },
            "wiki/hr/salary.md": {
                "owner": "",
                "read": ["hr-lead"],
                "write": ["hr-lead"],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        scope = store.compute_access_scope("wiki/hr/salary.md")
        assert scope["read"] == ["hr-lead"]
        assert scope["write"] == ["hr-lead"]

    def test_personal_scope(self):
        store = _make_store({})
        scope = store.compute_access_scope("@alice/notes.md")
        assert scope["read"] == ["@alice"]
        assert scope["write"] == ["@alice"]

    def test_scope_includes_owner_doc_override(self):
        """Owner principal must appear in scope even if not in read/write lists."""
        acl = {
            "wiki/hr/salary.md": {
                "owner": "hr-admin",
                "read": ["hr-lead"],
                "write": ["hr-lead"],
                "manage": ["hr-admin"],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        scope = store.compute_access_scope("wiki/hr/salary.md")
        assert "@hr-admin" in scope["read"]
        assert "@hr-admin" in scope["write"]
        assert "hr-lead" in scope["read"]

    def test_scope_includes_owner_folder_inheritance(self):
        """Owner principal from parent folder must appear in inherited scope."""
        acl = {
            "wiki/hr/": {
                "owner": "hr-admin",
                "read": ["hr-team"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        scope = store.compute_access_scope("wiki/hr/policy.md")
        assert "@hr-admin" in scope["read"]
        assert "@hr-admin" in scope["write"]
        assert "hr-team" in scope["read"]

    def test_scope_no_duplicate_owner(self):
        """If owner is already in the list as @user, don't duplicate."""
        acl = {
            "wiki/doc.md": {
                "owner": "alice",
                "read": ["@alice", "team-a"],
                "write": ["@alice"],
                "manage": [],
                "inherited": False,
            }
        }
        store = _make_store(acl)
        scope = store.compute_access_scope("wiki/doc.md")
        assert scope["read"].count("@alice") == 1
        assert scope["write"].count("@alice") == 1


class TestBatchGroupOperations:
    """Batch operations for group rename/removal."""

    def test_get_paths_with_group(self):
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["hr-team"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            },
            "wiki/eng/": {
                "owner": "",
                "read": ["eng-team"],
                "write": ["eng-team"],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        paths = store.get_paths_with_group("hr-team")
        assert "wiki/hr/" in paths
        assert "wiki/eng/" not in paths

    def test_rename_group_references(self):
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["hr-team"],
                "write": ["hr-team", "admin"],
                "manage": ["hr-team"],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        store.rename_group_references("hr-team", "people-team")
        entry = store.get_all()["wiki/hr/"]
        assert "people-team" in entry["read"]
        assert "hr-team" not in entry["read"]
        assert "people-team" in entry["write"]
        assert "people-team" in entry["manage"]

    def test_remove_group_references(self):
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["hr-team", "all"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        store.remove_group_references("hr-team")
        entry = store.get_all()["wiki/hr/"]
        assert "hr-team" not in entry["read"]
        assert "all" in entry["read"]  # 'all' should remain
        assert "hr-team" not in entry["write"]

    def test_rename_handles_all_occurrences(self):
        """If a group appears multiple times in a field, all must be renamed."""
        acl = {
            "wiki/test/": {
                "owner": "",
                "read": ["team-a", "team-a"],
                "write": ["team-a"],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        store.rename_group_references("team-a", "team-b")
        entry = store.get_all()["wiki/test/"]
        assert "team-a" not in entry["read"]
        assert entry["read"].count("team-b") == 2
        assert entry["write"] == ["team-b"]

    def test_remove_handles_all_occurrences(self):
        """If a group appears multiple times in a field, all must be removed."""
        acl = {
            "wiki/test/": {
                "owner": "",
                "read": ["team-a", "team-a", "other"],
                "write": ["team-a"],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        store.remove_group_references("team-a")
        entry = store.get_all()["wiki/test/"]
        assert "team-a" not in entry["read"]
        assert entry["read"] == ["other"]
        assert entry["write"] == []


class TestGetAccessiblePrefixes:
    """get_accessible_prefixes with User object."""

    def test_returns_matching_prefixes(self):
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["hr-team"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            },
            "wiki/eng/": {
                "owner": "",
                "read": ["eng-team"],
                "write": ["eng-team"],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        user = _user("u1", groups=["hr-team"])
        prefixes = store.get_accessible_prefixes(user, "read")
        assert "wiki/hr" in prefixes
        assert "wiki/eng" not in prefixes

    def test_admin_gets_all_prefixes(self):
        acl = {
            "wiki/hr/": {
                "owner": "",
                "read": ["hr-team"],
                "write": ["hr-team"],
                "manage": [],
                "inherited": False,
            },
            "wiki/eng/": {
                "owner": "",
                "read": ["eng-team"],
                "write": ["eng-team"],
                "manage": [],
                "inherited": False,
            },
        }
        store = _make_store(acl)
        admin = _user("admin1", roles=["admin"])
        prefixes = store.get_accessible_prefixes(admin, "read")
        assert "wiki/hr" in prefixes
        assert "wiki/eng" in prefixes
