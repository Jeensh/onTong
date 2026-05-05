"""JSON file backend — original behavior."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .metadata_protocol import MetadataBackend, empty_default

logger = logging.getLogger(__name__)


class JsonFileBackend(MetadataBackend):
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._cache: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if self._path.exists():
            try:
                self._cache = json.loads(self._path.read_text(encoding="utf-8"))
                return self._cache
            except Exception as e:
                logger.warning(f"Failed to load metadata index: {e}")
        self._cache = empty_default()
        return self._cache

    def save(self, data: dict[str, Any]) -> None:
        self._cache = data
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save metadata index: {e}")
