"""SQLite-backed SnapshotStore — dev profile.

Same pattern as SqliteVersionStore / SqliteRefIndex:
  check_same_thread=False, WAL mode, busy_timeout=5000, RLock for serialization.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .snapshot_protocol import Snapshot, SnapshotStore

SQLITE_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS wiki_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT NOT NULL,
    version     TEXT NOT NULL,
    content     BLOB NOT NULL,
    user_name   TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    reason      TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_path_time ON wiki_snapshots (path, created_at DESC);
"""


class SqliteSnapshotStore(SnapshotStore):
    DEFAULT_KEEP = 20

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SQLITE_SNAPSHOT_DDL)

    def append(self, path: str, content: str, version: str, user_name: str, reason: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO wiki_snapshots (path, version, content, user_name, reason) VALUES (?, ?, ?, ?, ?)",
                (path, version, content.encode("utf-8"), user_name, reason),
            )
            # Prune: keep only most recent DEFAULT_KEEP rows for this path
            self._conn.execute(
                """
                DELETE FROM wiki_snapshots
                WHERE id IN (
                    SELECT id FROM wiki_snapshots
                    WHERE path = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (path, self.DEFAULT_KEEP),
            )

    def list(self, path: str, *, limit: int = 20) -> list[Snapshot]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT path, version, user_name, created_at, reason FROM wiki_snapshots "
                "WHERE path=? ORDER BY created_at DESC, id DESC LIMIT ?",
                (path, limit),
            )
            results: list[Snapshot] = []
            for row in cur.fetchall():
                ts_str = row["created_at"]
                try:
                    dt = datetime.fromisoformat(ts_str.replace(" ", "T"))
                    epoch = dt.timestamp()
                except Exception:
                    epoch = 0.0
                results.append(Snapshot(
                    path=row["path"],
                    version=row["version"],
                    user_name=row["user_name"] or "",
                    created_at=epoch,
                    reason=row["reason"] or "",
                ))
            return results

    def get_content(self, path: str, version: str) -> str | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT content FROM wiki_snapshots WHERE path=? AND version=? ORDER BY id DESC LIMIT 1",
                (path, version),
            )
            row = cur.fetchone()
            if row is None:
                return None
            blob = row["content"]
            return blob.decode("utf-8") if isinstance(blob, (bytes, memoryview)) else str(blob)

    def prune(self, path: str, *, keep: int) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                DELETE FROM wiki_snapshots
                WHERE id IN (
                    SELECT id FROM wiki_snapshots
                    WHERE path = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (path, keep),
            )
            return cur.rowcount

    def delete_for_path(self, path: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM wiki_snapshots WHERE path=?", (path,))
            return cur.rowcount
