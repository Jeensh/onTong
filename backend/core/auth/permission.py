"""Permission check dependencies for FastAPI routes.

Usage:
    from backend.core.auth.permission import require_read, require_write

    @router.get("/file/{path:path}")
    async def get_file(path: str, user: User = Depends(require_read)):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from backend.core.auth.acl_store import acl_store
from backend.core.auth.deps import get_current_user
from backend.core.auth.models import User


async def require_read(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """Dependency that checks read permission for the path in the request."""
    path = _extract_path(request)
    if path and not acl_store.check_permission(path, user.roles, "read"):
        raise HTTPException(status_code=403, detail=f"No read access to {path}")
    return user


async def require_write(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """Dependency that checks write permission for the path in the request."""
    path = _extract_path(request)
    if path and not acl_store.check_permission(path, user.roles, "write"):
        raise HTTPException(status_code=403, detail=f"No write access to {path}")
    return user


def _extract_path(request: Request) -> str | None:
    """Extract wiki file path from request path parameters."""
    return request.path_params.get("path")
