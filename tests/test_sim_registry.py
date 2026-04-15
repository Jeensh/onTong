# tests/test_sim_registry.py
import pytest
from backend.modeling.simulation.sim_registry import SimRegistry


class TestSimRegistry:
    def test_get_params_known_entity(self):
        params = SimRegistry.get_params("com.ontong.scm.inventory.SafetyStockCalculator")
        assert len(params) == 3
        names = {p.param_name for p in params}
        assert "safety_factor" in names
        assert "lead_time_days" in names
        assert "service_level" in names

    def test_get_params_unknown_entity(self):
        params = SimRegistry.get_params("com.example.Unknown")
        assert params == []

    def test_all_nine_entities_registered(self):
        expected = [
            "com.ontong.scm.inventory.SafetyStockCalculator",
            "com.ontong.scm.inventory.InventoryManager",
            "com.ontong.scm.order.OrderService",
            "com.ontong.scm.production.ProductionPlanner",
            "com.ontong.scm.production.WorkOrderProcessor",
            "com.ontong.scm.procurement.PurchaseOrderService",
            "com.ontong.scm.procurement.SupplierEvaluator",
            "com.ontong.scm.logistics.ShipmentTracker",
            "com.ontong.scm.logistics.WarehouseController",
        ]
        for eid in expected:
            params = SimRegistry.get_params(eid)
            assert len(params) > 0, f"No params for {eid}"

    def test_calculate_safety_stock(self):
        outputs = SimRegistry.calculate(
            "com.ontong.scm.inventory.SafetyStockCalculator",
            {"safety_factor": "2.0", "lead_time_days": "14", "service_level": "0.95"},
        )
        assert len(outputs) >= 2
        ss_out = next(o for o in outputs if o.metric_name == "safety_stock_level")
        assert float(ss_out.after_value) > float(ss_out.before_value)
        assert ss_out.change_pct > 0

    def test_calculate_unknown_entity_returns_empty(self):
        outputs = SimRegistry.calculate("com.example.Unknown", {})
        assert outputs == []

    def test_calculate_with_default_params(self):
        outputs = SimRegistry.calculate(
            "com.ontong.scm.inventory.SafetyStockCalculator",
            {"safety_factor": "1.65", "lead_time_days": "14", "service_level": "0.95"},
        )
        ss_out = next(o for o in outputs if o.metric_name == "safety_stock_level")
        assert abs(ss_out.change_pct) < 0.01
