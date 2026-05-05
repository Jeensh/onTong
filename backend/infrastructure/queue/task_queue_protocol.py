"""TaskQueue protocol — abstract over asyncio (dev) and Arq (team/enterprise)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class TaskQueue(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def enqueue(self, queue: str, fn: str, *args, audit_id: str = "", **kwargs) -> str: ...

    @abstractmethod
    async def progress(self, audit_id: str) -> dict: ...
