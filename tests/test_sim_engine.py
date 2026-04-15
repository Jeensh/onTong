import pytest
from unittest.mock import MagicMock

from backend.modeling.simulation.sim_engine import SimulationEngine
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus


class TestSimulationEngine:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.engine = SimulationEngine(self.neo4j)

    def _make_mf(self) -> MappingFile:
        return MappingFile(repo_id="scm-demo", mappings=[
            Mapping(code="com.ontong.scm.inventory.SafetyStockCalculator",
                    domain="SCOR/Plan/InventoryPlanning",
                    status=MappingStatus.CONFIRMED, owner="system"),
            Mapping(code="com.ontong.scm.order.OrderService",
                    domain="SCOR/Plan/DemandPlanning",
                    status=MappingStatus.CONFIRMED, owner="system"),
        ])

    def test_simulate_known_entity(self):
        self.neo4j.query.side_effect = [
            # domain name lookup for source entity's domain
            [{"name": "Inventory Planning"}],
            # BFS: entities that depend on SafetyStockCalculator
            [{"qn": "com.ontong.scm.order.OrderService", "depth": 1}],
            # Domain name lookup for OrderService's domain
            [{"name": "Demand Planning"}],
        ]

        mf = self._make_mf()
        result = self.engine.simulate(
            entity_id="com.ontong.scm.inventory.SafetyStockCalculator",
            params={"safety_factor": "2.0", "lead_time_days": "14", "service_level": "0.95"},
            repo_id="scm-demo",
            mf=mf,
        )
        assert result.entity_name == "SafetyStockCalculator"
        assert len(result.outputs) >= 2
        assert any(o.metric_name == "safety_stock_level" for o in result.outputs)
        assert len(result.affected_processes) >= 1

    def test_simulate_unknown_entity_returns_empty(self):
        mf = self._make_mf()
        result = self.engine.simulate(
            entity_id="com.example.Unknown",
            params={},
            repo_id="scm-demo",
            mf=mf,
        )
        assert result.outputs == []
        assert "지원되지 않는" in result.message

    def test_simulate_uses_registry_defaults_for_missing_params(self):
        self.neo4j.query.return_value = []
        mf = self._make_mf()
        result = self.engine.simulate(
            entity_id="com.ontong.scm.inventory.SafetyStockCalculator",
            params={"safety_factor": "2.0"},
            repo_id="scm-demo",
            mf=mf,
        )
        assert result.params_after["safety_factor"] == "2.0"
        assert result.params_after["lead_time_days"] == "14"
