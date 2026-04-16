"""Section 3 Slab Agent API — SSE streaming endpoints for 3 business scenarios.

Endpoints:
    POST /api/simulation/slab/run              → Run agent (SSE stream)
    GET  /api/simulation/slab/orders           → List mock orders
    GET  /api/simulation/slab/ontology         → Get ontology graph for visualization
    POST /api/simulation/slab/calculate        → Slab size design calculation
    GET  /api/simulation/slab/constraints      → Equipment constraint ranges
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation/slab", tags=["slab-agent"])


class SlabAgentRequest(BaseModel):
    scenario: str    # "A" | "B" | "C"
    message: str


@router.post("/run")
async def run_slab_agent(req: SlabAgentRequest):
    """Run a Slab scenario agent and stream SSE events back."""

    async def event_stream():
        try:
            if req.scenario == "A":
                from backend.simulation.agent.scenario_a_agent import run_scenario_a
                gen = run_scenario_a(req.message)
            elif req.scenario == "B":
                from backend.simulation.agent.scenario_b_agent import run_scenario_b
                gen = run_scenario_b(req.message)
            elif req.scenario == "C":
                from backend.simulation.agent.scenario_c_agent import run_scenario_c
                gen = run_scenario_c(req.message)
            else:
                yield f"event: error\ndata: {json.dumps({'message': f'Unknown scenario: {req.scenario}'})}\n\n"
                return

            async for evt in gen:
                event_type = evt.get("event", "message")
                data = json.dumps(evt.get("data", {}), ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data}\n\n"

        except Exception as e:
            logger.exception(f"Slab agent error (scenario={req.scenario}): {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/orders")
async def get_orders():
    """Return mock orders list."""
    import json
    from pathlib import Path

    data_dir = Path(__file__).parent.parent / "data"
    with open(data_dir / "mock_orders.json", encoding="utf-8") as f:
        return json.load(f)["orders"]


@router.get("/ontology")
async def get_ontology():
    """Return ontology graph for frontend visualization."""
    from backend.simulation.tools.ontology_graph import get_graph_data
    return get_graph_data()


@router.get("/equipment")
async def get_equipment():
    """Return equipment spec data."""
    import json
    from pathlib import Path

    data_dir = Path(__file__).parent.parent / "data"
    with open(data_dir / "mock_equipment_spec.json", encoding="utf-8") as f:
        return json.load(f)


@router.post("/calculate")
async def calculate_slab(params_data: dict):
    """Slab Size 설계 파라미터로 SEQ 전체 계산을 수행하고 결과를 반환한다."""
    from backend.shared.contracts.simulation import SlabSizeParams
    from backend.simulation.mock.scenarios.slab_size_simulator import calculate_slab_design

    params = SlabSizeParams(**params_data)
    result = calculate_slab_design(params)
    return result.model_dump()


@router.get("/constraints")
async def get_slab_constraints():
    """슬라이더 min/max 범위 설정용 설비 제약 기준을 반환한다."""
    from backend.simulation.mock.scenarios.slab_size_simulator import get_equipment_constraints
    return get_equipment_constraints()


@router.get("/tools")
async def get_available_tools():
    """등록된 시뮬레이션 툴 목록을 반환한다. 커스텀 에이전트 빌더 UI에서 사용."""
    from backend.simulation.tools.tool_registry import get_registry
    registry = get_registry()
    return {"tools": registry.list_tools()}
