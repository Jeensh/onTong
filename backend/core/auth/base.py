"""Abstract auth provider protocol.

Any authentication backend (SSO, LDAP, OIDC, JWT, API-key, etc.)
must implement this interface. The framework calls these methods
via FastAPI dependency injection — individual routes never touch
provider internals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import Request

from backend.core.auth.models import User


class AuthProvider(ABC):
    """Contract every auth provider must fulfil."""

    @abstractmethod
    async def authenticate(self, request: Request) -> User:
        """Extract and validate credentials from the incoming request.

        Implementations might read:
        - Authorization header (Bearer token, API key)
        - Cookies (session ID, SSO token)
        - Custom headers (X-User-Id from an API gateway)

        Raise ``fastapi.HTTPException(401)`` on failure.
        """

    @abstractmethod
    async def resolve_groups(self, user_id: str) -> list[str]:
        """Return group names the user belongs to."""

    @abstractmethod
    async def on_startup(self) -> None:
        """Run once at application startup (e.g., fetch JWKS, connect to LDAP)."""

    @abstractmethod
    async def on_shutdown(self) -> None:
        """Clean up on application shutdown."""
