# tests/test_term_resolver.py
import pytest
from backend.modeling.query.term_resolver import TermResolver, KOREAN_ALIASES
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus


def _make_mf() -> MappingFile:
    return MappingFile(repo_id="scm-demo", mappings=[
        Mapping(code="com.ontong.scm.inventory.SafetyStockCalculator",
                domain="SCOR/Plan/InventoryPlanning",
                status=MappingStatus.CONFIRMED, owner="system"),
        Mapping(code="com.ontong.scm.order.OrderService",
                domain="SCOR/Plan/DemandPlanning",
                status=MappingStatus.CONFIRMED, owner="system"),
        Mapping(code="com.ontong.scm.inventory.InventoryManager",
                domain="SCOR/Plan/InventoryPlanning",
                status=MappingStatus.CONFIRMED, owner="system"),
        Mapping(code="com.ontong.scm.production.ProductionPlanner",
                domain="SCOR/Make/Manufacturing",
                status=MappingStatus.CONFIRMED, owner="system"),
    ])


class TestTermResolver:
    def setup_method(self):
        self.resolver = TermResolver()
        self.mf = _make_mf()

    def test_exact_code_match(self):
        result = self.resolver.resolve_deterministic("SafetyStockCalculator", self.mf)
        assert result == "com.ontong.scm.inventory.SafetyStockCalculator"

    def test_full_qualified_match(self):
        result = self.resolver.resolve_deterministic(
            "com.ontong.scm.order.OrderService", self.mf
        )
        assert result == "com.ontong.scm.order.OrderService"

    def test_domain_match(self):
        result = self.resolver.resolve_deterministic("InventoryPlanning", self.mf)
        assert result == "com.ontong.scm.inventory.SafetyStockCalculator"

    def test_korean_alias_exact(self):
        result = self.resolver.resolve_deterministic("안전재고", self.mf)
        assert result == "com.ontong.scm.inventory.SafetyStockCalculator"

    def test_korean_alias_partial(self):
        result = self.resolver.resolve_deterministic("주문 서비스", self.mf)
        assert result == "com.ontong.scm.order.OrderService"

    def test_fuzzy_match_typo(self):
        result = self.resolver.resolve_deterministic("SaftyStockCalc", self.mf)
        assert result == "com.ontong.scm.inventory.SafetyStockCalculator"

    def test_no_match_returns_none(self):
        result = self.resolver.resolve_deterministic("CompletelyUnknown", self.mf)
        assert result is None

    def test_korean_alias_table_coverage(self):
        demo_classes = [
            "SafetyStockCalculator", "InventoryManager", "OrderService",
            "ProductionPlanner", "WorkOrderProcessor", "PurchaseOrderService",
            "SupplierEvaluator", "ShipmentTracker", "WarehouseController",
        ]
        targets = set(KOREAN_ALIASES.values())
        for cls in demo_classes:
            assert cls in targets, f"Missing Korean alias for {cls}"
