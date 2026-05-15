"""UC2 banking saga — @Compensable annotation activation (W20, G2 prereq).

Demonstrates ADR-007 meta-programming (annotation processing) in action:
  1. Translate `TransferService.transfer` Java method (with @Compensable)
  2. Translate `TransferService.refund` (the compensation method)
  3. Invoke `banking.compensable` annotation handler (W6.1) to produce a
     saga-wrap function `_compensable_wrap(__fn)`
  4. Apply wrap to `transfer` so failures trigger `refund` + SagaCompensatedException
  5. Run 2 scenarios:
     - success: transfer completes, refund NOT called
     - compliance_failure: transfer raises, refund called, SagaCompensatedException

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc2_banking_saga.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import tree_sitter_java as tsjava
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.contracts.base import (
    DECIMAL64,
    RoundingMode,
    bd_set_scale,
)
from backend.sim_v2.core.synthesizer.annotations.registry import (
    AnnotationContext,
    get_default_registry as get_annotation_registry,
)
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.ontology_type_resolver import OntologyTypeResolver
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    CompositeTypeResolver,
)

# Trigger banking annotation auto-registration (W6.1 CompensableHandler)
import backend.sim_v2.plugins.banking.annotations  # noqa: F401

from backend.sim_v2.plugins.banking.contracts.exception import (
    ComplianceException,
    SagaCompensatedException,
)


JAVA_LANGUAGE = Language(tsjava.language())


JAVA_SOURCE = """
class TransferService {
    public void transfer(Account sender, Account receiver, BigDecimal amount) {
        sender.setBalance(sender.getBalance().subtract(amount));
        receiver.setBalance(receiver.getBalance().add(amount));
        if (receiver.getBalance().compareTo(new BigDecimal("100000")) > 0) {
            throw new ComplianceException("receiver balance exceeds limit");
        }
    }

    public void refund(Account sender, Account receiver, BigDecimal amount) {
        sender.setBalance(sender.getBalance().add(amount));
        receiver.setBalance(receiver.getBalance().subtract(amount));
    }
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Mock Account
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Account:
    accountId: str
    balance:   Decimal
    def getBalance(self) -> Decimal: return self.balance
    def setBalance(self, v: Decimal) -> None: self.balance = v


# ─────────────────────────────────────────────────────────────────────────────
# Ontology
# ─────────────────────────────────────────────────────────────────────────────


def build_ontology_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        CodeTypeRow.__table__, CodeMethodRow.__table__,
    ])
    s = Session(engine)
    repo_id = "banking-saga"
    s.add(CodeTypeRow(
        fqn="com.bank.Account", simple_name="Account",
        package="com.bank", kind="CLASS", role="entity", repo_id=repo_id,
    ))
    s.add_all([
        CodeMethodRow(
            fqn="com.bank.Account#getBalance", name="getBalance",
            parent_type_fqn="com.bank.Account",
            return_type="java.math.BigDecimal", repo_id=repo_id,
        ),
        CodeMethodRow(
            fqn="com.bank.Account#setBalance", name="setBalance",
            parent_type_fqn="com.bank.Account",
            return_type="void", repo_id=repo_id,
        ),
    ])
    s.commit()
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Translate methods + invoke annotation handler
# ─────────────────────────────────────────────────────────────────────────────


def _find_methods(tree):
    """Return list of (method_name, method_node)."""
    out: list[tuple[str, Any]] = []
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    n = m.child_by_field_name("name")
                    out.append((n.text.decode(), m))
    return out


def translate_service(session: Session) -> tuple[dict[str, str], str]:
    """Translate both methods + invoke @Compensable handler.

    Returns (method_sources: dict[name → python_source], wrapper_source: str).
    """
    tree = Parser(JAVA_LANGUAGE).parse(JAVA_SOURCE.encode())
    methods = _find_methods(tree)

    resolver = CompositeTypeResolver([
        OntologyTypeResolver(session, "banking-saga"),
        BigDecimalAwareResolver(),
    ])
    method_sources: dict[str, str] = {}
    for name, node in methods:
        tr = JavaToPythonTranslator(type_resolver=resolver).translate(node, indent=0)
        method_sources[name] = tr.python_source

    # Invoke the @Compensable annotation handler for `transfer` with
    # compensationMethod="refund". In production this would be triggered by
    # the translator after detecting `@Compensable` on the method declaration;
    # for W20 we drive it explicitly to keep the wiring visible.
    annotation_registry = get_annotation_registry()
    handler = annotation_registry.get("bank.annotation.Compensable")
    ctx = AnnotationContext(
        annotation_fqn="bank.annotation.Compensable",
        annotation_args={"compensationMethod": "refund"},
        target_kind="method",
        target_metadata={
            "class_fqn":   "com.bank.TransferService",
            "method_name": "transfer",
        },
        plugin_name="banking",
    )
    wrap_output = handler.handle(ctx)
    wrapper_source = wrap_output.python_source
    return method_sources, wrapper_source


# ─────────────────────────────────────────────────────────────────────────────
# Compose into a Service class
# ─────────────────────────────────────────────────────────────────────────────


