"""User model — the single representation of an authenticated user."""

from __future__ import annotations

from pydantic import BaseModel


class User(BaseModel):
    """Authenticated user.

    All auth providers must produce this model.
    Add fields here as the product evolves (e.g., department, role).
    """

    id: str
    name: str
    email: str = ""
    roles: list[str] = []
    groups: list[str] = []
