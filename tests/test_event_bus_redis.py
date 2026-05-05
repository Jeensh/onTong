"""Redis Pub/Sub event bus tests."""
from __future__ import annotations

import asyncio
import pytest

import fakeredis.aioredis as fake_async


@pytest.mark.asyncio
async def test_publish_subscribe_round_trip(monkeypatch):
    fake = fake_async.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.events.event_bus_redis._build_async_client",
        lambda url: fake,
    )

    from backend.infrastructure.events.event_bus_redis import RedisEventBus

    bus = RedisEventBus(redis_url="redis://fake")
    await bus.start()

    received: list[dict] = []

    async def collect():
        async for ev in bus.subscribe():
            received.append({"type": ev.type, "data": ev.data})
            if len(received) >= 1:
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)  # subscriber ready
    bus.publish("tree_change", {"path": "foo.md"})
    await asyncio.wait_for(task, timeout=2.0)

    assert received == [{"type": "tree_change", "data": {"path": "foo.md"}}]
    await bus.stop()


@pytest.mark.asyncio
async def test_callbacks_run_inline_for_publisher(monkeypatch):
    fake = fake_async.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "backend.infrastructure.events.event_bus_redis._build_async_client",
        lambda url: fake,
    )
    from backend.infrastructure.events.event_bus_redis import RedisEventBus

    bus = RedisEventBus(redis_url="redis://fake")
    await bus.start()

    seen: list[dict] = []
    bus.on("index_status", lambda d: seen.append(d))
    bus.publish("index_status", {"path": "x", "action": "done"})

    assert seen == [{"path": "x", "action": "done"}]
    await bus.stop()
