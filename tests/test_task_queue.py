"""TaskQueue tests — both backends behave equivalently for basic enqueue."""
from __future__ import annotations

import asyncio
import pytest


@pytest.mark.asyncio
async def test_asyncio_queue_runs_task():
    from backend.infrastructure.queue.asyncio_queue import AsyncioTaskQueue

    received: list[tuple] = []

    async def my_task(arg1: str, arg2: int) -> None:
        received.append((arg1, arg2))

    q = AsyncioTaskQueue(handlers={"my_task": my_task})
    await q.start()
    job_id = await q.enqueue("path", "my_task", "hello", 42)
    await asyncio.sleep(0.1)
    await q.stop()

    assert received == [("hello", 42)]
    assert job_id


@pytest.mark.asyncio
async def test_asyncio_queue_progress():
    from backend.infrastructure.queue.asyncio_queue import AsyncioTaskQueue

    async def slow_task() -> None:
        await asyncio.sleep(0.05)

    q = AsyncioTaskQueue(handlers={"slow_task": slow_task})
    await q.start()
    audit_id = "audit-1"
    await q.enqueue("path", "slow_task", audit_id=audit_id)
    await q.enqueue("path", "slow_task", audit_id=audit_id)
    p = await q.progress(audit_id)
    assert p["total"] == 2
    await asyncio.sleep(0.2)
    p = await q.progress(audit_id)
    assert p["done"] == 2
    await q.stop()
