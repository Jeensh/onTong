"""In-process asyncio task queue — dev profile."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Awaitable, Callable

from .task_queue_protocol import TaskQueue

logger = logging.getLogger(__name__)


class AsyncioTaskQueue(TaskQueue):
    def __init__(self, handlers: dict[str, Callable[..., Awaitable]] | None = None) -> None:
        self._handlers = handlers or {}
        self._queues: dict[str, asyncio.Queue] = {"path": asyncio.Queue(), "content": asyncio.Queue()}
        self._workers: list[asyncio.Task] = []
        # progress[audit_id] = {"total": int, "done": int, "failed": int}
        self._progress: dict[str, dict] = defaultdict(lambda: {"total": 0, "done": 0, "failed": 0})

    def register(self, fn_name: str, handler: Callable[..., Awaitable]) -> None:
        self._handlers[fn_name] = handler

    async def start(self) -> None:
        for qname in self._queues:
            self._workers.append(asyncio.create_task(self._worker_loop(qname)))

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        for w in self._workers:
            try:
                await w
            except asyncio.CancelledError:
                pass
        self._workers.clear()

    async def enqueue(self, queue: str, fn: str, *args, audit_id: str = "", **kwargs) -> str:
        if queue not in self._queues:
            raise ValueError(f"unknown queue: {queue}")
        if fn not in self._handlers:
            raise ValueError(f"no handler registered for {fn}")
        job_id = uuid.uuid4().hex
        if audit_id:
            self._progress[audit_id]["total"] += 1
        await self._queues[queue].put((job_id, fn, args, kwargs, audit_id))
        return job_id

    async def progress(self, audit_id: str) -> dict:
        return dict(self._progress[audit_id])

    async def _worker_loop(self, qname: str) -> None:
        q = self._queues[qname]
        while True:
            job_id, fn, args, kwargs, audit_id = await q.get()
            try:
                handler = self._handlers[fn]
                await handler(*args, **kwargs)
                if audit_id:
                    self._progress[audit_id]["done"] += 1
            except Exception as e:
                logger.error(f"Task {fn} ({job_id}) failed: {e}")
                if audit_id:
                    self._progress[audit_id]["failed"] += 1
            finally:
                q.task_done()
