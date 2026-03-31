"""File content hash store for incremental indexing."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileHashStore:
    """Tracks content hashes to detect changes for incremental indexing.

    Stores a JSON map of {file_path: content_hash} on disk.
    """

    def __init__(self, store_path: str | Path) -> None:
        self._path = Path(store_path)
        self._hashes: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._hashes = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._hashes = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._hashes, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def compute_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def has_changed(self, file_path: str, content: str) -> bool:
        """Return True if the file content has changed since last index."""
        new_hash = self.compute_hash(content)
        return self._hashes.get(file_path) != new_hash

    def update(self, file_path: str, content: str) -> None:
        """Record the current hash for a file."""
        self._hashes[file_path] = self.compute_hash(content)
        self._save()

    def remove(self, file_path: str) -> None:
        """Remove a file from the hash store."""
        self._hashes.pop(file_path, None)
        self._save()

    def clear(self) -> None:
        """Clear all hashes (for full reindex)."""
        self._hashes.clear()
        self._save()

    @property
    def tracked_files(self) -> set[str]:
        return set(self._hashes.keys())
