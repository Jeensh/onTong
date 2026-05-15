"""UC2 banking Drools — polymorphic dispatch activation (W22, G2 prereq).

Demonstrates ADR-006 meta-programming (polymorphic dispatch) in action:
  1. Define a Drools-style loan eligibility kbase (rules + LHS/RHS)
  2. Invoke `banking.drools_kbase_lookup` dispatcher (W6.2) — produces an
     equivalent Python if-elif decision tree
  3. Wrap into `evaluate_eligibility(applicant, loan)` function
  4. Run 5 scenarios — one per rule + default approve

ADR-006 의 핵심: Java side 의 `kbase.newKieSession(); session.insert(...); session.fireAllRules();`
같은 opaque KIE container 호출 → Python decision tree 로 substitution.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc2_banking_drools.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    DispatchContext,
    get_default_registry as get_dispatcher_registry,
)

# Trigger banking dispatcher auto-registration (W6.2 DroolsKbaseLookupDispatcher)
import backend.sim_v2.plugins.banking.dispatchers  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Banking domain mocks
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Applicant:
    name:         str
    age:          int
    credit_score: int


@dataclass
class Loan:
    amount:    Decimal
    term_months: int


# ─────────────────────────────────────────────────────────────────────────────
# KIE kbase — 4 rules + implicit default
# ─────────────────────────────────────────────────────────────────────────────


KBASE_NAME = "loan-approval-kbase"

RULES = [
    {
        "name": "low_credit_decline",
        "lhs":  "applicant.credit_score < 600",
        "rhs":  "decision = 'DECLINED'",
    },
    {
        "name": "high_amount_escalate",
        "lhs":  "loan.amount > 500_000",
        "rhs":  "decision = 'ESCALATE'",
    },
    {
        "name": "young_applicant_review",
        "lhs":  "applicant.age < 25",
        "rhs":  "decision = 'MANUAL_REVIEW'",
    },
    {
        "name": "long_term_flag",
        "lhs":  "loan.term_months > 360",
        "rhs":  "decision = 'EXTENDED_TERM_REVIEW'",
    },
    # implicit default: decision = 'APPROVED' (from dispatcher)
]


# ─────────────────────────────────────────────────────────────────────────────
# Invoke dispatcher + compose evaluator
# ─────────────────────────────────────────────────────────────────────────────


def synthesize_evaluator() -> tuple[str, Any]:
    """Returns (emitted_python, evaluator_callable).

    Invokes W6.2 DroolsKbaseLookupDispatcher via the synthesizer dispatch registry,
    then wraps the emitted code in a function.
    """
    registry = get_dispatcher_registry()
    dispatcher = registry.get("banking.drools_kbase_lookup")
    output = dispatcher.synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={
            "kbase_name": KBASE_NAME,
            "rules":      RULES,
        },
        plugin_name="banking",
    ))
    emitted = output.python_source

    # Wrap in a function — emitted code populates `decision` local.
    # Indent each line, prefix with `def evaluate(applicant, loan):`.
    indented = "\n".join("    " + line for line in emitted.split("\n"))
    full_function = (
        "def evaluate_eligibility(applicant, loan):\n"
        + indented + "\n"
        + "    return decision\n"
    )
    g: dict[str, Any] = {"Decimal": Decimal}
    exec(compile(full_function, "<demo-drools>", "exec"), g)
    return full_function, g["evaluate_eligibility"]


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Scenario:
    name:       str
    applicant:  Applicant
    loan:       Loan
    expected:   str


def make_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="low credit → DECLINED",
            applicant=Applicant("Alice", age=35, credit_score=550),
            loan=Loan(amount=Decimal("100000"), term_months=120),
            expected="DECLINED",
        ),
        Scenario(
            name="high amount → ESCALATE",
            applicant=Applicant("Bob", age=40, credit_score=720),
            loan=Loan(amount=Decimal("600000"), term_months=120),
            expected="ESCALATE",
        ),
        Scenario(
            name="young applicant → MANUAL_REVIEW",
            applicant=Applicant("Carol", age=22, credit_score=700),
            loan=Loan(amount=Decimal("50000"), term_months=120),
            expected="MANUAL_REVIEW",
        ),
        Scenario(
            name="long term → EXTENDED_TERM_REVIEW",
            applicant=Applicant("Dave", age=45, credit_score=750),
            loan=Loan(amount=Decimal("100000"), term_months=480),
            expected="EXTENDED_TERM_REVIEW",
        ),
        Scenario(
            name="default → APPROVED",
            applicant=Applicant("Eve", age=35, credit_score=720),
            loan=Loan(amount=Decimal("100000"), term_months=240),
            expected="APPROVED",
        ),
    ]


def main() -> int:
    print("=" * 78)
    print("UC2 banking Drools — polymorphic dispatch activation (W22, G2 prereq)")
    print("=" * 78)
    print()

    print(f"Step 1: KIE kbase = {KBASE_NAME!r} with {len(RULES)} rules")
    for r in RULES:
        print(f"  • {r['name']:<28} when {r['lhs']:<35} → {r['rhs']}")
    print()

    print("Step 2: Invoke banking.drools_kbase_lookup dispatcher (W6.2)")
    full_function, evaluator = synthesize_evaluator()
    print(f"  ✓ emitted {len(full_function.split(chr(10)))} lines of Python")
    print()
    print("Generated evaluator:")
    for line in full_function.split("\n"):
        print(f"  | {line}")
    print()

    print("Step 3: Run 5 scenarios")
    print()
    print(f"  {'Scenario':<42} {'Decision':<26} {'Verdict':<8}")
    print(f"  {'-' * 42} {'-' * 26} {'-' * 8}")
    all_pass = True
    for scenario in make_scenarios():
        actual = evaluator(scenario.applicant, scenario.loan)
        ok = actual == scenario.expected
        verdict = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  {scenario.name:<42} {actual:<26} {verdict:<8}")

    print()
    if all_pass:
        print("✓ Final verdict: PASS — Drools dispatcher activation works end-to-end")
        print("  G2 gate progress: ADR-006 + ADR-007 + ADR-008 — 3 / 4 meta-programming areas")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
