# Section 2 Modeling Engine — Phase 1a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an "Analysis Console" and "Simulation Panel" that lets an operator type "안전재고 계산 로직 변경" and see impact analysis + parameter simulation results in under 30 seconds, with zero manual setup beyond clicking "SCM 데모 로드".

**Architecture:** The engine wraps existing QueryEngine (BFS impact analysis) with a new term resolution layer (Korean alias table + fuzzy match + LLM extraction) and adds a parametric simulation engine with pre-defined Python calc functions per demo entity. Frontend restructures the sidebar to make "분석 콘솔" the default entry point, with a new "시뮬레이션" tab for parameter tweaking.

**Tech Stack:** Python 3.11+ / FastAPI / Pydantic / pydantic_ai / Neo4j (existing) / Next.js 15 / React 19 / Tailwind CSS v4 / lucide-react

**Design Spec:** `~/.gstack/projects/Jeensh-onTong/donghae-main-design-20260415-213837.md`

---

## File Structure

### New Files (Backend)
| File | Responsibility |
|------|---------------|
| `backend/modeling/simulation/sim_models.py` | Pydantic models: SimulationParam, SimulationOutput, ParametricSimResult |
| `backend/modeling/simulation/sim_registry.py` | Demo data registry: 9 SCM entities with params + calc functions |
| `backend/modeling/simulation/sim_engine.py` | SimulationEngine: run params through calc function, trace impact |
| `backend/modeling/query/term_resolver.py` | TermResolver: Korean alias → fuzzy match → LLM extraction |
| `backend/modeling/api/engine_api.py` | Engine API: /engine/query, /engine/simulate, /engine/status |

### Modified Files (Backend)
| File | Change |
|------|--------|
| `backend/modeling/api/modeling.py` | Include engine_api router, pass dependencies |
| `backend/modeling/api/seed_api.py` | Register simulation params during seed |

### New Files (Frontend)
| File | Responsibility |
|------|---------------|
| `frontend/src/components/sections/modeling/AnalysisConsole.tsx` | Natural language query → impact results + sim link |
| `frontend/src/components/sections/modeling/SimulationPanel.tsx` | Parameter sliders → before/after results |

### Modified Files (Frontend)
| File | Change |
|------|--------|
| `frontend/src/lib/api/modeling.ts` | Add engine API types + fetch functions |
| `frontend/src/components/sections/ModelingSection.tsx` | Restructure sidebar, default to analysis console |

### Test Files
| File | What it tests |
|------|--------------|
| `tests/test_sim_models.py` | Model validation |
| `tests/test_term_resolver.py` | Korean alias, fuzzy match, resolution chain |
| `tests/test_sim_engine.py` | Calculation functions, impact tracing |
| `tests/test_engine_api.py` | Engine API endpoints (FastAPI TestClient) |

---

### Task 1: Simulation Data Models

**Files:**
- Create: `backend/modeling/simulation/sim_models.py`
- Test: `tests/test_sim_models.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_sim_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_sim_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.modeling.simulation.sim_models'`

- [ ] **Step 3: Implement the models**

```python
# backend/modeling/simulation/sim_models.py
"""Pydantic models for parametric simulation."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SimulationParam(BaseModel):
    """A tunable parameter on a code entity."""
    entity_id: str
    param_name: str
    param_type: str = "float"  # float | int | bool
    default_value: str
    current_value: str = ""    # filled from default if empty
    min_value: str | None = None
    max_value: str | None = None
    step: str | None = None
    unit: str = ""
    description: str = ""
    formula: str | None = None  # display-only

    def model_post_init(self, __context) -> None:
        if not self.current_value:
            self.current_value = self.default_value


class SimulationOutput(BaseModel):
    """One computed metric from a simulation run."""
    metric_name: str
    label: str
    before_value: str
    after_value: str
    change_pct: float
    unit: str = ""


class AffectedProcessRef(BaseModel):
    """Lightweight reference to an affected domain process."""
    domain_id: str
    domain_name: str
    distance: int


class ParametricSimResult(BaseModel):
    """Result of running a parametric simulation."""
    entity_id: str
    entity_name: str
    params_before: dict[str, str]
    params_after: dict[str, str]
    outputs: list[SimulationOutput]
    affected_processes: list[AffectedProcessRef]
    message: str
```

- [ ] **Step 4: Update `__init__.py`**

```python
# backend/modeling/simulation/__init__.py
"""Simulation engine — parametric models for code entity what-if analysis."""
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_sim_models.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/simulation/sim_models.py backend/modeling/simulation/__init__.py tests/test_sim_models.py
git commit -m "feat(modeling): add parametric simulation data models"
```

---

### Task 2: Korean Alias Table + Term Resolver

**Files:**
- Create: `backend/modeling/query/term_resolver.py`
- Test: `tests/test_term_resolver.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_term_resolver.py
import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.modeling.query.term_resolver import TermResolver
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
        """Each demo entity has at least one Korean alias."""
        from backend.modeling.query.term_resolver import KOREAN_ALIASES
        demo_classes = [
            "SafetyStockCalculator", "InventoryManager", "OrderService",
            "ProductionPlanner", "WorkOrderProcessor", "PurchaseOrderService",
            "SupplierEvaluator", "ShipmentTracker", "WarehouseController",
        ]
        targets = set(KOREAN_ALIASES.values())
        for cls in demo_classes:
            assert cls in targets, f"Missing Korean alias for {cls}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_term_resolver.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement TermResolver**

```python
# backend/modeling/query/term_resolver.py
"""Term resolution chain: exact match → Korean alias → fuzzy match → LLM."""
from __future__ import annotations

import logging
from difflib import SequenceMatcher

from backend.modeling.mapping.mapping_models import MappingFile

logger = logging.getLogger(__name__)

# Korean alias table — maps Korean terms to simple class names
KOREAN_ALIASES: dict[str, str] = {
    # SafetyStockCalculator
    "안전재고": "SafetyStockCalculator",
    "안전 재고": "SafetyStockCalculator",
    "안전재고 계산": "SafetyStockCalculator",
    "서비스 수준": "SafetyStockCalculator",
    # InventoryManager
    "재고 관리": "InventoryManager",
    "재고관리": "InventoryManager",
    "재주문점": "InventoryManager",
    "재고": "InventoryManager",
    # OrderService
    "주문": "OrderService",
    "주문 서비스": "OrderService",
    "수주": "OrderService",
    "판매 주문": "OrderService",
    # ProductionPlanner
    "생산 계획": "ProductionPlanner",
    "생산계획": "ProductionPlanner",
    "생산": "ProductionPlanner",
    # WorkOrderProcessor
    "작업 지시": "WorkOrderProcessor",
    "작업지시": "WorkOrderProcessor",
    "공정 지시": "WorkOrderProcessor",
    # PurchaseOrderService
    "구매": "PurchaseOrderService",
    "구매 주문": "PurchaseOrderService",
    "발주": "PurchaseOrderService",
    # SupplierEvaluator
    "공급업체": "SupplierEvaluator",
    "공급업체 평가": "SupplierEvaluator",
    "협력사": "SupplierEvaluator",
    # ShipmentTracker
    "배송": "ShipmentTracker",
    "배송 추적": "ShipmentTracker",
    "출하": "ShipmentTracker",
    # WarehouseController
    "창고": "WarehouseController",
    "창고 관리": "WarehouseController",
    "물류 센터": "WarehouseController",
}

FUZZY_THRESHOLD = 0.55


