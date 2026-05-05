"""Snapshot store protocol + Snapshot dataclass.

A Snapshot is a pre-image of a file captured before a write (save/delete/rename).
The retention window is N=20 per path — enforced on every append.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    path: str
    version: str
    user_name: str
    created_at: float           # unix epoch seconds
    reason: str                 # "save" | "pre_delete" | "pre_rename" | "pre_merge"


class SnapshotStore(ABC):
    @abstractmethod
    def append(self, path: str, content: str, version: str, user_name: str, reason: str) -> None:
        """Insert a new snapshot row, then prune to keep only N most recent for this path."""

    @abstractmethod
    def list(self, path: str, *, limit: int = 20) -> list[Snapshot]:
        """Most-recent-first list of snapshot metadata (no content). Used by /snapshots endpoint."""

    @abstractmethod
    def get_content(self, path: str, version: str) -> str | None:
        """Return raw content (decoded as UTF-8) for the specified path+version, or None."""

    @abstractmethod
    def prune(self, path: str, *, keep: int) -> int:
        """Remove all but the N most recent snapshots for this path. Returns rows deleted."""

    @abstractmethod
    def delete_for_path(self, path: str) -> int:
        """Remove ALL snapshots for path (used when file is permanently deleted+G7-cleared)."""
