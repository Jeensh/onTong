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
            # Register source + refresh last_indexed_at + stem.
            # The DO UPDATE on conflict is critical: DO NOTHING here would mean
            # a re-indexed source keeps its original timestamp and looks stale forever.
            stem = PurePosixPath(source_path).stem
            cur.execute(
                "INSERT INTO wiki_sources (source_path, stem, last_indexed_at) VALUES (%s, %s, now()) "
                "ON CONFLICT (source_path) DO UPDATE SET "
                "  stem = EXCLUDED.stem, "
                "  last_indexed_at = now()",
                (source_path, stem),
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
            # Keep wiki_sources in sync with the rename + refresh timestamp + stem.
            new_stem = PurePosixPath(new).stem
            cur.execute(
                "INSERT INTO wiki_sources (source_path, stem, last_indexed_at) VALUES (%s, %s, now()) "
                "ON CONFLICT (source_path) DO UPDATE SET "
                "  stem = EXCLUDED.stem, "
                "  last_indexed_at = now()",
                (new, new_stem),
            )
            cur.execute("DELETE FROM wiki_sources WHERE source_path=%s", (old,))
            conn.commit()
            return n

    def stems(self) -> dict[str, list[str]]:
        """Map of stem → [source_paths with that stem].

        Reads the materialized stem column directly. Used by broken() (now SQL-side)
        and exposed for legacy callers / tests.
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT stem, source_path FROM wiki_sources")
            result: dict[str, list[str]] = defaultdict(list)
            for row in cur.fetchall():
                result[row["stem"]].append(row["source_path"])
        return dict(result)

    def broken(self, *, limit: int = 100, offset: int = 0, kind: int | None = None) -> list[Reference]:
        """References whose target_path doesn't resolve to any known source.

        Implementation (E3): SQL-side anti-join against wiki_sources.
        idx_wiki_sources_stem and the source_path PK make both NOT EXISTS
        subqueries index-lookups, so this scales linearly with broken-ref count
        rather than (refs * sources) like the prior Python pass.
        """
        sql = (
            "SELECT r.* FROM wiki_references r WHERE "
            "((r.kind = %s AND NOT EXISTS (SELECT 1 FROM wiki_sources s WHERE s.stem = r.target_path)) "
            " OR "
            " (r.kind != %s AND NOT EXISTS (SELECT 1 FROM wiki_sources s WHERE s.source_path = r.target_path)))"
        )
        params: list = [RefKind.BODY_WIKILINK, RefKind.BODY_WIKILINK]
        if kind is not None:
            sql += " AND r.kind = %s"
            params.append(kind)
        sql += " ORDER BY r.id LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return [self._row_to_ref(r) for r in cur.fetchall()]

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
