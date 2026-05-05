"""SQLite-backed AuditStore — dev profile.

Same pattern as SqliteSnapshotStore / SqliteVersionStore:
  check_same_thread=False, WAL mode, busy_timeout=5000, RLock for serialization.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .audit_protocol import AuditStore
from .types import RenameAuditRow, RenameJobRow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  op TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload TEXT NOT NULL,
  started_at REAL NOT NULL,
  finished_at REAL,
  status TEXT NOT NULL DEFAULT 'running',
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_actor_time ON wiki_audit(actor, started_at DESC);

CREATE TABLE IF NOT EXISTS wiki_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  audit_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  target_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER DEFAULT 0,
  last_error TEXT,
  updated_at REAL DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY(audit_id) REFERENCES wiki_audit(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_jobs_audit ON wiki_jobs(audit_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON wiki_jobs(status);
"""


def _row_to_audit(row: sqlite3.Row) -> RenameAuditRow:
    return RenameAuditRow(
        id=row["id"],
        op=row["op"],
        actor=row["actor"],
        payload=json.loads(row["payload"]),
        started_at=float(row["started_at"]),
        finished_at=float(row["finished_at"]) if row["finished_at"] is not None else None,
        status=row["status"],
        error=row["error"],
    )


def _row_to_job(row: sqlite3.Row) -> RenameJobRow:
    return RenameJobRow(
        id=row["id"],
        audit_id=row["audit_id"],
        kind=row["kind"],
        target_path=row["target_path"],
        status=row["status"],
        attempts=row["attempts"],
        last_error=row["last_error"],
        updated_at=float(row["updated_at"]) if row["updated_at"] is not None else 0.0,
    )


class SqliteAuditStore(AuditStore):
    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    def create_audit(self, op: str, actor: str, payload: dict) -> int:
        now = time.time()
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO wiki_audit (op, actor, payload, started_at, status) VALUES (?, ?, ?, ?, 'running')",
                (op, actor, payload_json, now),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def update_audit_status(self, audit_id: int, status: str, error: str | None = None) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE wiki_audit SET status=?, finished_at=?, error=? WHERE id=?",
                (status, now, error, audit_id),
            )

    def get_audit(self, audit_id: int) -> RenameAuditRow | None:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM wiki_audit WHERE id=?", (audit_id,))
            row = cur.fetchone()
            return _row_to_audit(row) if row else None

    def list_audits(self, *, actor: str | None = None, since: float | None = None,
                    op: str | None = None, status: str | None = None,
                    limit: int = 50) -> list[RenameAuditRow]:
        sql = "SELECT * FROM wiki_audit WHERE 1=1"
        params: list = []
        if actor is not None:
            sql += " AND actor=?"
            params.append(actor)
        if since is not None:
            sql += " AND started_at>=?"
            params.append(since)
        if op is not None:
            sql += " AND op=?"
            params.append(op)
        if status is not None:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [_row_to_audit(row) for row in cur.fetchall()]

    def add_jobs(self, audit_id: int, jobs: list[tuple[str, str]]) -> int:
        now = time.time()
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT INTO wiki_jobs (audit_id, kind, target_path, status, attempts, updated_at) "
                "VALUES (?, ?, ?, 'pending', 0, ?)",
                [(audit_id, kind, target_path, now) for kind, target_path in jobs],
            )
            return len(jobs)

    def update_job(self, job_id: int, *, status: str, last_error: str | None = None,
                   increment_attempts: bool = True) -> None:
        now = time.time()
        with self._lock, self._conn:
            if increment_attempts:
                self._conn.execute(
                    "UPDATE wiki_jobs SET status=?, last_error=?, attempts=attempts+1, updated_at=? WHERE id=?",
                    (status, last_error, now, job_id),
                )
            else:
                self._conn.execute(
                    "UPDATE wiki_jobs SET status=?, last_error=?, updated_at=? WHERE id=?",
                    (status, last_error, now, job_id),
                )

    def list_jobs(self, audit_id: int, *, status: str | None = None) -> list[RenameJobRow]:
        sql = "SELECT * FROM wiki_jobs WHERE audit_id=?"
        params: list = [audit_id]
        if status is not None:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY id"
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [_row_to_job(row) for row in cur.fetchall()]

    def progress(self, audit_id: int) -> dict:
        result = {"total": 0, "pending": 0, "running": 0, "done": 0, "failed": 0}
        with self._lock:
            cur = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM wiki_jobs WHERE audit_id=? GROUP BY status",
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
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM wiki_jobs")
            self._conn.execute("DELETE FROM wiki_audit")
