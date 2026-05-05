"""LockBackend protocol — moved from application/lock_service.py."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

DEFAULT_TTL = 300


@dataclass
class LockInfo:
    path: str
    user: str
    acquired_at: float = field(default_factory=time.time)
    ttl: int = DEFAULT_TTL

    @property
    def is_expired(self) -> bool:
        return time.time() - self.acquired_at > self.ttl

    @property
    def remaining(self) -> int:
        r = self.ttl - (time.time() - self.acquired_at)
        return max(0, int(r))

    def refresh(self) -> None:
        self.acquired_at = time.time()

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "user": self.user,
            "acquired_at": self.acquired_at,
            "ttl": self.ttl,
            "remaining": self.remaining,
            "is_expired": self.is_expired,
        }


class LockBackend(ABC):
    @abstractmethod
    def acquire(self, path: str, user: str, ttl: int) -> LockInfo | None: ...

    @abstractmethod
    def release(self, path: str, user: str) -> bool: ...

    @abstractmethod
    def status(self, path: str) -> LockInfo | None: ...

    @abstractmethod
    def refresh(self, path: str, user: str) -> bool: ...

    @abstractmethod
    def release_all_by_user(self, user: str) -> int: ...

    def batch_refresh(self, paths: list[str], user: str) -> int:
        count = 0
        for p in paths:
            if self.refresh(p, user):
                count += 1
        return count
