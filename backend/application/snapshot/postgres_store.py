"""Postgres-backed SnapshotStore — team/enterprise profile.

Sync psycopg3, connection-per-op pattern (mirrors PostgresVersionStore / PostgresRefIndex).
Table: wiki_snapshots — created by alembic migration 2026_05_05_001_initial_schema.py.
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from .snapshot_protocol import Snapshot, SnapshotStore


def _normalize_dsn(dsn: str) -> str:
    return (
        dsn
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


class PostgresSnapshotStore(SnapshotStore):
    DEFAULT_KEEP = 20

    def __init__(self, dsn: str) -> None:
        self._dsn = _normalize_dsn(dsn)

    def _conn(self):
        return psycopg.connect(self._dsn, row_factory=dict_row, autocommit=False)

    def append(self, path: str, content: str, version: str, user_name: str, reason: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wiki_snapshots (path, version, content, user_name, reason)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (path, version, content.encode("utf-8"), user_name, reason),
            )
            # Prune: keep only the most recent DEFAULT_KEEP rows for this path
            cur.execute(
                """
                DELETE FROM wiki_snapshots
                WHERE id IN (
                    SELECT id FROM wiki_snapshots
                    WHERE path = %s
                    ORDER BY created_at DESC, id DESC
                    OFFSET %s
                )
                """,
                (path, self.DEFAULT_KEEP),
            )
            conn.commit()

    def list(self, path: str, *, limit: int = 20) -> list[Snapshot]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT path, version, user_name, created_at, reason
                FROM wiki_snapshots
                WHERE path=%s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (path, limit),
            )
            results: list[Snapshot] = []
            for row in cur.fetchall():
                ts = row["created_at"]
                # psycopg3 returns datetime objects for TIMESTAMPTZ
                if hasattr(ts, "timestamp"):
                    epoch = ts.timestamp()
                else:
                    try:
                        from datetime import datetime
                        epoch = datetime.fromisoformat(str(ts)).timestamp()
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
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM wiki_snapshots
                WHERE path=%s AND version=%s
                ORDER BY id DESC LIMIT 1
                """,
                (path, version),
            )
            row = cur.fetchone()
            if row is None:
                return None
            blob = row["content"]
            return bytes(blob).decode("utf-8") if isinstance(blob, (bytes, memoryview)) else str(blob)

    def prune(self, path: str, *, keep: int) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM wiki_snapshots
                WHERE id IN (
                    SELECT id FROM wiki_snapshots
                    WHERE path = %s
                    ORDER BY created_at DESC, id DESC
                    OFFSET %s
                )
                """,
                (path, keep),
            )
            deleted = cur.rowcount
            conn.commit()
            return deleted

    def delete_for_path(self, path: str) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_snapshots WHERE path=%s", (path,))
            deleted = cur.rowcount
            conn.commit()
            return deleted