class TermResolver:
    """Resolve a user query to a code entity qualified name."""

    def resolve_deterministic(
        self, query: str, mf: MappingFile
    ) -> str | None:
        """Try deterministic resolution: exact → domain → alias → fuzzy."""
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
        """Look up Korean alias. Tries exact match, then substring containment."""
        q = query.strip()
        # Exact alias match
        if q in KOREAN_ALIASES:
            return KOREAN_ALIASES[q]
        # Check if any alias key is contained in the query
        for alias, cls in sorted(KOREAN_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in q:
                return cls
        return None

    def _fuzzy_match(self, query: str, mf: MappingFile) -> str | None:
        """Fuzzy match against mapped class simple names."""
        best_score = 0.0
        best_code: str | None = None
        for m in mf.mappings:
            simple_name = m.code.rsplit(".", 1)[-1]
            score = SequenceMatcher(None, query.lower(), simple_name.lower()).ratio()
            if score > best_score and score >= FUZZY_THRESHOLD:
                best_score = score
                best_code = m.code
        return best_code

    async def resolve_with_llm(
        self, query: str, mf: MappingFile
    ) -> str | None:
        """LLM-assisted term extraction as final fallback."""
        # Try deterministic first
        det = self.resolve_deterministic(query, mf)
        if det:
            return det

        # LLM extraction
        try:
            return await self._llm_extract(query, mf)
        except Exception as e:
            logger.warning("LLM term extraction failed: %s", e)
            return None

    async def _llm_extract(self, query: str, mf: MappingFile) -> str | None:
        """Use LLM to extract the most relevant code entity from a natural language query."""
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

        # Map extracted simple name back to qualified name
        for m in mf.mappings:
            if m.code.endswith(f".{extraction.extracted_term}"):
                return m.code

        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_term_resolver.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/query/term_resolver.py tests/test_term_resolver.py
git commit -m "feat(modeling): add term resolver with Korean alias and fuzzy match"
```

---

### Task 3: Simulation Registry (Demo Data + Calc Functions)

**Files:**
- Create: `backend/modeling/simulation/sim_registry.py`
- Test: `tests/test_sim_registry.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_sim_registry.py
import pytest
from backend.modeling.simulation.sim_registry import SimRegistry
from backend.modeling.simulation.sim_models import SimulationOutput


class TestSimRegistry:
    def test_get_params_known_entity(self):
        params = SimRegistry.get_params(
            "com.ontong.scm.inventory.SafetyStockCalculator"
        )
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
        """Calc with defaults should produce 0% change."""
        outputs = SimRegistry.calculate(
            "com.ontong.scm.inventory.SafetyStockCalculator",
            {"safety_factor": "1.65", "lead_time_days": "14", "service_level": "0.95"},
        )
        ss_out = next(o for o in outputs if o.metric_name == "safety_stock_level")
        assert abs(ss_out.change_pct) < 0.01
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_sim_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the registry**

```python
# backend/modeling/simulation/sim_registry.py
"""Registry of simulation parameters and calculation functions for demo entities."""
from __future__ import annotations

import math
from typing import Callable

from backend.modeling.simulation.sim_models import SimulationParam, SimulationOutput

# Type alias for calc functions
CalcFn = Callable[[dict[str, str]], list[SimulationOutput]]


def _pct(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return round((after - before) / before * 100, 1)


# ── Calculation functions ───────────────────────────────────────────


def _calc_safety_stock(params: dict[str, str]) -> list[SimulationOutput]:
    z = float(params.get("safety_factor", "1.65"))
    lt = float(params.get("lead_time_days", "14"))
    # Fixed demo constants
    demand_std_dev = 20.0
    avg_daily_demand = 50.0

    z_default, lt_default = 1.65, 14.0
    ss_before = z_default * demand_std_dev * math.sqrt(lt_default)
    ss_after = z * demand_std_dev * math.sqrt(lt)
    rop_before = avg_daily_demand * lt_default + ss_before
    rop_after = avg_daily_demand * lt + ss_after

    return [
        SimulationOutput(
            metric_name="safety_stock_level",
            label="안전재고 수준",
            before_value=str(round(ss_before)),
            after_value=str(round(ss_after)),
            change_pct=_pct(ss_before, ss_after),
            unit="개",
        ),
        SimulationOutput(
            metric_name="reorder_point",
            label="재주문점",
            before_value=str(round(rop_before)),
            after_value=str(round(rop_after)),
            change_pct=_pct(rop_before, rop_after),
            unit="개",
        ),
    ]


def _calc_inventory_manager(params: dict[str, str]) -> list[SimulationOutput]:
    rop = float(params.get("reorder_point", "200"))
    max_stock = float(params.get("max_stock_level", "1000"))
    min_order = float(params.get("min_order_qty", "50"))
    d_rop, d_max, d_min = 200.0, 1000.0, 50.0
    order_size_before = max(d_max - d_rop, d_min)
    order_size_after = max(max_stock - rop, min_order)
    holding_before = d_max * 0.5 * 0.02  # avg stock * daily holding cost
    holding_after = max_stock * 0.5 * 0.02

    return [
        SimulationOutput(
            metric_name="order_quantity", label="발주 수량",
            before_value=str(round(order_size_before)),
            after_value=str(round(order_size_after)),
            change_pct=_pct(order_size_before, order_size_after), unit="개",
        ),
        SimulationOutput(
            metric_name="daily_holding_cost", label="일 보관비용",
            before_value=str(round(holding_before, 1)),
            after_value=str(round(holding_after, 1)),
            change_pct=_pct(holding_before, holding_after), unit="만원",
        ),
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
        SimulationOutput(
            metric_name="daily_batches", label="일 배치 처리 횟수",
            before_value=str(round(daily_orders / d_batch)),
            after_value=str(batches_after),
            change_pct=_pct(batches_before, batches_after), unit="회",
        ),
        SimulationOutput(
            metric_name="fill_rate", label="주문 충족률",
            before_value="95.0",
            after_value=str(round(fill_rate * 100, 1)),
            change_pct=_pct(95.0, fill_rate * 100), unit="%",
        ),
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
        SimulationOutput(
            metric_name="daily_throughput", label="일 생산량",
            before_value=str(round(throughput_before)),
            after_value=str(round(throughput_after)),
            change_pct=_pct(throughput_before, throughput_after), unit="개",
        ),
        SimulationOutput(
            metric_name="planning_horizon", label="계획 기간",
            before_value="30", after_value=str(round(horizon)),
            change_pct=_pct(30.0, horizon), unit="일",
        ),
    ]


def _calc_work_order_processor(params: dict[str, str]) -> list[SimulationOutput]:
    threshold = int(float(params.get("priority_threshold", "3")))
    max_concurrent = int(float(params.get("max_concurrent_orders", "10")))
    d_threshold, d_max = 3, 10
    urgent_pct_before = (5 - d_threshold) / 5 * 100
    urgent_pct_after = (5 - threshold) / 5 * 100

    return [
        SimulationOutput(
            metric_name="urgent_order_pct", label="긴급 작업 비율",
            before_value=str(round(urgent_pct_before)),
            after_value=str(round(urgent_pct_after)),
            change_pct=_pct(urgent_pct_before, max(urgent_pct_after, 0.1)), unit="%",
        ),
        SimulationOutput(
            metric_name="max_concurrent", label="동시 처리 한도",
            before_value=str(d_max), after_value=str(max_concurrent),
            change_pct=_pct(d_max, max_concurrent), unit="건",
        ),
    ]


def _calc_purchase_order(params: dict[str, str]) -> list[SimulationOutput]:
    min_qty = float(params.get("min_purchase_qty", "100"))
    buffer = float(params.get("lead_time_buffer_days", "3"))
    d_qty, d_buffer = 100.0, 3.0
    annual_orders_before = 365 / (d_qty / 50)  # assuming 50 units/day consumption
    annual_orders_after = 365 / (min_qty / 50)
    effective_lt_before = 14 + d_buffer
    effective_lt_after = 14 + buffer

    return [
        SimulationOutput(
            metric_name="annual_orders", label="연간 발주 횟수",
            before_value=str(round(annual_orders_before)),
            after_value=str(round(annual_orders_after)),
            change_pct=_pct(annual_orders_before, annual_orders_after), unit="회",
        ),
        SimulationOutput(
            metric_name="effective_lead_time", label="실 리드타임",
            before_value=str(round(effective_lt_before)),
            after_value=str(round(effective_lt_after)),
            change_pct=_pct(effective_lt_before, effective_lt_after), unit="일",
        ),
    ]


def _calc_supplier_evaluator(params: dict[str, str]) -> list[SimulationOutput]:
    qw = float(params.get("quality_weight", "0.4"))
    cw = float(params.get("cost_weight", "0.35"))
    dw = float(params.get("delivery_weight", "0.25"))
    # Demo supplier scores: quality=85, cost=70, delivery=90
    score_before = 85 * 0.4 + 70 * 0.35 + 90 * 0.25
    score_after = 85 * qw + 70 * cw + 90 * dw

    return [
        SimulationOutput(
            metric_name="supplier_score", label="공급업체 종합점수",
            before_value=str(round(score_before, 1)),
            after_value=str(round(score_after, 1)),
            change_pct=_pct(score_before, score_after), unit="점",
        ),
    ]


def _calc_shipment_tracker(params: dict[str, str]) -> list[SimulationOutput]:
    interval = float(params.get("tracking_interval_hours", "4"))
    delay_threshold = float(params.get("delay_threshold_hours", "24"))
    d_interval, d_threshold = 4.0, 24.0
    checks_per_day_before = 24 / d_interval
    checks_per_day_after = 24 / interval
    # Assume 10% of shipments have minor delays (8-30 hours)
    detected_before = 10 if d_threshold <= 24 else 5
    detected_after = 10 if delay_threshold <= 24 else 5

    return [
        SimulationOutput(
            metric_name="daily_checks", label="일 추적 횟수",
            before_value=str(round(checks_per_day_before)),
            after_value=str(round(checks_per_day_after)),
            change_pct=_pct(checks_per_day_before, checks_per_day_after), unit="회",
        ),
        SimulationOutput(
            metric_name="delay_detection_rate", label="지연 감지율",
            before_value=str(detected_before),
            after_value=str(detected_after),
            change_pct=_pct(detected_before, max(detected_after, 0.1)), unit="%",
        ),
    ]


def _calc_warehouse_controller(params: dict[str, str]) -> list[SimulationOutput]:
    batch = float(params.get("pick_batch_size", "20"))
    zone_cap = float(params.get("zone_capacity", "500"))
    d_batch, d_zone = 20.0, 500.0
    daily_picks = 200.0
    rounds_before = math.ceil(daily_picks / d_batch)
    rounds_after = math.ceil(daily_picks / batch)
    utilization_before = 400 / d_zone * 100  # assume 400 items stored
    utilization_after = 400 / zone_cap * 100

    return [
        SimulationOutput(
            metric_name="pick_rounds", label="일 피킹 라운드",
            before_value=str(rounds_before),
            after_value=str(rounds_after),
            change_pct=_pct(rounds_before, rounds_after), unit="회",
        ),
        SimulationOutput(
            metric_name="zone_utilization", label="구역 활용률",
            before_value=str(round(utilization_before, 1)),
            after_value=str(round(utilization_after, 1)),
            change_pct=_pct(utilization_before, utilization_after), unit="%",
        ),
    ]


# ── Registry ────────────────────────────────────────────────────────


_REGISTRY: dict[str, tuple[list[SimulationParam], CalcFn]] = {}


def _reg(entity_id: str, params: list[SimulationParam], calc: CalcFn) -> None:
    _REGISTRY[entity_id] = (params, calc)


def _p(entity_id: str, name: str, default: str, **kw) -> SimulationParam:
    return SimulationParam(entity_id=entity_id, param_name=name, default_value=default, **kw)


# Register all 9 demo entities
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
    """Static access to registered simulation entities."""

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_sim_registry.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/simulation/sim_registry.py tests/test_sim_registry.py
git commit -m "feat(modeling): add simulation registry with 9 SCM demo entities"
```

---

### Task 4: Simulation Engine

**Files:**
- Create: `backend/modeling/simulation/sim_engine.py`
- Test: `tests/test_sim_engine.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_sim_engine.py
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
        # Mock BFS dependents
        self.neo4j.query.side_effect = [
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
        self.neo4j.query.return_value = []  # no dependents
        mf = self._make_mf()
        result = self.engine.simulate(
            entity_id="com.ontong.scm.inventory.SafetyStockCalculator",
            params={"safety_factor": "2.0"},  # only one param provided
            repo_id="scm-demo",
            mf=mf,
        )
        assert result.params_after["safety_factor"] == "2.0"
        assert result.params_after["lead_time_days"] == "14"  # default filled
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_sim_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement SimulationEngine**

```python
# backend/modeling/simulation/sim_engine.py
"""Simulation engine: run parametric simulations and trace domain impact."""
from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.mapping.mapping_models import MappingFile
from backend.modeling.mapping.mapping_service import MappingService
from backend.modeling.simulation.sim_models import (
    AffectedProcessRef,
    ParametricSimResult,
)
from backend.modeling.simulation.sim_registry import SimRegistry

logger = logging.getLogger(__name__)


class SimulationEngine:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j
        self._mapping_svc = MappingService(neo4j)

    def simulate(
        self,
        entity_id: str,
        params: dict[str, str],
        repo_id: str,
        mf: MappingFile,
    ) -> ParametricSimResult:
        simple_name = entity_id.rsplit(".", 1)[-1] if "." in entity_id else entity_id

        if not SimRegistry.has_entity(entity_id):
            return ParametricSimResult(
                entity_id=entity_id,
                entity_name=simple_name,
                params_before={},
                params_after={},
                outputs=[],
                affected_processes=[],
                message=f"'{simple_name}'은(는) 지원되지 않는 시뮬레이션 대상입니다.",
            )

        # Fill missing params with defaults
        registered_params = SimRegistry.get_params(entity_id)
        defaults = {p.param_name: p.default_value for p in registered_params}
        full_params = {**defaults, **params}

        # Run calculation
        outputs = SimRegistry.calculate(entity_id, full_params)

        # Trace affected domain processes via BFS
        affected = self._trace_affected_processes(entity_id, repo_id, mf)

        change_count = sum(1 for o in outputs if abs(o.change_pct) > 0.01)
        message = (
            f"{simple_name}: {change_count}개 지표 변경, "
            f"{len(affected)}개 프로세스 영향"
        )

        return ParametricSimResult(
            entity_id=entity_id,
            entity_name=simple_name,
            params_before=defaults,
            params_after=full_params,
            outputs=outputs,
            affected_processes=affected,
            message=message,
        )

    def _trace_affected_processes(
        self, entity_id: str, repo_id: str, mf: MappingFile
    ) -> list[AffectedProcessRef]:
        # 1. Get direct domain mapping for this entity
        source_domain = self._mapping_svc.resolve(mf, entity_id)
        affected: list[AffectedProcessRef] = []

        if source_domain:
            domain_info = self._neo4j.query(
                "MATCH (n:DomainNode {id: $id}) RETURN n.name as name",
                {"id": source_domain},
            )
            domain_name = domain_info[0]["name"] if domain_info else source_domain
            affected.append(AffectedProcessRef(
                domain_id=source_domain, domain_name=domain_name, distance=0,
            ))

        # 2. BFS for dependents (same logic as QueryEngine)
        cypher = """
        MATCH (source:CodeEntity {qualified_name: $qn, repo_id: $repo_id})
        MATCH path = (other:CodeEntity)-[:CALLS|EXTENDS|IMPLEMENTS|DEPENDS_ON*1..3]->(source)
        WHERE other.repo_id = $repo_id
        RETURN DISTINCT other.qualified_name as qn, length(path) as depth
        ORDER BY depth
        """
        dependents = self._neo4j.query(cypher, {"qn": entity_id, "repo_id": repo_id})

        seen_domains: set[str] = {source_domain} if source_domain else set()
        for dep in dependents:
            domain = self._mapping_svc.resolve(mf, dep["qn"])
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                domain_info = self._neo4j.query(
                    "MATCH (n:DomainNode {id: $id}) RETURN n.name as name",
                    {"id": domain},
                )
                domain_name = domain_info[0]["name"] if domain_info else domain
                affected.append(AffectedProcessRef(
                    domain_id=domain, domain_name=domain_name, distance=dep["depth"],
                ))

        return affected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_sim_engine.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/simulation/sim_engine.py tests/test_sim_engine.py
git commit -m "feat(modeling): add simulation engine with BFS impact tracing"
```

---

### Task 5: Engine API Router

**Files:**
- Create: `backend/modeling/api/engine_api.py`
- Modify: `backend/modeling/api/modeling.py`
- Test: `tests/test_engine_api.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_engine_api.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import engine_api


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(engine_api.router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_deps():
    """Set up engine_api module-level dependencies."""
    neo4j = MagicMock()
    neo4j.query.return_value = []

    from backend.modeling.query.query_engine import QueryEngine
    from backend.modeling.mapping.mapping_service import MappingService
    from backend.modeling.simulation.sim_engine import SimulationEngine
    from backend.modeling.query.term_resolver import TermResolver

    engine_api._query_engine = QueryEngine(neo4j)
    engine_api._mapping_svc = MappingService(neo4j)
    engine_api._sim_engine = SimulationEngine(neo4j)
    engine_api._term_resolver = TermResolver()
    engine_api._git = MagicMock()

    # Mock git to return a mapping YAML path
    from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus
    mf = MappingFile(repo_id="scm-demo", mappings=[
        Mapping(code="com.ontong.scm.inventory.SafetyStockCalculator",
                domain="SCOR/Plan/InventoryPlanning",
                status=MappingStatus.CONFIRMED, owner="system"),
    ])
    engine_api._load_mapping_file = MagicMock(return_value=mf)

    yield neo4j


class TestEngineQueryEndpoint:
    def test_query_resolves_term(self, client, mock_deps):
        mock_deps.query.side_effect = [
            [],  # BFS: no dependents
        ]
        resp = client.post("/api/modeling/engine/query", json={
            "query": "SafetyStockCalculator",
            "repo_id": "scm-demo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert "SafetyStockCalculator" in data["source_code_entity"]

    def test_query_unresolved(self, client, mock_deps):
        resp = client.post("/api/modeling/engine/query", json={
            "query": "CompletelyUnknownThing",
            "repo_id": "scm-demo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is False


class TestEngineSimulateEndpoint:
    def test_simulate_known_entity(self, client, mock_deps):
        mock_deps.query.return_value = []  # no dependents
        resp = client.post("/api/modeling/engine/simulate", json={
            "entity_id": "com.ontong.scm.inventory.SafetyStockCalculator",
            "repo_id": "scm-demo",
            "params": {"safety_factor": "2.0"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_name"] == "SafetyStockCalculator"
        assert len(data["outputs"]) >= 2

    def test_simulate_unknown_entity(self, client, mock_deps):
        resp = client.post("/api/modeling/engine/simulate", json={
            "entity_id": "com.example.Unknown",
            "repo_id": "scm-demo",
            "params": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "지원되지 않는" in data["message"]


class TestEngineStatusEndpoint:
    def test_status_returns_counts(self, client, mock_deps):
        resp = client.get("/api/modeling/engine/status?repo_id=scm-demo")
        assert resp.status_code == 200
        data = resp.json()
        assert "mapping_count" in data
        assert "simulatable_entities" in data


class TestEngineParamsEndpoint:
    def test_get_params_for_entity(self, client, mock_deps):
        resp = client.get(
            "/api/modeling/engine/params/com.ontong.scm.inventory.SafetyStockCalculator"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["params"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_engine_api.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Engine API**

```python
# backend/modeling/api/engine_api.py
"""Engine API — unified entry for analysis console and simulation."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.modeling.query.query_models import ImpactQuery, ImpactResult
from backend.modeling.simulation.sim_models import ParametricSimResult, SimulationParam
from backend.modeling.simulation.sim_registry import SimRegistry

router = APIRouter(prefix="/api/modeling/engine", tags=["modeling-engine"])
logger = logging.getLogger(__name__)

_query_engine = None
_mapping_svc = None
_sim_engine = None
_term_resolver = None
_git = None
_load_mapping_file = None  # injected helper


def init(query_engine, mapping_svc, sim_engine, term_resolver, git) -> None:
    global _query_engine, _mapping_svc, _sim_engine, _term_resolver, _git, _load_mapping_file
    _query_engine = query_engine
    _mapping_svc = mapping_svc
    _sim_engine = sim_engine
    _term_resolver = term_resolver
    _git = git

    def _load_mf(repo_id: str):
        from backend.modeling.mapping.yaml_store import load_mapping_yaml
        mf_path = Path("/tmp/ontong-repos") / repo_id / ".ontology" / "mapping.yaml"
        if not mf_path.exists():
            from backend.modeling.mapping.mapping_models import MappingFile
            return MappingFile(repo_id=repo_id, mappings=[])
        return load_mapping_yaml(mf_path)

    _load_mapping_file = _load_mf


# ── Request / Response models ──────────────────────────────────────


class EngineQueryRequest(BaseModel):
    query: str
    repo_id: str
    depth: int = Field(default=3, ge=1, le=10)
    use_llm: bool = False  # opt-in for LLM term extraction


class EngineSimulateRequest(BaseModel):
    entity_id: str
    repo_id: str
    params: dict[str, str]


# ── Endpoints ──────────────────────────────────────────────────────


@router.post("/query")
async def engine_query(req: EngineQueryRequest) -> ImpactResult:
    """Natural language or keyword query → term resolution → impact analysis."""
    if _query_engine is None:
        raise HTTPException(503, "Engine not initialized")

    mf = _load_mapping_file(req.repo_id)

    # Resolve term: deterministic first, LLM fallback if requested
    if req.use_llm:
        resolved = await _term_resolver.resolve_with_llm(req.query, mf)
    else:
        resolved = _term_resolver.resolve_deterministic(req.query, mf)

    if resolved is None:
        return ImpactResult(
            source_term=req.query,
            source_code_entity=None,
            source_domain=None,
            affected_processes=[],
            unmapped_entities=[],
            resolved=False,
            message=f"'{req.query}'에 해당하는 코드 엔티티를 찾을 수 없습니다.",
        )

    # Run impact analysis with the resolved term
    impact_query = ImpactQuery(
        term=resolved, repo_id=req.repo_id,
        depth=req.depth, confirmed_only=False,
    )
    return _query_engine.analyze(impact_query, mf)


@router.post("/simulate")
async def engine_simulate(req: EngineSimulateRequest) -> ParametricSimResult:
    """Run parametric simulation for a code entity."""
    if _sim_engine is None:
        raise HTTPException(503, "Engine not initialized")

    mf = _load_mapping_file(req.repo_id)
    return _sim_engine.simulate(
        entity_id=req.entity_id,
        params=req.params,
        repo_id=req.repo_id,
        mf=mf,
    )


@router.get("/params/{entity_id:path}")
async def engine_params(entity_id: str) -> dict:
    """Get simulation parameters for an entity."""
    params = SimRegistry.get_params(entity_id)
    return {"entity_id": entity_id, "params": [p.model_dump() for p in params]}


@router.get("/status")
async def engine_status(repo_id: str = "scm-demo") -> dict:
    """Engine readiness: mapping count, simulatable entities, etc."""
    mf = _load_mapping_file(repo_id) if _load_mapping_file else None
    mapping_count = len(mf.mappings) if mf else 0
    sim_entities = SimRegistry.all_entity_ids()
    simulatable_in_repo = [
        eid for eid in sim_entities
        if mf and any(m.code == eid for m in mf.mappings)
    ]

    return {
        "repo_id": repo_id,
        "mapping_count": mapping_count,
        "total_mappings": mapping_count,
        "simulatable_entities": len(simulatable_in_repo),
        "total_registered": len(sim_entities),
        "ready": mapping_count > 0,
    }
```

- [ ] **Step 4: Wire engine_api into the main modeling router**

Add to `backend/modeling/api/modeling.py`:

```python
# After existing imports, add:
from backend.modeling.api import engine_api

# In the router.include_router section, add:
router.include_router(engine_api.router)

# In the init() function, after existing initialization, add:
from backend.modeling.simulation.sim_engine import SimulationEngine
from backend.modeling.query.term_resolver import TermResolver

sim_engine = SimulationEngine(neo4j_client)
term_resolver = TermResolver()

engine_api.init(query_eng, mapping_svc, sim_engine, term_resolver, git)

# In the health endpoint capabilities list, add:
"simulation",
"engine_query",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_engine_api.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/api/engine_api.py backend/modeling/api/modeling.py tests/test_engine_api.py
git commit -m "feat(modeling): add engine API with query, simulate, params, and status endpoints"
```

---

### Task 6: Seed Enhancement

**Files:**
- Modify: `backend/modeling/api/seed_api.py`

- [ ] **Step 1: Add simulation param registration to seed flow**

In `backend/modeling/api/seed_api.py`, after the existing mapping sync (line 107), add simulation parameter registration. The seed endpoint should also return `sim_entities` count.

Add after `_mapping_svc.sync_to_neo4j(mf)` (line 107):

```python
    # 5. Register simulation parameters (sim_registry is pre-loaded with demo data)
    from backend.modeling.simulation.sim_registry import SimRegistry
    sim_entity_ids = SimRegistry.all_entity_ids()
    sim_count = len([eid for eid in sim_entity_ids if any(m.code == eid for m in mf.mappings)])
```

Update the return dict to include simulation info:

```python
    return {
        "status": "ok",
        "repo_id": SAMPLE_REPO_ID,
        "files_parsed": len(java_files),
        "entities_count": total_entities,
        "relations_count": total_relations,
        "ontology_nodes": ontology_count,
        "mappings_created": len(PRESET_MAPPINGS),
        "sim_entities": sim_count,
    }
```

- [ ] **Step 2: Run existing seed tests to verify no regressions**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_modeling_api.py tests/test_modeling_e2e.py -v -k seed 2>/dev/null; echo "exit: $?"`
Expected: Existing tests still pass (or skip if they don't test seed specifically)

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/api/seed_api.py
git commit -m "feat(modeling): include simulation entity count in seed response"
```

---

### Task 7: Frontend API Client Extensions

**Files:**
- Modify: `frontend/src/lib/api/modeling.ts`

- [ ] **Step 1: Add new types and functions**

Append to the end of `frontend/src/lib/api/modeling.ts` (before the final line):

```typescript
// ── Engine API ──

export interface EngineQueryRequest {
  query: string;
  repo_id: string;
  depth?: number;
  use_llm?: boolean;
}

export interface SimulationParam {
  entity_id: string;
  param_name: string;
  param_type: string;
  default_value: string;
  current_value: string;
  min_value: string | null;
  max_value: string | null;
  step: string | null;
  unit: string;
  description: string;
  formula: string | null;
}

export interface SimulationOutput {
  metric_name: string;
  label: string;
  before_value: string;
  after_value: string;
  change_pct: number;
  unit: string;
}

export interface AffectedProcessRef {
  domain_id: string;
  domain_name: string;
  distance: number;
}

export interface ParametricSimResult {
  entity_id: string;
  entity_name: string;
  params_before: Record<string, string>;
  params_after: Record<string, string>;
  outputs: SimulationOutput[];
  affected_processes: AffectedProcessRef[];
  message: string;
}

export interface EngineStatus {
  repo_id: string;
  mapping_count: number;
  total_mappings: number;
  simulatable_entities: number;
  total_registered: number;
  ready: boolean;
}

export async function engineQuery(query: string, repoId: string, useLlm = false): Promise<ImpactResult> {
  const res = await fetch(`${API_BASE}/api/modeling/engine/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, repo_id: repoId, use_llm: useLlm }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function engineSimulate(
  entityId: string,
  repoId: string,
  params: Record<string, string>,
): Promise<ParametricSimResult> {
  const res = await fetch(`${API_BASE}/api/modeling/engine/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_id: entityId, repo_id: repoId, params }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function engineGetParams(entityId: string): Promise<{ params: SimulationParam[] }> {
  const res = await fetch(`${API_BASE}/api/modeling/engine/params/${entityId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function engineStatus(repoId: string): Promise<EngineStatus> {
  const res = await fetch(`${API_BASE}/api/modeling/engine/status?repo_id=${repoId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 2: Update SeedResult to include sim_entities**

In the existing `SeedResult` interface, add:

```typescript
export interface SeedResult {
  status: string;
  repo_id: string;
  files_parsed: number;
  entities_count: number;
  relations_count: number;
  ontology_nodes: number;
  mappings_created: number;
  sim_entities?: number;  // NEW
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/lib/api/modeling.ts
git commit -m "feat(frontend): add engine API client functions and types"
```

---

### Task 8: Analysis Console Component

**Files:**
- Create: `frontend/src/components/sections/modeling/AnalysisConsole.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/sections/modeling/AnalysisConsole.tsx
"use client";

import React, { useState } from "react";
import {
  Search,
  Loader2,
  ArrowRight,
  AlertTriangle,
  Zap,
  Lightbulb,
} from "lucide-react";
import { engineQuery, type ImpactResult } from "@/lib/api/modeling";

interface AnalysisConsoleProps {
  repoId: string;
  onNavigateToSim?: (entityId: string) => void;
}

const EXAMPLE_QUERIES = [
  { text: "안전재고 계산 로직 변경", desc: "SafetyStockCalculator 영향 범위" },
  { text: "주문 서비스 수정", desc: "OrderService 의존성 추적" },
  { text: "생산 계획 변경", desc: "ProductionPlanner 영향 분석" },
  { text: "InventoryManager", desc: "재고 관리 코드 직접 검색" },
];

export function AnalysisConsole({ repoId, onNavigateToSim }: AnalysisConsoleProps) {
  const [query, setQuery] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<ImpactResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (input?: string) => {
    const q = (input ?? query).trim();
    if (!q) return;
    if (input) setQuery(input);

    setAnalyzing(true);
    setError(null);
    setResult(null);
    try {
      const res = await engineQuery(q, repoId);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.nativeEvent.isComposing) {
      handleAnalyze();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold mb-1">영향 분석</h2>
        <p className="text-sm text-muted-foreground">
          현업 요청이나 코드 이름을 입력하면, 변경 시 영향받는 비즈니스 프로세스를 자동으로 찾아줍니다.
        </p>
      </div>

      {/* Search bar */}
      <div className="relative">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder='현업 요청이나 코드를 입력하세요... 예: "안전재고 계산 로직 변경"'
              className="w-full pl-10 pr-4 py-3 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              disabled={analyzing}
            />
          </div>
          <button
            onClick={() => handleAnalyze()}
            disabled={analyzing || !query.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {analyzing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            분석
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-4 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Example queries (when no result) */}
      {!result && !analyzing && !error && (
        <div className="rounded-lg border border-border bg-muted/20 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="h-4 w-4 text-amber-500" />
            <span className="text-sm font-medium">예시 질의</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {EXAMPLE_QUERIES.map((eq) => (
              <button
                key={eq.text}
                onClick={() => handleAnalyze(eq.text)}
                className="text-left rounded-md border border-border bg-background px-3 py-2 hover:bg-muted/50 transition-colors"
              >
                <span className="text-sm font-medium text-foreground">{eq.text}</span>
                <span className="block text-xs text-muted-foreground mt-0.5">{eq.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {analyzing && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          <span className="text-sm">영향 범위를 분석하고 있습니다...</span>
        </div>
      )}

      {/* Results */}
      {result && !analyzing && (
        <div className="space-y-4">
          {/* Source resolution */}
          {result.resolved ? (
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="text-xs text-muted-foreground mb-2">검색 대상</div>
              <div className="flex items-center gap-3">
                <div>
                  <span className="font-mono text-sm font-medium">
                    {result.source_code_entity?.split(".").pop()}
                  </span>
                  <span className="text-xs text-muted-foreground ml-2">
                    {result.source_code_entity}
                  </span>
                </div>
                {result.source_domain && (
                  <>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-sm font-medium text-primary">
                      {result.source_domain}
                    </span>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm text-amber-700 dark:text-amber-400">
                  {result.message}
                </span>
              </div>
            </div>
          )}

          {/* Affected processes */}
          {result.affected_processes.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="text-xs text-muted-foreground mb-3">
                영향받는 프로세스 ({result.affected_processes.length}개)
              </div>
              <div className="space-y-2">
                {result.affected_processes.map((ap, i) => (
                  <div
                    key={ap.domain_id}
                    className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{ap.domain_name}</span>
                      <span className="text-xs text-muted-foreground">{ap.domain_id}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      ap.distance === 0
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground"
                    }`}>
                      {ap.distance === 0 ? "직접 매핑" : `거리: ${ap.distance}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Simulation link */}
          {result.resolved && result.source_code_entity && onNavigateToSim && (
            <button
              onClick={() => onNavigateToSim(result.source_code_entity!)}
              className="inline-flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm font-medium text-primary hover:bg-primary/10 transition-colors w-full justify-center"
            >
              <Zap className="h-4 w-4" />
              시뮬레이션 실행
              <ArrowRight className="h-4 w-4" />
            </button>
          )}

          {/* Unmapped entities */}
          {result.unmapped_entities.length > 0 && (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
                  미매핑 엔티티 {result.unmapped_entities.length}개
                </span>
              </div>
              <div className="space-y-1">
                {result.unmapped_entities.map((ue) => (
                  <div key={ue} className="text-xs font-mono text-amber-600 dark:text-amber-400">
                    {ue.split(".").pop()}
                    <span className="text-amber-400 dark:text-amber-600 ml-1">{ue}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary message */}
          <div className="text-xs text-muted-foreground text-center pt-2">
            {result.message}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/modeling/AnalysisConsole.tsx
git commit -m "feat(frontend): add analysis console component with natural language query"
```

---

### Task 9: Simulation Panel Component

**Files:**
- Create: `frontend/src/components/sections/modeling/SimulationPanel.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/sections/modeling/SimulationPanel.tsx
"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  Play,
  RotateCcw,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
} from "lucide-react";
import {
  engineGetParams,
  engineSimulate,
  type SimulationParam,
  type ParametricSimResult,
} from "@/lib/api/modeling";

interface SimulationPanelProps {
  repoId: string;
  initialEntityId?: string | null;
}

export function SimulationPanel({ repoId, initialEntityId }: SimulationPanelProps) {
  const [entityId, setEntityId] = useState(initialEntityId ?? "");
  const [params, setParams] = useState<SimulationParam[]>([]);
  const [localValues, setLocalValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ParametricSimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingParams, setLoadingParams] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Known entities for the dropdown
  const KNOWN_ENTITIES = [
    { id: "com.ontong.scm.inventory.SafetyStockCalculator", label: "SafetyStockCalculator", desc: "안전재고 계산" },
    { id: "com.ontong.scm.inventory.InventoryManager", label: "InventoryManager", desc: "재고 관리" },
    { id: "com.ontong.scm.order.OrderService", label: "OrderService", desc: "주문 서비스" },
    { id: "com.ontong.scm.production.ProductionPlanner", label: "ProductionPlanner", desc: "생산 계획" },
    { id: "com.ontong.scm.production.WorkOrderProcessor", label: "WorkOrderProcessor", desc: "작업 지시" },
    { id: "com.ontong.scm.procurement.PurchaseOrderService", label: "PurchaseOrderService", desc: "구매 주문" },
    { id: "com.ontong.scm.procurement.SupplierEvaluator", label: "SupplierEvaluator", desc: "공급업체 평가" },
    { id: "com.ontong.scm.logistics.ShipmentTracker", label: "ShipmentTracker", desc: "배송 추적" },
    { id: "com.ontong.scm.logistics.WarehouseController", label: "WarehouseController", desc: "창고 관리" },
  ];

  const fetchParams = useCallback(async (eid: string) => {
    if (!eid) return;
    setLoadingParams(true);
    setError(null);
    setResult(null);
    try {
      const data = await engineGetParams(eid);
      setParams(data.params);
      const vals: Record<string, string> = {};
      for (const p of data.params) {
        vals[p.param_name] = p.default_value;
      }
      setLocalValues(vals);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingParams(false);
    }
  }, []);

  useEffect(() => {
    if (entityId) fetchParams(entityId);
  }, [entityId, fetchParams]);

  // Sync initialEntityId changes
  useEffect(() => {
    if (initialEntityId && initialEntityId !== entityId) {
      setEntityId(initialEntityId);
    }
  }, [initialEntityId]);

  const handleParamChange = (name: string, value: string) => {
    setLocalValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleReset = () => {
    const vals: Record<string, string> = {};
    for (const p of params) {
      vals[p.param_name] = p.default_value;
    }
    setLocalValues(vals);
    setResult(null);
  };

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await engineSimulate(entityId, repoId, localValues);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const hasChanges = params.some(
    (p) => localValues[p.param_name] !== p.default_value
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold mb-1">시뮬레이션</h2>
        <p className="text-sm text-muted-foreground">
          코드 엔티티의 파라미터를 변경하고 비즈니스 영향을 확인합니다.
        </p>
      </div>

      {/* Entity selector */}
      <div>
        <label className="text-xs text-muted-foreground">시뮬레이션 대상</label>
        <div className="relative mt-1">
          <select
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            className="w-full appearance-none px-3 py-2 pr-8 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">엔티티를 선택하세요...</option>
            {KNOWN_ENTITIES.map((e) => (
              <option key={e.id} value={e.id}>
                {e.label} — {e.desc}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Loading params */}
      {loadingParams && (
        <div className="flex items-center justify-center py-8 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          <span className="text-sm">파라미터 로드 중...</span>
        </div>
      )}

      {/* Parameter sliders */}
      {params.length > 0 && !loadingParams && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">파라미터 조정</span>
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="h-3 w-3" />
              초기화
            </button>
          </div>

          {params.map((p) => {
            if (p.param_type === "bool") {
              return (
                <div key={p.param_name} className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-mono">{p.param_name}</span>
                    <span className="text-xs text-muted-foreground ml-2">{p.description}</span>
                  </div>
                  <button
                    onClick={() =>
                      handleParamChange(
                        p.param_name,
                        localValues[p.param_name] === "true" ? "false" : "true"
                      )
                    }
                    className={`px-3 py-1 rounded text-xs font-medium ${
                      localValues[p.param_name] === "true"
                        ? "bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400"
                        : "bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-400"
                    }`}
                  >
                    {localValues[p.param_name] === "true" ? "ON" : "OFF"}
                  </button>
                </div>
              );
            }

            const isChanged = localValues[p.param_name] !== p.default_value;

            return (
              <div key={p.param_name}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono">{p.param_name}</span>
                    <span className="text-xs text-muted-foreground">{p.description}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    {isChanged && (
                      <span className="text-xs text-muted-foreground line-through">
                        {p.default_value}
                      </span>
                    )}
                    <span className={`font-mono font-medium ${isChanged ? "text-primary" : ""}`}>
                      {localValues[p.param_name]}
                    </span>
                    {p.unit && <span className="text-xs text-muted-foreground">{p.unit}</span>}
                  </div>
                </div>
                {p.min_value && p.max_value && (
                  <input
                    type="range"
                    min={p.min_value}
                    max={p.max_value}
                    step={p.step ?? "1"}
                    value={localValues[p.param_name]}
                    onChange={(e) => handleParamChange(p.param_name, e.target.value)}
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  />
                )}
                {p.formula && (
                  <div className="text-[10px] text-muted-foreground mt-0.5 font-mono">
                    {p.formula}
                  </div>
                )}
              </div>
            );
          })}

          {/* Execute button */}
          <button
            onClick={handleSimulate}
            disabled={loading || !hasChanges}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {hasChanges ? "실행" : "파라미터를 변경하세요"}
          </button>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-4">
          {/* Outputs */}
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground mb-3">시뮬레이션 결과</div>
            <div className="space-y-3">
              {result.outputs.map((o) => {
                const icon =
                  o.change_pct > 0 ? (
                    <TrendingUp className="h-4 w-4 text-blue-500" />
                  ) : o.change_pct < 0 ? (
                    <TrendingDown className="h-4 w-4 text-amber-500" />
                  ) : (
                    <Minus className="h-4 w-4 text-muted-foreground" />
                  );

                return (
                  <div key={o.metric_name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {icon}
                      <span className="text-sm">{o.label}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-muted-foreground">{o.before_value}{o.unit}</span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span className="font-medium">{o.after_value}{o.unit}</span>
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          o.change_pct > 0
                            ? "bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400"
                            : o.change_pct < 0
                            ? "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {o.change_pct > 0 ? "+" : ""}
                        {o.change_pct}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Affected processes */}
          {result.affected_processes.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="text-xs text-muted-foreground mb-3">
                영향받는 프로세스 ({result.affected_processes.length}개)
              </div>
              <div className="space-y-2">
                {result.affected_processes.map((ap) => (
                  <div
                    key={ap.domain_id}
                    className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-2"
                  >
                    <span className="text-sm font-medium">{ap.domain_name}</span>
                    <span className="text-xs text-muted-foreground">
                      {ap.distance === 0 ? "직접 매핑" : `거리: ${ap.distance}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          <div className="text-xs text-muted-foreground text-center">
            {result.message}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!entityId && !loadingParams && (
        <div className="text-center py-12 text-muted-foreground space-y-2">
          <Zap className="h-8 w-8 mx-auto mb-2 opacity-20" />
          <p className="text-sm">시뮬레이션할 엔티티를 선택하세요.</p>
          <p className="text-xs">
            분석 콘솔에서 영향분석 후 &ldquo;시뮬레이션 실행&rdquo;을 클릭하면 자동으로 연결됩니다.
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/modeling/SimulationPanel.tsx
git commit -m "feat(frontend): add simulation panel with parameter sliders and results"
```

---

### Task 10: Sidebar Restructure + Demo Flow

**Files:**
- Modify: `frontend/src/components/sections/ModelingSection.tsx`

- [ ] **Step 1: Restructure the sidebar navigation**

Replace the entire `ModelingSection.tsx` with the restructured version. Key changes:
- Add `ModelingView` types: `"analysis"` and `"simulation"` (new)
- Default `activeView` to `"analysis"` instead of `"code"`
- Split nav items into "main" group (analysis, simulation) and "settings" group (code, ontology, mapping, approval)
- Add `simTarget` state for cross-component entity passing
- Wire `onNavigateToSim` from AnalysisConsole to set simTarget and switch to simulation tab
- Update seed flow to auto-navigate to analysis tab after loading demo
- Update `ViewRouter` to include new components

```tsx
// frontend/src/components/sections/ModelingSection.tsx
"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Code,
  Network,
  GitCompare,
  Search,
  CheckSquare,
  PackageOpen,
  Loader2,
  CircleCheck,
  Circle,
  CircleDot,
  Zap,
  Settings2,
} from "lucide-react";
import { CodeGraphViewer } from "./modeling/CodeGraphViewer";
import { DomainOntologyEditor } from "./modeling/DomainOntologyEditor";
import { MappingSplitView } from "./modeling/MappingSplitView";
import { ImpactQueryPanel } from "./modeling/ImpactQueryPanel";
import { ApprovalList } from "./modeling/ApprovalList";
import { AnalysisConsole } from "./modeling/AnalysisConsole";
import { SimulationPanel } from "./modeling/SimulationPanel";
import { seedScmDemo, getCodeGraph, getOntologyTree, getMappings } from "@/lib/api/modeling";

type ModelingView = "analysis" | "simulation" | "code" | "ontology" | "mapping" | "impact" | "approval";

interface NavItem {
  id: ModelingView;
  label: string;
  icon: React.ReactNode;
  description: string;
  step?: number;
}

const MAIN_NAV: NavItem[] = [
  { id: "analysis", label: "분석 콘솔", icon: <Search size={18} />, description: "자연어 영향 분석" },
  { id: "simulation", label: "시뮬레이션", icon: <Zap size={18} />, description: "파라미터 what-if 분석" },
];

const SETTINGS_NAV: NavItem[] = [
  { id: "code", label: "코드 분석", icon: <Code size={18} />, description: "Java 코드 파싱", step: 1 },
  { id: "ontology", label: "도메인 온톨로지", icon: <Network size={18} />, description: "SCOR+ISA-95 트리", step: 2 },
  { id: "mapping", label: "매핑 관리", icon: <GitCompare size={18} />, description: "코드 ↔ 도메인 연결", step: 3 },
  { id: "approval", label: "검토 요청", icon: <CheckSquare size={18} />, description: "매핑 승인/반려" },
];

interface WorkflowStatus {
  codeParsed: boolean;
  ontologyLoaded: boolean;
  mappingExists: boolean;
}

export function ModelingSection() {
  const [activeView, setActiveView] = useState<ModelingView>("analysis");
  const [repoId, setRepoId] = useState<string>("");
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowStatus>({ codeParsed: false, ontologyLoaded: false, mappingExists: false });
  const [simTarget, setSimTarget] = useState<string | null>(null);

  const checkWorkflow = useCallback(async (rid: string) => {
    if (!rid) return;
    const status: WorkflowStatus = { codeParsed: false, ontologyLoaded: false, mappingExists: false };
    try {
      const [codeRes, ontoRes, mapRes] = await Promise.allSettled([
        getCodeGraph(rid),
        getOntologyTree(),
        getMappings(rid),
      ]);
      if (codeRes.status === "fulfilled" && codeRes.value.entities.length > 0) status.codeParsed = true;
      if (ontoRes.status === "fulfilled" && ontoRes.value.nodes.length > 0) status.ontologyLoaded = true;
      if (mapRes.status === "fulfilled" && mapRes.value.mappings.length > 0) status.mappingExists = true;
    } catch { /* ignore */ }
    setWorkflow(status);
  }, []);

  useEffect(() => {
    if (repoId) checkWorkflow(repoId);
  }, [repoId, checkWorkflow]);

  useEffect(() => {
    if (repoId) checkWorkflow(repoId);
  }, [activeView, repoId, checkWorkflow]);

  const handleLoadDemo = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const result = await seedScmDemo();
      setRepoId("scm-demo");
      setSeedResult(
        `${result.files_parsed}개 파일, ${result.entities_count}개 엔티티, ${result.mappings_created}개 매핑 로드 완료`
      );
      // Auto-navigate to analysis console after demo load
      setActiveView("analysis");
    } catch (e) {
      setSeedResult(`오류: ${(e as Error).message}`);
    } finally {
      setSeeding(false);
    }
  };

  const handleNavigateToSim = (entityId: string) => {
    setSimTarget(entityId);
    setActiveView("simulation");
  };

  const nextStep = !workflow.codeParsed ? 1 : !workflow.ontologyLoaded ? 2 : !workflow.mappingExists ? 3 : 0;

  function getStepIcon(item: NavItem) {
    if (!item.step || !repoId) return null;
    const done =
      (item.step === 1 && workflow.codeParsed) ||
      (item.step === 2 && workflow.ontologyLoaded) ||
      (item.step === 3 && workflow.mappingExists);
    const isNext = item.step === nextStep;

    if (done) return <CircleCheck className="h-3.5 w-3.5 text-green-500 shrink-0" />;
    if (isNext) return <CircleDot className="h-3.5 w-3.5 text-primary shrink-0 animate-pulse" />;
    return <Circle className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />;
  }

  function renderNavButton(item: NavItem) {
    const stepIcon = getStepIcon(item);
    return (
      <button
        key={item.id}
        onClick={() => setActiveView(item.id)}
        className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
          activeView === item.id
            ? "bg-primary/10 text-primary font-medium"
            : item.step === nextStep && repoId
            ? "text-foreground bg-muted/50 hover:bg-muted"
            : "text-muted-foreground hover:bg-muted hover:text-foreground"
        }`}
      >
        {item.icon}
        <span className="flex-1 text-left">{item.label}</span>
        {stepIcon}
      </button>
    );
  }

  return (
    <div className="flex h-full">
      {/* Left nav */}
      <div className="w-56 border-r border-border bg-muted/30 p-3 flex flex-col gap-1">
        <div className="px-2 py-3 mb-2">
          <h2 className="text-sm font-semibold text-foreground">모델링</h2>
          <p className="text-xs text-muted-foreground mt-1">코드-도메인 연결 관리</p>
        </div>

        {/* Repo selector */}
        <div className="px-2 mb-3">
          <label className="text-xs text-muted-foreground">Repository</label>
          <input
            type="text"
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            placeholder="repo-id"
            className="w-full mt-1 px-2 py-1 text-xs bg-background border border-border rounded"
          />
        </div>

        {/* Main nav (analysis + simulation) */}
        {MAIN_NAV.map(renderNavButton)}

        {/* Divider */}
        <div className="flex items-center gap-2 px-3 py-2 mt-2">
          <Settings2 className="h-3 w-3 text-muted-foreground/60" />
          <span className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider">설정</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        {/* Settings nav (code, ontology, mapping, approval) */}
        {SETTINGS_NAV.map(renderNavButton)}

        {/* Workflow hint */}
        {repoId && nextStep > 0 && (
          <div className="mt-3 mx-2 px-2 py-2 rounded bg-primary/5 border border-primary/20">
            <p className="text-[10px] text-primary font-medium">
              {nextStep === 1 && "코드를 파싱하세요"}
              {nextStep === 2 && "온톨로지를 로드하세요"}
              {nextStep === 3 && "코드-도메인 매핑을 추가하세요"}
            </p>
          </div>
        )}
        {repoId && nextStep === 0 && (
          <div className="mt-3 mx-2 px-2 py-2 rounded bg-green-500/5 border border-green-500/20">
            <p className="text-[10px] text-green-600 dark:text-green-400 font-medium">
              기본 설정 완료 — 분석 콘솔을 사용하세요
            </p>
          </div>
        )}
      </div>

      {/* Main content */}
      <div className="flex-1 p-6 overflow-auto">
        {!repoId ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
            <PackageOpen className="h-12 w-12 opacity-20" />
            <div className="text-center space-y-2">
              <p className="text-sm font-medium text-foreground">Repository를 선택하세요</p>
              <p className="text-xs">왼쪽에서 Repository ID를 입력하거나, 데모 데이터를 로드하세요.</p>
            </div>
            <button
              onClick={handleLoadDemo}
              disabled={seeding}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {seeding ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageOpen className="h-4 w-4" />}
              SCM 데모 프로젝트 로드
            </button>
            {seedResult && (
              <p className={`text-xs ${seedResult.startsWith("오류") ? "text-red-500" : "text-green-600"}`}>
                {seedResult}
              </p>
            )}
          </div>
        ) : (
          <ViewRouter
            view={activeView}
            repoId={repoId}
            simTarget={simTarget}
            onNavigateToSim={handleNavigateToSim}
          />
        )}
      </div>
    </div>
  );
}

function ViewRouter({
  view,
  repoId,
  simTarget,
  onNavigateToSim,
}: {
  view: ModelingView;
  repoId: string;
  simTarget: string | null;
  onNavigateToSim: (entityId: string) => void;
}) {
  switch (view) {
    case "analysis":
      return <AnalysisConsole repoId={repoId} onNavigateToSim={onNavigateToSim} />;
    case "simulation":
      return <SimulationPanel repoId={repoId} initialEntityId={simTarget} />;
    case "code":
      return <CodeGraphViewer repoId={repoId} />;
    case "ontology":
      return <DomainOntologyEditor repoId={repoId} />;
    case "mapping":
      return <MappingSplitView repoId={repoId} />;
    case "impact":
      return <ImpactQueryPanel repoId={repoId} />;
    case "approval":
      return <ApprovalList repoId={repoId} />;
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Run dev server and verify UI**

Run: `cd /Users/donghae/workspace/ai/onTong/frontend && npm run dev`
Verify:
1. Navigate to Section 2 (Modeling)
2. "분석 콘솔" is the default selected tab
3. "시뮬레이션" tab is second
4. "설정" divider separates from code/ontology/mapping/approval tabs
5. Click "SCM 데모 프로젝트 로드" → auto-navigates to "분석 콘솔"
6. Click example query "안전재고 계산 로직 변경" → shows impact results
7. Click "시뮬레이션 실행" → switches to simulation tab with SafetyStockCalculator pre-selected
8. Adjust safety_factor slider → click "실행" → see before/after comparison

- [ ] **Step 4: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/ModelingSection.tsx
git commit -m "feat(frontend): restructure modeling sidebar with analysis console as default"
```

---

## Self-Review Checklist

**1. Spec coverage:**
| Spec Requirement | Task |
|-----------------|------|
| Analysis Console UI | Task 8 |
| Natural language → LLM term extraction → impact analysis | Task 2, 5 |
| Korean alias table | Task 2 |
| Fuzzy match (Levenshtein) | Task 2 |
| Simulation parameter data model | Task 1 |
| Demo data (9 entities with params) | Task 3 |
| Calculation functions (Python) | Task 3 |
| Simulation UI (parameter sliders + results) | Task 9 |
| Sidebar restructure (analysis default) | Task 10 |
| Demo flow (1-click seed → analysis console) | Task 10 |
| POST /api/modeling/engine/query | Task 5 |
| POST /api/modeling/engine/simulate | Task 5 |
| GET /api/modeling/engine/params | Task 5 |
| GET /api/modeling/engine/status | Task 5 |
| ParametricSimResult naming (distinct from SimulationResult) | Task 1 |
| Seed enhancement | Task 6 |

**2. Placeholder scan:** No TBD/TODO/placeholder text found.

**3. Type consistency:** SimulationParam, ParametricSimResult, AffectedProcessRef used consistently across backend models (Task 1), registry (Task 3), engine (Task 4), API (Task 5), frontend types (Task 7), and components (Task 8, 9).

**Not in scope (Phase 1b/2):**
- AI mapping suggestion API (Phase 1b)
- Reverse tracing API (Phase 2)
- Docker/JVM sandbox (Phase 2)
- Cross-entity parameter propagation (Phase 2)
