"""In-memory LRU + TTL cache for confidence scores.

Invalidated on tree_change events via EventBus.
Bounded to MAX_SIZE entries to prevent memory leaks at 100K+ document scale.
"""

from __future__ import annotations

import time
import threading
from collections import OrderedDict

from backend.application.trust.confidence import ConfidenceResult

DEFAULT_TTL = 300  # 5 minutes
DEFAULT_MAX_SIZE = 5_000  # LRU cap — sufficient for hot working set


class ConfidenceCache:
    """Thread-safe LRU + TTL cache for confidence results.

    At 100K documents, we don't cache everything — the LRU keeps the
    most recently accessed entries and evicts the rest.
    """

    def __init__(self, ttl: int = DEFAULT_TTL, max_size: int = DEFAULT_MAX_SIZE) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._store: OrderedDict[str, tuple[ConfidenceResult, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, path: str) -> ConfidenceResult | None:
        with self._lock:
            entry = self._store.get(path)
            if entry is None:
                return None
            result, ts = entry
            if time.time() - ts > self._ttl:
                del self._store[path]
                return None
            # Move to end (most recently used)
            self._store.move_to_end(path)
            return result

    def put(self, path: str, result: ConfidenceResult) -> None:
        with self._lock:
            if path in self._store:
                self._store.move_to_end(path)
            self._store[path] = (result, time.time())
            # Evict oldest entries if over capacity
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def invalidate(self, path: str) -> None:
        with self._lock:
            self._store.pop(path, None)

    def invalidate_all(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)
