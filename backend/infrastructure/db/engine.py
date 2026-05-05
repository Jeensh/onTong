"""SQLAlchemy async engine — singleton."""
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is not None:
        return _engine
    from backend.core.config import settings
    if not settings.postgres_dsn:
        raise RuntimeError("settings.postgres_dsn is empty; team/enterprise profile requires it")
    _engine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True, pool_size=10)
    logger.info("Postgres async engine initialized")
    return _engine


async def dispose() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
