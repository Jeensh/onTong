"""UC1 broadleaf demo verification — W19.3. G1 gate closure tests."""
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
from backend.sim_v2.demos.uc1_broadleaf.run import (
    Order,
    build_ontology_session,
    compile_to_callable,
    ground_truth_calculate,
    main,
    make_scenarios,
    translate_method,
    _StubRecommendationEngine,
)
from backend.sim_v2.plugins.broadleaf.contracts.exception import PricingException


def test_demo_main_returns_zero():
    assert main() == 0


def test_translation_signature_locked_false():
    session = build_ontology_session()
    _, meta = translate_method(session, with_trace=True)
    assert not meta["locked"], f"signature_locked: notes={meta['notes']}"


def test_translation_emits_bd_set_scale_and_operators():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    assert "bd_set_scale" in py
    assert "*" in py
    assert "+" in py
    # No method-call fallback
    assert ".multiply(" not in py
    assert ".add(" not in py


def test_translation_emits_pricing_exception_passthrough():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    assert "raise PricingException" in py


def test_normal_scenario_returns_108():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    order = Order("O", subtotal=Decimal("100.00"))
    result = fn(order, Decimal("0.08"))
    assert result == Decimal("108.00")
    assert order.tax == Decimal("8.00")
    assert order.grandTotal == Decimal("108.00")


def test_rounding_half_up():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    order = Order("O", subtotal=Decimal("99.95"))
    # tax = 99.95 * 0.075 = 7.49625 → 7.50 (HALF_UP)
    result = fn(order, Decimal("0.075"))
    assert order.tax == Decimal("7.50")
    assert result == Decimal("107.45")


def test_negative_rate_raises_pricing_exception():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    order = Order("O", subtotal=Decimal("100.00"))
    with pytest.raises(PricingException, match="tax cannot be negative"):
        fn(order, Decimal("-0.05"))
    # setters not called on error path
    assert order.tax is None
    assert order.grandTotal is None


def test_ground_truth_matches_translated_normal():
    session = build_ontology_session()
    py, _ = translate_method(session, with_trace=False)
    fn = compile_to_callable(py)
    o1 = Order("A", subtotal=Decimal("250"))
    o2 = Order("B", subtotal=Decimal("250"))
    assert fn(o1, Decimal("0.10")) == ground_truth_calculate(o2, Decimal("0.10"))


def test_full_integrator_pipeline_with_trace_all_pass():
    """Run the full Proposal lifecycle with trace diff active."""
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
        type="code_change", description="test", plugin="broadleaf",
        code_diff={"method": "calculateGrandTotal"},
    )
    prop_id = integrator.submit_proposal(prop)
    engine.fixtures = make_scenarios()
    oracle = integrator.request_oracle(prop_id, list(fixtures.keys()))
    assert oracle.aggregate_status == "PASS"
    for fid, r in oracle.by_fixture.items():
        assert r.status == "PASS", f"{fid}: {r.status}"
        assert r.trace_diff.is_equivalent, f"{fid} trace: {r.trace_diff.summary}"

    integrator.review_proposal(prop_id, UserFeedback(
        decision="ACCEPT", timestamp=datetime.now(timezone.utc), user="test",
    ))
    rev_id = integrator.merge_proposal(
        prop_id=prop_id,
        ontology_revision="broadleaf@test",
        code_revision="git:bl",
        schema_revision="alembic:test",
        created_by="test",
    )
    assert integrator.get_proposal(prop_id).state == "MERGED"
    assert integrator.revision_store.get(rev_id) is not None


def test_ontology_seeds_order_methods():
    session = build_ontology_session()
    from backend.modeling.code_layer.orm import CodeMethodRow
    names = {m.name for m in session.query(CodeMethodRow).all()}
    assert {"getSubtotal", "setTax", "setGrandTotal"}.issubset(names)


# ─────────────────────────────────────────────────────────────────────────────
# G1 gate closure — all 3 system demos pass simultaneously
# ─────────────────────────────────────────────────────────────────────────────


def test_g1_gate_v2_demo_passes():
    """v2 (slab-design) demo passes — G1 gate system #1."""
    from backend.sim_v2.demos.uc1_integrator_pipeline.run import main as v2_main
    assert v2_main() == 0


def test_g1_gate_banking_demo_passes():
    """banking demo passes — G1 gate system #2."""
    from backend.sim_v2.demos.uc1_banking.run import main as banking_main
    assert banking_main() == 0


def test_g1_gate_broadleaf_demo_passes():
    """broadleaf demo passes — G1 gate system #3."""
    from backend.sim_v2.demos.uc1_broadleaf.run import main as broadleaf_main
    assert broadleaf_main() == 0


def test_g1_gate_3_systems_closed():
    """G1 gate aggregate check — all 3 system demos PASS = gate closed."""
    from backend.sim_v2.demos.uc1_banking.run import main as banking_main
    from backend.sim_v2.demos.uc1_broadleaf.run import main as broadleaf_main
    from backend.sim_v2.demos.uc1_integrator_pipeline.run import main as v2_main
    assert v2_main() == 0
    assert banking_main() == 0
    assert broadleaf_main() == 0
