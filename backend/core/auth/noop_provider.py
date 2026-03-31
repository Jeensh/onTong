"""No-op auth provider for development / demo.

Always returns a default user without checking any credentials.
"""

from __future__ import annotations

from fastapi import Request

from backend.core.auth.base import AuthProvider
from backend.core.auth.models import User

DEV_USER = User(
    id="dev-user",
    name="개발자",
    email="dev@ontong.local",
    roles=["admin"],
)


class NoOpAuthProvider(AuthProvider):
    """Zero-auth provider — every request is the dev user."""

    async def authenticate(self, request: Request) -> User:
        return DEV_USER

    async def on_startup(self) -> None:
        pass

    async def on_shutdown(self) -> None:
        pass
