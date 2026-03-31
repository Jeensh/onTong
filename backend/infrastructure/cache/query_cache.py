"""Query cache for RAG search results.

Supports two backends:
- In-memory OrderedDict LRU (default, for development / single worker)
- Redis (for production multi-worker, shared cache with higher hit rate)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes
DEFAULT_MAX_SIZE = 128


@dataclass
class CacheEntry:
    results: dict
    created_at: float
    query: str


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class QueryCache:
    """LRU cache for search query results with TTL expiry."""

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl: int = DEFAULT_TTL) -> None:
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self.stats = CacheStats()

    @staticmethod
    def _make_key(query: str, metadata_filter: dict | None = None) -> str:
        raw = query.strip().lower()
        if metadata_filter:
            raw += f"|{sorted(metadata_filter.items())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, query: str, metadata_filter: dict | None = None) -> dict | None:
        key = self._make_key(query, metadata_filter)
        entry = self._cache.get(key)
        if entry is None:
            self.stats.misses += 1
            return None

        if time.time() - entry.created_at > self._ttl:
            del self._cache[key]
            self.stats.misses += 1
            return None

        self._cache.move_to_end(key)
        self.stats.hits += 1
        return entry.results

    def put(self, query: str, results: dict, metadata_filter: dict | None = None) -> None:
        key = self._make_key(query, metadata_filter)

        if len(self._cache) >= self._max_size and key not in self._cache:
            self._cache.popitem(last=False)
            self.stats.evictions += 1

        self._cache[key] = CacheEntry(
            results=results,
            created_at=time.time(),
            query=query,
        )
        self._cache.move_to_end(key)

    def invalidate_by_file(self, file_path: str) -> int:
        to_remove = []
        for key, entry in self._cache.items():
            metas = entry.results.get("metadatas", [[]])[0]
            for meta in metas:
                if meta.get("file_path") == file_path:
                    to_remove.append(key)
                    break

        for key in to_remove:
            del self._cache[key]
        self.stats.invalidations += len(to_remove)

        if to_remove:
            logger.info(f"Cache invalidated {len(to_remove)} entries for {file_path}")
        return len(to_remove)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class RedisQueryCache(QueryCache):
    """Redis-backed query cache (multi-worker shared, LRU via Redis eviction)."""

    CACHE_PREFIX = "ontong:qcache:"
    FILE_INDEX_PREFIX = "ontong:qcache_file:"

    def __init__(self, redis_url: str, ttl: int = DEFAULT_TTL) -> None:
        super().__init__(ttl=ttl)
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl
        logger.info("Redis query cache connected")

    def get(self, query: str, metadata_filter: dict | None = None) -> dict | None:
        key = self._make_key(query, metadata_filter)
        raw = self._redis.get(f"{self.CACHE_PREFIX}{key}")
        if raw is None:
            self.stats.misses += 1
            return None
        self.stats.hits += 1
        return json.loads(raw)

    def put(self, query: str, results: dict, metadata_filter: dict | None = None) -> None:
        key = self._make_key(query, metadata_filter)
        redis_key = f"{self.CACHE_PREFIX}{key}"
        self._redis.set(redis_key, json.dumps(results), ex=self._ttl)

        # Track which cache keys contain which file paths for invalidation
        metas = results.get("metadatas", [[]])[0]
        for meta in metas:
            fp = meta.get("file_path")
            if fp:
                self._redis.sadd(f"{self.FILE_INDEX_PREFIX}{fp}", key)

    def invalidate_by_file(self, file_path: str) -> int:
        index_key = f"{self.FILE_INDEX_PREFIX}{file_path}"
        cache_keys = self._redis.smembers(index_key)
        count = 0
        if cache_keys:
            pipe = self._redis.pipeline()
            for key in cache_keys:
                pipe.delete(f"{self.CACHE_PREFIX}{key}")
            pipe.delete(index_key)
            pipe.execute()
            count = len(cache_keys)
        self.stats.invalidations += count
        if count:
            logger.info(f"Redis cache invalidated {count} entries for {file_path}")
        return count

    def clear(self) -> None:
        # Clear all cache keys (use SCAN to avoid blocking)
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match=f"{self.CACHE_PREFIX}*", count=100)
            if keys:
                self._redis.delete(*keys)
            if cursor == 0:
                break
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match=f"{self.FILE_INDEX_PREFIX}*", count=100)
            if keys:
                self._redis.delete(*keys)
            if cursor == 0:
                break

    @property
    def size(self) -> int:
        count = 0
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match=f"{self.CACHE_PREFIX}*", count=100)
            count += len(keys)
            if cursor == 0:
                break
        return count


def create_query_cache() -> QueryCache:
    """Create query cache with appropriate backend based on config."""
    from backend.core.config import settings
    if settings.redis_url:
        try:
            return RedisQueryCache(settings.redis_url)
        except Exception as e:
            logger.warning(f"Redis query cache failed, falling back to in-memory: {e}")
    return QueryCache()


# Singleton
query_cache = create_query_cache()
