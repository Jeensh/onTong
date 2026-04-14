"""Auth REST API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.auth import User, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user."""
    return user.model_dump()
