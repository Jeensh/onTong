"""Tests for Group model and JSONGroupStore."""

import json
import pytest
from pathlib import Path

from backend.core.auth.group_store import Group, JSONGroupStore


# ------------------------------------------------------------------
# TestGroupModel
# ------------------------------------------------------------------


class TestGroupModel:
    """Tests for the Group Pydantic model."""

    def test_create_department(self):
        g = Group(
            id="grp-infra",
            name="인프라팀",
            type="department",
            members=["alice", "bob"],
            created_by="admin",
            managed_by=["admin"],
        )
        assert g.id == "grp-infra"
        assert g.name == "인프라팀"
        assert g.type == "department"
        assert g.members == ["alice", "bob"]
        assert g.created_by == "admin"
        assert g.managed_by == ["admin"]

    def test_create_custom(self):
        g = Group(
            id="grp-proj-x",
            name="Project X",
            type="custom",
            members=["carol"],
            created_by="carol",
            managed_by=["carol"],
        )
        assert g.type == "custom"
        assert g.created_by == "carol"


# ------------------------------------------------------------------
# TestJSONGroupStore
# ------------------------------------------------------------------


class TestJSONGroupStore:
    """Tests for the JSON file-backed GroupStore."""

    @pytest.fixture()
    def store(self, tmp_path: Path) -> JSONGroupStore:
        return JSONGroupStore(path=tmp_path / "groups.json")

    @pytest.fixture()
    def sample_group(self) -> Group:
        return Group(
            id="grp-1",
            name="인프라팀",
            type="department",
            members=["alice", "bob"],
            created_by="admin",
            managed_by=["admin"],
        )

    # -- create & get ------------------------------------------------

    def test_create_and_get(self, store: JSONGroupStore, sample_group: Group):
        store.create(sample_group)
        fetched = store.get(sample_group.id)
        assert fetched is not None
        assert fetched.id == sample_group.id
        assert fetched.name == sample_group.name
        assert fetched.members == sample_group.members

    def test_get_nonexistent(self, store: JSONGroupStore):
        assert store.get("does-not-exist") is None

    # -- list_all ----------------------------------------------------

    def test_list_all(self, store: JSONGroupStore, sample_group: Group):
        g2 = Group(
            id="grp-2",
            name="Project X",
            type="custom",
            members=["carol"],
            created_by="carol",
            managed_by=["carol"],
        )
        store.create(sample_group)
        store.create(g2)
        groups = store.list_all()
        assert len(groups) == 2
        ids = {g.id for g in groups}
        assert ids == {"grp-1", "grp-2"}

    # -- add_member --------------------------------------------------

    def test_add_member(self, store: JSONGroupStore, sample_group: Group):
        store.create(sample_group)
        store.add_member("grp-1", "carol")
        g = store.get("grp-1")
        assert g is not None
        assert "carol" in g.members

    def test_add_member_idempotent(self, store: JSONGroupStore, sample_group: Group):
        store.create(sample_group)
        store.add_member("grp-1", "alice")  # alice already a member
        g = store.get("grp-1")
        assert g is not None
        assert g.members.count("alice") == 1

    # -- remove_member -----------------------------------------------

    def test_remove_member(self, store: JSONGroupStore, sample_group: Group):
        store.create(sample_group)
        store.remove_member("grp-1", "bob")
        g = store.get("grp-1")
        assert g is not None
        assert "bob" not in g.members
        assert "alice" in g.members

    # -- rename ------------------------------------------------------

    def test_rename(self, store: JSONGroupStore, sample_group: Group):
        store.create(sample_group)
        store.rename("grp-1", "인프라운영팀")
        g = store.get("grp-1")
        assert g is not None
        assert g.name == "인프라운영팀"

    # -- delete ------------------------------------------------------

    def test_delete(self, store: JSONGroupStore, sample_group: Group):
        store.create(sample_group)
        result = store.delete("grp-1")
        assert result is True
        assert store.get("grp-1") is None

    def test_delete_nonexistent(self, store: JSONGroupStore):
        result = store.delete("does-not-exist")
        assert result is False

    # -- get_user_groups ---------------------------------------------

    def test_get_user_groups(self, store: JSONGroupStore, sample_group: Group):
        g2 = Group(
            id="grp-2",
            name="Project X",
            type="custom",
            members=["alice", "carol"],
            created_by="carol",
            managed_by=["carol"],
        )
        store.create(sample_group)
        store.create(g2)

        alice_groups = store.get_user_groups("alice")
        assert len(alice_groups) == 2

        carol_groups = store.get_user_groups("carol")
        assert len(carol_groups) == 1
        assert carol_groups[0].id == "grp-2"

        nobody_groups = store.get_user_groups("nobody")
        assert len(nobody_groups) == 0

    # -- persistence -------------------------------------------------

    def test_persistence(self, tmp_path: Path, sample_group: Group):
        path = tmp_path / "groups.json"
        store1 = JSONGroupStore(path=path)
        store1.create(sample_group)

        # New store instance reads from the same file
        store2 = JSONGroupStore(path=path)
        fetched = store2.get("grp-1")
        assert fetched is not None
        assert fetched.name == "인프라팀"

    # -- get_by_name -------------------------------------------------

    def test_get_by_name(self, store: JSONGroupStore, sample_group: Group):
        store.create(sample_group)
        fetched = store.get_by_name("인프라팀")
        assert fetched is not None
        assert fetched.id == "grp-1"

    def test_get_by_name_nonexistent(self, store: JSONGroupStore):
        assert store.get_by_name("ghost") is None
