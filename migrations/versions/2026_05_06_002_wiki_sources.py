"""wiki_sources table for stem disambiguation (Phase 5-A)

Revision ID: 2026_05_06_002
Revises: 2026_05_05_001
Create Date: 2026-05-06

Adds wiki_sources to track all indexed source paths (even those with zero
outbound refs). Used by RefIndex.stems() and broken() to disambiguate
BODY_WIKILINK from valid wikilink targets. Backfills from existing
wiki_references DISTINCT source_paths.
"""
from alembic import op


revision = "2026_05_06_002"
down_revision = "2026_05_05_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS wiki_sources (
            source_path TEXT PRIMARY KEY,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    # Backfill from existing wiki_references so stems()/broken() work
    # immediately after deploy without waiting for next save.
    op.execute("""
        INSERT INTO wiki_sources (source_path)
        SELECT DISTINCT source_path FROM wiki_references
        ON CONFLICT (source_path) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wiki_sources;")
