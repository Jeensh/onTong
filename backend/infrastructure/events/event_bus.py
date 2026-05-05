"""SSE event bus.

The concrete implementation is selected by Profile (see backend.core.backends).
Module-level `event_bus` singleton is initialized on first access.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass
class Event:
    type: str
    data: dict
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False)
        return f"event: {self.type}\ndata: {payload}\n\n"


class _EventBusProxy:
    """Lazy proxy — resolves backend on first call."""
    def __init__(self) -> None:
        self._impl = None

    def _get(self):
        if self._impl is None:
            from backend.core.config import settings
            from backend.core.backends import get_event_bus
            self._impl = get_event_bus(settings.resolve_profile(), redis_url=settings.redis_url)
        return self._impl

    def __getattr__(self, name):
        return getattr(self._get(), name)


event_bus = _EventBusProxy()
