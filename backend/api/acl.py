"""ACL management API — admin only."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import User, get_current_user
from backend.core.auth.acl_store import acl_store

router = APIRouter(prefix="/api/acl", tags=["acl"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


class ACLEntry(BaseModel):
    path: str
    read: list[str]
    write: list[str]


@router.get("", dependencies=[Depends(_require_admin)])
async def get_acl():
    """Get full ACL configuration."""
    return acl_store.get_all()


@router.put("", dependencies=[Depends(_require_admin)])
async def set_acl(entry: ACLEntry):
    """Set ACL for a path (folder or document)."""
    acl_store.set_acl(entry.path, entry.read, entry.write)
    return {"path": entry.path, "read": entry.read, "write": entry.write}


@router.delete("", dependencies=[Depends(_require_admin)])
async def remove_acl(path: str):
    """Remove ACL entry for a path."""
    removed = acl_store.remove_acl(path)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No ACL entry for: {path}")
    return {"removed": path}
