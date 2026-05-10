"""Java ↔ Python differential test API.

POST /api/simulation/differential/run
  body: {"order": {...}, "rules": {...}?}
  response: DifferentialResult.to_dict()

GET  /api/simulation/differential/status
  Java Bridge JAR 가용 여부 + 빌드 안내.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.simulation.jvm_bridge import (
    is_bridge_available,
    run_differential,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation/differential", tags=["simulation-differential"])


class DifferentialRequest(BaseModel):
    order: dict[str, Any] = Field(default_factory=dict, description="SDOrder 입력 dict")
    slab: dict[str, Any] = Field(default_factory=dict, description="SDSlab 초기 상태 (선택)")
    rules: dict[str, Any] = Field(default_factory=dict, description="룰 override (hr/hrf/anl1)")
    rel_tolerance: float = Field(1e-9, description="상대 허용오차 (BigDecimal 비교)")
    abs_tolerance: float = Field(1e-12, description="절대 허용오차")
    java_timeout_sec: float = Field(30.0, description="Java 호출 timeout")


@router.get("/status")
def status() -> dict[str, Any]:
    """Java Bridge 가용 여부 + 다음 액션 가이드."""
    avail = is_bridge_available()
    return {
        "java_bridge_available": avail,
        "guide": (
            "사용 가능 — POST /run 으로 Java/Python 동시 실행 가능"
            if avail
            else "Java Bridge 미빌드 — `cd backend/simulation/jvm_bridge/java_bridge "
                 "&& mvn package -DskipTests` 후 재시도. 그 전에 `sample-repos/slab-design "
                 "&& ./mvnw install -DskipTests` 로 slab-design jar 적재 필요."
        ),
    }


@router.post("/run")
def run(req: DifferentialRequest) -> dict[str, Any]:
    """같은 입력으로 Java SdDesigner / Python pipeline_full 양쪽 실행 + diff."""
    from decimal import Decimal

    inputs: dict[str, Any] = {
        "order": req.order,
        "slab": req.slab,
        "rules": req.rules,
    }
    try:
        result = run_differential(
            inputs,
            rel=Decimal(str(req.rel_tolerance)),
            abs_=Decimal(str(req.abs_tolerance)),
            java_timeout_sec=req.java_timeout_sec,
        )
    except Exception as exc:
        logger.exception("Differential 실행 실패")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", **result.to_dict()}
