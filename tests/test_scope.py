"""Access scope computation tests."""
from backend.core.auth.models import User
from backend.core.auth.scope import (
    get_user_scope,
    format_scope_for_chroma,
    build_scope_where_clause,
)


def make_user(uid: str, roles=None, groups=None) -> User:
    return User(id=uid, name=uid, roles=roles or [], groups=groups or [])


class TestGetUserScope:
    def test_basic_scope(self):
        user = make_user("donghae", roles=["admin"], groups=["인프라팀"])
        scope = get_user_scope(user)
        assert "@donghae" in scope
        assert "인프라팀" in scope
        assert "admin" in scope
        assert "all" in scope

    def test_no_groups_no_roles(self):
        user = make_user("viewer")
        scope = get_user_scope(user)
        assert scope == ["@viewer", "all"]

    def test_multiple_groups(self):
        user = make_user("u1", groups=["인프라팀", "프로젝트X"])
        scope = get_user_scope(user)
        assert "인프라팀" in scope
        assert "프로젝트X" in scope


class TestFormatScopeForChroma:
    def test_pipe_delimited(self):
        principals = ["인프라팀", "@donghae", "admin"]
        result = format_scope_for_chroma(principals)
        assert result == "|인프라팀|@donghae|admin|"

    def test_empty(self):
        assert format_scope_for_chroma([]) == ""

    def test_single(self):
        assert format_scope_for_chroma(["@kim"]) == "|@kim|"


class TestBuildScopeWhereClause:
    def test_admin_returns_none(self):
        scope = ["@donghae", "인프라팀", "admin", "all"]
        assert build_scope_where_clause(scope) is None

    def test_empty_scope_never_matches(self):
        result = build_scope_where_clause([])
        assert result == {"access_read": {"$eq": "__never_match__"}}

    def test_single_item(self):
        result = build_scope_where_clause(["@kim"])
        assert result == {"access_read": {"$contains": "|@kim|"}}

    def test_multiple_items_or_clause(self):
        result = build_scope_where_clause(["@kim", "인프라팀", "all"])
        assert "$or" in result
        assert len(result["$or"]) == 3
        assert {"access_read": {"$contains": "|@kim|"}} in result["$or"]
        assert {"access_read": {"$contains": "|인프라팀|"}} in result["$or"]
        assert {"access_read": {"$contains": "|all|"}} in result["$or"]
