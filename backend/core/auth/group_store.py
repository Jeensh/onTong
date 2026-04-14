"""Group store for managing user groups (departments and custom teams).

Groups are stored as a JSON file. Each group has:
- id: unique identifier (e.g. "grp-infra")
- name: display name (e.g. "인프라팀")
- type: "department" (admin-managed, org structure) or "custom" (user-created)
- members: list of user IDs
- created_by: user ID who created the group
- managed_by: list of user IDs who can manage the group

Used by the ACL system for permission checks (e.g. "인프라팀" can read/write "인프라/").
"""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Group(BaseModel):
    """A user group — either a department or a custom team."""

    id: str
    name: str
    type: Literal["department", "custom"]
    members: list[str] = []
    created_by: str = ""
    managed_by: list[str] = []


class GroupStore(ABC):
    """Abstract interface for group storage."""

    @abstractmethod
    def create(self, group: Group) -> Group: ...

    @abstractmethod
    def get(self, group_id: str) -> Group | None: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Group | None: ...

    @abstractmethod
    def list_all(self) -> list[Group]: ...

    @abstractmethod
    def add_member(self, group_id: str, user_id: str) -> bool: ...

    @abstractmethod
    def remove_member(self, group_id: str, user_id: str) -> bool: ...

    @abstractmethod
    def rename(self, group_id: str, new_name: str) -> bool: ...

    @abstractmethod
    def delete(self, group_id: str) -> bool: ...

    @abstractmethod
    def get_user_groups(self, user_id: str) -> list[Group]: ...


class JSONGroupStore(GroupStore):
    """JSON file-backed group store with thread-safe locking."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path("data/groups.json")
        self._lock = threading.Lock()
        self._groups: dict[str, Group] = {}
        self._load()

    # -- persistence -------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._groups = {
                    gid: Group.model_validate(gdata)
                    for gid, gdata in data.items()
                }
                logger.info("Groups loaded: %d entries from %s", len(self._groups), self._path)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load groups: %s", e)
                self._groups = {}
        else:
            self._groups = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(
                {gid: g.model_dump() for gid, g in self._groups.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    # -- public API --------------------------------------------------

    def create(self, group: Group) -> Group:
        with self._lock:
            self._groups[group.id] = group
            self._save()
        return group

    def get(self, group_id: str) -> Group | None:
        return self._groups.get(group_id)

    def get_by_name(self, name: str) -> Group | None:
        for g in self._groups.values():
            if g.name == name:
                return g
        return None

    def list_all(self) -> list[Group]:
        return list(self._groups.values())

    def add_member(self, group_id: str, user_id: str) -> bool:
        with self._lock:
            group = self._groups.get(group_id)
            if group is None:
                return False
            if user_id not in group.members:
                group.members.append(user_id)
                self._save()
            return True

    def remove_member(self, group_id: str, user_id: str) -> bool:
        with self._lock:
            group = self._groups.get(group_id)
            if group is None:
                return False
            if user_id in group.members:
                group.members.remove(user_id)
                self._save()
            return True

    def rename(self, group_id: str, new_name: str) -> bool:
        with self._lock:
            group = self._groups.get(group_id)
            if group is None:
                return False
            group.name = new_name
            self._save()
            return True

    def delete(self, group_id: str) -> bool:
        with self._lock:
            if group_id not in self._groups:
                return False
            del self._groups[group_id]
            self._save()
            return True

    def get_user_groups(self, user_id: str) -> list[Group]:
        return [g for g in self._groups.values() if user_id in g.members]
