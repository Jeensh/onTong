"""VersionStore protocol — backend-agnostic OCC version tracking."""
from __future__ import annotations

from abc import ABC, abstractmethod


class VersionStore(ABC):
    @abstractmethod
    def get(self, path: str) -> str | None:
        """Return current version for path, or None if no row exists yet."""

    @abstractmethod
    def set(self, path: str, version: str, updated_by: str = "") -> None:
        """Upsert version row. Idempotent."""

    @abstractmethod
    def delete(self, path: str) -> None:
        """Remove the version row (file deleted)."""

    @abstractmethod
    def rename(self, old: str, new: str) -> None:
        """Update path key (file renamed). If `new` already has a row, raise ValueError."""

    @abstractmethod
    def clear(self) -> None:
        """Test/migration helper."""
