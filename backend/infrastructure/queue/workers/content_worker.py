"""Content-worker — handles BG indexing, embedding, snapshot persistence.

Phase 0 ships skeleton; real impls in Phase 1 (refindex extract) and Phase 2 (snapshot).
"""
from __future__ import annotations

import logging
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


async def bg_index(ctx: dict, path: str, audit_id: str = "") -> None:
    """Stub: index a file (chunking + embeddings + BM25). Real impl in P1+."""
    logger.info(f"[content-worker] bg_index stub: {path} (audit={audit_id})")


async def bg_remove_chunks(ctx: dict, path: str, audit_id: str = "") -> None:
    """Stub: remove chunks for a deleted file."""
    logger.info(f"[content-worker] bg_remove_chunks stub: {path} (audit={audit_id})")


async def bg_reembed_chunks(ctx: dict, path: str, audit_id: str = "") -> None:
    """Stub: regenerate embeddings after chunk-body path prefix change (OQ-4=A)."""
    logger.info(f"[content-worker] bg_reembed_chunks stub: {path} (audit={audit_id})")


class WorkerSettings:
    queue_name = "arq:queue:content"
    functions = [bg_index, bg_remove_chunks, bg_reembed_chunks]

    @staticmethod
    def redis_settings():
        from backend.core.config import settings
        return RedisSettings.from_dsn(settings.redis_url)
