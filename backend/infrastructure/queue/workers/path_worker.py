"""Path-worker — handles rename inbound patches and chunk metadata updates.

Phase 0 ships skeleton handlers that log and exit. Real implementations
land in Phase 3 (single-file rename) and Phase 4 (folder/bulk).
"""
from __future__ import annotations

import logging
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


async def patch_inbound(ctx: dict, source: str, old_target: str, new_target: str, audit_id: str = "") -> None:
    """Stub: patch a single inbound document. Real impl in Phase 3."""
    logger.info(f"[path-worker] patch_inbound stub: {source} {old_target}->{new_target} (audit={audit_id})")


async def update_chunk_metadata(ctx: dict, old_path: str, new_path: str, audit_id: str = "") -> None:
    """Stub: update chunk metadata in vector DB. Real impl in Phase 3."""
    logger.info(f"[path-worker] update_chunk_metadata stub: {old_path}->{new_path} (audit={audit_id})")


class WorkerSettings:
    """Arq worker config. Run with: `arq backend.infrastructure.queue.workers.path_worker.WorkerSettings`."""
    queue_name = "arq:queue:path"
    functions = [patch_inbound, update_chunk_metadata]

    @staticmethod
    def redis_settings():
        from backend.core.config import settings
        return RedisSettings.from_dsn(settings.redis_url)
