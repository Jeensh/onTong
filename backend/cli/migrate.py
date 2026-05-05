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
    sync_dsn = settings.postgres_dsn.replace("+asyncpg", "+psycopg")
    cfg.set_main_option("sqlalchemy.url", sync_dsn)
    print(f"Running alembic upgrade head against {sync_dsn} ...")
    command.upgrade(cfg, "head")
    print("Done.")
    return 0


def cmd_refindex_build(args: argparse.Namespace) -> int:
    """Build RefIndex from existing wiki content.

    Iterates every .md file under settings.wiki_dir (skipping system paths),
    extracts references via ReferenceExtractor, and upserts to RefIndex.
    """
    from pathlib import Path
    import time
    from backend.core.config import settings
    from backend.core.backends import get_ref_index, _reset_for_test
    from backend.application.refindex.extractor import ReferenceExtractor
    from backend.infrastructure.storage.local_fs import LocalFSAdapter

    profile = settings.resolve_profile()
    wiki_dir = Path(settings.wiki_dir)

    if not wiki_dir.is_dir():
        print(f"ERROR: wiki_dir not found: {wiki_dir}")
        return 2

    # Resolve RefIndex
    if profile.ref_index_backend == "sqlite":
        sqlite_path = wiki_dir / ".ontong" / "refs.db"
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        _reset_for_test()  # ensure fresh in-process binding to this path
        ref_index = get_ref_index(profile, sqlite_path=str(sqlite_path))
    elif profile.ref_index_backend == "postgres":
        if not settings.postgres_dsn:
            print("ERROR: settings.postgres_dsn is empty")
            return 2
        _reset_for_test()
        ref_index = get_ref_index(profile, postgres_dsn=settings.postgres_dsn)
    else:
        print(f"ERROR: unknown ref_index backend: {profile.ref_index_backend}")
        return 2

    # If --reset flag, clear before loading
    if getattr(args, "reset", False):
        ref_index.clear()
        print("RefIndex cleared (--reset).")

    extractor = ReferenceExtractor()

    # Iterate all markdown files
    started = time.time()
    count_files = 0
    count_refs = 0
    SYSTEM_PREFIXES = ("_skills/", "_personas/", ".ontong/", "assets/")

    for path_obj in wiki_dir.rglob("*.md"):
        rel = path_obj.relative_to(wiki_dir).as_posix()
        # Skip hidden directories
        if any(part.startswith(".") for part in path_obj.relative_to(wiki_dir).parts):
            continue
        if rel.startswith(SYSTEM_PREFIXES):
            continue
        try:
            raw = path_obj.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  SKIP {rel}: {e}")
            continue
        refs = extractor.extract(rel, raw)
        ref_index.upsert_for_source(rel, refs)
        count_files += 1
        count_refs += len(refs)
        if count_files % args.batch == 0:
            print(f"  ... {count_files} files, {count_refs} refs ({time.time()-started:.1f}s)")

    elapsed = time.time() - started
    print(f"Done: {count_files} files, {count_refs} refs in {elapsed:.1f}s "
          f"({count_files/elapsed:.0f} files/s)")
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

    rb = msub.add_parser("refindex-build", help="Build ReferenceIndex from existing wiki content")
    rb.add_argument("--batch", type=int, default=1000)
    rb.add_argument("--workers", type=int, default=4)  # reserved for future parallelism
    rb.add_argument("--reset", action="store_true", help="Clear existing RefIndex before building")
    rb.set_defaults(func=cmd_refindex_build)

    se = msub.add_parser("snapshots-export", help="Export snapshots between backends (Phase 2)")
    se.add_argument("--from", dest="from_", required=True)
    se.add_argument("--to", required=True)
    se.set_defaults(func=cmd_snapshots_export)

    fe = msub.add_parser("fulltext-export", help="Export search index between backends (Phase 6)")
    fe.add_argument("--from", dest="from_", required=True)
    fe.add_argument("--to", required=True)
    fe.set_defaults(func=cmd_fulltext_export)
