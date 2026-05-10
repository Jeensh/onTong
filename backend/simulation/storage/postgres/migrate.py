"""스키마 적용 / 리셋.

`schema.sql` 을 idempotent 하게 실행 (CREATE TABLE IF NOT EXISTS).
reset_schema 는 모든 테이블 TRUNCATE — 시드 재시작 시 사용.
"""

from __future__ import annotations

from pathlib import Path

from backend.simulation.storage.postgres.connection import get_connection

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# 시드 리셋 시 TRUNCATE 대상 (의존 순서 무관 — FK 미사용)
_TRUNCATE_TABLES = (
    "cast_spec",
    "hr_spec",
    "edging_spec",
    "edging_group",
    "plant_mapping",
    "hr_min_wgt",
    "hr_max_wgt",
    "productivity_std",
    "customer_std",
    "order_os",
)


def apply_schema() -> None:
    """schema.sql 실행. 모든 DDL idempotent 이므로 반복 호출 안전."""
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def reset_schema(*, drop_tables: bool = False) -> None:
    """모든 테이블 비우기. drop_tables=True 면 DROP 후 재생성 (스키마 변경 시).

    멱등 시드 재시작용 — fixtures.py seed 진입 직전에 호출.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            if drop_tables:
                for table in reversed(_TRUNCATE_TABLES):
                    cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            else:
                tables_csv = ", ".join(_TRUNCATE_TABLES)
                cur.execute(f"TRUNCATE TABLE {tables_csv} RESTART IDENTITY CASCADE")
        conn.commit()
    if drop_tables:
        apply_schema()
