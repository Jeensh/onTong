"""SQLAlchemy engine + session factory + base ORM class + bootstrap helpers.

`bootstrap_database()` 는 main.py 가 startup 시 호출. metadata.create_all() 로
신규 DB 자동 생성, 기존 DB 는 그대로.

세션 사용 패턴 :
    >>> with session_scope() as s:
    >>>     row = s.query(BusinessTermRow).filter_by(...).one_or_none()
    >>>     ...
    >>>     # commit / rollback 자동
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


_DEFAULT_DB_PATH = Path("data") / "ontology.db"


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속. metadata 는 Base.metadata 한 곳에 집중."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _resolve_db_path() -> Path:
    raw = os.getenv("ONTONG_DB_PATH")
    return Path(raw) if raw else _DEFAULT_DB_PATH


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        path = _resolve_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{path.resolve()}"
        _engine = create_engine(url, echo=False, future=True, connect_args={"check_same_thread": False})

        # SQLite 는 기본적으로 FK 를 enforce 하지 않음 → ON DELETE CASCADE 가 무시되어
        # delete_repo 의 bulk delete 시 자식 row (code_methods 등) 가 orphan 으로 남아
        # UNIQUE constraint 충돌 발생. connection 마다 PRAGMA 활성화.
        @event.listens_for(_engine, "connect")
        def _enable_sqlite_fk(dbapi_conn, _conn_rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        logger.info("SQLite engine bound: %s (FK enforcement ON)", url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """ORM 세션 + commit/rollback 자동. store 메서드 안에서만 사용."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def bootstrap_database() -> None:
    """startup 시 호출 — metadata.create_all().

    2026-05-02 변경: archive 된 persistence.models 대신, 각 layer 의 ORM 모듈
    (code_layer.orm / domain_layer.orm / mapping_layer.orm) 을 main.py 가 직접
    import 해서 Base.metadata 에 등록한다. 이 함수는 그 후 create_all 만 호출.
    """
    Base.metadata.create_all(bind=get_engine())
    logger.info("Database bootstrap complete: %s", _resolve_db_path())


def reset_engine_for_tests() -> None:
    """테스트 isolation — engine + session factory 리셋. ONTONG_DB_PATH 변경 후 호출."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


__all__ = [
    "Base",
    "bootstrap_database",
    "get_engine",
    "get_session_factory",
    "reset_engine_for_tests",
    "session_scope",
]
