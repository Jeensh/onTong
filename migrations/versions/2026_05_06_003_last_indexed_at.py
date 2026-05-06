"""rename wiki_sources.indexed_at to last_indexed_at + add index (Phase 7-E5)

Revision ID: 2026_05_06_003
Revises: 2026_05_06_002
Create Date: 2026-05-06

Renames the column from `indexed_at` to `last_indexed_at` so its semantics
(time of most recent re-index, not first index) are explicit. Adds an index on
the column so stale_sources(threshold) can scan in time order without a seq scan.

The previous implementation used `ON CONFLICT DO NOTHING` on Postgres, which
meant the timestamp froze at first index. That's fixed in the backends as part
of this migration — DO UPDATE SET last_indexed_at = now() is now used.
"""
from alembic import op


revision = "2026_05_06_003"
down_revision = "2026_05_06_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename the column. SQLite requires 3.25+; Postgres always supports it.
    op.execute("ALTER TABLE wiki_sources RENAME COLUMN indexed_at TO last_indexed_at;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wiki_sources_last_indexed ON wiki_sources (last_indexed_at);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_wiki_sources_last_indexed;")
    op.execute("ALTER TABLE wiki_sources RENAME COLUMN last_indexed_at TO indexed_at;")
