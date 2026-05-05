"""Redis-backed metadata index — single hash key for the entire blob.

Uses a single Redis key holding the JSON blob (same shape as the JSON file).
For 100K files this is ~10-20MB; well within Redis limits and atomic for
single-key reads/writes. If size becomes an issue, this can be sharded later
(e.g. one hash per file).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .metadata_protocol import MetadataBackend, empty_default

logger = logging.getLogger(__name__)

KEY = "ontong:metadata_index"


def _build_client(url: str):
    import redis
    return redis.from_url(url, decode_responses=True)


class RedisHashBackend(MetadataBackend):
    def __init__(self, redis_url: str) -> None:
        self._r = _build_client(redis_url)

    def load(self) -> dict[str, Any]:
        raw = self._r.get(KEY)
        if not raw:
            return empty_default()
        try:
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Corrupt metadata index in Redis, returning empty: {e}")
            return empty_default()

    def save(self, data: dict[str, Any]) -> None:
        self._r.set(KEY, json.dumps(data, ensure_ascii=False))
