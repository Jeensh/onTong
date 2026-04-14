"""Development auth provider — multi-user from config file.

Selects user via X-User-Id header (default: first user in config).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Request

from backend.core.auth.base import AuthProvider
from backend.core.auth.models import User

logger = logging.getLogger(__name__)

_DEFAULT_USER = User(
    id="dev-user", name="개발자", email="dev@ontong.local", roles=["admin"],
)


class NoOpAuthProvider(AuthProvider):
    def __init__(self, users_path: Path | None = None,
                 group_store=None) -> None:
        self._users_path = users_path or Path("data/users.json")
        self._users: dict[str, User] = {}
        self._group_store = group_store

    async def on_startup(self) -> None:
        if self._users_path.exists():
            try:
                data = json.loads(
                    self._users_path.read_text(encoding="utf-8")
                )
                for u in data.get("users", []):
                    user = User(**u)
                    self._users[user.id] = user
                logger.info("Loaded %d dev users", len(self._users))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load users: %s", e)
        if not self._users:
            self._users[_DEFAULT_USER.id] = _DEFAULT_USER

    async def on_shutdown(self) -> None:
        pass

    async def authenticate(self, request: Request) -> User:
        user_id = request.headers.get("X-User-Id", "")
        user = self._users.get(user_id)
        if not user:
            # Default to first user
            user = next(iter(self._users.values()))
        # Resolve groups
        groups = await self.resolve_groups(user.id)
        return user.model_copy(update={"groups": groups})

    async def resolve_groups(self, user_id: str) -> list[str]:
        if not self._group_store:
            return []
        user_groups = self._group_store.get_user_groups(user_id)
        return [g.name for g in user_groups]
