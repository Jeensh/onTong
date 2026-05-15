"""UC2 banking BPMN demo verification — W23.3 (G2 gate close).

Validates ADR-009 (bytecode / dynamic class) end-to-end activation:
  - banking.bpmn_dynamic_class handler (W6.3) is registered
  - Handler emits a Python registry dict + lookup_bpmn_delegate function
  - Emitted code compiles + executes against real delegate classes
  - ProcessEngine walks PROCESS_FLOW + dispatches each task via the lookup
  - Happy path / low-credit (early terminate) / high-DTI / medium-risk all pass
  - Unknown task_id → BpmnDeploymentException (SIGNATURE_LOCKED runtime guard)
"""
from __future__ import annotations

import importlib
from decimal import Decimal

import pytest

from backend.sim_v2.core.synthesizer.bytecode.registry import (
    BytecodeContext,
    get_default_registry as get_bytecode_registry,
)
from backend.sim_v2.plugins.banking.contracts.exception import BpmnDeploymentException


@pytest.fixture(autouse=True)
def _ensure_banking_bytecode_registered():
    """Reload to recover from cross-test registry resets.

    test_banking_extensions.py uses an autouse fixture that calls
    reset_bytecode() between tests; cross-test ordering may leave the bytecode
    registry empty when these demo tests run. Reload here to guarantee
    banking.bpmn_dynamic_class is back.
    """
    import backend.sim_v2.plugins.banking.bytecode as banking_byte
    importlib.reload(banking_byte)
    yield


from backend.sim_v2.demos.uc2_banking_bpmn.run import (
    DELEGATES,
    PROCESS_FLOW,
    PROCESS_ID,
    CreditCheckDelegate,
    LoanApprovalDelegate,
    LoanContext,
    RiskAssessmentDelegate,
    Scenario,
    main,
    make_scenarios,
    run_process,
    synthesize_registry,
)


