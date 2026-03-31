"""ACL (Access Control List) store for folder/document level permissions.

ACL is stored as a JSON file. Structure:
{
  "wiki/hr/": { "read": ["all"], "write": ["hr-team", "admin"] },
  "wiki/finance/": { "read": ["finance-team", "admin"], "write": ["finance-team", "admin"] }
}

Rules:
- "all" grants access to everyone
- Folder paths end with "/"
- Child documents inherit parent folder permissions
- Document-level overrides are supported (exact path match)
- If no ACL entry exists, default is read/write for all (open by default)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from backend.core.config import settings

logger = logging.getLogger(__name__)

Permission = Literal["read", "write"]

# Default ACL: everyone can read/write everything
DEFAULT_ACL: dict[str, dict[str, list[str]]] = {}

_CACHE_TTL = 60  # seconds
_FILE_POLL_INTERVAL = 30  # seconds


class ACLStore:
    """JSON file-based ACL manager with LRU caching and hot reload."""

    def __init__(self, acl_path: Path | None = None) -> None:
        self._acl_path = acl_path or (settings.wiki_dir / ".acl.json")
        self._acl: dict[str, dict[str, list[str]]] = {}
        self._last_mtime: float = 0.0
        self._perm_cache: dict[tuple[str, tuple[str, ...], str], tuple[bool, float]] = {}
        self._load()
        self._start_watcher()

    def _load(self) -> None:
        if self._acl_path.exists():
            try:
                with open(self._acl_path, "r", encoding="utf-8") as f:
                    self._acl = json.load(f)
                self._last_mtime = os.path.getmtime(self._acl_path)
                self._invalidate_cache()
                logger.info(f"ACL loaded: {len(self._acl)} entries from {self._acl_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load ACL: {e}, using default (open)")
                self._acl = DEFAULT_ACL.copy()
        else:
            self._acl = DEFAULT_ACL.copy()
            logger.info("No ACL file found, using default (open access)")

    def _save(self) -> None:
        self._acl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._acl_path, "w", encoding="utf-8") as f:
            json.dump(self._acl, f, ensure_ascii=False, indent=2)
        self._last_mtime = os.path.getmtime(self._acl_path)
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        self._perm_cache.clear()

    def _check_file_changed(self) -> None:
        """Reload ACL if the file has been modified externally."""
        try:
            if self._acl_path.exists():
                mtime = os.path.getmtime(self._acl_path)
                if mtime > self._last_mtime:
                    logger.info("ACL file changed on disk, reloading")
                    self._load()
        except OSError:
            pass

    def _start_watcher(self) -> None:
        """Start a daemon thread that polls the ACL file for changes."""
        def _poll():
            while True:
                time.sleep(_FILE_POLL_INTERVAL)
                self._check_file_changed()

        t = threading.Thread(target=_poll, daemon=True, name="acl-watcher")
        t.start()

    def check_permission(
        self, path: str, user_roles: list[str], permission: Permission
    ) -> bool:
        """Check if user with given roles has permission on path.

        Results are cached with TTL for repeated checks on the same path/roles.

        Lookup order:
        1. Exact path match (document-level override)
        2. Walk up parent folders until a match is found
        3. If no ACL entry exists → allow (open by default)
        """
        cache_key = (path, tuple(sorted(user_roles)), permission)
        cached = self._perm_cache.get(cache_key)
        if cached is not None:
            result, ts = cached
            if time.time() - ts < _CACHE_TTL:
                return result

        result = self._check_permission_uncached(path, user_roles, permission)
        self._perm_cache[cache_key] = (result, time.time())
        return result

    def _check_permission_uncached(
        self, path: str, user_roles: list[str], permission: Permission
    ) -> bool:
        # 1. Exact match
        entry = self._acl.get(path)
        if entry:
            return self._roles_match(entry.get(permission, []), user_roles)

        # 2. Walk up parent folders
        parts = path.split("/")
        for i in range(len(parts) - 1, 0, -1):
            folder_path = "/".join(parts[:i]) + "/"
            entry = self._acl.get(folder_path)
            if entry:
                return self._roles_match(entry.get(permission, []), user_roles)

        # 3. No ACL → open access
        return True

    def get_accessible_prefixes(self, user_roles: list[str], permission: Permission) -> list[str]:
        """Get list of path prefixes the user can access.

        Returns empty list if no ACL restrictions exist (all accessible).
        Used by RAG to filter search results.
        """
        if not self._acl:
            return []  # No ACL → everything accessible

        prefixes: list[str] = []
        for path, entry in self._acl.items():
            allowed = entry.get(permission, [])
            if self._roles_match(allowed, user_roles):
                prefixes.append(path.rstrip("/"))

        return prefixes

    def set_acl(self, path: str, read: list[str], write: list[str]) -> None:
        """Set ACL for a path (folder or document)."""
        self._acl[path] = {"read": read, "write": write}
        self._save()

    def remove_acl(self, path: str) -> bool:
        """Remove ACL entry for a path."""
        if path in self._acl:
            del self._acl[path]
            self._save()
            return True
        return False

    def get_all(self) -> dict[str, dict[str, list[str]]]:
        """Get full ACL data."""
        return self._acl.copy()

    @staticmethod
    def _roles_match(allowed_roles: list[str], user_roles: list[str]) -> bool:
        """Check if any user role matches the allowed roles."""
        if "all" in allowed_roles:
            return True
        if "admin" in user_roles:
            return True  # Admin always has access
        return bool(set(allowed_roles) & set(user_roles))


# Singleton
acl_store = ACLStore()
