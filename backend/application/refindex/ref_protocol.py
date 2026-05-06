"""RefIndex Protocol — abstract base for reference index backends."""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.application.refindex.extractor import Reference


class RefIndex(ABC):
    @abstractmethod
    def upsert_for_source(self, source_path: str, refs: list[Reference]) -> None:
        """Replace all refs originating from source_path with the given list.

        Implementation: DELETE WHERE source_path=? then INSERT each ref.
        Atomic per source (single transaction)."""

    @abstractmethod
    def remove_for_source(self, source_path: str) -> None:
        """Remove all refs originating from source_path (file deleted)."""

    @abstractmethod
    def inbound(self, target_path: str, *, kind: int | None = None) -> list[Reference]:
        """All refs whose target_path == target. Used for delete-block check + rename impact."""

    @abstractmethod
    def outbound(self, source_path: str) -> list[Reference]:
        """All refs originating from source_path. Used for body-edit reconciliation."""

    @abstractmethod
    def rename_target(self, old: str, new: str) -> int:
        """UPDATE wiki_references SET target_path=new WHERE target_path=old. Returns row count.
        Used by Phase 3 RenameOrchestrator after a file is renamed."""

    @abstractmethod
    def rename_source(self, old: str, new: str) -> int:
        """UPDATE source_path. Returns row count. Used after a file rename to track its new identity."""

    @abstractmethod
    def broken(self, *, limit: int = 100, offset: int = 0, kind: int | None = None) -> list[Reference]:
        """References whose target_path doesn't exist as a known source. Used by /broken-refs API.

        Implementation: LEFT JOIN against the set of known sources. The "known sources" set =
        DISTINCT source_path from the same table (every indexed file appears as a source).
        Yes, this means a doc with no outbound refs is invisible to broken() — that's acceptable
        for Phase 1; Phase 6 can refine."""

    @abstractmethod
    def stems(self) -> dict[str, list[str]]:
        """Map of stem → [source_paths with that stem].

        Stem = filename without .md extension. Built from DISTINCT source_path
        in the index. Used by broken() to disambiguate wikilink false positives:
        a [[foo]] wikilink is only broken if no indexed source has stem 'foo'.
        """

    @abstractmethod
    def clear(self) -> None:
        """Wipe the entire index. Test-only / migration use."""
