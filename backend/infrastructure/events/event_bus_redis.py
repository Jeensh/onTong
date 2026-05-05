"""Redis Pub/Sub-backed EventBus for multi-host SSE fan-out."""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import AsyncGenerator

from .event_bus import Event

logger = logging.getLogger(__name__)

CHANNEL = "ontong:events"


def _build_async_client(url: str):
    """Factory function — monkey-patchable in tests."""
    import redis.asyncio as aioredis
    return aioredis.from_url(url, decode_responses=True)


class RedisEventBus:
    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._redis = _build_async_client(redis_url)
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._callbacks: dict[str, list] = {}

    async def start(self) -> None:
        if self._listener_task is not None:
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(CHANNEL)
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub:
            await self._pubsub.unsubscribe(CHANNEL)
            await self._pubsub.aclose()
            self._pubsub = None
        await self._redis.aclose()

    async def _listen(self) -> None:
        """Read messages from Redis pubsub and fan out to local subscribers.

        On transient errors (connection drop, etc.) the loop logs and retries
        with exponential backoff up to 30s. CancelledError propagates so stop()
        can shut down cleanly.
        """
        backoff = 1.0
        while True:
            try:
                async for msg in self._pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    try:
                        payload = json.loads(msg["data"])
                    except (json.JSONDecodeError, KeyError):
                        continue
                    event = Event(type=payload["type"], data=payload["data"])
                    self._fanout_to_local(event)
                    backoff = 1.0  # reset after a successful message
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Redis pubsub listener error (retry in %.1fs): %s", backoff, e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    def _fanout_to_local(self, event: Event) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    def on(self, event_type: str, callback) -> None:
        self._callbacks.setdefault(event_type, []).append(callback)

    def publish(self, event_type: str, data: dict) -> None:
        # 1. Run local callbacks inline (cache invalidation etc)
        for cb in self._callbacks.get(event_type, []):
            if inspect.iscoroutinefunction(cb):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(cb(data))
                except RuntimeError:
                    pass
            else:
                try:
                    cb(data)
                except Exception as e:
                    logger.warning("Event callback error for %s: %s", event_type, e)

        # 2. Publish to Redis (fan-out across hosts)
        payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._redis.publish(CHANNEL, payload))
        except RuntimeError:
            # No running event loop (e.g. publish called from sync context outside FastAPI).
            # Cannot use asyncio.run here — it would deadlock if a parent loop ever resumes.
            # Local callbacks already ran above; remote fan-out is dropped with a warning.
            logger.warning(
                "RedisEventBus.publish called outside an event loop; remote fan-out skipped (event_type=%s)",
                event_type,
            )

    async def subscribe(self) -> AsyncGenerator[Event, None]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
