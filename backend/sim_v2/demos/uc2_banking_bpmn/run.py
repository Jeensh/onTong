"""UC2 banking BPMN — bytecode generation activation (W23, G2 gate close).

Demonstrates ADR-009 meta-programming (bytecode / dynamic class) in action:
  1. Define a virtual Activiti BPMN process (loan-approval-process) with 3
     service tasks, each referencing an `activiti:class` delegate FQN.
  2. Invoke `banking.bpmn_dynamic_class` handler (W6.3) — produces a Python
     class registry dict + `lookup_bpmn_delegate(task_id)` function.
  3. Compose with the real Python delegate classes injected into exec scope.
  4. Run the process via a tiny ProcessEngine that walks tasks, looks up
     delegates via the emitted lookup, and calls `execute(context)`.
  5. Run 4 scenarios — happy path / low credit / high risk / unknown task.

ADR-009 핵심: Activiti runtime 의 `Class.forName("com.foo.MyDelegate").newInstance()`
같은 reflection-based dynamic class loading → Python 의 explicit dict lookup 으로 대체.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc2_banking_bpmn.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from backend.sim_v2.core.synthesizer.bytecode.registry import (
    BytecodeContext,
    get_default_registry as get_bytecode_registry,
)
from backend.sim_v2.plugins.banking.contracts.exception import BpmnDeploymentException

# Trigger banking bytecode handler auto-registration (W6.3)
import backend.sim_v2.plugins.banking.bytecode  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Activiti BPMN process metadata (would normally come from .bpmn20.xml)
# ─────────────────────────────────────────────────────────────────────────────


PROCESS_ID = "loan-approval-process"


PROCESS_FLOW = [
    "credit_check_task",
    "risk_assessment_task",
    "loan_approval_task",
]


DELEGATES = {
    "credit_check_task":    "com.bank.CreditCheckDelegate",
    "risk_assessment_task": "com.bank.RiskAssessmentDelegate",
    "loan_approval_task":   "com.bank.LoanApprovalDelegate",
}


# ─────────────────────────────────────────────────────────────────────────────
# Python delegate classes (JavaDelegate equivalent — execute(context))
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class LoanContext:
    """ProcessEngine 가 task 간 전달하는 mutable state — Activiti DelegateExecution 대응."""
    applicant_name:    str
    credit_score:      int
    annual_income:     Decimal
    loan_amount:       Decimal
    debt_to_income:    Decimal
    # Filled in by delegates as the flow progresses
    credit_decision:   str = ""
    risk_tier:         str = ""
    final_decision:    str = ""
    log:               list[str] = field(default_factory=list)


class CreditCheckDelegate:
    """credit_check_task: low score → DECLINED, otherwise PASS."""

    def execute(self, ctx: LoanContext) -> None:
        if ctx.credit_score < 600:
            ctx.credit_decision = "DECLINED"
            ctx.final_decision  = "DECLINED"
            ctx.log.append(f"CreditCheck: score={ctx.credit_score} → DECLINED (terminal)")
        else:
            ctx.credit_decision = "PASS"
            ctx.log.append(f"CreditCheck: score={ctx.credit_score} → PASS")


class RiskAssessmentDelegate:
    """risk_assessment_task: high DTI → HIGH, mid → MEDIUM, else LOW."""

    def execute(self, ctx: LoanContext) -> None:
        dti = ctx.debt_to_income
        if dti > Decimal("0.5"):
            ctx.risk_tier = "HIGH"
        elif dti > Decimal("0.3"):
            ctx.risk_tier = "MEDIUM"
        else:
            ctx.risk_tier = "LOW"
        ctx.log.append(f"RiskAssessment: DTI={dti} → tier={ctx.risk_tier}")


class LoanApprovalDelegate:
    """loan_approval_task: final decision based on accumulated context."""

    def execute(self, ctx: LoanContext) -> None:
        if ctx.risk_tier == "HIGH":
            ctx.final_decision = "ESCALATE"
        elif ctx.risk_tier == "MEDIUM" and ctx.loan_amount > Decimal("300000"):
            ctx.final_decision = "MANUAL_REVIEW"
        else:
            ctx.final_decision = "APPROVED"
        ctx.log.append(f"LoanApproval: tier={ctx.risk_tier} amount={ctx.loan_amount} → {ctx.final_decision}")


# ─────────────────────────────────────────────────────────────────────────────
# Invoke W6.3 handler → get emitted registry source + lookup function
# ─────────────────────────────────────────────────────────────────────────────


def synthesize_registry() -> tuple[str, Any]:
    """Returns (emitted_python, lookup_callable).

    Invokes W6.3 BpmnDynamicClassHandler via the bytecode registry, then
    exec's the emitted source with the real Python delegate classes bound
    under their mangled FQN identifiers (com_bank_X — Activiti class loader
    proxy).
    """
    registry = get_bytecode_registry()
    handler = registry.get("banking.bpmn_dynamic_class")
    output = handler.synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        target_class=PROCESS_ID,
        pattern_args={
            "process_id": PROCESS_ID,
            "delegates":  DELEGATES,
        },
        plugin_name="banking",
    ))
    emitted = output.python_source

    # The emitted dict literal references bare identifiers like com_bank_CreditCheckDelegate.
    # Bind those to the actual Python classes (Activiti class loader equivalent).
    g: dict[str, Any] = {
        "com_bank_CreditCheckDelegate":    CreditCheckDelegate,
        "com_bank_RiskAssessmentDelegate": RiskAssessmentDelegate,
        "com_bank_LoanApprovalDelegate":   LoanApprovalDelegate,
    }
    exec(compile(emitted, "<demo-bpmn>", "exec"), g)
    return emitted, g["lookup_bpmn_delegate"]


# ─────────────────────────────────────────────────────────────────────────────
# Tiny ProcessEngine — walks PROCESS_FLOW + delegates to looked-up classes
# ─────────────────────────────────────────────────────────────────────────────


def run_process(ctx: LoanContext, lookup) -> LoanContext:
    """Walk the process tasks in order; let each delegate mutate ctx.

    Terminates early if a delegate sets `final_decision` (e.g. credit DECLINED).
    """
    for task_id in PROCESS_FLOW:
        delegate_cls = lookup(task_id)
        delegate_cls().execute(ctx)
        if ctx.final_decision:
            break
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Scenario:
    name:             str
    ctx:              LoanContext
    expected:         str
    expect_exception: type | None = None
    override_flow:    list[str] | None = None


def make_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="happy path → APPROVED",
            ctx=LoanContext(
                applicant_name="Alice", credit_score=720, annual_income=Decimal("120000"),
                loan_amount=Decimal("100000"), debt_to_income=Decimal("0.25"),
            ),
            expected="APPROVED",
        ),
        Scenario(
            name="low credit → DECLINED (early terminate)",
            ctx=LoanContext(
                applicant_name="Bob", credit_score=550, annual_income=Decimal("80000"),
                loan_amount=Decimal("50000"), debt_to_income=Decimal("0.2"),
            ),
            expected="DECLINED",
        ),
        Scenario(
            name="high DTI → ESCALATE",
            ctx=LoanContext(
                applicant_name="Carol", credit_score=700, annual_income=Decimal("60000"),
                loan_amount=Decimal("80000"), debt_to_income=Decimal("0.6"),
            ),
            expected="ESCALATE",
        ),
        Scenario(
            name="medium risk + large amount → MANUAL_REVIEW",
            ctx=LoanContext(
                applicant_name="Dave", credit_score=710, annual_income=Decimal("150000"),
                loan_amount=Decimal("400000"), debt_to_income=Decimal("0.4"),
            ),
            expected="MANUAL_REVIEW",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 78)
    print("UC2 banking BPMN — bytecode dynamic class activation (W23, G2 close)")
    print("=" * 78)
    print()

    print(f"Step 1: Activiti BPMN process = {PROCESS_ID!r}")
    print(f"  flow: {' → '.join(PROCESS_FLOW)}")
    for task_id, fqn in DELEGATES.items():
        print(f"  • {task_id:<24} → {fqn}")
    print()

    print("Step 2: Invoke banking.bpmn_dynamic_class handler (W6.3)")
    emitted, lookup = synthesize_registry()
    print(f"  ✓ emitted {len(emitted.splitlines())} lines of Python registry + lookup")
    print()
    print("Generated registry source:")
    for line in emitted.split("\n"):
        print(f"  | {line}")
    print()

    print("Step 3: Validate registry lookup for each task_id")
    for task_id in PROCESS_FLOW:
        cls = lookup(task_id)
        print(f"  • lookup({task_id!r}) → {cls.__name__}")
    print()

    print("Step 4: Validate SIGNATURE_LOCKED fallback for unknown task_id")
    try:
        lookup("nonexistent_task")
        print("  ✗ expected BpmnDeploymentException — none raised")
        return 1
    except BpmnDeploymentException as e:
        print(f"  ✓ correctly raised BpmnDeploymentException: {e}")
    print()

    print("Step 5: Run scenarios end-to-end via ProcessEngine")
    print()
    print(f"  {'Scenario':<48} {'Decision':<18} {'Verdict':<10}")
    print(f"  {'-' * 48} {'-' * 18} {'-' * 10}")
    all_pass = True
    for scenario in make_scenarios():
        try:
            run_process(scenario.ctx, lookup)
            actual = scenario.ctx.final_decision
            ok = actual == scenario.expected
        except Exception as e:
            actual = f"<{type(e).__name__}>"
            ok = False
        verdict = "PASS" if ok else f"FAIL"
        if not ok:
            all_pass = False
        print(f"  {scenario.name:<48} {actual:<18} {verdict:<10}")

    print()
    if all_pass:
        print("✓ Final verdict: PASS — BPMN dynamic class activation works end-to-end")
        print("  G2 gate progress: ADR-006 + ADR-007 + ADR-008 + ADR-009 — 4 / 4 ✓ CLOSED")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
