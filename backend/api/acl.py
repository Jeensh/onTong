"""ACL management API.

Endpoints:
    GET    /api/acl               → get all ACLs (admin only)
    GET    /api/acl/{path:path}   → get ACL for specific path (any authenticated user)
    PUT    /api/acl/{path:path}   → set ACL (requires manage permission or admin)
    DELETE /api/acl               → remove ACL (admin only, path as query param)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import User, get_current_user
from backend.core.auth.acl_store import acl_store
from backend.infrastructure.events.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/acl", tags=["acl"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


class ACLEntry(BaseModel):
    read: list[str] = []
    write: list[str] = []
    manage: list[str] = []
    owner: str = ""
    inherited: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(_require_admin)])
async def get_all_acl() -> dict:
    """Get full ACL configuration (admin only)."""
    return acl_store.get_all()


@router.get("/{path:path}")
async def get_acl_for_path(
    path: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Get effective ACL for a specific path.

    Returns the direct entry if it exists, otherwise returns the inherited
    entry resolved by walking up parent folders. Returns 404 if no ACL
    covers this path.
    """
    all_acl = acl_store.get_all()

    # Direct entry takes precedence
    entry = all_acl.get(path)
    if entry is not None:
        return {"path": path, **entry}

    # Compute effective (inherited) entry via compute_access_scope
    scope = acl_store.compute_access_scope(path)
    if scope["read"] or scope["write"]:
        return {
            "path": path,
            "read": scope["read"],
            "write": scope["write"],
            "manage": [],
            "owner": "",
            "inherited": True,
        }

    raise HTTPException(status_code=404, detail=f"No ACL entry found for: {path}")


@router.put("/{path:path}")
async def set_acl_for_path(
    path: str,
    entry: ACLEntry,
    user: User = Depends(get_current_user),
) -> dict:
    """Set ACL for a path (folder or document).

    Requires manage permission on the path, or admin role.
    Preserves existing owner if none is specified.
    """
    is_admin = "admin" in user.roles

    if not is_admin:
        has_manage = acl_store.check_permission(path, user, "manage")
        if not has_manage:
            raise HTTPException(
                status_code=403,
                detail="manage permission required to set ACL on this path",
            )

    # Preserve existing owner if the request doesn't specify one
    owner = entry.owner
    if not owner:
        existing = acl_store.get_all().get(path, {})
        owner = existing.get("owner", user.id)

    acl_store.set_acl(
        path=path,
        read=entry.read,
        write=entry.write,
        manage=entry.manage,
        owner=owner,
        inherited=entry.inherited,
    )

    event_bus.publish("acl_changed", {"path": path, "changed_by": user.id})

    result = {
        "path": path,
        "read": entry.read,
        "write": entry.write,
        "manage": entry.manage,
        "owner": owner,
        "inherited": entry.inherited,
    }
    logger.info("ACL set for %s by %s", path, user.id)
    return result


@router.delete("", dependencies=[Depends(_require_admin)])
async def remove_acl(path: str) -> dict:
    """Remove ACL entry for a path (admin only, path as query param)."""
    removed = acl_store.remove_acl(path)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No ACL entry for: {path}")
    return {"removed": path}
