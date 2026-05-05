"""In-memory KV store — single process only."""
from __future__ import annotations

from threading import RLock
from .kv_protocol import KVStore


class MemoryKVStore(KVStore):
    def __init__(self) -> None:
        self._d: dict[str, str] = {}
        self._lock = RLock()

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._d.get(key)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._d[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._d.pop(key, None)

    def keys(self, prefix: str) -> list[str]:
        with self._lock:
            return [k for k in self._d if k.startswith(prefix)]

    def clear(self) -> None:
        with self._lock:
            self._d.clear()
