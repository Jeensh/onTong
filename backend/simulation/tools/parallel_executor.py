"""Parallel tool execution utilities for Slab design simulation.

asyncio.gather 기반 병렬 툴 실행.
주로 시나리오 B (Edging 변경 파급 효과)에서 다수 주문을 동시 분석할 때 사용한다.

SimulationToolExecutor의 parallel_tool_calls 지원과 함께,
단일 배치 툴로도 병렬 분석을 지원한다.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def parallel_simulate_width_impact(
    order_ids: list[str],
    new_edging_max: int,
) -> dict:
    """
    여러 주문의 Edging 변경 영향을 asyncio.gather로 병렬 분석.

    Args:
        order_ids: 분석할 주문 ID 목록
        new_edging_max: 새로운 Edging 최대 능력 (mm)

    Returns:
        {
            "new_edging_max": int,
            "total_orders": int,
            "orders_affected": int,
            "orders_safe": int,
            "impact_rate": str,
            "details": list[dict],
        }
    """
    from backend.simulation.tools.mock_simulator import simulate_width_impact

    async def _analyze_one(order_id: str) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, simulate_width_impact, order_id, new_edging_max)

    logger.info(
        f"병렬 파급 효과 분석 시작: {len(order_ids)}개 주문, "
        f"new_edging_max={new_edging_max}mm"
    )

    results: list[dict] = list(
        await asyncio.gather(*[_analyze_one(oid) for oid in order_ids])
    )

    affected = [r for r in results if not r.get("new_feasible") and r.get("original_feasible")]
    safe = [r for r in results if r.get("new_feasible")]
    total = len(results)

    logger.info(
        f"병렬 분석 완료: 전체 {total}건, 영향 {len(affected)}건, 안전 {len(safe)}건"
    )

    return {
        "new_edging_max": new_edging_max,
        "total_orders": total,
        "orders_affected": len(affected),
        "orders_safe": len(safe),
        "impact_rate": f"{len(affected) / total * 100:.1f}%" if total else "0%",
        "details": results,
    }


async def parallel_execute_tools(
    tasks: list[tuple[str, dict]],
    registry,
) -> list[tuple[str, Any]]:
    """
    여러 (tool_name, args) 쌍을 asyncio.gather로 병렬 실행.

    Args:
        tasks: [(tool_name, args), ...] 목록
        registry: SimulationToolRegistry 인스턴스

    Returns:
        [(tool_name, result), ...] — 입력 순서 유지
    """
    async def _exec(tool_name: str, args: dict) -> tuple[str, Any]:
        try:
            result = await registry.execute_async(tool_name, args)
            return tool_name, result
        except Exception as e:
            logger.error(f"Tool {tool_name} 병렬 실행 오류: {e}")
            return tool_name, {"error": str(e)}

    return list(await asyncio.gather(*[_exec(name, args) for name, args in tasks]))
