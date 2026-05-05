"""initial schema: refs / versions / snapshots / audit / jobs

Revision ID: 2026_05_05_001
Revises:
Create Date: 2026-05-05
"""
from alembic import op


revision = "2026_05_05_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE wiki_references (
            id           BIGSERIAL PRIMARY KEY,
            source_path  TEXT NOT NULL,
            target_path  TEXT NOT NULL,
            kind         SMALLINT NOT NULL,
            location     JSONB NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX idx_refs_target ON wiki_references (target_path);")
    op.execute("CREATE INDEX idx_refs_source ON wiki_references (source_path);")
    op.execute("""
        CREATE UNIQUE INDEX idx_refs_unique
        ON wiki_references (source_path, target_path, kind, (location->>'offset'));
    """)

    op.execute("""
        CREATE TABLE wiki_versions (
            path        TEXT PRIMARY KEY,
            version     TEXT NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_by  TEXT
        );
    """)

    op.execute("""
        CREATE TABLE wiki_snapshots (
            id          BIGSERIAL PRIMARY KEY,
            path        TEXT NOT NULL,
            version     TEXT NOT NULL,
            content     BYTEA NOT NULL,
            user_name   TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason      TEXT
        );
    """)
    op.execute("CREATE INDEX idx_snap_path_time ON wiki_snapshots (path, created_at DESC);")

    op.execute("""
        CREATE TABLE wiki_audit (
            id           BIGSERIAL PRIMARY KEY,
            op           TEXT NOT NULL,
            actor        TEXT NOT NULL,
            payload      JSONB NOT NULL,
            started_at   TIMESTAMPTZ NOT NULL,
            finished_at  TIMESTAMPTZ,
            status       TEXT NOT NULL,
            error        TEXT
        );
    """)

    op.execute("""
        CREATE TABLE wiki_jobs (
            id           BIGSERIAL PRIMARY KEY,
            audit_id     BIGINT REFERENCES wiki_audit(id),
            kind         TEXT NOT NULL,
            target_path  TEXT NOT NULL,
            status       TEXT NOT NULL,
            attempts     SMALLINT DEFAULT 0,
            last_error   TEXT,
            updated_at   TIMESTAMPTZ DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX idx_jobs_audit ON wiki_jobs (audit_id);")
    op.execute("""
        CREATE INDEX idx_jobs_status ON wiki_jobs (status)
        WHERE status IN ('pending', 'failed');
    """)

    op.execute("""
        CREATE VIEW wiki_broken_refs AS
        SELECT r.* FROM wiki_references r
        LEFT JOIN wiki_versions v ON v.path = r.target_path
        WHERE v.path IS NULL;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS wiki_broken_refs;")
    op.execute("DROP TABLE IF EXISTS wiki_jobs;")
    op.execute("DROP TABLE IF EXISTS wiki_audit;")
    op.execute("DROP TABLE IF EXISTS wiki_snapshots;")
    op.execute("DROP TABLE IF EXISTS wiki_versions;")
    op.execute("DROP TABLE IF EXISTS wiki_references;")
