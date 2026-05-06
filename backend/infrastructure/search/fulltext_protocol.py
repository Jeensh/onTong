"""FullTextSearch protocol — abstraction over BM25 / ES / PG-FTS."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    file_path: str
    chunk_id: str
    heading: str
    content: str
    score: float


class FullTextSearch(ABC):
    @abstractmethod
    def add_documents(self, docs: list) -> int:
        """Add chunk documents. Each must have id, file_path, heading, content, tokens.
        Returns count added."""

    @abstractmethod
    def remove_by_file(self, file_path: str) -> int:
        """Remove all chunks for a file. Returns count removed."""

    @abstractmethod
    def search(self, query: str, limit: int = 10, *, file_predicate=None) -> list[SearchHit]:
        """Full-text search. file_predicate filters before scoring."""

    @abstractmethod
    def has_file(self, file_path: str) -> bool:
        """True iff at least one chunk for file_path is present.

        Used by WikiIndexer to skip re-adding documents that are already
        indexed (BM25 is in-process; on cold-start it may be empty even when
        ChromaDB is up-to-date)."""

    @abstractmethod
    def clear(self) -> None: ...

    @property
    @abstractmethod
    def size(self) -> int: ...
