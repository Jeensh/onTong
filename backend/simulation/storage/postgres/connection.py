"""Section 3 PostgreSQL 연결.

DATABASE_URL (또는 SIM_DB_*) 환경변수가 설정되면 활성화.
psycopg 3.x sync 모드 + ConnectionPool 사용.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Iterator, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    _PSYCOPG_AVAILABLE = True
except ImportError:  # pragma: no cover — psycopg 미설치 환경
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore
    ConnectionPool = None  # type: ignore
    _PSYCOPG_AVAILABLE = False


@dataclass(frozen=True)
class PgSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}"
        )


def pg_settings() -> Optional[PgSettings]:
    """env 에서 PG 연결 정보 조립. SIMULATION_DATABASE_URL 우선, 없으면 SIM_DB_* 조합.

    SIMULATION_DATABASE_URL 미설정 시 None 반환 → in-memory 모드.
    """
    url = os.getenv("SIMULATION_DATABASE_URL")
    if url:
        # postgres://user:pass@host:port/db 파싱
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return PgSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5434,
            database=(parsed.path or "/simulation").lstrip("/"),
            user=parsed.username or "simulation",
            password=parsed.password or "",
        )
    if os.getenv("SIM_DB_HOST"):
        return PgSettings(
            host=os.environ["SIM_DB_HOST"],
            port=int(os.getenv("SIM_DB_PORT", "5434")),
            database=os.getenv("SIM_DB_NAME", "simulation"),
            user=os.getenv("SIM_DB_USER", "simulation"),
            password=os.getenv("SIM_DB_PASSWORD", "simulation_dev"),
        )
    return None


def is_pg_enabled() -> bool:
    """PG 모드 활성 여부 (driver 설치 + env 모두 충족)."""
    return _PSYCOPG_AVAILABLE and pg_settings() is not None


_pool: Optional["ConnectionPool"] = None
_pool_lock = Lock()


def close_pool() -> None:
    """전역 pool close — short-lived 자식 프로세스(sandbox runner 등) 종료 직전에 호출.
    호출 안 하면 psycopg_pool background worker thread 가 5초 join hang → 호출자 timeout.
    """
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
            _pool = None


def get_pool() -> "ConnectionPool":
    """전역 ConnectionPool. 최초 호출 시 lazy 초기화."""
    if not _PSYCOPG_AVAILABLE:
        raise RuntimeError("psycopg 가 미설치 — `poetry install` 또는 `pip install 'psycopg[binary]'`")
    settings = pg_settings()
    if settings is None:
        raise RuntimeError(
            "PG 연결 정보 없음 — SIMULATION_DATABASE_URL 또는 SIM_DB_HOST 등 환경변수 설정 필요"
        )

    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ConnectionPool(
                conninfo=settings.dsn,
                min_size=1,
                max_size=4,
                timeout=10.0,
                kwargs={"row_factory": dict_row, "autocommit": False},
            )
            _pool.wait()
    return _pool


@contextmanager
def get_connection() -> Iterator["psycopg.Connection"]:
    """Connection context manager. 트랜잭션은 호출자 책임 (with conn.transaction())."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def close_pool() -> None:
    """uvicorn shutdown 훅 등에서 호출. 다음 get_pool() 호출 시 재초기화."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
