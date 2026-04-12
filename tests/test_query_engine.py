import pytest
from unittest.mock import MagicMock

from backend.modeling.query.query_engine import QueryEngine
from backend.modeling.query.query_models import ImpactQuery
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus


class TestQueryEngine:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.engine = QueryEngine(self.neo4j)

    def _make_mapping_file(self) -> MappingFile:
        return MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.inventory.SafetyStockCalc",
                    domain="SCOR/Plan/InventoryPlanning",
                    status=MappingStatus.CONFIRMED, owner="kim"),
            Mapping(code="com.example.order.OrderService",
                    domain="SCOR/Deliver/OrderManagement",
                    status=MappingStatus.CONFIRMED, owner="lee"),
            Mapping(code="com.example.replenish.ReplenishJob",
                    domain="SCOR/Source/Procurement",
                    status=MappingStatus.CONFIRMED, owner="park"),
        ])

    def test_resolve_term_by_exact_match(self):
        mf = self._make_mapping_file()
        result = self.engine._resolve_term("SafetyStockCalc", mf)
        assert result == "com.example.inventory.SafetyStockCalc"

    def test_resolve_term_not_found(self):
        mf = self._make_mapping_file()
        result = self.engine._resolve_term("NonExistent", mf)
        assert result is None

    def test_resolve_term_by_domain_name(self):
        mf = self._make_mapping_file()
        # Should find via domain lookup when code doesn't match
        self.neo4j.query.return_value = []  # no code entity match
        result = self.engine._resolve_term("InventoryPlanning", mf)
        # Should resolve via domain id partial match
        assert result == "com.example.inventory.SafetyStockCalc"

    def test_analyze_returns_affected_processes(self):
        mf = self._make_mapping_file()
        # Mock BFS then domain name lookups
        self.neo4j.query.side_effect = [
            # 1st call: BFS dependents
            [
                {"qn": "com.example.order.OrderService", "depth": 1},
                {"qn": "com.example.replenish.ReplenishJob", "depth": 1},
            ],
            # 2nd call: domain name lookup for OrderService's domain
            [{"name": "Order Management"}],
            # 3rd call: domain name lookup for ReplenishJob's domain
            [{"name": "Procurement"}],
        ]
        query = ImpactQuery(term="SafetyStockCalc", repo_id="test-repo")
        result = self.engine.analyze(query, mf)
        assert result.resolved is True
        assert len(result.affected_processes) == 2
        domains = {p.domain_id for p in result.affected_processes}
        assert "SCOR/Deliver/OrderManagement" in domains
        assert "SCOR/Source/Procurement" in domains

    def test_analyze_unresolved_term(self):
        mf = self._make_mapping_file()
        query = ImpactQuery(term="DoesNotExist", repo_id="test-repo")
        result = self.engine.analyze(query, mf)
        assert result.resolved is False
        assert "매핑되지 않은" in result.message or "not found" in result.message.lower()

    def test_analyze_reports_unmapped_entities(self):
        mf = self._make_mapping_file()
        # Mock BFS then domain name lookup (only for OrderService; Logger is unmapped)
        self.neo4j.query.side_effect = [
            # 1st call: BFS dependents
            [
                {"qn": "com.example.order.OrderService", "depth": 1},
                {"qn": "com.example.util.Logger", "depth": 2},
            ],
            # 2nd call: domain name lookup for OrderService's domain
            [{"name": "Order Management"}],
        ]
        query = ImpactQuery(term="SafetyStockCalc", repo_id="test-repo")
        result = self.engine.analyze(query, mf)
        assert "com.example.util.Logger" in result.unmapped_entities
