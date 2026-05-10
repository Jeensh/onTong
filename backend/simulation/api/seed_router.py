"""DB 시드 / 상태 엔드포인트.

- POST `/api/simulation/seed` — fixtures default 데이터 + 샘플 주문 5건 PG 적재
- GET `/api/simulation/seed/status` — 각 테이블 행 수
- GET `/api/simulation/orders` — order_os 전체 (사용자 픽업용)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.simulation.storage.postgres.connection import get_connection, is_pg_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation", tags=["simulation-seed"])


_TABLES = (
    "plant_mapping", "cast_spec", "hr_spec",
    "edging_spec", "edging_group",
    "hr_min_wgt", "hr_max_wgt",
    "productivity_std", "customer_std",
    "order_os",
)


def _ensure_pg() -> None:
    if not is_pg_enabled():
        raise HTTPException(
            status_code=503,
            detail="PG 미활성 — SIMULATION_DATABASE_URL 또는 SIM_DB_HOST 환경변수 + psycopg 설치 필요.",
        )


@router.post("/seed")
def seed_db(reset: bool = True) -> dict[str, Any]:
    """DB 시드 초기화. reset=True (기본) → TRUNCATE 후 INSERT.

    UI 의 "DB 시드 초기화" 버튼이 호출.
    """
    _ensure_pg()
    from backend.simulation.storage.postgres.seed import seed_all

    try:
        counts = seed_all(reset=reset)
    except Exception as exc:
        logger.exception("Seed 실패")
        raise HTTPException(status_code=500, detail=f"Seed 실패: {exc}") from exc
    return {"status": "ok", "reset": reset, "counts": counts}


@router.get("/seed/status")
def seed_status() -> dict[str, Any]:
    """각 테이블 행 수 — 시드 완료 여부 확인."""
    _ensure_pg()
    counts: dict[str, int] = {}
    with get_connection() as conn, conn.cursor() as cur:
        for table in _TABLES:
            cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
            row = cur.fetchone()
            counts[table] = int(row["n"]) if row else 0
    return {"status": "ok", "counts": counts}


@router.get("/orders")
def list_orders() -> dict[str, Any]:
    """order_os 전체. 검증 시 사용자가 picker 로 활용."""
    _ensure_pg()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT cmp_cd, org_cd, order_no, stock_code,
                      order_width, order_length, order_wgt_low, order_wgt_high,
                      pkg_wgt_low, pkg_wgt_high, grade_cd, customer_cd
               FROM order_os
               ORDER BY order_no"""
        )
        rows = cur.fetchall()
    return {"status": "ok", "orders": [dict(r) for r in rows], "count": len(rows)}
