"""In-process EventBus — original implementation, single Python process only."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import AsyncGenerator

from .event_bus import Event  # Event dataclass stays in event_bus.py

logger = logging.getLogger(__name__)


class InProcessEventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._callbacks: dict[str, list] = {}

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    def on(self, event_type: str, callback) -> None:
        self._callbacks.setdefault(event_type, []).append(callback)

    def publish(self, event_type: str, data: dict) -> None:
        event = Event(type=event_type, data=data)
        for cb in self._callbacks.get(event_type, []):
            if inspect.iscoroutinefunction(cb):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(cb(data))
                except RuntimeError:
                    logger.warning(
                        "Async callback for %s dropped (no running event loop)",
                        event_type,
                    )
            else:
                try:
                    cb(data)
                except Exception as e:
                    logger.warning("Event callback error for %s: %s", event_type, e)

        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

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
