"""Slab 3D 뷰어용 보존 라우터 (Day 13 정리 후).

ROADMAP §3-2의 SlabViewer3D / SlabParamController frontend 컴포넌트가 사용하는
``/api/simulation/slab/{calculate,constraints}`` 두 엔드포인트만 남긴다.
시나리오 A/B/C, Custom Agent Hub, /run, /orders, /ontology, /equipment, /tools는
모두 v1 잔재로 제거됨.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation/slab", tags=["slab-3d"])


@router.post("/calculate")
async def calculate_slab(params_data: dict) -> dict:
    """Slab Size 설계 파라미터로 SEQ 전체 계산. SlabViewer3D용 보존 엔드포인트."""
    from backend.shared.contracts.simulation import SlabSizeParams
    from backend.simulation.mock.scenarios.slab_size_simulator import (
        calculate_slab_design,
    )

    params = SlabSizeParams(**params_data)
    result = calculate_slab_design(params)
    return result.model_dump()


@router.get("/constraints")
async def get_slab_constraints() -> dict:
    """슬라이더 min/max 범위용 설비 제약. SlabParamController용 보존 엔드포인트."""
    from backend.simulation.mock.scenarios.slab_size_simulator import (
        get_equipment_constraints,
    )

    return get_equipment_constraints()
