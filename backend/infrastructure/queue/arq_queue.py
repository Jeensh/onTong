"""Arq task queue — team/enterprise profile.

Workers run as separate processes via `arq backend.infrastructure.queue.workers.path_worker.WorkerSettings`.
This class is the producer side — schedules jobs into Redis.
"""
from __future__ import annotations

import logging
import uuid
from typing import Awaitable, Callable

from .task_queue_protocol import TaskQueue

logger = logging.getLogger(__name__)


class ArqTaskQueue(TaskQueue):
    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._pool = None

    async def start(self) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings
        self._pool = await create_pool(RedisSettings.from_dsn(self._url))

    async def stop(self) -> None:
        if self._pool:
            await self._pool.aclose()
            self._pool = None

    def register(self, fn_name: str, handler: Callable[..., Awaitable]) -> None:
        # Arq registers handlers in WorkerSettings (separate file). No-op here.
        logger.debug(f"Arq.register noop for {fn_name} — workers register via WorkerSettings")

    async def enqueue(self, queue: str, fn: str, *args, audit_id: str = "", **kwargs) -> str:
        assert self._pool is not None, "ArqTaskQueue.start() not called"
        job_id = uuid.uuid4().hex
        # Use queue_name to route to path-worker or content-worker
        await self._pool.enqueue_job(
            fn, *args, _queue_name=f"arq:queue:{queue}", _job_id=job_id, audit_id=audit_id, **kwargs,
        )
        return job_id

    async def progress(self, audit_id: str) -> dict:
        # Progress is read from Postgres wiki_jobs in higher layers. Arq itself
        # doesn't track audit-level rollups, so this returns the live job state
        # by querying wiki_jobs (P3+ wires this in). For Phase 0 stub:
        return {"total": 0, "done": 0, "failed": 0}
