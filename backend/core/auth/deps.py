"""FastAPI dependency — the only thing routes import.

Usage in any router:
    from backend.core.auth import get_current_user, User

    @router.get("/something")
    async def something(user: User = Depends(get_current_user)):
        ...
"""

from __future__ import annotations

from fastapi import Depends, Request

from backend.core.auth.base import AuthProvider
from backend.core.auth.models import User

# Populated at startup by init_auth()
_provider: AuthProvider | None = None


def init_auth(provider: AuthProvider) -> None:
    """Called once from main.py lifespan."""
    global _provider
    _provider = provider


def get_provider() -> AuthProvider:
    if _provider is None:
        raise RuntimeError("AuthProvider not initialized — call init_auth() at startup")
    return _provider


async def get_current_user(
    request: Request,
    provider: AuthProvider = Depends(get_provider),
) -> User:
    """FastAPI dependency that resolves the current user."""
    return await provider.authenticate(request)
