"""UC2 banking saga demo verification — W20.3.

Validates ADR-007 (annotation processing) end-to-end activation:
  - Translator emits methods normally
  - @Compensable annotation handler (W6.1) produces wrapper
  - Wrapper applied at exec time
  - Saga semantics: success path doesn't compensate, failure path does
"""
from __future__ import annotations

import importlib
from decimal import Decimal

import pytest

from backend.sim_v2.core.synthesizer.annotations.registry import (
    AnnotationContext,
    get_default_registry,
)


@pytest.fixture(autouse=True)
def _ensure_banking_compensable_registered():
    """Ensure W6.1 banking.compensable handler is registered.

    test_banking_extensions.py uses an autouse fixture that resets + reloads the
    annotation registry. Cross-test ordering may leave the registry empty when
    these demo tests run. Reload here to guarantee the handler is back.
    """
    import backend.sim_v2.plugins.banking.annotations as banking_ann
    importlib.reload(banking_ann)
    yield
from backend.sim_v2.demos.uc2_banking_saga.run import (
    Account,
    Scenario,
    build_ontology_session,
    build_service,
    main,
    make_scenarios,
    translate_service,
)
from backend.sim_v2.plugins.banking.contracts.exception import (
    ComplianceException,
    SagaCompensatedException,
)


def test_demo_main_returns_zero():
    """The W20 demo main() exits 0 — both scenarios PASS."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Translation
# ─────────────────────────────────────────────────────────────────────────────


def test_both_methods_translated():
    session = build_ontology_session()
    method_sources, _ = translate_service(session)
    assert "transfer" in method_sources
    assert "refund" in method_sources
    assert "def transfer(self, sender, receiver, amount):" in method_sources["transfer"]
    assert "def refund(self, sender, receiver, amount):" in method_sources["refund"]


def test_transfer_emits_subtract_add_compareTo_throw():
    session = build_ontology_session()
    method_sources, _ = translate_service(session)
    src = method_sources["transfer"]
    # BigDecimal.subtract → - operator, .add → + operator
    assert "(sender.getBalance() - amount)" in src
    assert "(receiver.getBalance() + amount)" in src
    # compareTo → sign-of-diff
    assert "receiver.getBalance() > Decimal(\"100000\")" in src
    # throw → raise ComplianceException
    assert "raise ComplianceException" in src


def test_refund_emits_inverse_operations():
    session = build_ontology_session()
    method_sources, _ = translate_service(session)
    src = method_sources["refund"]
    assert "(sender.getBalance() + amount)" in src    # add to sender (reverses subtract)
    assert "(receiver.getBalance() - amount)" in src  # subtract from receiver


# ─────────────────────────────────────────────────────────────────────────────
# Annotation handler invocation
# ─────────────────────────────────────────────────────────────────────────────


def test_compensable_handler_invoked():
    """W6.1 banking.compensable handler is invoked + produces wrap function."""
    session = build_ontology_session()
    _, wrapper_source = translate_service(session)
    assert "_compensable_wrap" in wrapper_source
    assert "SagaCompensatedException" in wrapper_source
    # The compensationMethod=refund is baked into the wrapper
    assert "self.refund(*args, **kwargs)" in wrapper_source


def test_annotation_registry_has_banking_compensable():
    """W6.1 auto-registers banking.compensable on import — confirm registry hit."""
    import backend.sim_v2.plugins.banking.annotations  # noqa: F401 — triggers registration
    registry = get_default_registry()
    handler = registry.get("bank.annotation.Compensable")
    assert handler is not None
    assert handler.name == "banking.compensable"


# ─────────────────────────────────────────────────────────────────────────────
# Saga semantics
# ─────────────────────────────────────────────────────────────────────────────


def test_success_scenario_no_compensation():
    session = build_ontology_session()
    method_sources, wrapper_source = translate_service(session)
    service = build_service(method_sources, wrapper_source)

    sender = Account("S", balance=Decimal("1000"))
    receiver = Account("R", balance=Decimal("500"))
    service.transfer(sender, receiver, Decimal("200"))
    # Forward path applied, refund NOT called
    assert sender.balance == Decimal("800")
    assert receiver.balance == Decimal("700")


def test_failure_scenario_compensation_triggered():
    """Transfer pushes receiver over limit → ComplianceException → refund triggered →
    SagaCompensatedException raised + balances reverted."""
    session = build_ontology_session()
    method_sources, wrapper_source = translate_service(session)
    service = build_service(method_sources, wrapper_source)

    sender = Account("S", balance=Decimal("200000"))
    receiver = Account("R", balance=Decimal("99000"))
    with pytest.raises(SagaCompensatedException) as exc_info:
        service.transfer(sender, receiver, Decimal("5000"))

    # Cause is the original ComplianceException
    assert isinstance(exc_info.value.__cause__, ComplianceException)
    # Compensation reverted balances
    assert sender.balance == Decimal("200000")
    assert receiver.balance == Decimal("99000")
    # Message mentions compensation
    assert "compensated" in str(exc_info.value)
    assert "refund" in str(exc_info.value)


def test_multiple_scenarios_all_pass():
    """Both scenarios in make_scenarios() produce expected balances/exceptions."""
    session = build_ontology_session()
    method_sources, wrapper_source = translate_service(session)
    service = build_service(method_sources, wrapper_source)

    for scenario in make_scenarios():
        try:
            service.transfer(scenario.sender, scenario.receiver, scenario.amount)
            exc = None
        except Exception as e:
            exc = e

        if scenario.expect_exception is not None:
            assert isinstance(exc, scenario.expect_exception), (
                f"{scenario.name}: expected {scenario.expect_exception.__name__}, got {type(exc).__name__ if exc else None}"
            )
        else:
            assert exc is None, f"{scenario.name}: unexpected exception {exc}"

        assert scenario.sender.balance == scenario.expect_sender_balance
        assert scenario.receiver.balance == scenario.expect_receiver_balance


def test_ontology_seeded_with_account_methods():
    session = build_ontology_session()
    from backend.modeling.code_layer.orm import CodeMethodRow
    names = {m.name for m in session.query(CodeMethodRow).all()}
    assert {"getBalance", "setBalance"}.issubset(names)


# ─────────────────────────────────────────────────────────────────────────────
# G2 gate marker
# ─────────────────────────────────────────────────────────────────────────────


def test_g2_gate_adr_007_annotation_covered():
    """G2 gate ADR-007 (annotation processing) — W6.1 handler activates here."""
    assert main() == 0
