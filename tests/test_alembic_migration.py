"""Smoke test: alembic upgrade creates all expected tables + view.

Requires PostgreSQL (pg_ctl / pg_config) on PATH.
If PG is not installed locally the test is automatically skipped.
"""
from __future__ import annotations

import subprocess
import shutil
import pytest


# ---------------------------------------------------------------------------
# Skip the entire module gracefully when pg_config / pg_ctl are missing.
# pytest_postgresql crashes at fixture-setup (not collection) when PG binaries
# are absent, so we check here at import time.
# ---------------------------------------------------------------------------
_pg_available = shutil.which("pg_config") is not None or shutil.which("pg_ctl") is not None
if not _pg_available:
    pytest.skip(
        "PostgreSQL binaries (pg_config / pg_ctl) not found — skipping migration smoke test",
        allow_module_level=True,
    )

from pytest_postgresql import factories  # noqa: E402 — only reached when PG present

postgres = factories.postgresql_proc(port=None)
postgres_db = factories.postgresql("postgres")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_alembic(dsn: str) -> None:
    from alembic.config import Config
    from alembic import command

    cfg = Config("migrations/alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", dsn)
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_initial_migration_creates_all_tables(postgres_db, monkeypatch):
    info = postgres_db.info
    sync_dsn = (
        f"postgresql://{info.user}:{info.password}@{info.host}:{info.port}/{info.dbname}"
    )
    async_dsn = sync_dsn.replace("postgresql://", "postgresql+asyncpg://")
    monkeypatch.setenv("POSTGRES_DSN", async_dsn)

    # Reload settings so the monkeypatched env var is picked up
    import importlib
    import backend.core.config
    importlib.reload(backend.core.config)

    _run_alembic(sync_dsn)

    cur = postgres_db.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [r[0] for r in cur.fetchall()]
    assert "wiki_references" in tables
    assert "wiki_versions" in tables
    assert "wiki_snapshots" in tables
    assert "wiki_audit" in tables
    assert "wiki_jobs" in tables

    cur.execute("""
        SELECT table_name FROM information_schema.views
        WHERE table_schema = 'public';
    """)
    views = [r[0] for r in cur.fetchall()]
    assert "wiki_broken_refs" in views
