"""SimulationToolRegistry — Slab 설계 툴의 자기 기술(self-describing) 레지스트리.

각 툴이 name/description/input_schema/python_fn/domain_tags를 보유하며,
SimulationToolExecutor가 레지스트리에서 Anthropic tool 스키마와 실행 함수를 동적으로 조회한다.

사용법:
    registry = get_registry()
    tool_schemas = registry.get_anthropic_schemas(["get_order_info", "simulate_width_range"])
    result = registry.execute("get_order_info", {"order_id": "ORD-2024-0042"})
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class SimulationTool:
    name: str
    description: str
    input_schema: dict
    python_fn: Callable
    domain_tags: list[str] = field(default_factory=list)
    requires_approval: bool = False

    def to_anthropic_schema(self) -> dict:
        """Anthropic tool_use API 형식으로 반환."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class SimulationToolRegistry:
    """Slab 설계 툴을 중앙 등록·조회하는 레지스트리."""

    def __init__(self) -> None:
        self._tools: dict[str, SimulationTool] = {}

    def register(self, tool: SimulationTool) -> None:
        self._tools[tool.name] = tool
        logger.debug(f"Tool registered: {tool.name}")

    def get(self, name: str) -> SimulationTool | None:
        return self._tools.get(name)

    def get_anthropic_schemas(self, names: list[str] | None = None) -> list[dict]:
        """주어진 이름 목록의 Anthropic 스키마를 반환. None이면 전체 반환."""
        if names is None:
            tools = list(self._tools.values())
        else:
            tools = [self._tools[n] for n in names if n in self._tools]
        return [t.to_anthropic_schema() for t in tools]

    def execute(self, name: str, args: dict) -> Any:
        """툴을 동기적으로 실행. 비동기 툴은 asyncio.run() 으로 감싼다."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        result = tool.python_fn(**args)
        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)
        return result

    async def execute_async(self, name: str, args: dict) -> Any:
        """툴을 비동기적으로 실행."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        result = tool.python_fn(**args)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def list_tools(self) -> list[dict]:
        """API 노출용 툴 목록 (name, description, domain_tags)."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "domain_tags": t.domain_tags,
                "requires_approval": t.requires_approval,
            }
            for t in self._tools.values()
        ]

    def all_tool_names(self) -> list[str]:
        return list(self._tools.keys())


# ── 설비 spec 래퍼 ────────────────────────────────────────────────────────────

def _get_equipment_spec() -> dict:
    with open(_DATA_DIR / "mock_equipment_spec.json", encoding="utf-8") as f:
        return json.load(f)


def _calc_slab_design_wrapper(params: dict) -> dict:
    from backend.shared.contracts.simulation import SlabSizeParams
    from backend.simulation.mock.scenarios.slab_size_simulator import calculate_slab_design
    slab_params = SlabSizeParams(**params)
    return calculate_slab_design(slab_params).model_dump()


# ── 온톨로지 래퍼 ─────────────────────────────────────────────────────────────

def _find_orders_by_rolling_line(rolling_line_id: str) -> dict:
    from backend.simulation.tools.ontology_graph import build_mock_graph, find_orders_by_rolling_line
    G = build_mock_graph()
    orders, traversal, highlighted_edges = find_orders_by_rolling_line(G, rolling_line_id)
    return {
        "rolling_line": rolling_line_id,
        "orders": orders,
        "traversal": traversal,
        "highlighted_edges": [{"from": e[0], "to": e[1]} for e in highlighted_edges],
        "order_count": len(orders),
        "order_ids": [o.get("id", o.get("order_id", "")) for o in orders],
    }


def _find_edging_specs_for_order(order_id: str) -> dict:
    from backend.simulation.tools.ontology_graph import build_mock_graph, find_edging_specs_for_order
    G = build_mock_graph()
    edging_specs, traversal, highlighted_edges = find_edging_specs_for_order(G, order_id)
    return {
        "order_id": order_id,
        "edging_specs": edging_specs,
        "traversal": traversal,
        "highlighted_edges": [{"from": e[0], "to": e[1]} for e in highlighted_edges],
        "node_count": len(traversal),
    }


# ── 병렬 배치 툴 ──────────────────────────────────────────────────────────────

async def _batch_simulate_width_impact(order_ids: list[str], new_edging_max: int) -> dict:
    from backend.simulation.tools.mock_simulator import simulate_width_impact

    async def _single(oid: str) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, simulate_width_impact, oid, new_edging_max)

    results = await asyncio.gather(*[_single(oid) for oid in order_ids])
    impacts = list(results)

    affected = [i for i in impacts if not i.get("new_feasible") and i.get("original_feasible")]
    safe = [i for i in impacts if i.get("new_feasible")]
    total = len(impacts)

    return {
        "new_edging_max": new_edging_max,
        "total_orders": total,
        "orders_affected": len(affected),
        "orders_safe": len(safe),
        "impact_rate": f"{len(affected) / total * 100:.1f}%" if total else "0%",
        "details": impacts,
    }


def _batch_simulate_width_impact_sync(order_ids: list[str], new_edging_max: int) -> dict:
    """동기 래퍼 — executor에서 asyncio.gather를 실행."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 실행 중인 이벤트 루프가 있으면 concurrent.futures로 처리
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    _batch_simulate_width_impact(order_ids, new_edging_max)
                )
                return future.result()
        else:
            return loop.run_until_complete(_batch_simulate_width_impact(order_ids, new_edging_max))
    except RuntimeError:
        return asyncio.run(_batch_simulate_width_impact(order_ids, new_edging_max))


