# backend/modeling/query/term_resolver.py
"""Term resolution chain: exact match → Korean alias → fuzzy match → LLM."""
from __future__ import annotations

import logging
from difflib import SequenceMatcher

from backend.modeling.mapping.mapping_models import MappingFile

logger = logging.getLogger(__name__)

KOREAN_ALIASES: dict[str, str] = {
    "안전재고": "SafetyStockCalculator",
    "안전 재고": "SafetyStockCalculator",
    "안전재고 계산": "SafetyStockCalculator",
    "서비스 수준": "SafetyStockCalculator",
    "재고 관리": "InventoryManager",
    "재고관리": "InventoryManager",
    "재주문점": "InventoryManager",
    "재고": "InventoryManager",
    "주문": "OrderService",
    "주문 서비스": "OrderService",
    "수주": "OrderService",
    "판매 주문": "OrderService",
    "생산 계획": "ProductionPlanner",
    "생산계획": "ProductionPlanner",
    "생산": "ProductionPlanner",
    "작업 지시": "WorkOrderProcessor",
    "작업지시": "WorkOrderProcessor",
    "공정 지시": "WorkOrderProcessor",
    "구매": "PurchaseOrderService",
    "구매 주문": "PurchaseOrderService",
    "발주": "PurchaseOrderService",
    "공급업체": "SupplierEvaluator",
    "공급업체 평가": "SupplierEvaluator",
    "협력사": "SupplierEvaluator",
    "배송": "ShipmentTracker",
    "배송 추적": "ShipmentTracker",
    "출하": "ShipmentTracker",
    "창고": "WarehouseController",
    "창고 관리": "WarehouseController",
    "물류 센터": "WarehouseController",
}

FUZZY_THRESHOLD = 0.55


class TermResolver:
    def resolve_deterministic(self, query: str, mf: MappingFile) -> str | None:
        # 1. Exact code entity match (suffix)
        for m in mf.mappings:
            if m.code == query or m.code.endswith(f".{query}"):
                return m.code
        # 2. Domain id match
        for m in mf.mappings:
            domain_suffix = m.domain.split("/")[-1]
            if query.lower() == domain_suffix.lower() or query.lower() in m.domain.lower():
                return m.code
        # 3. Korean alias table
        resolved_class = self._korean_alias_lookup(query)
        if resolved_class:
            for m in mf.mappings:
                if m.code.endswith(f".{resolved_class}"):
                    return m.code
        # 4. Fuzzy match on class names
        best_match = self._fuzzy_match(query, mf)
        if best_match:
            return best_match
        return None

    def _korean_alias_lookup(self, query: str) -> str | None:
        q = query.strip()
        if q in KOREAN_ALIASES:
            return KOREAN_ALIASES[q]
        for alias, cls in sorted(KOREAN_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in q:
                return cls
        return None

    def _fuzzy_match(self, query: str, mf: MappingFile) -> str | None:
        best_score = 0.0
        best_code: str | None = None
        for m in mf.mappings:
            simple_name = m.code.rsplit(".", 1)[-1]
            score = SequenceMatcher(None, query.lower(), simple_name.lower()).ratio()
            if score > best_score and score >= FUZZY_THRESHOLD:
                best_score = score
                best_code = m.code
        return best_code

    async def resolve_with_llm(self, query: str, mf: MappingFile) -> str | None:
        det = self.resolve_deterministic(query, mf)
        if det:
            return det
        try:
            return await self._llm_extract(query, mf)
        except Exception as e:
            logger.warning("LLM term extraction failed: %s", e)
            return None

    async def _llm_extract(self, query: str, mf: MappingFile) -> str | None:
        from pydantic import BaseModel as PydanticBaseModel
        from pydantic_ai import Agent
        from backend.application.agent.llm_factory import get_model

        class TermExtraction(PydanticBaseModel):
            extracted_term: str
            confidence: float

        entities_str = ", ".join(m.code.rsplit(".", 1)[-1] for m in mf.mappings)
        domains_str = ", ".join(set(m.domain for m in mf.mappings))

        system_prompt = (
            "You are a term extractor for an SCM code analysis tool. "
            "Given a natural language query (possibly in Korean), extract the single "
            "most relevant Java class name from the available entities.\n\n"
            f"Available code entities: {entities_str}\n"
            f"Available domain concepts: {domains_str}\n\n"
            "Return the simple class name (e.g. 'SafetyStockCalculator') and your confidence (0-1)."
        )

        agent: Agent[None, TermExtraction] = Agent(
            get_model(),
            output_type=TermExtraction,
            system_prompt=system_prompt,
        )
        result = await agent.run(query)
        extraction = result.output

        if extraction.confidence < 0.3:
            return None

        for m in mf.mappings:
            if m.code.endswith(f".{extraction.extracted_term}"):
                return m.code
        return None
