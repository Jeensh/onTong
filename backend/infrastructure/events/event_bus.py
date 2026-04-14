"""Server-Sent Events (SSE) event bus for real-time broadcasting.

Events: tree changes, indexing status, lock status.
Clients subscribe via GET /api/events (SSE stream).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


@dataclass
class Event:
    type: str  # "tree_change" | "index_status" | "lock_change"
    data: dict
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False)
        return f"event: {self.type}\ndata: {payload}\n\n"


class EventBus:
    """Async broadcast hub — fan-out events to all connected SSE clients.

    Also supports synchronous callbacks for cache invalidation etc.
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._callbacks: dict[str, list] = {}  # event_type → [callable]

    def on(self, event_type: str, callback) -> None:
        """Register a synchronous callback for an event type.

        Used for cache invalidation on tree_change events.
        Callbacks must be fast (no I/O) — they run in the publish path.
        """
        self._callbacks.setdefault(event_type, []).append(callback)

    def publish(self, event_type: str, data: dict) -> None:
        event = Event(type=event_type, data=data)

        # Fire synchronous callbacks first (cache invalidation, etc.)
        for cb in self._callbacks.get(event_type, []):
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
        # Remove dead/full queues
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


# Singleton
event_bus = EventBus()
