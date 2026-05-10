"""Section 3 PostgreSQL 마스터 데이터 저장소.

slab-design 자바 JPA Entity 그대로 미러링한 10 테이블 (9 마스터 + 주문 1).
in-memory `repository.py` 와 dual-mode 로 동작 — DATABASE_URL 환경변수가
설정되면 SQL backed Repo 로 전환, 미설정이면 기존 in-memory dict 룩업 유지.
"""

from backend.simulation.storage.postgres.connection import (
    get_connection,
    get_pool,
    is_pg_enabled,
    pg_settings,
)
from backend.simulation.storage.postgres.migrate import apply_schema, reset_schema

__all__ = [
    "apply_schema",
    "get_connection",
    "get_pool",
    "is_pg_enabled",
    "pg_settings",
    "reset_schema",
]
