"""Redis lock backend."""
from __future__ import annotations

import json
import logging
import time
from .lock_protocol import LockBackend, LockInfo, DEFAULT_TTL

logger = logging.getLogger(__name__)


def _build_client(url: str):
    """Factory function — monkey-patchable in tests."""
    import redis
    return redis.from_url(url, decode_responses=True)


class RedisLockBackend(LockBackend):
    KEY_PREFIX = "ontong:lock:"
    USER_INDEX_PREFIX = "ontong:user_locks:"

    def __init__(self, redis_url: str) -> None:
        self._redis = _build_client(redis_url)
        logger.info(f"Redis lock backend connected: {redis_url}")

    def _key(self, path: str) -> str:
        return f"{self.KEY_PREFIX}{path}"

    def acquire(self, path: str, user: str, ttl: int = DEFAULT_TTL) -> LockInfo | None:
        key = self._key(path)
        now = time.time()
        lock_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})

        if self._redis.set(key, lock_data, nx=True, ex=ttl):
            self._redis.sadd(f"{self.USER_INDEX_PREFIX}{user}", path)
            logger.info(f"Lock acquired (Redis): {path} by {user}")
            return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)

        existing_raw = self._redis.get(key)
        if not existing_raw:
            if self._redis.set(key, lock_data, nx=True, ex=ttl):
                self._redis.sadd(f"{self.USER_INDEX_PREFIX}{user}", path)
                return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)
            return None

        existing = json.loads(existing_raw)
        if existing["user"] == user:
            self._redis.set(key, lock_data, ex=ttl)
            return LockInfo(path=path, user=user, acquired_at=now, ttl=ttl)

        return None

    def release(self, path: str, user: str) -> bool:
        key = self._key(path)
        existing_raw = self._redis.get(key)
        if not existing_raw:
            return True
        existing = json.loads(existing_raw)
        if existing["user"] != user:
            return False
        self._redis.delete(key)
        self._redis.srem(f"{self.USER_INDEX_PREFIX}{user}", path)
        logger.info(f"Lock released (Redis): {path} by {user}")
        return True

    def status(self, path: str) -> LockInfo | None:
        raw = self._redis.get(self._key(path))
        if not raw:
            return None
        data = json.loads(raw)
        return LockInfo(
            path=path, user=data["user"],
            acquired_at=data["acquired_at"], ttl=data["ttl"],
        )

    def refresh(self, path: str, user: str) -> bool:
        key = self._key(path)
        raw = self._redis.get(key)
        if not raw:
            return False
        data = json.loads(raw)
        if data["user"] != user:
            return False
        now = time.time()
        ttl = data["ttl"]
        new_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})
        self._redis.set(key, new_data, ex=ttl)
        return True

    def release_all_by_user(self, user: str) -> int:
        index_key = f"{self.USER_INDEX_PREFIX}{user}"
        paths = self._redis.smembers(index_key)
        count = 0
        for path in paths:
            key = self._key(path)
            raw = self._redis.get(key)
            if raw:
                data = json.loads(raw)
                if data["user"] == user:
                    self._redis.delete(key)
                    count += 1
        self._redis.delete(index_key)
        if count:
            logger.info(f"Released {count} locks for user {user} (Redis)")
        return count

    def batch_refresh(self, paths: list[str], user: str) -> int:
        pipe = self._redis.pipeline()
        for path in paths:
            pipe.get(self._key(path))
        results = pipe.execute()

        now = time.time()
        refresh_pipe = self._redis.pipeline()
        count = 0
        for path, raw in zip(paths, results):
            if not raw:
                continue
            data = json.loads(raw)
            if data["user"] != user:
                continue
            ttl = data["ttl"]
            new_data = json.dumps({"user": user, "acquired_at": now, "ttl": ttl})
            refresh_pipe.set(self._key(path), new_data, ex=ttl)
            count += 1
        if count:
            refresh_pipe.execute()
        return count
