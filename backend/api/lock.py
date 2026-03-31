"""Document lock API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.application.lock_service import get_lock_service

router = APIRouter(prefix="/api/lock", tags=["lock"])


def _svc():
    return get_lock_service()


class LockRequest(BaseModel):
    path: str
    user: str
    ttl: int = 300


class LockResponse(BaseModel):
    locked: bool
    path: str
    user: str = ""
    remaining: int = 0
    message: str = ""


@router.post("", response_model=LockResponse)
async def acquire_lock(req: LockRequest):
    """Acquire a lock on a document."""
    lock = _svc().acquire(req.path, req.user, req.ttl)
    if lock:
        return LockResponse(
            locked=True,
            path=lock.path,
            user=lock.user,
            remaining=lock.remaining,
            message="Lock acquired",
        )

    # Lock held by another user
    existing = _svc().status(req.path)
    return LockResponse(
        locked=False,
        path=req.path,
        user=existing.user if existing else "",
        remaining=existing.remaining if existing else 0,
        message=f"Document is being edited by {existing.user}" if existing else "",
    )


@router.delete("")
async def release_lock(path: str, user: str):
    """Release a lock on a document."""
    released = _svc().release(path, user)
    if not released:
        raise HTTPException(status_code=403, detail="Cannot release lock held by another user")
    return {"released": True, "path": path}


@router.get("/status")
async def get_lock_status(path: str):
    """Check lock status for a document."""
    lock = _svc().status(path)
    if lock:
        return LockResponse(
            locked=True,
            path=lock.path,
            user=lock.user,
            remaining=lock.remaining,
        )
    return LockResponse(locked=False, path=path)


@router.post("/refresh")
async def refresh_lock(path: str, user: str):
    """Refresh lock TTL."""
    refreshed = _svc().refresh(path, user)
    if not refreshed:
        raise HTTPException(status_code=403, detail="No active lock found for this user")
    lock = _svc().status(path)
    return LockResponse(
        locked=True,
        path=path,
        user=user,
        remaining=lock.remaining if lock else 0,
        message="Lock refreshed",
    )


class BatchRefreshRequest(BaseModel):
    paths: list[str]
    user: str


@router.post("/batch-refresh")
async def batch_refresh_locks(req: BatchRefreshRequest):
    """Refresh multiple locks at once (reduces request count from N to 1)."""
    count = _svc().batch_refresh(req.paths, req.user)
    return {"refreshed": count, "total": len(req.paths)}


@router.delete("/user")
async def release_all_user_locks(user: str):
    """Release all locks held by a user (e.g., on session end)."""
    count = _svc().release_all_by_user(user)
    return {"released_count": count, "user": user}
