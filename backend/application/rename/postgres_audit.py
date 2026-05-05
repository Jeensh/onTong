"""PostgresAuditStore — team / enterprise profile.

Mirrors PostgresSnapshotStore patterns: sync psycopg3 connection-per-op.
Uses wiki_audit / wiki_jobs tables created by the alembic migration
2026_05_05_001_initial_schema.py.

NOTE: Postgres wiki_audit.started_at is TIMESTAMPTZ. Convert to/from epoch float
at the API boundary. payload is JSONB.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from .audit_protocol import AuditStore
from .types import RenameAuditRow, RenameJobRow


def _to_epoch(dt) -> float:
    if dt is None:
        return 0.0
    if isinstance(dt, (int, float)):
        return float(dt)
    return dt.timestamp() if hasattr(dt, "timestamp") else 0.0


class PostgresAuditStore(AuditStore):
    def __init__(self, dsn: str) -> None:
        # Accept various URL schemes and normalize to plain postgresql://
        self._dsn = (
            dsn
            .replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgresql+psycopg://", "postgresql://")
        )

    def _conn(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self._dsn, row_factory=dict_row, autocommit=False)

    def create_audit(self, op: str, actor: str, payload: dict) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wiki_audit (op, actor, payload, started_at, status)
                VALUES (%s, %s, %s::jsonb, now(), 'running')
                RETURNING id
                """,
                (op, actor, json.dumps(payload, ensure_ascii=False)),
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            return int(new_id)

    def update_audit_status(self, audit_id: int, status: str, error: str | None = None) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE wiki_audit SET status=%s, finished_at=now(), error=%s WHERE id=%s",
                (status, error, audit_id),
            )
            conn.commit()

    def get_audit(self, audit_id: int) -> RenameAuditRow | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM wiki_audit WHERE id=%s", (audit_id,))
            row = cur.fetchone()
            if row is None:
                return None
            return RenameAuditRow(
                id=row["id"],
                op=row["op"],
                actor=row["actor"],
                payload=row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"]),
                started_at=_to_epoch(row["started_at"]),
                finished_at=_to_epoch(row["finished_at"]) if row["finished_at"] else None,
                status=row["status"],
                error=row.get("error"),
            )

    def list_audits(self, *, actor: str | None = None, since: float | None = None,
                    op: str | None = None, status: str | None = None,
                    limit: int = 50) -> list[RenameAuditRow]:
        sql = "SELECT * FROM wiki_audit WHERE true"
        params: list = []
        if actor is not None:
            sql += " AND actor=%s"
            params.append(actor)
        if since is not None:
            dt = datetime.fromtimestamp(since, tz=timezone.utc)
            sql += " AND started_at>=%s"
            params.append(dt)
        if op is not None:
            sql += " AND op=%s"
            params.append(op)
        if status is not None:
            sql += " AND status=%s"
            params.append(status)
        sql += " ORDER BY started_at DESC LIMIT %s"
        params.append(limit)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        results = []
        for row in rows:
            results.append(RenameAuditRow(
                id=row["id"],
                op=row["op"],
                actor=row["actor"],
                payload=row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"]),
                started_at=_to_epoch(row["started_at"]),
                finished_at=_to_epoch(row["finished_at"]) if row["finished_at"] else None,
                status=row["status"],
                error=row.get("error"),
            ))
        return results

    def add_jobs(self, audit_id: int, jobs: list[tuple[str, str]]) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO wiki_jobs (audit_id, kind, target_path, status, attempts) VALUES (%s, %s, %s, 'pending', 0)",
                [(audit_id, kind, target_path) for kind, target_path in jobs],
            )
            conn.commit()
        return len(jobs)

    def update_job(self, job_id: int, *, status: str, last_error: str | None = None,
                   increment_attempts: bool = True) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            if increment_attempts:
                cur.execute(
                    "UPDATE wiki_jobs SET status=%s, last_error=%s, attempts=attempts+1, updated_at=now() WHERE id=%s",
                    (status, last_error, job_id),
                )
            else:
                cur.execute(
                    "UPDATE wiki_jobs SET status=%s, last_error=%s, updated_at=now() WHERE id=%s",
                    (status, last_error, job_id),
                )
            conn.commit()

    def list_jobs(self, audit_id: int, *, status: str | None = None) -> list[RenameJobRow]:
        sql = "SELECT * FROM wiki_jobs WHERE audit_id=%s"
        params: list = [audit_id]
        if status is not None:
            sql += " AND status=%s"
            params.append(status)
        sql += " ORDER BY id"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [
            RenameJobRow(
                id=row["id"],
                audit_id=row["audit_id"],
                kind=row["kind"],
                target_path=row["target_path"],
                status=row["status"],
                attempts=row["attempts"] or 0,
                last_error=row.get("last_error"),
                updated_at=_to_epoch(row.get("updated_at")),
            )
            for row in rows
        ]

    def progress(self, audit_id: int) -> dict:
        result = {"total": 0, "pending": 0, "running": 0, "done": 0, "failed": 0}
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status, COUNT(*) as cnt FROM wiki_jobs WHERE audit_id=%s GROUP BY status",
                (audit_id,),
            )
            for row in cur.fetchall():
                s = row["status"]
                n = row["cnt"]
                result["total"] += n
                if s in result:
                    result[s] = n
        return result

    def clear(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM wiki_jobs")
            cur.execute("DELETE FROM wiki_audit")
            conn.commit()
