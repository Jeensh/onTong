"""SQLite-backed ReferenceIndex — dev profile.

Single connection, threading.Lock guards writes (sqlite3 default isolation_level
serializes writes anyway, but explicit lock prevents transaction interleaving
with the upsert_for_source DELETE+INSERT pair).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path, PurePosixPath

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
        self._conn.execute("PRAGMA busy_timeout=5000")  # 5s wait on SQLITE_BUSY (multi-worker hardening)
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
            # Register source + refresh last_indexed_at so stale_sources() works.
            # ON CONFLICT updates the timestamp; without it the row would keep
            # its original timestamp and look stale forever.
            self._conn.execute(
                "INSERT INTO wiki_sources (source_path, last_indexed_at) VALUES (?, datetime('now')) "
                "ON CONFLICT(source_path) DO UPDATE SET last_indexed_at = datetime('now')",
                (source_path,),
            )

    def remove_for_source(self, source_path: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM wiki_references WHERE source_path=?", (source_path,))
            self._conn.execute("DELETE FROM wiki_sources WHERE source_path=?", (source_path,))

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
            # Keep wiki_sources in sync with the rename + refresh timestamp.
            self._conn.execute(
                "INSERT INTO wiki_sources (source_path, last_indexed_at) VALUES (?, datetime('now')) "
                "ON CONFLICT(source_path) DO UPDATE SET last_indexed_at = datetime('now')",
                (new,),
            )
            self._conn.execute("DELETE FROM wiki_sources WHERE source_path=?", (old,))
            return cur.rowcount

    def stems(self) -> dict[str, list[str]]:
        """Map of stem → [source_paths with that stem].

        Stem = filename without .md extension. Derived from wiki_sources table
        (all indexed paths, even those with no outbound refs). Used by broken()
        to disambiguate wikilink false positives.
        """
        from collections import defaultdict
        with self._lock:
            cur = self._conn.execute("SELECT source_path FROM wiki_sources")
            result: dict[str, list[str]] = defaultdict(list)
            for row in cur.fetchall():
                sp = row["source_path"]
                stem = PurePosixPath(sp).stem
                result[stem].append(sp)
        return dict(result)

    def broken(self, *, limit: int = 100, offset: int = 0, kind: int | None = None) -> list[Reference]:
        """References whose target_path doesn't resolve to any known source.

        Wikilinks (BODY_WIKILINK) carry a stem as target_path and are checked
        against the stem map built from all known source paths. Path-based refs
        (BODY_MD_LINK, FM_*) are checked against the full source_path set.

        Implementation: Python-side filter after fetching candidates. This loads
        all candidate rows into memory, which is acceptable at 100K-row scale
        (~20MB). Phase 6 can materialize stem as a DB column or use a temp table
        if benchmarks show contention.
        """
        # Step 1: collect all known source paths from wiki_sources (includes zero-ref sources)
        with self._lock:
            cur = self._conn.execute("SELECT source_path FROM wiki_sources")
            all_sources = [row["source_path"] for row in cur.fetchall()]

        known_paths = set(all_sources)
        known_stems = {PurePosixPath(p).stem for p in all_sources}

        # Step 2: fetch candidate refs (optionally filtered by kind)
        sql = "SELECT * FROM wiki_references"
        params: list = []
        if kind is not None:
            sql += " WHERE kind=?"
            params.append(kind)
        sql += " ORDER BY id"

        with self._lock:
            cur = self._conn.execute(sql, params)
            all_rows = cur.fetchall()

        # Step 3: Python-filter "broken"
        broken_refs: list[Reference] = []
        for row in all_rows:
            ref = self._row_to_ref(row)
            if ref.kind == RefKind.BODY_WIKILINK:
                # Wikilinks use stem as target; broken iff stem not in any source
                if ref.target_path not in known_stems:
                    broken_refs.append(ref)
            else:
                # Path-based refs: broken iff full target_path not in known sources
                if ref.target_path not in known_paths:
                    broken_refs.append(ref)
            if len(broken_refs) >= offset + limit:
                break  # enough collected for this page

        return broken_refs[offset: offset + limit]

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM wiki_references")
            self._conn.execute("DELETE FROM wiki_sources")

    def stale_sources(self, threshold_seconds: int) -> list[str]:
        """Source paths whose last_indexed_at is older than threshold_seconds.

        Returns sorted source_paths so callers can deterministically pick a batch
        to re-index. Operators use this to find files where the on-disk content
        may have drifted from the indexed refs.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT source_path FROM wiki_sources "
                "WHERE last_indexed_at < datetime('now', ?) "
                "ORDER BY last_indexed_at",
                (f"-{int(threshold_seconds)} seconds",),
            )
            return [row["source_path"] for row in cur.fetchall()]