def test_demo_main_returns_zero():
    """The W23 demo main() exits 0 — all 4 scenarios PASS."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration + invocation
# ─────────────────────────────────────────────────────────────────────────────


def test_handler_registered():
    """W6.3 auto-registers banking.bpmn_dynamic_class on import."""
    registry = get_bytecode_registry()
    handler = registry.get("banking.bpmn_dynamic_class")
    assert handler is not None
    assert handler.name == "banking.bpmn_dynamic_class"


def test_handler_emits_registry_and_lookup():
    """Handler transforms DELEGATES dict into a Python registry + lookup function."""
    registry = get_bytecode_registry()
    handler = registry.get("banking.bpmn_dynamic_class")
    out = handler.synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        pattern_args={"process_id": PROCESS_ID, "delegates": DELEGATES},
        plugin_name="banking",
    ))
    src = out.python_source
    # Registry dict variable mangled from process id
    assert "_BPMN_REGISTRY_LOAN_APPROVAL_PROCESS" in src
    # All 3 task ids appear as dict keys
    for task_id in PROCESS_FLOW:
        assert f"'{task_id}'" in src
    # All 3 delegate class FQNs appear as mangled identifiers
    for fqn in DELEGATES.values():
        assert fqn.replace(".", "_") in src
    # The lookup function + import are emitted
    assert "def lookup_bpmn_delegate(task_id: str):" in src
    assert "BpmnDeploymentException" in src


def test_handler_emitted_source_compiles():
    """Emitted Python must actually compile (nested f-string quoting regression)."""
    registry = get_bytecode_registry()
    handler = registry.get("banking.bpmn_dynamic_class")
    out = handler.synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        pattern_args={"process_id": PROCESS_ID, "delegates": DELEGATES},
        plugin_name="banking",
    ))
    compile(out.python_source, "<test>", "exec")  # raises SyntaxError on failure


def test_handler_missing_process_id_signature_locked():
    """Missing process_id → SIGNATURE_LOCKED (ADR-013 strong-assumption guard)."""
    registry = get_bytecode_registry()
    handler = registry.get("banking.bpmn_dynamic_class")
    out = handler.synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        pattern_args={"delegates": DELEGATES},
    ))
    assert out.signature_locked is True
    assert "SIGNATURE_LOCKED" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Composition + lookup
# ─────────────────────────────────────────────────────────────────────────────


def test_synthesize_registry_returns_callable_lookup():
    emitted, lookup = synthesize_registry()
    assert callable(lookup)
    assert "lookup_bpmn_delegate" in emitted


def test_lookup_returns_each_delegate_class():
    _, lookup = synthesize_registry()
    assert lookup("credit_check_task")    is CreditCheckDelegate
    assert lookup("risk_assessment_task") is RiskAssessmentDelegate
    assert lookup("loan_approval_task")   is LoanApprovalDelegate


def test_lookup_unknown_task_raises_bpmn_deployment_exception():
    _, lookup = synthesize_registry()
    with pytest.raises(BpmnDeploymentException) as exc_info:
        lookup("nonexistent_task")
    msg = str(exc_info.value)
    assert "nonexistent_task" in msg
    assert PROCESS_ID in msg


# ─────────────────────────────────────────────────────────────────────────────
# Each scenario through the ProcessEngine
# ─────────────────────────────────────────────────────────────────────────────


def test_scenario_happy_path_approved():
    _, lookup = synthesize_registry()
    ctx = LoanContext(
        applicant_name="Alice", credit_score=720, annual_income=Decimal("120000"),
        loan_amount=Decimal("100000"), debt_to_income=Decimal("0.25"),
    )
    run_process(ctx, lookup)
    assert ctx.final_decision == "APPROVED"
    # All three delegates ran
    assert len(ctx.log) == 3


def test_scenario_low_credit_short_circuits():
    """Credit check sets final_decision = DECLINED → engine breaks early."""
    _, lookup = synthesize_registry()
    ctx = LoanContext(
        applicant_name="Bob", credit_score=550, annual_income=Decimal("80000"),
        loan_amount=Decimal("50000"), debt_to_income=Decimal("0.2"),
    )
    run_process(ctx, lookup)
    assert ctx.final_decision == "DECLINED"
    assert ctx.credit_decision == "DECLINED"
    # Risk + approval delegates did NOT run
    assert ctx.risk_tier == ""
    assert len(ctx.log) == 1


def test_scenario_high_dti_escalate():
    _, lookup = synthesize_registry()
    ctx = LoanContext(
        applicant_name="Carol", credit_score=700, annual_income=Decimal("60000"),
        loan_amount=Decimal("80000"), debt_to_income=Decimal("0.6"),
    )
    run_process(ctx, lookup)
    assert ctx.final_decision == "ESCALATE"
    assert ctx.risk_tier == "HIGH"


def test_scenario_medium_risk_large_amount_manual_review():
    _, lookup = synthesize_registry()
    ctx = LoanContext(
        applicant_name="Dave", credit_score=710, annual_income=Decimal("150000"),
        loan_amount=Decimal("400000"), debt_to_income=Decimal("0.4"),
    )
    run_process(ctx, lookup)
    assert ctx.final_decision == "MANUAL_REVIEW"
    assert ctx.risk_tier == "MEDIUM"


def test_all_scenarios_pass():
    _, lookup = synthesize_registry()
    for scenario in make_scenarios():
        run_process(scenario.ctx, lookup)
        assert scenario.ctx.final_decision == scenario.expected, (
            f"{scenario.name}: got {scenario.ctx.final_decision}, expected {scenario.expected}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# G2 gate close marker
# ─────────────────────────────────────────────────────────────────────────────


def test_g2_gate_adr_009_bytecode_covered():
    """G2 gate ADR-009 (bytecode / dynamic class) — W6.3 handler activates here.

    With W20 (ADR-007), W21 (ADR-008), W22 (ADR-006), and W23 (ADR-009) all
    PASSing, the G2 gate is CLOSED — all 4 meta-programming areas demonstrated.
    """
    assert main() == 0
