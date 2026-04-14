"""Group management API.

Endpoints:
    GET    /api/groups            → list all groups
    POST   /api/groups            → create group
    GET    /api/groups/{group_id} → get single group
    PUT    /api/groups/{group_id}/members → add/remove members
    PUT    /api/groups/{group_id} → rename group (admin only)
    DELETE /api/groups/{group_id} → delete group (admin only)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import User, get_current_user
from backend.core.auth.group_store import Group, GroupStore
from backend.core.auth.acl_store import acl_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/groups", tags=["groups"])

_group_store: GroupStore | None = None


def init(group_store: GroupStore) -> None:
    global _group_store
    _group_store = group_store


def _store() -> GroupStore:
    if _group_store is None:
        raise RuntimeError("GroupStore not initialized")
    return _group_store


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


# ── Request models ────────────────────────────────────────────────────────────


class CreateGroupRequest(BaseModel):
    id: str
    name: str
    type: str = "custom"
    members: list[str] = []


class MemberUpdateRequest(BaseModel):
    add: list[str] = []
    remove: list[str] = []


class RenameRequest(BaseModel):
    name: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("")
async def list_groups(user: User = Depends(get_current_user)) -> list[dict]:
    """List all groups."""
    return [g.model_dump() for g in _store().list_all()]


@router.post("", status_code=201)
async def create_group(
    req: CreateGroupRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Create a new group.

    - custom type: any authenticated user
    - department type: admin only
    """
    if req.type == "department" and "admin" not in user.roles:
        raise HTTPException(
            status_code=403,
            detail="Admin role required to create department groups",
        )

    # Guard against duplicate IDs
    if _store().get(req.id) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Group with id '{req.id}' already exists",
        )

    group = Group(
        id=req.id,
        name=req.name,
        type=req.type,  # type: ignore[arg-type]
        members=req.members,
        created_by=user.id,
        managed_by=[user.id],
    )
    created = _store().create(group)
    logger.info("Group created: %s by %s", created.id, user.id)
    return created.model_dump()


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Get a single group by ID."""
    group = _store().get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")
    return group.model_dump()


@router.put("/{group_id}/members")
async def update_members(
    group_id: str,
    req: MemberUpdateRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Add or remove group members.

    Requires: caller is in managed_by list or has admin role.
    """
    group = _store().get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")

    # Permission check: admin or group manager
    if "admin" not in user.roles and user.id not in group.managed_by:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage this group's members",
        )

    for uid in req.add:
        _store().add_member(group_id, uid)
    for uid in req.remove:
        _store().remove_member(group_id, uid)

    updated = _store().get(group_id)
    logger.info(
        "Group %s members updated by %s: +%s -%s",
        group_id,
        user.id,
        req.add,
        req.remove,
    )
    return updated.model_dump() if updated else {}


@router.put("/{group_id}")
async def rename_group(
    group_id: str,
    req: RenameRequest,
    user: User = Depends(_require_admin),
) -> dict:
    """Rename a group and update all ACL references (admin only)."""
    group = _store().get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")

    old_name = group.name
    renamed = _store().rename(group_id, req.name)
    if not renamed:
        raise HTTPException(status_code=500, detail="Rename failed")

    # Update references in ACL store
    acl_store.rename_group_references(old_name, req.name)

    updated = _store().get(group_id)
    logger.info("Group %s renamed: %s → %s by %s", group_id, old_name, req.name, user.id)
    return updated.model_dump() if updated else {}


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    user: User = Depends(_require_admin),
) -> dict:
    """Delete a group and remove all ACL references (admin only)."""
    group = _store().get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")

    group_name = group.name

    # Remove all ACL references first
    acl_store.remove_group_references(group_name)

    deleted = _store().delete(group_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Delete failed")

    logger.info("Group %s (%s) deleted by %s", group_id, group_name, user.id)
    return {"deleted": group_id, "name": group_name}
