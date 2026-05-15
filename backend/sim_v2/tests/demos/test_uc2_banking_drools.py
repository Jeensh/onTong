"""UC2 banking Drools demo verification — W22.3.

Validates ADR-006 (polymorphic dispatch) end-to-end activation:
  - banking.drools_kbase_lookup dispatcher (W6.2) is registered
  - Dispatcher emits Python if-elif chain from KIE-style rule list
  - Emitted code compiles + executes as evaluate_eligibility(applicant, loan)
  - Each rule + the implicit default branch fire on the right scenarios
"""
from __future__ import annotations

import importlib
from decimal import Decimal

import pytest

from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    DispatchContext,
    get_default_registry as get_dispatcher_registry,
)


@pytest.fixture(autouse=True)
def _ensure_banking_dispatcher_registered():
    """Reload to recover from cross-test registry resets.

    test_banking_extensions.py uses an autouse fixture that calls
    reset_dispatchers() between tests; cross-test ordering may leave the
    dispatcher registry empty when these demo tests run. Reload here to
    guarantee banking.drools_kbase_lookup is back.
    """
    import backend.sim_v2.plugins.banking.dispatchers as banking_disp
    importlib.reload(banking_disp)
    yield


from backend.sim_v2.demos.uc2_banking_drools.run import (
    Applicant,
    KBASE_NAME,
    Loan,
    RULES,
    Scenario,
    main,
    make_scenarios,
    synthesize_evaluator,
)


def test_demo_main_returns_zero():
    """The W22 demo main() exits 0 — all 5 scenarios PASS."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher registration + invocation
# ─────────────────────────────────────────────────────────────────────────────


def test_dispatcher_registered():
    """W6.2 auto-registers banking.drools_kbase_lookup on import."""
    registry = get_dispatcher_registry()
    dispatcher = registry.get("banking.drools_kbase_lookup")
    assert dispatcher is not None
    assert dispatcher.name == "banking.drools_kbase_lookup"


def test_dispatcher_emits_decision_tree():
    """Dispatcher transforms RULES into a Python if-elif chain with default."""
    registry = get_dispatcher_registry()
    dispatcher = registry.get("banking.drools_kbase_lookup")
    output = dispatcher.synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={"kbase_name": KBASE_NAME, "rules": RULES},
        plugin_name="banking",
    ))
    src = output.python_source
    # Each rule appears as an if/elif branch
    assert "if applicant.credit_score < 600:" in src
    assert "elif loan.amount > 500_000:" in src
    assert "elif applicant.age < 25:" in src
    assert "elif loan.term_months > 360:" in src
    # Default branch
    assert "else:" in src
    assert "decision = 'APPROVED'" in src


def test_dispatcher_kbase_name_in_emitted_comment():
    """Emitted Python includes a comment referencing the original kbase name."""
    registry = get_dispatcher_registry()
    dispatcher = registry.get("banking.drools_kbase_lookup")
    output = dispatcher.synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={"kbase_name": KBASE_NAME, "rules": RULES},
        plugin_name="banking",
    ))
    assert f"'{KBASE_NAME}'" in output.python_source


def test_dispatcher_without_kbase_name_is_signature_locked():
    """Missing kbase_name → SIGNATURE_LOCKED output (ADR-006 strong-assumption guard)."""
    registry = get_dispatcher_registry()
    dispatcher = registry.get("banking.drools_kbase_lookup")
    output = dispatcher.synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={"rules": RULES},  # no kbase_name
        plugin_name="banking",
    ))
    assert output.signature_locked is True
    assert "SIGNATURE_LOCKED" in output.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Synthesizer composition
# ─────────────────────────────────────────────────────────────────────────────


def test_synthesize_evaluator_returns_callable():
    full_function, evaluator = synthesize_evaluator()
    assert callable(evaluator)
    assert "def evaluate_eligibility(applicant, loan):" in full_function
    assert "return decision" in full_function


def test_evaluator_includes_all_rule_branches():
    full_function, _ = synthesize_evaluator()
    # All 4 rule names appear in inline comments
    for rule in RULES:
        assert rule["name"] in full_function


# ─────────────────────────────────────────────────────────────────────────────
# Each rule's scenario
# ─────────────────────────────────────────────────────────────────────────────


def test_rule_low_credit_declined():
    _, evaluator = synthesize_evaluator()
    applicant = Applicant("X", age=35, credit_score=500)
    loan = Loan(amount=Decimal("100000"), term_months=120)
    assert evaluator(applicant, loan) == "DECLINED"


def test_rule_high_amount_escalates():
    _, evaluator = synthesize_evaluator()
    applicant = Applicant("X", age=35, credit_score=720)
    loan = Loan(amount=Decimal("600000"), term_months=120)
    assert evaluator(applicant, loan) == "ESCALATE"


def test_rule_young_applicant_manual_review():
    _, evaluator = synthesize_evaluator()
    applicant = Applicant("X", age=22, credit_score=720)
    loan = Loan(amount=Decimal("100000"), term_months=120)
    assert evaluator(applicant, loan) == "MANUAL_REVIEW"


def test_rule_long_term_extended_review():
    _, evaluator = synthesize_evaluator()
    applicant = Applicant("X", age=35, credit_score=720)
    loan = Loan(amount=Decimal("100000"), term_months=480)
    assert evaluator(applicant, loan) == "EXTENDED_TERM_REVIEW"


def test_default_branch_approves():
    """No rule matched → APPROVED (else branch)."""
    _, evaluator = synthesize_evaluator()
    applicant = Applicant("X", age=35, credit_score=720)
    loan = Loan(amount=Decimal("100000"), term_months=240)
    assert evaluator(applicant, loan) == "APPROVED"


def test_rule_priority_low_credit_wins_over_high_amount():
    """Both LHS true → first rule wins (Drools default salience semantics)."""
    _, evaluator = synthesize_evaluator()
    applicant = Applicant("X", age=35, credit_score=500)   # low credit triggers
    loan = Loan(amount=Decimal("700000"), term_months=480)  # high amount + long term also true
    assert evaluator(applicant, loan) == "DECLINED"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario sweep
# ─────────────────────────────────────────────────────────────────────────────


def test_all_scenarios_pass():
    _, evaluator = synthesize_evaluator()
    for scenario in make_scenarios():
        actual = evaluator(scenario.applicant, scenario.loan)
        assert actual == scenario.expected, (
            f"{scenario.name}: got {actual}, expected {scenario.expected}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# G2 gate marker
# ─────────────────────────────────────────────────────────────────────────────


def test_g2_gate_adr_006_dispatch_covered():
    """G2 gate ADR-006 (polymorphic dispatch) — W6.2 dispatcher activates here."""
    assert main() == 0