def build_service(method_sources: dict[str, str], wrapper_source: str):
    """Compile both methods + wrapper, attach to a Service class with @Compensable
    applied to `transfer`.
    """
    # Strip `self, ` from each `def transfer(self, ...)` so they're top-level fns
    transfer_src = method_sources["transfer"]
    refund_src = method_sources["refund"]

    g: dict[str, Any] = {
        "Decimal":               Decimal,
        "RoundingMode":          RoundingMode,
        "DECIMAL64":             DECIMAL64,
        "bd_set_scale":          bd_set_scale,
        "ComplianceException":   ComplianceException,
        "SagaCompensatedException": SagaCompensatedException,
    }
    # exec both method bodies (with self) and the wrapper definition
    full = (
        transfer_src + "\n\n"
        + refund_src + "\n\n"
        + wrapper_source + "\n\n"
        # Apply wrap
        "transfer = _compensable_wrap(transfer)\n"
    )
    exec(compile(full, "<demo-saga>", "exec"), g)

    # Build a Service object that exposes transfer + refund as bound methods
    class TransferService:
        pass
    TransferService.transfer = g["transfer"]
    TransferService.refund   = g["refund"]
    return TransferService()


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Scenario:
    name: str
    sender:   Account
    receiver: Account
    amount:   Decimal
    expect_exception: type | None = None
    expect_sender_balance: Decimal | None = None
    expect_receiver_balance: Decimal | None = None


def make_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="success (no compensation)",
            sender=Account("S1", balance=Decimal("1000")),
            receiver=Account("R1", balance=Decimal("500")),
            amount=Decimal("200"),
            # post: sender=800, receiver=700, no exception
            expect_sender_balance=Decimal("800"),
            expect_receiver_balance=Decimal("700"),
        ),
        Scenario(
            name="compliance_failure (compensation triggered)",
            sender=Account("S2", balance=Decimal("200000")),
            receiver=Account("R2", balance=Decimal("99000")),
            amount=Decimal("5000"),
            # transfer: sender=195000, receiver=104000 (exceeds limit) → raise
            # refund:   sender=200000, receiver=99000 (restored) → SagaCompensatedException
            expect_exception=SagaCompensatedException,
            expect_sender_balance=Decimal("200000"),
            expect_receiver_balance=Decimal("99000"),
        ),
    ]


def main() -> int:
    print("=" * 78)
    print("UC2 banking saga — @Compensable annotation activation (W20, G2 prereq)")
    print("=" * 78)
    print()

    print("Step 1: Populate Code Layer ontology")
    session = build_ontology_session()
    print(f"  ✓ {session.query(CodeMethodRow).count()} method rows seeded")
    print()

    print("Step 2: Translate transfer + refund + invoke @Compensable handler (W6.1)")
    method_sources, wrapper_source = translate_service(session)
    print(f"  ✓ translated transfer ({len(method_sources['transfer'].split(chr(10)))} lines)")
    print(f"  ✓ translated refund   ({len(method_sources['refund'].split(chr(10)))} lines)")
    print(f"  ✓ @Compensable wrapper ({len(wrapper_source.split(chr(10)))} lines)")
    print()
    print("Translated transfer:")
    for line in method_sources["transfer"].split("\n"):
        print(f"  | {line}")
    print()
    print("Translated refund:")
    for line in method_sources["refund"].split("\n"):
        print(f"  | {line}")
    print()
    print("@Compensable wrapper:")
    for line in wrapper_source.split("\n"):
        print(f"  | {line}")
    print()

    print("Step 3: Compose Service + apply @Compensable wrap")
    service = build_service(method_sources, wrapper_source)
    print(f"  ✓ service ready — transfer is now compensable")
    print()

    print("Step 4: Run scenarios")
    print()
    print(f"  {'Scenario':<45} {'Outcome':<18} {'Sender':<12} {'Receiver':<12}")
    print(f"  {'-' * 45} {'-' * 18} {'-' * 12} {'-' * 12}")
    all_pass = True
    for scenario in make_scenarios():
        exc: Exception | None = None
        try:
            service.transfer(scenario.sender, scenario.receiver, scenario.amount)
        except Exception as e:
            exc = e

        # Verify outcome
        if scenario.expect_exception is not None:
            if exc is not None and isinstance(exc, scenario.expect_exception):
                outcome = f"PASS ({type(exc).__name__})"
            else:
                outcome = f"FAIL (exc={type(exc).__name__ if exc else None})"
                all_pass = False
        else:
            if exc is None:
                outcome = "PASS"
            else:
                outcome = f"FAIL ({type(exc).__name__}: {exc})"
                all_pass = False

        # Verify balances
        if (
            scenario.sender.balance != scenario.expect_sender_balance
            or scenario.receiver.balance != scenario.expect_receiver_balance
        ):
            outcome += " [BAL_MISMATCH]"
            all_pass = False

        print(f"  {scenario.name:<45} {outcome:<18} "
              f"{str(scenario.sender.balance):<12} {str(scenario.receiver.balance):<12}")

    print()
    if all_pass:
        print("✓ Final verdict: PASS — @Compensable annotation activation works end-to-end")
        print("  G2 gate progress: ADR-007 (annotation) — 1 / 4 meta-programming areas covered")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
