"""OCCManager + ConflictPayload + VersionConflict exception."""
from __future__ import annotations

from dataclasses import dataclass

from ulid import ULID

from .version_protocol import VersionStore


@dataclass(frozen=True)
class ConflictPayload:
    path: str
    base_version: str
    server_version: str
    server_content: str
    server_updated_by: str


class VersionConflict(Exception):
    """Raised when If-Match version does not match server's current version."""

    def __init__(self, payload: ConflictPayload) -> None:
        self.payload = payload
        super().__init__(
            f"Version conflict for {payload.path}: "
            f"client={payload.base_version}, server={payload.server_version}"
        )


class OCCManager:
    def __init__(self, store: VersionStore) -> None:
        self._store = store

    def issue(self, path: str, *, updated_by: str = "") -> str:
        """Generate a fresh ULID and write it to the store."""
        v = str(ULID())
        self._store.set(path, v, updated_by=updated_by)
        return v

    def current(self, path: str) -> str | None:
        return self._store.get(path)

    def advance(self, path: str, *, updated_by: str = "") -> str:
        """Same as issue — semantic alias for post-save."""
        return self.issue(path, updated_by=updated_by)

    def check_or_raise(
        self,
        path: str,
        expected: str | None,
        server_content: str = "",
        server_updated_by: str = "",
    ) -> None:
        """If `expected` is None, no check is performed (legacy callers).

        If expected matches current (or current is None), pass.
        Otherwise raise VersionConflict with payload.
        """
        if expected is None:
            return  # caller opted out

        current = self._store.get(path)

        # Fresh file: no row yet — accept any expectation
        if current is None:
            return

        if expected == current:
            return

        raise VersionConflict(
            ConflictPayload(
                path=path,
                base_version=expected,
                server_version=current,
                server_content=server_content,
                server_updated_by=server_updated_by,
            )
        )

    def lazy_version_for(self, path: str, *, mtime_fallback: float = 0.0) -> str:
        """For Task 2-8 migration: return current version, or generate one from mtime if missing."""
        v = self._store.get(path)
        if v is not None:
            return v

        # Generate ULID derived from mtime so it's stable for the same file across processes
        from datetime import datetime, timezone
        if mtime_fallback > 0:
            dt = datetime.fromtimestamp(mtime_fallback, tz=timezone.utc)
            v = str(ULID.from_datetime(dt))
        else:
            v = str(ULID())

        self._store.set(path, v, updated_by="system:lazy")
        return v
