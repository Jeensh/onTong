"""Schema DDL — kept here so both backends and Alembic migration share text."""
from __future__ import annotations

POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS wiki_references (
    id           BIGSERIAL PRIMARY KEY,
    source_path  TEXT NOT NULL,
    target_path  TEXT NOT NULL,
    kind         SMALLINT NOT NULL,
    location     JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_refs_target ON wiki_references (target_path);
CREATE INDEX IF NOT EXISTS idx_refs_source ON wiki_references (source_path);
CREATE UNIQUE INDEX IF NOT EXISTS idx_refs_unique
    ON wiki_references (source_path, target_path, kind, (location->>'offset'));
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS wiki_references (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path  TEXT NOT NULL,
    target_path  TEXT NOT NULL,
    kind         INTEGER NOT NULL,
    location     TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_refs_target ON wiki_references (target_path);
CREATE INDEX IF NOT EXISTS idx_refs_source ON wiki_references (source_path);
"""

# Note: SQLite uses generic JSON-as-TEXT; the unique index over (location->>'offset')
# requires Postgres JSONB. SQLite version skips that constraint and relies on
# upsert_for_source's DELETE-then-INSERT to enforce per-source uniqueness.
