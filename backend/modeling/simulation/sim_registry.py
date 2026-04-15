# backend/modeling/simulation/sim_registry.py
"""Registry of simulation parameters and calculation functions for demo entities."""
from __future__ import annotations

import math
from typing import Callable

from backend.modeling.simulation.sim_models import SimulationParam, SimulationOutput

CalcFn = Callable[[dict[str, str]], list[SimulationOutput]]


def _pct(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return round((after - before) / before * 100, 1)


def _calc_safety_stock(params: dict[str, str]) -> list[SimulationOutput]:
    z = float(params.get("safety_factor", "1.65"))
    lt = float(params.get("lead_time_days", "14"))
    demand_std_dev = 20.0
    avg_daily_demand = 50.0
    z_default, lt_default = 1.65, 14.0
    ss_before = z_default * demand_std_dev * math.sqrt(lt_default)
    ss_after = z * demand_std_dev * math.sqrt(lt)
    rop_before = avg_daily_demand * lt_default + ss_before
    rop_after = avg_daily_demand * lt + ss_after
    return [
        SimulationOutput(metric_name="safety_stock_level", label="안전재고 수준",
            before_value=str(round(ss_before)), after_value=str(round(ss_after)),
            change_pct=_pct(ss_before, ss_after), unit="개"),
        SimulationOutput(metric_name="reorder_point", label="재주문점",
            before_value=str(round(rop_before)), after_value=str(round(rop_after)),
            change_pct=_pct(rop_before, rop_after), unit="개"),
    ]


def _calc_inventory_manager(params: dict[str, str]) -> list[SimulationOutput]:
    rop = float(params.get("reorder_point", "200"))
    max_stock = float(params.get("max_stock_level", "1000"))
    min_order = float(params.get("min_order_qty", "50"))
    d_rop, d_max, d_min = 200.0, 1000.0, 50.0
    order_size_before = max(d_max - d_rop, d_min)
    order_size_after = max(max_stock - rop, min_order)
    holding_before = d_max * 0.5 * 0.02
    holding_after = max_stock * 0.5 * 0.02
    return [
        SimulationOutput(metric_name="order_quantity", label="발주 수량",
            before_value=str(round(order_size_before)), after_value=str(round(order_size_after)),
            change_pct=_pct(order_size_before, order_size_after), unit="개"),
        SimulationOutput(metric_name="daily_holding_cost", label="일 보관비용",
            before_value=str(round(holding_before, 1)), after_value=str(round(holding_after, 1)),
            change_pct=_pct(holding_before, holding_after), unit="만원"),
    ]


def _calc_order_service(params: dict[str, str]) -> list[SimulationOutput]:
    batch = float(params.get("order_batch_size", "100"))
    backorder = params.get("backorder_allowed", "true") == "true"
    d_batch = 100.0
    daily_orders = 500.0
    batches_before = math.ceil(daily_orders / d_batch)
    batches_after = math.ceil(daily_orders / batch)
    fill_rate = 0.95 if backorder else 0.88
    return [
        SimulationOutput(metric_name="daily_batches", label="일 배치 처리 횟수",
            before_value=str(round(daily_orders / d_batch)), after_value=str(batches_after),
            change_pct=_pct(batches_before, batches_after), unit="회"),
        SimulationOutput(metric_name="fill_rate", label="주문 충족률",
            before_value="95.0", after_value=str(round(fill_rate * 100, 1)),
            change_pct=_pct(95.0, fill_rate * 100), unit="%"),
    ]


def _calc_production_planner(params: dict[str, str]) -> list[SimulationOutput]:
    util = float(params.get("capacity_utilization", "0.85"))
    shifts = int(float(params.get("shift_count", "2")))
    horizon = float(params.get("planning_horizon_days", "30"))
    d_util, d_shifts = 0.85, 2
    capacity_per_shift = 500.0
    throughput_before = capacity_per_shift * d_shifts * d_util
    throughput_after = capacity_per_shift * shifts * util
    return [
        SimulationOutput(metric_name="daily_throughput", label="일 생산량",
            before_value=str(round(throughput_before)), after_value=str(round(throughput_after)),
            change_pct=_pct(throughput_before, throughput_after), unit="개"),
        SimulationOutput(metric_name="planning_horizon", label="계획 기간",
            before_value="30", after_value=str(round(horizon)),
            change_pct=_pct(30.0, horizon), unit="일"),
    ]


def _calc_work_order_processor(params: dict[str, str]) -> list[SimulationOutput]:
    threshold = int(float(params.get("priority_threshold", "3")))
    max_concurrent = int(float(params.get("max_concurrent_orders", "10")))
    d_threshold, d_max = 3, 10
    urgent_pct_before = (5 - d_threshold) / 5 * 100
    urgent_pct_after = (5 - threshold) / 5 * 100
    return [
        SimulationOutput(metric_name="urgent_order_pct", label="긴급 작업 비율",
            before_value=str(round(urgent_pct_before)), after_value=str(round(urgent_pct_after)),
            change_pct=_pct(urgent_pct_before, max(urgent_pct_after, 0.1)), unit="%"),
        SimulationOutput(metric_name="max_concurrent", label="동시 처리 한도",
            before_value=str(d_max), after_value=str(max_concurrent),
            change_pct=_pct(d_max, max_concurrent), unit="건"),
    ]


def _calc_purchase_order(params: dict[str, str]) -> list[SimulationOutput]:
    min_qty = float(params.get("min_purchase_qty", "100"))
    buffer = float(params.get("lead_time_buffer_days", "3"))
    d_qty, d_buffer = 100.0, 3.0
    annual_orders_before = 365 / (d_qty / 50)
    annual_orders_after = 365 / (min_qty / 50)
    effective_lt_before = 14 + d_buffer
    effective_lt_after = 14 + buffer
    return [
        SimulationOutput(metric_name="annual_orders", label="연간 발주 횟수",
            before_value=str(round(annual_orders_before)), after_value=str(round(annual_orders_after)),
            change_pct=_pct(annual_orders_before, annual_orders_after), unit="회"),
        SimulationOutput(metric_name="effective_lead_time", label="실 리드타임",
            before_value=str(round(effective_lt_before)), after_value=str(round(effective_lt_after)),
            change_pct=_pct(effective_lt_before, effective_lt_after), unit="일"),
    ]


def _calc_supplier_evaluator(params: dict[str, str]) -> list[SimulationOutput]:
    qw = float(params.get("quality_weight", "0.4"))
    cw = float(params.get("cost_weight", "0.35"))
    dw = float(params.get("delivery_weight", "0.25"))
    score_before = 85 * 0.4 + 70 * 0.35 + 90 * 0.25
    score_after = 85 * qw + 70 * cw + 90 * dw
    return [
        SimulationOutput(metric_name="supplier_score", label="공급업체 종합점수",
            before_value=str(round(score_before, 1)), after_value=str(round(score_after, 1)),
            change_pct=_pct(score_before, score_after), unit="점"),
    ]


def _calc_shipment_tracker(params: dict[str, str]) -> list[SimulationOutput]:
    interval = float(params.get("tracking_interval_hours", "4"))
    delay_threshold = float(params.get("delay_threshold_hours", "24"))
    d_interval = 4.0
    checks_per_day_before = 24 / d_interval
    checks_per_day_after = 24 / interval
    d_threshold = 24.0
    detected_before = 10 if d_threshold <= 24 else 5
    detected_after = 10 if delay_threshold <= 24 else 5
    return [
        SimulationOutput(metric_name="daily_checks", label="일 추적 횟수",
            before_value=str(round(checks_per_day_before)), after_value=str(round(checks_per_day_after)),
            change_pct=_pct(checks_per_day_before, checks_per_day_after), unit="회"),
        SimulationOutput(metric_name="delay_detection_rate", label="지연 감지율",
            before_value=str(detected_before), after_value=str(detected_after),
            change_pct=_pct(detected_before, max(detected_after, 0.1)), unit="%"),
    ]


def _calc_warehouse_controller(params: dict[str, str]) -> list[SimulationOutput]:
    batch = float(params.get("pick_batch_size", "20"))
    zone_cap = float(params.get("zone_capacity", "500"))
    d_batch, d_zone = 20.0, 500.0
    daily_picks = 200.0
    rounds_before = math.ceil(daily_picks / d_batch)
    rounds_after = math.ceil(daily_picks / batch)
    utilization_before = 400 / d_zone * 100
    utilization_after = 400 / zone_cap * 100
    return [
        SimulationOutput(metric_name="pick_rounds", label="일 피킹 라운드",
            before_value=str(rounds_before), after_value=str(rounds_after),
            change_pct=_pct(rounds_before, rounds_after), unit="회"),
        SimulationOutput(metric_name="zone_utilization", label="구역 활용률",
            before_value=str(round(utilization_before, 1)), after_value=str(round(utilization_after, 1)),
            change_pct=_pct(utilization_before, utilization_after), unit="%"),
    ]


# ── Registry ────────────────────────────────────────────────────────

_REGISTRY: dict[str, tuple[list[SimulationParam], CalcFn]] = {}


def _reg(entity_id: str, params: list[SimulationParam], calc: CalcFn) -> None:
    _REGISTRY[entity_id] = (params, calc)


def _p(entity_id: str, name: str, default: str, **kw) -> SimulationParam:
    return SimulationParam(entity_id=entity_id, param_name=name, default_value=default, **kw)


_SSC = "com.ontong.scm.inventory.SafetyStockCalculator"
_reg(_SSC, [
    _p(_SSC, "safety_factor", "1.65", param_type="float", min_value="0.5", max_value="5.0", step="0.05",
       description="서비스 수준 계수 (Z-score)", formula="safety_stock = z × σ × √(lead_time)"),
    _p(_SSC, "lead_time_days", "14", param_type="int", min_value="1", max_value="90", step="1",
       unit="일", description="공급 리드타임"),
    _p(_SSC, "service_level", "0.95", param_type="float", min_value="0.5", max_value="0.99", step="0.01",
       description="목표 서비스 수준"),
], _calc_safety_stock)

_IM = "com.ontong.scm.inventory.InventoryManager"
_reg(_IM, [
    _p(_IM, "reorder_point", "200", param_type="int", min_value="50", max_value="500", step="10",
       unit="개", description="재주문점"),
    _p(_IM, "max_stock_level", "1000", param_type="int", min_value="200", max_value="5000", step="50",
       unit="개", description="최대 재고 수준"),
    _p(_IM, "min_order_qty", "50", param_type="int", min_value="10", max_value="500", step="10",
       unit="개", description="최소 발주 수량"),
], _calc_inventory_manager)

_OS = "com.ontong.scm.order.OrderService"
_reg(_OS, [
    _p(_OS, "order_batch_size", "100", param_type="int", min_value="10", max_value="500", step="10",
       unit="건", description="주문 배치 크기"),
    _p(_OS, "backorder_allowed", "true", param_type="bool", description="역발주 허용 여부"),
], _calc_order_service)

_PP = "com.ontong.scm.production.ProductionPlanner"
_reg(_PP, [
    _p(_PP, "capacity_utilization", "0.85", param_type="float", min_value="0.3", max_value="1.0", step="0.05",
       description="설비 가동률"),
    _p(_PP, "shift_count", "2", param_type="int", min_value="1", max_value="3", step="1",
       unit="교대", description="교대 횟수"),
    _p(_PP, "planning_horizon_days", "30", param_type="int", min_value="7", max_value="90", step="1",
       unit="일", description="계획 기간"),
], _calc_production_planner)

_WO = "com.ontong.scm.production.WorkOrderProcessor"
_reg(_WO, [
    _p(_WO, "priority_threshold", "3", param_type="int", min_value="1", max_value="5", step="1",
       description="긴급 우선순위 임계값 (1=최고, 5=최저)"),
    _p(_WO, "max_concurrent_orders", "10", param_type="int", min_value="1", max_value="50", step="1",
       unit="건", description="동시 처리 가능 작업수"),
], _calc_work_order_processor)

_PO = "com.ontong.scm.procurement.PurchaseOrderService"
_reg(_PO, [
    _p(_PO, "min_purchase_qty", "100", param_type="int", min_value="10", max_value="1000", step="10",
       unit="개", description="최소 구매 수량"),
    _p(_PO, "lead_time_buffer_days", "3", param_type="int", min_value="0", max_value="14", step="1",
       unit="일", description="리드타임 버퍼"),
], _calc_purchase_order)

_SE = "com.ontong.scm.procurement.SupplierEvaluator"
_reg(_SE, [
    _p(_SE, "quality_weight", "0.4", param_type="float", min_value="0.0", max_value="1.0", step="0.05",
       description="품질 가중치"),
    _p(_SE, "cost_weight", "0.35", param_type="float", min_value="0.0", max_value="1.0", step="0.05",
       description="비용 가중치"),
    _p(_SE, "delivery_weight", "0.25", param_type="float", min_value="0.0", max_value="1.0", step="0.05",
       description="납기 가중치"),
], _calc_supplier_evaluator)

_ST = "com.ontong.scm.logistics.ShipmentTracker"
_reg(_ST, [
    _p(_ST, "tracking_interval_hours", "4", param_type="int", min_value="1", max_value="24", step="1",
       unit="시간", description="추적 간격"),
    _p(_ST, "delay_threshold_hours", "24", param_type="int", min_value="4", max_value="72", step="1",
       unit="시간", description="지연 알림 임계값"),
], _calc_shipment_tracker)

_WC = "com.ontong.scm.logistics.WarehouseController"
_reg(_WC, [
    _p(_WC, "pick_batch_size", "20", param_type="int", min_value="5", max_value="100", step="5",
       unit="건", description="피킹 배치 크기"),
    _p(_WC, "zone_capacity", "500", param_type="int", min_value="100", max_value="2000", step="50",
       unit="개", description="구역 수용량"),
], _calc_warehouse_controller)


class SimRegistry:
    @staticmethod
    def get_params(entity_id: str) -> list[SimulationParam]:
        entry = _REGISTRY.get(entity_id)
        return [p.model_copy() for p in entry[0]] if entry else []

    @staticmethod
    def calculate(entity_id: str, params: dict[str, str]) -> list[SimulationOutput]:
        entry = _REGISTRY.get(entity_id)
        if entry is None:
            return []
        return entry[1](params)

    @staticmethod
    def has_entity(entity_id: str) -> bool:
        return entity_id in _REGISTRY

    @staticmethod
    def all_entity_ids() -> list[str]:
        return list(_REGISTRY.keys())
