"""Auth provider factory — resolves AUTH_PROVIDER setting to a concrete class."""

from __future__ import annotations

from backend.core.auth.base import AuthProvider


def create_auth_provider(provider_name: str) -> AuthProvider:
    """Return an AuthProvider instance for the given name.

    To add a new provider:
      1. Implement AuthProvider in a new module
      2. Add an elif branch here
    """
    if provider_name == "noop":
        from backend.core.auth.noop_provider import NoOpAuthProvider
        return NoOpAuthProvider()

    raise ValueError(
        f"Unknown auth provider: {provider_name!r}. "
        f"Available: noop"
    )
