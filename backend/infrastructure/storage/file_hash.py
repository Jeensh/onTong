"""File content hash store — backed by KVStore."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class FileHashStore:
    """Tracks per-file content hash to detect unchanged content during reindex.

    Backed by KVStore so it survives multi-worker / multi-host deployments.
    The `path` argument to `__init__` is retained for backward compat (legacy
    file-based callsites) but ignored when KV backend is 'redis'.
    """

    def __init__(self, path: Path | None = None) -> None:
        from backend.core.config import settings
        from backend.core.backends import get_kv_store
        profile = settings.resolve_profile()
        self._kv = get_kv_store(profile, namespace="hash", redis_url=settings.redis_url)
        # Legacy migration: load existing JSON file into KV on first init
        if path and path.exists() and profile.kv_backend == "memory":
            try:
                import json
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if self._kv.get(k) is None:
                        self._kv.set(k, v)
            except Exception as e:
                logger.warning(f"Legacy hash file load failed: {e}")

    def has_changed(self, file_path: str, content: str) -> bool:
        new_hash = _hash(content)
        old_hash = self._kv.get(file_path)
        return old_hash != new_hash

    def update(self, file_path: str, content: str) -> None:
        self._kv.set(file_path, _hash(content))

    def remove(self, file_path: str) -> None:
        self._kv.delete(file_path)

    def clear(self) -> None:
        self._kv.clear()
