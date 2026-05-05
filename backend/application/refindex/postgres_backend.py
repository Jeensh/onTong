"""Postgres-backed ReferenceIndex — team/enterprise profile.

Synchronous psycopg3 client. Index operations are fast (<1ms typical) so
sync-in-async is acceptable. If Phase 6 load testing shows contention,
swap to asyncpg + add an awaitable wrapper.
"""
from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .extractor import Reference
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
            conn.commit()

    def remove_for_source(self, source_path: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_references WHERE source_path=%s", (source_path,))
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
            conn.commit()
            return n

    def broken(self, *, limit: int = 100, offset: int = 0, kind: int | None = None) -> list[Reference]:
        sql = """
            SELECT r.* FROM wiki_references r
            LEFT JOIN (SELECT DISTINCT source_path FROM wiki_references) src
                ON src.source_path = r.target_path
            WHERE src.source_path IS NULL
        """
        params: list = []
        if kind is not None:
            sql += " AND r.kind=%s"
            params.append(kind)
        sql += " ORDER BY r.id LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return [self._row_to_ref(r) for r in cur.fetchall()]

    def clear(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_references")
            conn.commit()
