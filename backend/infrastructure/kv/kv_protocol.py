"""KVStore protocol — simple string KV with prefix scan."""
from __future__ import annotations

from abc import ABC, abstractmethod


class KVStore(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def keys(self, prefix: str) -> list[str]: ...

    @abstractmethod
    def clear(self) -> None: ...
