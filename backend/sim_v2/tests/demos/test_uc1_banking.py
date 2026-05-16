"""UC1 banking demo verification — W18.3.

Verifies that the banking demo end-to-end works:
  - Java translation (BigDecimal money math + compareTo + setScale + throw)
  - Ontology resolver (Account.getBalance → BigDecimal)
  - Full Proposal lifecycle
  - Cross-side trace diff PASS for all 3 scenarios
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.sim_v2.core.integrator.integrator import Integrator
from backend.sim_v2.core.integrator.proposal import Proposal, UserFeedback
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)
from backend.sim_v2.demos.uc1_banking.run import (
    Account,
    build_ontology_session,
    compile_to_callable,
    ground_truth_calculate,
    main,
    make_scenarios,
    translate_method,
    _StubRecommendationEngine,
)
from backend.sim_v2.plugins.banking.contracts.exception import ComplianceException


def test_demo_main_returns_zero():
    """The banking demo main() exits 0 (end-to-end PASS)."""
    assert main() == 0


def test_translation_signature_locked_false():
    session = build_ontology_session()
    _, meta = translate_method(session, with_trace=True)
    assert not meta["locked"], f"signature_locked: notes={meta['notes']}"


def test_translation_emits_bigdecimal_chain_as_operators():
    """multiply().multiply().divide() chain → * * / operators (BigDecimal type-aware)."""
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    # No fallback `.multiply(` / `.divide(` strings remain
    assert ".multiply(" not in py
    assert ".divide(" not in py
    # Operator form present
    assert "*" in py
    assert "/" in py


def test_translation_emits_compareTo_as_sign_diff():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    # compareTo(BigDecimal.ZERO) → ((x > Decimal(0)) - (x < Decimal(0))) < 0
    assert "(interest > Decimal(0)) - (interest < Decimal(0))" in py


def test_translation_emits_compliance_exception_passthrough():
    """Plugin-specific exception class kept as-is — banking imports it at compile."""
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    assert "raise ComplianceException" in py


def test_translation_emits_bd_set_scale():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    assert "bd_set_scale" in py


def test_normal_scenario_returns_500():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    account = Account("ACC", balance=Decimal("10000"))
    result = fn(account, Decimal("0.05"), 365)
    assert result == Decimal("500.00")
    assert account.lastInterest == Decimal("500.00")


def test_partial_year_scenario_rounds_correctly():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    account = Account("ACC", balance=Decimal("10000"))
    # 10000 * 0.05 * 30 / 365 = 41.0958904... → 41.10 (HALF_UP)
    result = fn(account, Decimal("0.05"), 30)
    assert result == Decimal("41.10")


def test_negative_rate_raises_compliance_exception():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    account = Account("ACC", balance=Decimal("10000"))
    with pytest.raises(ComplianceException, match="interest cannot be negative"):
        fn(account, Decimal("-0.05"), 30)
    assert account.lastInterest is None  # setter not called on error


def test_ground_truth_matches_translated_normal():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    a1 = Account("A1", balance=Decimal("10000"))
    a2 = Account("A2", balance=Decimal("10000"))
    assert fn(a1, Decimal("0.05"), 365) == ground_truth_calculate(a2, Decimal("0.05"), 365)


def test_full_integrator_pipeline_with_trace():
    """Run the full Proposal lifecycle with trace diff active. All 3 scenarios PASS."""
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=True)
    fn = compile_to_callable(py)
    fixtures = make_scenarios()
    engine = ScenarioVerificationEngine(
        translated_fn=fn,
        baseline_fn=ground_truth_calculate,
        fixtures=fixtures,
        with_trace=True,
    )
    integrator = Integrator(engine, _StubRecommendationEngine())

    prop = Proposal(
        type="code_change", description="test", plugin="banking",
        code_diff={"method": "calculateAccruedInterest"},
    )
    prop_id = integrator.submit_proposal(prop)
    engine.fixtures = make_scenarios()  # fresh state per fixture
    oracle = integrator.request_oracle(prop_id, list(fixtures.keys()))
    assert oracle.aggregate_status == "PASS"
    for fid, r in oracle.by_fixture.items():
        assert r.status == "PASS", f"{fid}: {r.status} ({r.output_diff.summary})"
        assert r.trace_diff.is_equivalent, f"{fid} trace differs: {r.trace_diff.summary}"

    integrator.review_proposal(prop_id, UserFeedback(
        decision="ACCEPT", timestamp=datetime.now(timezone.utc), user="test",
    ))
    rev_id = integrator.merge_proposal(
        prop_id=prop_id,
        ontology_revision="banking@test",
        code_revision="virtual:LoanInterestService",
        schema_revision="alembic:test",
        created_by="test",
    )
    assert integrator.get_proposal(prop_id).state == "MERGED"
    assert integrator.revision_store.get(rev_id) is not None


def test_ontology_session_seeds_account_methods():
    session = build_ontology_session()
    from backend.modeling.code_layer.orm import CodeMethodRow
    methods = session.query(CodeMethodRow).all()
    names = {m.name for m in methods}
    assert "getBalance" in names
    assert "setLastInterest" in names
