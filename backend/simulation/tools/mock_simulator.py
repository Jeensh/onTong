"""Parametric mock simulator tool functions for Slab design scenarios.

All three scenarios use these deterministic tool functions.
Tools are called by the Pydantic AI agents via @agent.tool_plain decorators.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_edging_table() -> list[dict]:
    with open(_DATA_DIR / "mock_edging_spec.json", encoding="utf-8") as f:
        return json.load(f)["edging_table"]


def _load_orders() -> list[dict]:
    with open(_DATA_DIR / "mock_orders.json", encoding="utf-8") as f:
        return json.load(f)["orders"]


def _load_equipment() -> dict:
    with open(_DATA_DIR / "mock_equipment_spec.json", encoding="utf-8") as f:
        return json.load(f)


# ── Scenario A: Width range calculation ──────────────────────────────


def simulate_width_range(
    target_width: int,
    rolling_line_id: str,
    edging_override: int | None = None,
) -> dict:
    """
    Calculate width range feasibility for given target width and rolling line.

    Args:
        target_width: Target product width in mm
        rolling_line_id: HR-A or HR-B
        edging_override: Override edging max capability for what-if analysis

    Returns:
        {"feasible": bool, "width_lower": int|None, "width_upper": int|None,
         "reason": str, "matched_spec": dict|None}
    """
    edging_table = _load_edging_table()
    matched = [
        e for e in edging_table
        if e["line_id"] == rolling_line_id
        and e["target_width_min"] <= target_width <= e["target_width_max"]
    ]

    if not matched:
        return {
            "feasible": False,
            "width_lower": None,
            "width_upper": None,
            "reason": (
                f"DG320: 목표폭 {target_width}mm가 {rolling_line_id} "
                f"Edging 기준 범위 어디에도 매칭되지 않음 "
                f"(설비 최대폭 초과)"
            ),
            "matched_spec": None,
        }

    spec = matched[0]
    edging_max = edging_override if edging_override is not None else spec["edging_ability_max"]
    edging_min = spec["edging_ability_min"]

    # 1차 폭 하한/상한 = 목표폭 ± Edging 능력 (10mm 단위 반올림)
    width_lower = ((target_width - edging_max) // 10) * 10
    width_upper = ((target_width + edging_max) // 10) * 10

    return {
        "feasible": True,
        "width_lower": max(width_lower, spec["target_width_min"]),
        "width_upper": min(width_upper, spec["target_width_max"] + edging_max),
        "reason": (
            f"정상 산정 완료. Edging능력 {edging_min}~{edging_max}mm 적용 "
            f"(RM Pass {spec['rm_pass_count']}회)"
        ),
        "matched_spec": spec,
    }


def get_order_info(order_id: str) -> dict | None:
    """Get order details from mock data."""
    orders = _load_orders()
    return next((o for o in orders if o["order_id"] == order_id), None)


def suggest_adjusted_width(order_id: str) -> dict:
    """
    Suggest a feasible target width for an order with DG320 error.
    Tries progressively lower widths until one matches Edging spec.
    """
    order = get_order_info(order_id)
    if not order:
        return {"error": f"주문 {order_id}를 찾을 수 없습니다."}

    original_width = order["target_width"]
    rolling = order["assigned_rolling"]
    edging_table = _load_edging_table()

    # Find max feasible width for this rolling line
    max_feasible = max(
        (e["target_width_max"] for e in edging_table if e["line_id"] == rolling),
        default=None,
    )
    if max_feasible is None:
        return {"error": f"열연라인 {rolling} Edging 기준을 찾을 수 없습니다."}

    # Verify the adjusted width works
    adjusted = simulate_width_range(max_feasible, rolling)
    return {
        "original_width": original_width,
        "suggested_width": max_feasible,
        "width_reduction": original_width - max_feasible,
        "simulation_result": adjusted,
        "recommendation": (
            f"목표폭을 {original_width}mm → {max_feasible}mm로 조정하면 "
            f"Edging 기준 매칭 가능합니다. ({original_width - max_feasible}mm 감소)"
        ),
    }


# ── Scenario B: Edging change ripple effect ───────────────────────────


def simulate_width_impact(order_id: str, new_edging_max: int) -> dict:
    """
    Evaluate impact of changing Edging max capability on a specific order.

    Args:
        order_id: Order to evaluate
        new_edging_max: New Edging max capability in mm

    Returns:
        Impact analysis with before/after comparison
    """
    orders = _load_orders()
    order = next((o for o in orders if o["order_id"] == order_id), None)
    if not order:
        return {"error": f"주문 {order_id}를 찾을 수 없습니다."}

    original = simulate_width_range(order["target_width"], order["assigned_rolling"])
    updated = simulate_width_range(
        order["target_width"], order["assigned_rolling"], edging_override=new_edging_max
    )

    status_change = "영향 없음"
    if original["feasible"] and not updated["feasible"]:
        status_change = "⚠️ 정상 → 설계불가 (Edging 능력 부족)"
    elif not original["feasible"] and updated["feasible"]:
        status_change = "✅ 에러 → 정상 (개선)"
    elif original["feasible"] and updated["feasible"]:
        orig_range = (original["width_upper"] or 0) - (original["width_lower"] or 0)
        new_range = (updated["width_upper"] or 0) - (updated["width_lower"] or 0)
        if new_range < orig_range:
            status_change = f"⚠️ 폭 범위 축소 ({orig_range}mm → {new_range}mm)"

    return {
        "order_id": order_id,
        "target_width": order["target_width"],
        "rolling_line": order["assigned_rolling"],
        "original_feasible": original["feasible"],
        "new_feasible": updated["feasible"],
        "original_range": (
            f"{original.get('width_lower')}~{original.get('width_upper')}mm"
            if original["feasible"] else "N/A"
        ),
        "new_range": (
            f"{updated.get('width_lower')}~{updated.get('width_upper')}mm"
            if updated["feasible"] else "N/A"
        ),
        "impact": status_change,
    }


def analyze_edging_change_ripple(rolling_line_id: str, new_edging_max: int) -> dict:
    """
    Full ripple effect analysis: all orders on rolling_line_id affected by edging change.
    """
    orders = _load_orders()
    affected_orders = [o for o in orders if o["assigned_rolling"] == rolling_line_id]

    impacts = []
    affected_count = 0
    for order in affected_orders:
        impact = simulate_width_impact(order["order_id"], new_edging_max)
        if "error" not in impact:
            impacts.append(impact)
            # Count as affected: either goes infeasible OR has range shrinkage
            if not impact["new_feasible"] and impact["original_feasible"]:
                affected_count += 1
            elif impact.get("impact") and "축소" in impact.get("impact", ""):
                affected_count += 1

    return {
        "rolling_line": rolling_line_id,
        "new_edging_max": new_edging_max,
        "total_orders_checked": len(affected_orders),
        "orders_affected": affected_count,
        "orders_unaffected": len(affected_orders) - affected_count,
        "impact_rate": f"{(affected_count / len(affected_orders) * 100):.1f}%" if affected_orders else "0%",
        "details": impacts,
    }


# ── Scenario C: Split count optimization ──────────────────────────────


def simulate_split_combinations(
    order_id: str,
    target_capacity: int | None = None,
    max_splits: int = 5,
) -> dict:
    """
    Calculate unit-weight satisfaction rates for split counts 1 to max_splits.
    Recommends the optimal split count.

    Args:
        order_id: Order to optimize
        target_capacity: Total slab capacity in kg (uses order data if None)
        max_splits: Maximum split count to evaluate

    Returns:
        All combinations + recommended split count
    """
    orders = _load_orders()
    order = next((o for o in orders if o["order_id"] == order_id), None)
    if not order:
        return {"error": f"주문 {order_id}를 찾을 수 없습니다."}

    weight_lower = order["order_weight_min"]
    weight_upper = order["order_weight_max"]
    yield_rate = order["yield_rate"]
    capacity = target_capacity or order.get("slab_weight", weight_upper)

    results = []
    for splits in range(1, max_splits + 1):
        # Each slab unit weight after yield loss
        slab_weight_upper = int(capacity / splits)
        slab_weight_lower = int(slab_weight_upper * 0.85)

        # Intersection with order weight range
        overlap_lower = max(weight_lower, slab_weight_lower)
        overlap_upper = min(weight_upper, slab_weight_upper)

        if overlap_upper > overlap_lower:
            satisfaction = round((overlap_upper - overlap_lower) / (weight_upper - weight_lower), 3)
        else:
            satisfaction = 0.0

        # Estimated actual weight considering yield
        actual_weight_upper = int(slab_weight_upper * yield_rate)

        results.append({
            "split_count": splits,
            "slab_weight_lower": slab_weight_lower,
            "slab_weight_upper": slab_weight_upper,
            "actual_weight_upper": actual_weight_upper,
            "satisfaction_rate": satisfaction,
            "meets_weight_range": overlap_upper > overlap_lower,
        })

    best = max(results, key=lambda x: x["satisfaction_rate"])
    current_satisfaction = order.get("satisfaction_rate", 0)
    improvement = round(best["satisfaction_rate"] - current_satisfaction, 3)

    return {
        "order_id": order_id,
        "current_split_count": order.get("split_count", "N/A"),
        "current_satisfaction_rate": current_satisfaction,
        "all_combinations": results,
        "recommended_split_count": best["split_count"],
        "recommended_satisfaction_rate": best["satisfaction_rate"],
        "improvement": f"+{improvement:.1%}" if improvement > 0 else f"{improvement:.1%}",
        "recommended_slab_range": f"{best['slab_weight_lower']}~{best['slab_weight_upper']}kg",
        "summary": (
            f"분할수 {best['split_count']}개가 최적입니다 "
            f"(단중 만족률 {best['satisfaction_rate']:.1%}, "
            f"현재 {current_satisfaction:.1%} 대비 {improvement:+.1%} 향상)"
        ),
    }
