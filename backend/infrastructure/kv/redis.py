"""Redis KV store with namespace prefix."""
from __future__ import annotations

from .kv_protocol import KVStore


def _build_client(url: str):
    """Factory — monkey-patchable in tests."""
    import redis
    return redis.from_url(url, decode_responses=True)


class RedisKVStore(KVStore):
    def __init__(self, redis_url: str, namespace: str) -> None:
        self._r = _build_client(redis_url)
        self._ns = f"ontong:kv:{namespace}:"

    def _key(self, key: str) -> str:
        return f"{self._ns}{key}"

    def get(self, key: str) -> str | None:
        return self._r.get(self._key(key))

    def set(self, key: str, value: str) -> None:
        self._r.set(self._key(key), value)

    def delete(self, key: str) -> None:
        self._r.delete(self._key(key))

    def keys(self, prefix: str) -> list[str]:
        full_prefix = self._key(prefix)
        ns_len = len(self._ns)
        return [k[ns_len:] for k in self._r.scan_iter(match=f"{full_prefix}*")]

    def clear(self) -> None:
        for k in list(self._r.scan_iter(match=f"{self._ns}*")):
            self._r.delete(k)
