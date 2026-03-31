"""BM25 keyword search index for hybrid retrieval.

Uses periodic background rebuild (10s interval) instead of blocking
rebuild on every search. Ensures search never blocks on index updates.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

REBUILD_INTERVAL = 10  # seconds


def tokenize(text: str) -> list[str]:
    """Simple tokenizer for mixed Korean/English text.

    Splits on whitespace and punctuation, lowercases, filters short tokens.
    """
    text = text.lower()
    # Split on non-alphanumeric (keeping Korean chars)
    tokens = re.findall(r"[가-힣a-z0-9]+", text)
    return [t for t in tokens if len(t) >= 1]


@dataclass
class BM25Document:
    id: str
    file_path: str
    heading: str
    content: str
    tokens: list[str] = field(default_factory=list)


class BM25Index:
    """In-memory BM25 index with periodic background rebuild.

    Write operations (add/remove) set a dirty flag.
    A daemon thread rebuilds the index every REBUILD_INTERVAL seconds when dirty.
    Search always uses the current (possibly stale) index — never blocks.
    """

    def __init__(self) -> None:
        self._documents: list[BM25Document] = []
        self._bm25: BM25Okapi | None = None
        self._dirty = True
        self._lock = threading.Lock()
        self._daemon_started = False

    def _start_daemon(self) -> None:
        if self._daemon_started:
            return
        self._daemon_started = True
        t = threading.Thread(target=self._rebuild_daemon, daemon=True)
        t.start()
        logger.info("BM25 rebuild daemon started (interval=%ds)", REBUILD_INTERVAL)

    def _rebuild_daemon(self) -> None:
        """Periodically rebuild BM25 index when dirty."""
        import time
        while True:
            time.sleep(REBUILD_INTERVAL)
            if self._dirty:
                self._rebuild()

    @property
    def size(self) -> int:
        return len(self._documents)

    def clear(self) -> None:
        with self._lock:
            self._documents.clear()
            self._bm25 = None
            self._dirty = True

    def add_documents(self, docs: list[BM25Document]) -> None:
        with self._lock:
            self._documents.extend(docs)
            self._dirty = True
        self._start_daemon()

    def remove_by_file(self, file_path: str) -> None:
        with self._lock:
            self._documents = [d for d in self._documents if d.file_path != file_path]
            self._dirty = True

    def _rebuild(self) -> None:
        with self._lock:
            if not self._documents:
                self._bm25 = None
                self._dirty = False
                return
            corpus = [d.tokens for d in self._documents]
            new_bm25 = BM25Okapi(corpus)
            # Atomic swap
            self._bm25 = new_bm25
            self._dirty = False
            logger.info(f"BM25 index rebuilt: {len(self._documents)} documents")

    def search(self, query: str, n_results: int = 8) -> list[tuple[BM25Document, float]]:
        """Search the BM25 index. Returns (doc, score) pairs sorted by score desc.

        Uses the current index snapshot — never blocks for rebuild.
        On first call with dirty index, does an immediate rebuild.
        """
        if self._dirty and self._bm25 is None:
            # First-time rebuild (blocking only on cold start)
            self._rebuild()

        bm25 = self._bm25
        if not bm25 or not self._documents:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        with self._lock:
            docs_snapshot = list(self._documents)

        scores = bm25.get_scores(query_tokens)

        # Pair with documents and sort by score
        scored = [(doc, float(score)) for doc, score in zip(docs_snapshot, scores)]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Filter zero-score results
        results = [(doc, score) for doc, score in scored[:n_results] if score > 0]
        return results


# Singleton
bm25_index = BM25Index()
