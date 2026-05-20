"""CLI — batch reindex wiki files into ChromaDB + BM25 + MetadataIndex
with the Phase 2 filter fields (authors[], doc_type, mtime_epoch).

Usage:
    python -m backend.cli.reindex_metadata                  # incremental (skip unchanged)
    python -m backend.cli.reindex_metadata --force           # full rebuild
    python -m backend.cli.reindex_metadata --dry-run         # show target files, no writes
    python -m backend.cli.reindex_metadata --batch 500       # batch size for progress logging

Assumes ChromaDB is reachable via settings.chroma_* config. Intended for 100K-scale
migrations where the BG indexer daemon alone would be slow.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.config import settings  # noqa: E402
from backend.infrastructure.vectordb.chroma import ChromaWrapper  # noqa: E402
from backend.infrastructure.storage.local_fs import LocalFSAdapter  # noqa: E402
from backend.application.wiki.wiki_indexer import (  # noqa: E402
    WikiIndexer,
    compute_effective_authors,
    compute_mtime_epoch,
)
from backend.application.metadata.metadata_index import MetadataIndex  # noqa: E402

logger = logging.getLogger(__name__)


async def _load_all_files(storage: LocalFSAdapter):
    """Yield every WikiFile under the wiki root."""
    tree = await storage.list_tree()

    def _walk(nodes):
        for n in nodes:
            if n.is_dir:
                yield from _walk(n.children or [])
            else:
                yield n.path

    paths = list(_walk(tree))
    files = []
    for p in paths:
        try:
            wf = await storage.read(p)
            if wf is not None and p.endswith(".md"):
                files.append(wf)
        except Exception as e:  # noqa: BLE001
            logger.warning("skip %s: %s", p, e)
    return files


async def _rebuild_metadata_index(meta_index: MetadataIndex, files, wiki_dir: Path) -> None:
    """Full rebuild with the extended entry format (authors/doc_type/mtime_epoch)."""
    extended = []
    for wf in files:
        m = wf.metadata
        abs_path = str(wiki_dir / wf.path)
        extended.append({
            "path": wf.path,
            "domain": m.domain,
            "process": m.process,
            "tags": list(m.tags),
            "updated": m.updated,
            "updated_by": m.updated_by,
            "created_by": m.created_by,
            "related": list(m.related),
            "status": m.status,
            "supersedes": m.supersedes,
            "superseded_by": m.superseded_by,
            "authors": compute_effective_authors(m),
            "doc_type": m.doc_type,
            "mtime_epoch": compute_mtime_epoch(m, abs_path),
        })
    meta_index.rebuild(extended=extended)


async def main(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    wiki_dir = Path(settings.wiki_dir)
    print(f"Wiki root: {wiki_dir}")

    storage = LocalFSAdapter(wiki_dir)
    files = await _load_all_files(storage)
    print(f"Found {len(files)} files.")

    if args.dry_run:
        for f in files[:20]:
            m = f.metadata
            authors = compute_effective_authors(m)
            mt = compute_mtime_epoch(m, str(wiki_dir / f.path))
            print(f"  {f.path:60s} authors={authors} doc_type={m.doc_type!r} mtime={mt:.0f}")
        if len(files) > 20:
            print(f"  ... ({len(files) - 20} more)")
        return 0

    chroma = ChromaWrapper()
    chroma.connect()
    from backend.core.backends import get_fulltext_search
    _ft_profile = settings.resolve_profile()
    fulltext = get_fulltext_search(_ft_profile, es_url=settings.es_url)
    indexer = WikiIndexer(chroma, fulltext)

    # 1) Rebuild MetadataIndex with new fields
    meta_index = MetadataIndex(str(wiki_dir))
    print("Rebuilding metadata index (authors/doc_type/mtime_epoch)...")
    await _rebuild_metadata_index(meta_index, files, wiki_dir)
    print(f"  metadata_index.json: {len(files)} files written")

    # 2) Reindex into Chroma + BM25
    print(f"Reindexing ChromaDB + BM25 (force={args.force})...")
    t0 = time.perf_counter()
    done = 0
    indexed_chunks = 0
    skipped = 0
    for wf in files:
        try:
            n = await indexer.index_file(wf, force=args.force)
            indexed_chunks += n
            if n == 0:
                skipped += 1
        except Exception as e:  # noqa: BLE001
            logger.error("failed %s: %s", wf.path, e)
        done += 1
        if done % args.batch == 0:
            elapsed = time.perf_counter() - t0
            rate = done / elapsed if elapsed else 0
            print(f"  {done}/{len(files)} files · {indexed_chunks} chunks · {rate:.1f} files/s")

    elapsed = time.perf_counter() - t0
    print(f"Done in {elapsed:.1f}s · {indexed_chunks} chunks written · {skipped} unchanged")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reindex wiki metadata for Phase 2 filter fields.")
    p.add_argument("--force", action="store_true", help="Clear and rebuild from scratch (ignore content hash cache)")
    p.add_argument("--dry-run", action="store_true", help="List target files + computed fields; no writes")
    p.add_argument("--batch", type=int, default=500, help="Progress logging batch size (default 500)")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
