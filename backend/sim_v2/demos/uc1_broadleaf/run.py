"""UC1 broadleaf demo — `OrderPricingService.calculateGrandTotal` (W19).

Closes the G1 gate by exercising the same end-to-end pipeline on the third
plugin (broadleaf). Demonstrates:
  - BigDecimal add + multiply + setScale + compareTo
  - Multiple side-effect setters (order.setTax / order.setGrandTotal)
  - PricingException plugin-specific exception passthrough

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc1_broadleaf.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import tree_sitter_java as tsjava
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.modeling.code_layer.orm import CodeFieldRow, CodeMethodRow, CodeTypeRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.contracts.base import (
    DECIMAL64,
    RoundingMode,
    bd_set_scale,
)
from backend.sim_v2.core.integrator.integrator import Integrator
from backend.sim_v2.core.integrator.proposal import Proposal, UserFeedback
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.ontology_type_resolver import OntologyTypeResolver
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    CompositeTypeResolver,
)
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)
from backend.sim_v2.plugins.broadleaf.contracts.exception import (
    BroadleafException,
    PricingException,
)


JAVA_LANGUAGE = Language(tsjava.language())

# Virtual broadleaf Java sample
JAVA_SOURCE = """
class OrderPricingService {
    public BigDecimal calculateGrandTotal(Order order, BigDecimal taxRate) {
        BigDecimal subtotal = order.getSubtotal();
        BigDecimal tax = subtotal.multiply(taxRate).setScale(2, RoundingMode.HALF_UP);
        if (tax.compareTo(BigDecimal.ZERO) < 0) {
            throw new PricingException("tax cannot be negative");
        }
        BigDecimal grandTotal = subtotal.add(tax);
        order.setTax(tax);
        order.setGrandTotal(grandTotal);
        return grandTotal;
    }
}
"""

# Module-level placeholder — ScenarioVerificationEngine injects fresh
# TraceCollector per fixture run.
_trace = None


# ─────────────────────────────────────────────────────────────────────────────
# Mock Order entity
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Order:
    orderId:    str
    subtotal:   Decimal
    tax:        Decimal | None = None
    grandTotal: Decimal | None = None

    def getSubtotal(self) -> Decimal:
        return self.subtotal

    def setTax(self, v: Decimal) -> None:
        self.tax = v

    def setGrandTotal(self, v: Decimal) -> None:
        self.grandTotal = v


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth — manually instrumented Python equivalent
# ─────────────────────────────────────────────────────────────────────────────


def ground_truth_calculate(order: Order, taxRate: Decimal) -> Decimal:
    subtotal = order.getSubtotal()
    if _trace is not None:
        _trace.step("anchor_1", {"subtotal": subtotal})

    tax = bd_set_scale(subtotal * taxRate, 2, RoundingMode.HALF_UP)
    if _trace is not None:
        _trace.step("anchor_2", {"tax": tax})

    cond = tax < Decimal(0)
    if _trace is not None:
        _trace.branch("anchor_3", bool(cond))

    if cond:
        msg = "tax cannot be negative"
        if _trace is not None:
            _trace.exception("anchor_4", "PricingException", str(msg))
        raise PricingException(msg)

    grand_total = subtotal + tax
    if _trace is not None:
        _trace.step("anchor_5", {"grandTotal": grand_total})

    order.setTax(tax)
    order.setGrandTotal(grand_total)
    return grand_total


# ─────────────────────────────────────────────────────────────────────────────
# Ontology — Order entity methods
# ─────────────────────────────────────────────────────────────────────────────


def build_ontology_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        CodeMethodRow.__table__,
    ])
    session = Session(engine)
    repo_id = "broadleaf-commerce"

    session.add(CodeTypeRow(
        fqn="org.broadleafcommerce.order.domain.Order", simple_name="Order",
        package="org.broadleafcommerce.order.domain",
        kind="CLASS", role="entity", repo_id=repo_id,
    ))
    session.add_all([
        CodeMethodRow(
            fqn="org.broadleafcommerce.order.domain.Order#getSubtotal",
            name="getSubtotal",
            parent_type_fqn="org.broadleafcommerce.order.domain.Order",
            return_type="java.math.BigDecimal",
            repo_id=repo_id,
        ),
        CodeMethodRow(
            fqn="org.broadleafcommerce.order.domain.Order#setTax",
            name="setTax",
            parent_type_fqn="org.broadleafcommerce.order.domain.Order",
            return_type="void",
            repo_id=repo_id,
        ),
        CodeMethodRow(
            fqn="org.broadleafcommerce.order.domain.Order#setGrandTotal",
            name="setGrandTotal",
            parent_type_fqn="org.broadleafcommerce.order.domain.Order",
            return_type="void",
            repo_id=repo_id,
        ),
    ])
    session.commit()
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Translate + compile
# ─────────────────────────────────────────────────────────────────────────────


def translate_method(session: Session, *, with_trace: bool = True) -> tuple[str, dict]:
    tree = Parser(JAVA_LANGUAGE).parse(JAVA_SOURCE.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    if method is None:
        raise RuntimeError("calculateGrandTotal method not found")

    resolver = CompositeTypeResolver([
        OntologyTypeResolver(session, "broadleaf-commerce"),
        BigDecimalAwareResolver(),
    ])
    translator = JavaToPythonTranslator(type_resolver=resolver)
    tr = translator.translate(method, indent=0, with_trace=with_trace)
    return tr.python_source, {
        "imports":   tr.imports_needed,
        "notes":     tr.notes,
        "locked":    tr.signature_locked,
    }


def compile_to_callable(python_source: str):
    python_source = python_source.replace(
        "def calculateGrandTotal(self, ", "def calculateGrandTotal(",
    )
    globals_dict: dict[str, Any] = {
        "Decimal":            Decimal,
        "RoundingMode":       RoundingMode,
        "DECIMAL64":          DECIMAL64,
        "bd_set_scale":       bd_set_scale,
        "PricingException":   PricingException,
        "_trace":             None,
    }
    exec(compile(python_source, "<demo-broadleaf>", "exec"), globals_dict)
    return globals_dict["calculateGrandTotal"]


# ─────────────────────────────────────────────────────────────────────────────
# Stub recommendation engine
# ─────────────────────────────────────────────────────────────────────────────


class _StubRecommendationEngine:
    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        return proposal


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────────────


def make_scenarios() -> dict[str, Scenario]:
    return {
        "S1_normal_8pct_tax": Scenario(
            fixture_id="S1_normal_8pct_tax",
            inputs={
                "order":   Order("ORD-1", subtotal=Decimal("100.00")),
                "taxRate": Decimal("0.08"),
            },
            # tax = 100 * 0.08 = 8.00, grand = 108.00
            expected_output=Decimal("108.00"),
        ),
        "S2_rounding_half_up": Scenario(
            fixture_id="S2_rounding_half_up",
            inputs={
                "order":   Order("ORD-2", subtotal=Decimal("99.95")),
                "taxRate": Decimal("0.075"),
            },
            # tax = 99.95 * 0.075 = 7.49625 → 7.50 (HALF_UP), grand = 107.45
            expected_output=Decimal("107.45"),
        ),
        "S3_negative_rate": Scenario(
            fixture_id="S3_negative_rate",
            inputs={
                "order":   Order("ORD-3", subtotal=Decimal("100.00")),
                "taxRate": Decimal("-0.05"),
            },
            expected_output=None,
            expected_exception=PricingException,
        ),
    }


def main() -> int:
    print("=" * 78)
    print("UC1 broadleaf demo — OrderPricingService.calculateGrandTotal (W19)")
    print("=" * 78)
    print()

    print("Step 1: Populate Code Layer ontology with Order entity methods")
    session = build_ontology_session()
    print(f"  ✓ {session.query(CodeMethodRow).count()} method rows seeded")
    print()

    print("Step 2: Translate JAVA_SOURCE with trace instrumentation")
    py_source, meta = translate_method(session, with_trace=True)
    if meta["locked"]:
        print(f"  ABORT — signature_locked. notes={meta['notes']}")
        return 1
    print(f"  ✓ translated — {len(py_source.split(chr(10)))} lines")
    print()
    print("Generated Python source:")
    for line in py_source.split("\n"):
        print(f"  | {line}")
    print()

    print("Step 3: Compile + wire Integrator")
    translated_fn = compile_to_callable(py_source)
    fixtures = make_scenarios()
    engine = ScenarioVerificationEngine(
        translated_fn=translated_fn,
        baseline_fn=ground_truth_calculate,
        fixtures=fixtures,
        with_trace=True,
    )
    integrator = Integrator(engine, _StubRecommendationEngine())
    print(f"  ✓ integrator initialized")
    print()

    print("Step 4-7: Proposal full lifecycle")
    prop = Proposal(
        type="code_change",
        description="Translate OrderPricingService.calculateGrandTotal (broadleaf)",
        plugin="broadleaf",
        code_diff={"method_fqn": "org.broadleafcommerce.order.service.OrderPricingService#calculateGrandTotal"},
    )
    prop_id = integrator.submit_proposal(prop)
    print(f"  DRAFT → PROPOSED ✓")

    engine.fixtures = make_scenarios()
    oracle = integrator.request_oracle(prop_id, list(fixtures.keys()))
    print(f"  PROPOSED → ORACLED ✓ (aggregate={oracle.aggregate_status})")
    for fid, r in oracle.by_fixture.items():
        print(f"    {fid:<22} {r.status:<12} output={r.output_diff.summary}")
        print(f"    {'':22} {'':12} trace= {r.trace_diff.summary}")

    integrator.review_proposal(prop_id, UserFeedback(
        decision="ACCEPT", timestamp=datetime.now(timezone.utc),
        user="demo-user",
        comments=f"all {len(fixtures)} scenarios PASS",
    ))
    print(f"  ORACLED → ACCEPTED ✓")

    revision_id = integrator.merge_proposal(
        prop_id=prop_id,
        ontology_revision="broadleaf@2026-05-13",
        code_revision="git:broadleaf-community-v6.x",
        schema_revision="alembic:broadleaf-baseline",
        created_by="demo-user",
    )
    final = integrator.get_proposal(prop_id)
    print(f"  ACCEPTED → MERGED ✓ revision={revision_id}")
    print()

    if (
        oracle.aggregate_status == "PASS"
        and final.state == "MERGED"
        and integrator.revision_store.get(revision_id) is not None
    ):
        print("✓ Final verdict: PASS — broadleaf system end-to-end")
        print(f"  G1 gate progress: v2 + banking + broadleaf — 3 / 3 systems ✓ GATE CLOSED")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
