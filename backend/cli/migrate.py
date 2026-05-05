"""ontong migrate <subcommand> — schema/data migrations."""
from __future__ import annotations

import argparse
import logging

logger = logging.getLogger(__name__)


def cmd_db_upgrade(args: argparse.Namespace) -> int:
    """Run alembic upgrade head against settings.postgres_dsn."""
    from alembic.config import Config
    from alembic import command
    from backend.core.config import settings

    if not settings.postgres_dsn:
        print("ERROR: settings.postgres_dsn is empty (set POSTGRES_DSN env var)")
        return 2

    cfg = Config("migrations/alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    sync_dsn = settings.postgres_dsn.replace("+asyncpg", "")
    cfg.set_main_option("sqlalchemy.url", sync_dsn)
    print(f"Running alembic upgrade head against {sync_dsn} ...")
    command.upgrade(cfg, "head")
    print("Done.")
    return 0


def cmd_refindex_build(args: argparse.Namespace) -> int:
    """Stub — real impl in Phase 1."""
    print("refindex-build is not yet implemented (lands in Phase 1).")
    return 0


def cmd_snapshots_export(args: argparse.Namespace) -> int:
    print("snapshots-export is not yet implemented (lands in Phase 2).")
    return 0


def cmd_fulltext_export(args: argparse.Namespace) -> int:
    print("fulltext-export is not yet implemented (lands in Phase 6).")
    return 0


def register_migrate(sub) -> None:
    p = sub.add_parser("migrate", help="Schema and data migrations")
    msub = p.add_subparsers(dest="migrate_cmd", required=True)

    db = msub.add_parser("db-upgrade", help="Run alembic upgrade head")
    db.set_defaults(func=cmd_db_upgrade)

    rb = msub.add_parser("refindex-build", help="Build ReferenceIndex from existing wiki content (Phase 1)")
    rb.add_argument("--batch", type=int, default=1000)
    rb.add_argument("--workers", type=int, default=4)
    rb.set_defaults(func=cmd_refindex_build)

    se = msub.add_parser("snapshots-export", help="Export snapshots between backends (Phase 2)")
    se.add_argument("--from", dest="from_", required=True)
    se.add_argument("--to", required=True)
    se.set_defaults(func=cmd_snapshots_export)

    fe = msub.add_parser("fulltext-export", help="Export search index between backends (Phase 6)")
    fe.add_argument("--from", dest="from_", required=True)
    fe.add_argument("--to", required=True)
    fe.set_defaults(func=cmd_fulltext_export)
