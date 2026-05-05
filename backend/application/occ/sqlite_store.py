"""SQLite-backed VersionStore — dev profile.

Same pattern as SqliteRefIndex: check_same_thread=False, WAL mode, busy_timeout,
RLock for serialization.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .version_protocol import VersionStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_versions (
    path        TEXT PRIMARY KEY,
    version     TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by  TEXT
);
"""


class SqliteVersionStore(VersionStore):
    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    def get(self, path: str) -> str | None:
        with self._lock:
            cur = self._conn.execute("SELECT version FROM wiki_versions WHERE path=?", (path,))
            row = cur.fetchone()
            return row["version"] if row else None

    def set(self, path: str, version: str, updated_by: str = "") -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO wiki_versions (path, version, updated_at, updated_by)
                VALUES (?, ?, datetime('now'), ?)
                ON CONFLICT(path) DO UPDATE SET
                    version=excluded.version,
                    updated_at=datetime('now'),
                    updated_by=excluded.updated_by
                """,
                (path, version, updated_by),
            )

    def delete(self, path: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM wiki_versions WHERE path=?", (path,))

    def rename(self, old: str, new: str) -> None:
        with self._lock, self._conn:
            # Check collision: new path must not already exist
            cur = self._conn.execute("SELECT 1 FROM wiki_versions WHERE path=?", (new,))
            if cur.fetchone():
                raise ValueError(f"Cannot rename '{old}' to '{new}': destination already has a version row")
            self._conn.execute("UPDATE wiki_versions SET path=? WHERE path=?", (new, old))

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM wiki_versions")
