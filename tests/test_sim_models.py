import pytest
from backend.modeling.simulation.sim_models import (
    SimulationParam,
    SimulationOutput,
    ParametricSimResult,
    AffectedProcessRef,
)


class TestSimulationParam:
    def test_minimal_param(self):
        p = SimulationParam(
            entity_id="com.ontong.scm.inventory.SafetyStockCalculator",
            param_name="safety_factor",
            param_type="float",
            default_value="1.65",
        )
        assert p.current_value == "1.65"
        assert p.min_value is None

    def test_full_param(self):
        p = SimulationParam(
            entity_id="com.ontong.scm.inventory.SafetyStockCalculator",
            param_name="safety_factor",
            param_type="float",
            default_value="1.65",
            min_value="0.5",
            max_value="5.0",
            step="0.05",
            unit="",
            description="서비스 수준 계수 (Z-score)",
            formula="safety_stock = z * σ * √(lead_time)",
        )
        assert p.step == "0.05"
        assert p.formula is not None


class TestSimulationOutput:
    def test_output_with_change(self):
        o = SimulationOutput(
            metric_name="safety_stock_level",
            label="안전재고 수준",
            before_value="124",
            after_value="150",
            change_pct=21.0,
            unit="개",
        )
        assert o.change_pct == 21.0

    def test_output_no_change(self):
        o = SimulationOutput(
            metric_name="lead_time",
            label="리드타임",
            before_value="14",
            after_value="14",
            change_pct=0.0,
            unit="일",
        )
        assert o.change_pct == 0.0


class TestParametricSimResult:
    def test_full_result(self):
        r = ParametricSimResult(
            entity_id="com.ontong.scm.inventory.SafetyStockCalculator",
            entity_name="SafetyStockCalculator",
            params_before={"safety_factor": "1.65"},
            params_after={"safety_factor": "2.0"},
            outputs=[
                SimulationOutput(
                    metric_name="safety_stock_level",
                    label="안전재고 수준",
                    before_value="124",
                    after_value="150",
                    change_pct=21.0,
                    unit="개",
                )
            ],
            affected_processes=[
                AffectedProcessRef(
                    domain_id="SCOR/Plan/InventoryPlanning",
                    domain_name="Inventory Planning",
                    distance=0,
                )
            ],
            message="safety_factor 변경 시 1개 지표, 1개 프로세스 영향",
        )
        assert len(r.outputs) == 1
        assert len(r.affected_processes) == 1
