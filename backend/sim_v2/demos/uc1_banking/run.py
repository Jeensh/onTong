"""UC1 banking demo — full G1-gate parallel run for the banking plugin (W18).

Virtual Banking Java method `LoanInterestService.calculateAccruedInterest` is
translated through the full sim_v2 pipeline (translator + ontology +
ScenarioVerificationEngine + Integrator) with trace instrumentation enabled.

Demonstrates that the framework is system-agnostic — same pipeline as
`uc1_integrator_pipeline` works for a completely different plugin contract
(banking exceptions instead of AlgorithmException, Account instead of SDSlabEntity).

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc1_banking.run
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
from backend.sim_v2.plugins.banking.contracts.exception import (
    BankingException,
    ComplianceException,
)


JAVA_LANGUAGE = Language(tsjava.language())

# Virtual banking Java sample — see BANKING-DESIGN.md for the full system shape.
# This sample exercises BigDecimal money math + compareTo + setScale + throw.
JAVA_SOURCE = """
class LoanInterestService {
    public BigDecimal calculateAccruedInterest(Account account, BigDecimal annualRate, int days) {
        BigDecimal balance = account.getBalance();
        BigDecimal interest = balance.multiply(annualRate)
            .multiply(new BigDecimal(days))
            .divide(new BigDecimal(365), MathContext.DECIMAL64);
        if (interest.compareTo(BigDecimal.ZERO) < 0) {
            throw new ComplianceException("interest cannot be negative");
        }
        BigDecimal rounded = interest.setScale(2, RoundingMode.HALF_UP);
        account.setLastInterest(rounded);
        return rounded;
    }
}
"""

# Module-level placeholder — ScenarioVerificationEngine injects a fresh
# TraceCollector here for each fixture run.
_trace = None


# ─────────────────────────────────────────────────────────────────────────────
# Mock Account entity
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Account:
    accountId:    str
    balance:      Decimal
    lastInterest: Decimal | None = None

    def getBalance(self) -> Decimal:
        return self.balance

    def setLastInterest(self, v: Decimal) -> None:
        self.lastInterest = v


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth Python equivalent — manually instrumented with same anchors
# ─────────────────────────────────────────────────────────────────────────────


def ground_truth_calculate(
    account: Account,
    annualRate: Decimal,
    days: int,
) -> Decimal:
    balance = account.getBalance()
    if _trace is not None:
        _trace.step("anchor_1", {"balance": balance})

    interest = balance * annualRate * Decimal(days) / Decimal(365)
    if _trace is not None:
        _trace.step("anchor_2", {"interest": interest})

    cond = interest < Decimal(0)
    if _trace is not None:
        _trace.branch("anchor_3", bool(cond))

    if cond:
        msg = "interest cannot be negative"
        if _trace is not None:
            _trace.exception("anchor_4", "ComplianceException", str(msg))
        raise ComplianceException(msg)

    rounded = bd_set_scale(interest, 2, RoundingMode.HALF_UP)
    if _trace is not None:
        _trace.step("anchor_5", {"rounded": rounded})

    account.setLastInterest(rounded)
    return rounded


# ─────────────────────────────────────────────────────────────────────────────
# Ontology — banking entity getter types
# ─────────────────────────────────────────────────────────────────────────────


def build_ontology_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        CodeMethodRow.__table__,
    ])
    session = Session(engine)
    repo_id = "banking-loan-twin"

    session.add(CodeTypeRow(
        fqn="com.bank.entity.Account", simple_name="Account",
        package="com.bank.entity", kind="CLASS", role="entity", repo_id=repo_id,
    ))
    session.add_all([
        CodeMethodRow(
            fqn="com.bank.entity.Account#getBalance",
            name="getBalance",
            parent_type_fqn="com.bank.entity.Account",
            return_type="java.math.BigDecimal",
            repo_id=repo_id,
        ),
        CodeMethodRow(
            fqn="com.bank.entity.Account#setLastInterest",
            name="setLastInterest",
            parent_type_fqn="com.bank.entity.Account",
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
        raise RuntimeError("calculateAccruedInterest method not found")

    resolver = CompositeTypeResolver([
        OntologyTypeResolver(session, "banking-loan-twin"),
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
    """Strip self + inject banking plugin contract globals + _trace placeholder."""
    python_source = python_source.replace(
        "def calculateAccruedInterest(self, ", "def calculateAccruedInterest(",
    )
    globals_dict: dict[str, Any] = {
        "Decimal":              Decimal,
        "RoundingMode":         RoundingMode,
        "DECIMAL64":            DECIMAL64,
        "bd_set_scale":         bd_set_scale,
        "ComplianceException":  ComplianceException,
        "_trace":               None,
    }
    exec(compile(python_source, "<demo-banking>", "exec"), globals_dict)
    return globals_dict["calculateAccruedInterest"]


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
        "S1_normal": Scenario(
            fixture_id="S1_normal",
            inputs={
                "account":    Account("ACC-001", balance=Decimal("10000")),
                "annualRate": Decimal("0.05"),
                "days":       365,
            },
            expected_output=Decimal("500.00"),  # 10000 * 0.05 * 365 / 365 = 500
        ),
        "S2_partial_year": Scenario(
            fixture_id="S2_partial_year",
            inputs={
                "account":    Account("ACC-002", balance=Decimal("10000")),
                "annualRate": Decimal("0.05"),
                "days":       30,
            },
            # 10000 * 0.05 * 30 / 365 = 41.0958... → 41.10 (HALF_UP)
            expected_output=Decimal("41.10"),
        ),
        "S3_negative_rate": Scenario(
            fixture_id="S3_negative_rate",
            inputs={
                "account":    Account("ACC-003", balance=Decimal("10000")),
                "annualRate": Decimal("-0.05"),
                "days":       30,
            },
            expected_output=None,
            expected_exception=ComplianceException,
        ),
    }


def main() -> int:
    print("=" * 78)
    print("UC1 banking demo — LoanInterestService.calculateAccruedInterest (W18)")
    print("=" * 78)
    print()

    # Step 1: Ontology
    print("Step 1: Populate Code Layer ontology with Account entity methods")
    session = build_ontology_session()
    print(f"  ✓ {session.query(CodeMethodRow).count()} method rows seeded")
    print()

    # Step 2: Translate (with trace)
    print("Step 2: Translate JAVA_SOURCE with trace instrumentation")
    py_source, meta = translate_method(session, with_trace=True)
    if meta["locked"]:
        print(f"  ABORT — signature_locked. notes={meta['notes']}")
        return 1
    print(f"  ✓ translated — {len(py_source.split(chr(10)))} lines, "
          f"signature_locked={meta['locked']}")
    print()
    print("Generated Python source:")
    for line in py_source.split("\n"):
        print(f"  | {line}")
    print()

    # Step 3: Compile
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

    # Step 4-7: Proposal lifecycle
    print("Step 4-7: Proposal full lifecycle")
    prop = Proposal(
        type="code_change",
        description="Translate LoanInterestService.calculateAccruedInterest (banking)",
        plugin="banking",
        code_diff={"method_fqn": "com.bank.service.LoanInterestService#calculateAccruedInterest"},
    )
    prop_id = integrator.submit_proposal(prop)
    print(f"  DRAFT → PROPOSED ✓")

    # Rebuild fixtures because banking fixtures share account objects across calls
    engine.fixtures = make_scenarios()
    oracle = integrator.request_oracle(prop_id, list(fixtures.keys()))
    print(f"  PROPOSED → ORACLED ✓ (aggregate={oracle.aggregate_status})")
    for fid, r in oracle.by_fixture.items():
        print(f"    {fid:<18} {r.status:<12} output={r.output_diff.summary}")
        print(f"    {'':18} {'':12} trace= {r.trace_diff.summary}")

    integrator.review_proposal(prop_id, UserFeedback(
        decision="ACCEPT", timestamp=datetime.now(timezone.utc),
        user="demo-user",
        comments=f"all {len(fixtures)} scenarios PASS",
    ))
    print(f"  ORACLED → ACCEPTED ✓")

    revision_id = integrator.merge_proposal(
        prop_id=prop_id,
        ontology_revision="banking@2026-05-13",
        code_revision="virtual:LoanInterestService-v1",
        schema_revision="alembic:banking-baseline",
        created_by="demo-user",
    )
    final = integrator.get_proposal(prop_id)
    print(f"  ACCEPTED → MERGED ✓ revision={revision_id}")
    print()

    # Step 8: Verdict
    if (
        oracle.aggregate_status == "PASS"
        and final.state == "MERGED"
        and integrator.revision_store.get(revision_id) is not None
    ):
        print("✓ Final verdict: PASS — banking system end-to-end")
        print(f"  G1 gate progress: v2 (W13-W17) + banking (W18) — 2 / 3 systems")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
