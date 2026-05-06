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
    def clear(self) -> None: ...

    @property
    @abstractmethod
    def size(self) -> int: ...
