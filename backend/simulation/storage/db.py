"""Phase 6-B — SQLite 영구 저장소 (시나리오 / 실행 이력 / 양방향 lineage).

설계 원칙:
- stdlib `sqlite3` 만 사용 (외부 의존성 없음)
- 모듈 레벨 default connection (test 격리는 path 주입으로 처리)
- 스키마 자동 마이그레이션 (`init_schema` idempotent)

스키마:
- scenarios: 시나리오 라이브러리 (이름, step_id, inputs YAML, tags, source)
- runs: 실행 이력 (scenario_id?, inputs/outputs JSON, stage, baseline flag, parent)
- lineage: 양방향 관계 (supersedes / baseline_of / regression_of)
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_LOCK = threading.RLock()
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "storage.db"


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scenarios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    step_id TEXT NOT NULL,
    inputs_yaml TEXT NOT NULL,
    tags TEXT,
    source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    scenario_id TEXT,
    step_id TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    outputs_json TEXT,
    stage TEXT,
    error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    elapsed_ms INTEGER,
    is_baseline INTEGER DEFAULT 0,
    parent_run_id TEXT,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id),
    FOREIGN KEY (parent_run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS lineage (
    from_run_id TEXT NOT NULL,
    to_run_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (from_run_id, to_run_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_runs_scenario ON runs(scenario_id);
CREATE INDEX IF NOT EXISTS idx_runs_step ON runs(step_id);
CREATE INDEX IF NOT EXISTS idx_runs_baseline ON runs(is_baseline);
CREATE INDEX IF NOT EXISTS idx_scenarios_step ON scenarios(step_id);
"""


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def init_schema(db_path: str | Path | None = None) -> Path:
    """DB 파일 + 테이블 idempotent 생성. 경로 반환."""
    path = Path(db_path) if db_path else _DEFAULT_DB_PATH
    _ensure_parent(path)
    with _LOCK:
        conn = sqlite3.connect(path, isolation_level=None)
        try:
            conn.executescript(_SCHEMA_SQL)
        finally:
            conn.close()
    return path


@contextmanager
def connect(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """SQLite connection context. Row → dict 자동 변환."""
    path = Path(db_path) if db_path else _DEFAULT_DB_PATH
    _ensure_parent(path)
    with _LOCK:
        conn = sqlite3.connect(path, isolation_level="IMMEDIATE")
        conn.row_factory = sqlite3.Row
        try:
            # 첫 호출 시 스키마 자동 init
            conn.executescript(_SCHEMA_SQL)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def reset_for_test(db_path: str | Path) -> None:
    """테스트 격리용: 파일 삭제 후 빈 스키마 재생성."""
    path = Path(db_path)
    if path.exists():
        path.unlink()
    init_schema(path)


def default_db_path() -> Path:
    return Path(os.environ.get("SIMULATION_DB_PATH") or _DEFAULT_DB_PATH)
