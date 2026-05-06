"""Postgres-backed ReferenceIndex — team/enterprise profile.

Synchronous psycopg3 client. Index operations are fast (<1ms typical) so
sync-in-async is acceptable. If Phase 6 load testing shows contention,
swap to asyncpg + add an awaitable wrapper.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .extractor import Reference, RefKind
from .ref_protocol import RefIndex


def _build_pool(dsn: str) -> str:
    """Factory — monkeypatchable in tests."""
    # Convert SQLAlchemy-style DSN if needed
    pg_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")
    return pg_dsn


class PostgresRefIndex(RefIndex):
    def __init__(self, dsn: str) -> None:
        self._dsn = _build_pool(dsn)

    def _conn(self):
        return psycopg.connect(self._dsn, row_factory=dict_row, autocommit=False)

    def _row_to_ref(self, row: dict[str, Any]) -> Reference:
        loc = row["location"]
        if isinstance(loc, str):
            loc = json.loads(loc)
        return Reference(
            source_path=row["source_path"],
            target_path=row["target_path"],
            kind=row["kind"],
            location=loc,
        )

    def upsert_for_source(self, source_path: str, refs: list[Reference]) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_references WHERE source_path=%s", (source_path,))
            if refs:
                cur.executemany(
                    "INSERT INTO wiki_references (source_path, target_path, kind, location) VALUES (%s, %s, %s, %s::jsonb)",
                    [(r.source_path, r.target_path, r.kind, json.dumps(r.location, ensure_ascii=False)) for r in refs],
                )
            # Register source + refresh last_indexed_at so stale_sources() works.
            # The DO UPDATE on conflict is critical: DO NOTHING here would mean
            # a re-indexed source keeps its original timestamp and looks stale forever.
            cur.execute(
                "INSERT INTO wiki_sources (source_path, last_indexed_at) VALUES (%s, now()) "
                "ON CONFLICT (source_path) DO UPDATE SET last_indexed_at = now()",
                (source_path,),
            )
            conn.commit()

    def remove_for_source(self, source_path: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_references WHERE source_path=%s", (source_path,))
            cur.execute("DELETE FROM wiki_sources WHERE source_path=%s", (source_path,))
            conn.commit()

    def inbound(self, target_path: str, *, kind: int | None = None) -> list[Reference]:
        with self._conn() as conn, conn.cursor() as cur:
            if kind is None:
                cur.execute("SELECT * FROM wiki_references WHERE target_path=%s", (target_path,))
            else:
                cur.execute("SELECT * FROM wiki_references WHERE target_path=%s AND kind=%s", (target_path, kind))
            return [self._row_to_ref(r) for r in cur.fetchall()]

    def outbound(self, source_path: str) -> list[Reference]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM wiki_references WHERE source_path=%s", (source_path,))
            return [self._row_to_ref(r) for r in cur.fetchall()]

    def rename_target(self, old: str, new: str) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("UPDATE wiki_references SET target_path=%s WHERE target_path=%s", (new, old))
            n = cur.rowcount
            conn.commit()
            return n

    def rename_source(self, old: str, new: str) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("UPDATE wiki_references SET source_path=%s WHERE source_path=%s", (new, old))
            n = cur.rowcount
            # Keep wiki_sources in sync with the rename + refresh timestamp.
            cur.execute(
                "INSERT INTO wiki_sources (source_path, last_indexed_at) VALUES (%s, now()) "
                "ON CONFLICT (source_path) DO UPDATE SET last_indexed_at = now()",
                (new,),
            )
            cur.execute("DELETE FROM wiki_sources WHERE source_path=%s", (old,))
            conn.commit()
            return n

    def stems(self) -> dict[str, list[str]]:
        """Map of stem → [source_paths with that stem].

        Stem = filename without .md extension. Derived from wiki_sources table
        (all indexed paths, even those with no outbound refs). Used by broken()
        to disambiguate wikilink false positives.
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT source_path FROM wiki_sources")
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
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT source_path FROM wiki_sources")
            all_sources = [row["source_path"] for row in cur.fetchall()]

        known_paths = set(all_sources)
        known_stems = {PurePosixPath(p).stem for p in all_sources}

        # Step 2: fetch candidate refs (optionally filtered by kind)
        sql = "SELECT * FROM wiki_references"
        params: list = []
        if kind is not None:
            sql += " WHERE kind=%s"
            params.append(kind)
        sql += " ORDER BY id"

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
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
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_references")
            cur.execute("DELETE FROM wiki_sources")
            conn.commit()

    def stale_sources(self, threshold_seconds: int) -> list[str]:
        """Source paths whose last_indexed_at is older than threshold_seconds.

        Returns sorted source_paths so callers can deterministically pick a batch
        to re-index. Operators use this to find files where the on-disk content
        may have drifted from the indexed refs.
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT source_path FROM wiki_sources "
                "WHERE last_indexed_at < now() - make_interval(secs => %s) "
                "ORDER BY last_indexed_at",
                (int(threshold_seconds),),
            )
            return [row["source_path"] for row in cur.fetchall()]
