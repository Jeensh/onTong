"""materialize wiki_sources.stem + index (Phase 7-E3)

Revision ID: 2026_05_06_004
Revises: 2026_05_06_003
Create Date: 2026-05-06

Adds stem column to wiki_sources so broken() can do a SQL-side anti-join
against wiki_references rather than pulling all rows into Python and filtering.

Backfill is straightforward: PurePosixPath(source_path).stem for every row.
The index on stem makes the NOT EXISTS lookup an index seek.
"""
from pathlib import PurePosixPath

import sqlalchemy as sa
from alembic import op


revision = "2026_05_06_004"
down_revision = "2026_05_06_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the column with an empty default so existing rows pass NOT NULL.
    op.execute("ALTER TABLE wiki_sources ADD COLUMN stem TEXT NOT NULL DEFAULT '';")

    # Backfill stem from source_path. Using Python because computing
    # filename-minus-.md in pure SQL across SQLite + Postgres is awkward.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT source_path FROM wiki_sources")).fetchall()
    for row in rows:
        sp = row[0]
        stem = PurePosixPath(sp).stem
        conn.execute(
            sa.text("UPDATE wiki_sources SET stem = :s WHERE source_path = :p"),
            {"s": stem, "p": sp},
        )

    op.execute("CREATE INDEX IF NOT EXISTS idx_wiki_sources_stem ON wiki_sources (stem);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_wiki_sources_stem;")
    op.execute("ALTER TABLE wiki_sources DROP COLUMN stem;")
