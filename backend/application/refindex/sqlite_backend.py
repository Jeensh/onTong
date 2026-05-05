"""SQLite-backed ReferenceIndex — dev profile.

Single connection, threading.Lock guards writes (sqlite3 default isolation_level
serializes writes anyway, but explicit lock prevents transaction interleaving
with the upsert_for_source DELETE+INSERT pair).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .extractor import Reference, RefKind
from .ref_protocol import RefIndex
from ._schema_sql import SQLITE_DDL


class SqliteRefIndex(RefIndex):
    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        # check_same_thread=False so FastAPI workers can share. Lock above serializes.
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        # Apply DDL (executescript handles multi-statement)
        self._conn.executescript(SQLITE_DDL)

    def _row_to_ref(self, row: sqlite3.Row) -> Reference:
        return Reference(
            source_path=row["source_path"],
            target_path=row["target_path"],
            kind=row["kind"],
            location=json.loads(row["location"]),
        )

    def upsert_for_source(self, source_path: str, refs: list[Reference]) -> None:
        with self._lock, self._conn:  # implicit transaction
            self._conn.execute("DELETE FROM wiki_references WHERE source_path=?", (source_path,))
            self._conn.executemany(
                "INSERT INTO wiki_references (source_path, target_path, kind, location) VALUES (?, ?, ?, ?)",
                [(r.source_path, r.target_path, r.kind, json.dumps(r.location, ensure_ascii=False)) for r in refs],
            )

    def remove_for_source(self, source_path: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM wiki_references WHERE source_path=?", (source_path,))

    def inbound(self, target_path: str, *, kind: int | None = None) -> list[Reference]:
        with self._lock:
            if kind is None:
                cur = self._conn.execute("SELECT * FROM wiki_references WHERE target_path=?", (target_path,))
            else:
                cur = self._conn.execute("SELECT * FROM wiki_references WHERE target_path=? AND kind=?", (target_path, kind))
            return [self._row_to_ref(r) for r in cur.fetchall()]

    def outbound(self, source_path: str) -> list[Reference]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM wiki_references WHERE source_path=?", (source_path,))
            return [self._row_to_ref(r) for r in cur.fetchall()]

    def rename_target(self, old: str, new: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("UPDATE wiki_references SET target_path=? WHERE target_path=?", (new, old))
            return cur.rowcount

    def rename_source(self, old: str, new: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("UPDATE wiki_references SET source_path=? WHERE source_path=?", (new, old))
            return cur.rowcount

    def broken(self, *, limit: int = 100, offset: int = 0, kind: int | None = None) -> list[Reference]:
        sql = """
            SELECT r.* FROM wiki_references r
            LEFT JOIN (SELECT DISTINCT source_path FROM wiki_references) src
                ON src.source_path = r.target_path
            WHERE src.source_path IS NULL
        """
        params: list = []
        if kind is not None:
            sql += " AND r.kind=?"
            params.append(kind)
        sql += " ORDER BY r.id LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [self._row_to_ref(r) for r in cur.fetchall()]

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM wiki_references")
