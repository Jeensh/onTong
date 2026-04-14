"""ACL (Access Control List) store v2 — default-deny, owner/manage, inheritance.

ACL is stored as a JSON file. Structure (v2):
{
  "wiki/hr/": {
    "owner": "hr-admin",
    "read": ["hr-team", "admin"],
    "write": ["hr-team", "admin"],
    "manage": ["hr-admin"],
    "inherited": false
  },
  "wiki/hr/salary.md": {
    "owner": "hr-admin",
    "read": ["hr-lead"],
    "write": ["hr-lead"],
    "manage": ["hr-admin"],
    "inherited": false
  }
}

Rules (v2):
- Default is DENY if no ACL entry exists (opposite of v1)
- "all" grants access to everyone
- "@username" matches a specific user by id
- Group names match user.groups, role names match user.roles
- Folder paths end with "/"
- Child documents inherit parent folder permissions (walk up)
- Document-level overrides (inherited=False on a doc) take precedence
- @username/ paths are personal spaces: only that user (and admin) can access
- Owner of a resource always has read + write + manage
- Admin role always has full access everywhere
- "manage" permission controls who can modify the ACL itself
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from backend.core.auth.models import User
from backend.core.config import settings

logger = logging.getLogger(__name__)

Permission = Literal["read", "write", "manage"]

# Cache TTL must be >= poll interval for consistent revocation behavior.
# A permission result can be stale for up to _CACHE_TTL seconds after a
# file change is detected by the watcher.
_CACHE_TTL = 60  # seconds
_FILE_POLL_INTERVAL = 30  # seconds


class ACLEntry(BaseModel):
    """Single ACL entry for a path (folder or document)."""

    path: str = ""
    owner: str = ""
    read: list[str] = []       # principals: group names, @userID, "all"
    write: list[str] = []
    manage: list[str] = []     # who can change this ACL
    inherited: bool = True     # True = inherited from parent folder


class ACLStore:
    """JSON file-based ACL manager v2 with default-deny, owner/manage, inheritance.

    Thread-safe: all public methods acquire self._lock (RLock for reentrant
    calls like _save → _invalidate_cache). The daemon watcher thread also
    acquires the lock before reloading.
    """

    def __init__(self, acl_path: Path | None = None) -> None:
        self._acl_path = acl_path or (settings.wiki_dir / ".acl.json")
        self._lock = threading.RLock()
        self._acl: dict[str, dict] = {}
        self._last_mtime: float = 0.0
        self._perm_cache: dict[tuple, tuple[bool, float]] = {}
        self._load()
        self._start_watcher()

    # ── Persistence ──────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load ACL from disk. Caller must hold self._lock or be in __init__."""
        if self._acl_path.exists():
            try:
                with open(self._acl_path, "r", encoding="utf-8") as f:
                    self._acl = json.load(f)
                self._last_mtime = os.path.getmtime(self._acl_path)
                self._invalidate_cache()
                logger.info("ACL loaded: %d entries from %s", len(self._acl), self._acl_path)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load ACL: %s, using empty (deny-all)", e)
                self._acl = {}
        else:
            self._acl = {}
            logger.info("No ACL file found, using default (deny-all)")

    def _save(self) -> None:
        """Save ACL to disk. Caller must hold self._lock."""
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
                    with self._lock:
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

    # ── Entry Resolution (shared by check_permission and compute_access_scope)

    def _resolve_entry(self, path: str) -> dict | None:
        """Return the effective ACL entry for a path, walking up folders.

        Caller must hold self._lock.

        Returns:
            The matching ACL entry dict, or None if no ACL covers this path.
        """
        # Exact match (document override, inherited=False)
        entry = self._acl.get(path)
        if entry and not entry.get("inherited", True):
            return entry

        # Walk up parent folders
        parts = path.split("/")
        for i in range(len(parts) - 1, 0, -1):
            folder_path = "/".join(parts[:i]) + "/"
            folder_entry = self._acl.get(folder_path)
            if folder_entry:
                return folder_entry

        return None

    # ── Permission Checking ──────────────────────────────────────────────

    def check_permission(
        self, path: str, user: User, permission: Permission
    ) -> bool:
        """Check if user has permission on path.

        Results are cached with TTL for repeated checks.

        Rules (evaluated in order):
        1. Admin role → always allow
        2. @username/ personal space → only that user (and admin)
        3. Document has own ACL (inherited=False) → use that ACL
        4. No own ACL → walk up parent folders recursively
        5. No ACL found at root → DENY (default-deny)
        6. Owner → always has read + write + manage on their resources
        """
        cache_key = (
            path,
            user.id,
            tuple(sorted(user.roles)),
            tuple(sorted(user.groups)),
            permission,
        )
        with self._lock:
            cached = self._perm_cache.get(cache_key)
            if cached is not None:
                result, ts = cached
                if time.time() - ts < _CACHE_TTL:
                    return result

            result = self._check_permission_uncached(path, user, permission)
            self._perm_cache[cache_key] = (result, time.time())
            return result

    def _check_permission_uncached(
        self, path: str, user: User, permission: Permission
    ) -> bool:
        """Caller must hold self._lock."""
        # Rule 1: admin role → always allow
        if "admin" in user.roles:
            return True

        # Rule 2: @username/ personal space — only that user
        if path.startswith("@"):
            slash_idx = path.find("/")
            if slash_idx > 0:
                space_owner = path[1:slash_idx]
                return user.id == space_owner
            space_owner = path[1:]
            return user.id == space_owner

        # Rules 3-4: resolve effective ACL entry (doc override or folder walk-up)
        entry = self._resolve_entry(path)
        if entry:
            return self._entry_allows(entry, user, permission)

        # Rule 5: no ACL found → DENY (default-deny)
        return False

    def _entry_allows(
        self, entry: dict, user: User, permission: Permission
    ) -> bool:
        """Check if an ACL entry grants permission to the user.

        Rule 6: Owner always has read + write + manage.
        Then check principals list for the requested permission.
        """
        owner = entry.get("owner", "")
        if owner and user.id == owner:
            return True

        principals: list[str] = entry.get(permission, [])
        return self._principals_match(principals, user)

    @staticmethod
    def _principals_match(principals: list[str], user: User) -> bool:
        """Check if any principal in the list matches the user.

        Matching rules:
        - "all" matches everyone
        - "@username" matches user.id
        - group names match user.groups
        - role names match user.roles
        """
        if not principals:
            return False
        if "all" in principals:
            return True

        user_identifiers: set[str] = set()
        user_identifiers.add(f"@{user.id}")
        user_identifiers.update(user.groups)
        user_identifiers.update(user.roles)

        return bool(set(principals) & user_identifiers)

    # ── Access Scope (for ChromaDB metadata) ─────────────────────────────

    @staticmethod
    def _inject_owner(entry: dict, read_list: list[str], write_list: list[str]) -> None:
        """Add @{owner} to read/write lists if not already present."""
        owner = entry.get("owner", "")
        if owner:
            owner_principal = f"@{owner}"
            if owner_principal not in read_list:
                read_list.append(owner_principal)
            if owner_principal not in write_list:
                write_list.append(owner_principal)

    def compute_access_scope(self, path: str) -> dict[str, list[str]]:
        """Return read/write principal lists for a path.

        Used to stamp ChromaDB metadata so search can pre-filter by access.
        """
        with self._lock:
            # Personal space
            if path.startswith("@"):
                slash_idx = path.find("/")
                if slash_idx > 0:
                    owner_principal = f"@{path[1:slash_idx]}"
                else:
                    owner_principal = f"@{path[1:]}"
                return {"read": [owner_principal], "write": [owner_principal]}

            entry = self._resolve_entry(path)
            if entry:
                read_list = list(entry.get("read", []))
                write_list = list(entry.get("write", []))
                self._inject_owner(entry, read_list, write_list)
                return {"read": read_list, "write": write_list}

            # No ACL → empty (deny all)
            return {"read": [], "write": []}

    # ── Accessible Prefixes (RAG fallback) ───────────────────────────────

    def get_accessible_prefixes(
        self, user: User, permission: Permission
    ) -> list[str]:
        """Get list of path prefixes the user can access.

        Returns list of path prefixes where the user has the given permission.
        Includes the user's personal space (@username).
        Used by RAG to filter search results.
        """
        with self._lock:
            prefixes: list[str] = []

            # Personal space is always accessible to the owner
            prefixes.append(f"@{user.id}")

            if not self._acl:
                return prefixes

            for path, entry in self._acl.items():
                # Admin always has access
                if "admin" in user.roles:
                    prefixes.append(path.rstrip("/"))
                    continue

                # Owner check
                owner = entry.get("owner", "")
                if owner and user.id == owner:
                    prefixes.append(path.rstrip("/"))
                    continue

                # Principals check
                allowed = entry.get(permission, [])
                if self._principals_match(allowed, user):
                    prefixes.append(path.rstrip("/"))

            return prefixes

    # ── Batch Group Operations ───────────────────────────────────────────

    def get_paths_with_group(self, group_name: str) -> list[str]:
        """Find all paths whose ACL references the given group name."""
        with self._lock:
            paths: list[str] = []
            for path, entry in self._acl.items():
                for field in ("read", "write", "manage"):
                    if group_name in entry.get(field, []):
                        paths.append(path)
                        break
            return paths

    def rename_group_references(self, old_name: str, new_name: str) -> None:
        """Rename a group in all ACL entries (all occurrences)."""
        with self._lock:
            changed = False
            for path, entry in self._acl.items():
                for field in ("read", "write", "manage"):
                    principals: list[str] = entry.get(field, [])
                    if old_name in principals:
                        entry[field] = [new_name if p == old_name else p for p in principals]
                        changed = True
            if changed:
                self._save()

    def remove_group_references(self, group_name: str) -> None:
        """Remove a group from all ACL entries (all occurrences)."""
        with self._lock:
            changed = False
            for path, entry in self._acl.items():
                for field in ("read", "write", "manage"):
                    principals: list[str] = entry.get(field, [])
                    if group_name in principals:
                        entry[field] = [p for p in principals if p != group_name]
                        changed = True
            if changed:
                self._save()

    # ── CRUD ─────────────────────────────────────────────────────────────

    def set_acl(
        self,
        path: str,
        read: list[str],
        write: list[str],
        manage: list[str] | None = None,
        owner: str = "",
        inherited: bool = False,
    ) -> None:
        """Set ACL for a path (folder or document)."""
        with self._lock:
            self._acl[path] = {
                "owner": owner,
                "read": read,
                "write": write,
                "manage": manage or [],
                "inherited": inherited,
            }
            self._save()

    def remove_acl(self, path: str) -> bool:
        """Remove ACL entry for a path."""
        with self._lock:
            if path in self._acl:
                del self._acl[path]
                self._save()
                return True
            return False

    def get_all(self) -> dict[str, dict]:
        """Get full ACL data (deep copy)."""
        import copy
        with self._lock:
            return copy.deepcopy(self._acl)


# Lazy singleton — avoids import-time I/O and thread spawning.
# Consumers that do `from backend.core.auth.acl_store import acl_store`
# will get the module-level __getattr__ triggered on first attribute access.
_acl_store_instance: ACLStore | None = None
_init_lock = threading.Lock()


def get_acl_store() -> ACLStore:
    """Return the singleton ACLStore, creating it on first call."""
    global _acl_store_instance
    if _acl_store_instance is None:
        with _init_lock:
            if _acl_store_instance is None:
                _acl_store_instance = ACLStore()
    return _acl_store_instance


def __getattr__(name: str):
    if name == "acl_store":
        return get_acl_store()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
