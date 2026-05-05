"""Postgres-backed VersionStore — team/enterprise profile.

Sync psycopg3, same connection-per-op pattern as PostgresRefIndex.
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from .version_protocol import VersionStore


def _normalize_dsn(dsn: str) -> str:
    return (
        dsn
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


class PostgresVersionStore(VersionStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = _normalize_dsn(dsn)

    def _conn(self):
        return psycopg.connect(self._dsn, row_factory=dict_row, autocommit=False)

    def get(self, path: str) -> str | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT version FROM wiki_versions WHERE path=%s", (path,))
            row = cur.fetchone()
            return row["version"] if row else None

    def set(self, path: str, version: str, updated_by: str = "") -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wiki_versions (path, version, updated_at, updated_by)
                VALUES (%s, %s, now(), %s)
                ON CONFLICT (path) DO UPDATE SET
                    version=EXCLUDED.version,
                    updated_at=now(),
                    updated_by=EXCLUDED.updated_by
                """,
                (path, version, updated_by),
            )
            conn.commit()

    def delete(self, path: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_versions WHERE path=%s", (path,))
            conn.commit()

    def rename(self, old: str, new: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM wiki_versions WHERE path=%s", (new,))
            if cur.fetchone():
                raise ValueError(f"Cannot rename '{old}' to '{new}': destination already has a version row")
            cur.execute("UPDATE wiki_versions SET path=%s WHERE path=%s", (new, old))
            conn.commit()

    def clear(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_versions")
            conn.commit()
