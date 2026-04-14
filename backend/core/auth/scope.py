"""Access scope computation for ChromaDB metadata."""
from __future__ import annotations

from backend.core.auth.models import User


def get_user_scope(user: User) -> list[str]:
    """Compute the list of principals this user matches.

    Used at query time to filter ChromaDB results:
    where: access_read contains any of user_scope.
    """
    scope = [f"@{user.id}"]
    scope.extend(user.groups)
    scope.extend(user.roles)
    scope.append("all")
    return scope


def format_scope_for_chroma(principals: list[str]) -> str:
    """Convert principal list to pipe-delimited string for ChromaDB.

    Example: ["인프라팀", "@kim"] → "|인프라팀|@kim|"
    Matches existing pipe-delimited convention for tags field.
    """
    if not principals:
        return ""
    return "|" + "|".join(principals) + "|"


def build_scope_where_clause(user_scope: list[str]) -> dict | None:
    """Build ChromaDB where clause for access_read filtering.

    Returns $or clause checking if access_read contains any scope item.
    Returns None if user has admin role (no filtering needed).
    """
    if "admin" in user_scope:
        return None  # admin sees everything
    if not user_scope:
        return {"access_read": {"$eq": "__never_match__"}}
    conditions = [
        {"access_read": {"$contains": f"|{item}|"}}
        for item in user_scope
    ]
    if len(conditions) == 1:
        return conditions[0]
    return {"$or": conditions}
