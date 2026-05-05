"""Async session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from .engine import get_engine

_session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncSession:
    return get_session_factory()()