# ── 레지스트리 초기화 ─────────────────────────────────────────────────────────

_registry: SimulationToolRegistry | None = None


def get_registry() -> SimulationToolRegistry:
    """싱글턴 레지스트리 반환. 최초 호출 시 모든 툴을 등록."""
    global _registry
    if _registry is not None:
        return _registry

    from backend.simulation.tools.mock_simulator import (
        get_order_info,
        simulate_width_range,
        suggest_adjusted_width,
        simulate_width_impact,
        analyze_edging_change_ripple,
        simulate_split_combinations,
    )
    from backend.simulation.tools.tool_definitions import (
        GET_ORDER_INFO,
        SIMULATE_WIDTH_RANGE,
        SUGGEST_ADJUSTED_WIDTH,
        SIMULATE_WIDTH_IMPACT,
        BATCH_SIMULATE_WIDTH_IMPACT,
        ANALYZE_EDGING_CHANGE_RIPPLE,
        SIMULATE_SPLIT_COMBINATIONS,
        GET_EQUIPMENT_SPEC,
        FIND_ORDERS_BY_ROLLING_LINE,
        FIND_EDGING_SPECS_FOR_ORDER,
    )

    registry = SimulationToolRegistry()

    registry.register(SimulationTool(
        name="get_order_info",
        description=GET_ORDER_INFO["description"],
        input_schema=GET_ORDER_INFO["input_schema"],
        python_fn=get_order_info,
        domain_tags=["order", "slab", "width"],
    ))

    registry.register(SimulationTool(
        name="simulate_width_range",
        description=SIMULATE_WIDTH_RANGE["description"],
        input_schema=SIMULATE_WIDTH_RANGE["input_schema"],
        python_fn=simulate_width_range,
        domain_tags=["width", "edging", "feasibility"],
    ))

    registry.register(SimulationTool(
        name="suggest_adjusted_width",
        description=SUGGEST_ADJUSTED_WIDTH["description"],
        input_schema=SUGGEST_ADJUSTED_WIDTH["input_schema"],
        python_fn=suggest_adjusted_width,
        domain_tags=["width", "adjustment", "DG320"],
    ))

    registry.register(SimulationTool(
        name="simulate_width_impact",
        description=SIMULATE_WIDTH_IMPACT["description"],
        input_schema=SIMULATE_WIDTH_IMPACT["input_schema"],
        python_fn=simulate_width_impact,
        domain_tags=["edging", "ripple", "what-if"],
    ))

    registry.register(SimulationTool(
        name="batch_simulate_width_impact",
        description=BATCH_SIMULATE_WIDTH_IMPACT["description"],
        input_schema=BATCH_SIMULATE_WIDTH_IMPACT["input_schema"],
        python_fn=_batch_simulate_width_impact_sync,
        domain_tags=["edging", "ripple", "batch", "parallel"],
    ))

    registry.register(SimulationTool(
        name="analyze_edging_change_ripple",
        description=ANALYZE_EDGING_CHANGE_RIPPLE["description"],
        input_schema=ANALYZE_EDGING_CHANGE_RIPPLE["input_schema"],
        python_fn=analyze_edging_change_ripple,
        domain_tags=["edging", "ripple", "rolling-line"],
    ))

    registry.register(SimulationTool(
        name="simulate_split_combinations",
        description=SIMULATE_SPLIT_COMBINATIONS["description"],
        input_schema=SIMULATE_SPLIT_COMBINATIONS["input_schema"],
        python_fn=simulate_split_combinations,
        domain_tags=["split", "weight", "optimization"],
    ))

    registry.register(SimulationTool(
        name="get_equipment_spec",
        description=GET_EQUIPMENT_SPEC["description"],
        input_schema=GET_EQUIPMENT_SPEC["input_schema"],
        python_fn=_get_equipment_spec,
        domain_tags=["equipment", "spec", "caster", "rolling"],
    ))

    registry.register(SimulationTool(
        name="find_orders_by_rolling_line",
        description=FIND_ORDERS_BY_ROLLING_LINE["description"],
        input_schema=FIND_ORDERS_BY_ROLLING_LINE["input_schema"],
        python_fn=_find_orders_by_rolling_line,
        domain_tags=["ontology", "rolling-line", "order"],
    ))

    registry.register(SimulationTool(
        name="find_edging_specs_for_order",
        description=FIND_EDGING_SPECS_FOR_ORDER["description"],
        input_schema=FIND_EDGING_SPECS_FOR_ORDER["input_schema"],
        python_fn=_find_edging_specs_for_order,
        domain_tags=["ontology", "edging", "order"],
    ))

    _registry = registry
    logger.info(f"SimulationToolRegistry initialized with {len(registry.all_tool_names())} tools")
    return _registry
