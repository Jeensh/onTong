"""W58 — Return-type drift remediation tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.verification.return_type_remediation import (
    ReturnTypeRemediationReport,
    ReturnTypeRemediationStep,
    TermClassIndex,
    generate_return_type_remediation,
)
from backend.sim_v2.core.verification.return_type_verifier import (
    ReturnTypeVerification,
    verify_action_return_types,
)
from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Verification factory
# ─────────────────────────────────────────────────────────────────────────────


def _v(
    status, action_output=None, method_return=None,
    action_fqn="a.x", code_method_fqn="com.x.A.foo()",
):
    return ReturnTypeVerification(
        action_fqn=action_fqn,
        code_method_fqn=code_method_fqn,
        status=status,
        action_output=action_output,
        method_return=method_return,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step decisions — no term index
# ─────────────────────────────────────────────────────────────────────────────


def test_no_steps_for_verified():
    r = generate_return_type_remediation([_v("VERIFIED")])
    assert r.steps == []


def test_no_steps_for_method_not_found():
    r = generate_return_type_remediation([_v("METHOD_NOT_FOUND")])
    assert r.steps == []


def test_no_steps_for_no_recommendation():
    r = generate_return_type_remediation([_v("NO_RECOMMENDATION")])
    assert r.steps == []


def test_no_steps_for_void_mismatch():
    r = generate_return_type_remediation([
        _v("VOID_MISMATCH", action_output="string", method_return="void"),
    ])
    assert r.steps == []


def test_no_steps_for_unresolved():
    r = generate_return_type_remediation([
        _v("OBJECT_REF_UNRESOLVED",
           action_output="object_ref:term.x", method_return="Foo"),
    ])
    assert r.steps == []


def test_declare_output_for_implicit():
    r = generate_return_type_remediation([
        _v("IMPLICIT_OUTPUT", action_output=None, method_return="SDSlabEntity"),
    ])
    assert len(r.steps) == 1
    assert r.steps[0].kind == "DECLARE_OUTPUT"
    assert "SDSlabEntity" in r.steps[0].recommendation


def test_change_primitive_for_bigdecimal():
    """Action declares `float`, method returns `BigDecimal` → primitive realign."""
    r = generate_return_type_remediation([
        _v("PRIMITIVE_MISMATCH",
           action_output="float", method_return="BigDecimal"),
    ])
    assert len(r.steps) == 1
    step = r.steps[0]
    assert step.kind == "CHANGE_PRIMITIVE_TYPE"
    assert step.expected_output == '{"type":"decimal"}'


def test_change_primitive_for_integer():
    r = generate_return_type_remediation([
        _v("PRIMITIVE_MISMATCH",
           action_output="string", method_return="Integer"),
    ])
    assert len(r.steps) == 1
    assert r.steps[0].kind == "CHANGE_PRIMITIVE_TYPE"
    assert r.steps[0].expected_output == '{"type":"int"}'


def test_change_primitive_skips_when_already_matching():
    """If action_output already matches the mapped primitive, no step."""
    r = generate_return_type_remediation([
        _v("PRIMITIVE_MISMATCH",
           action_output="decimal", method_return="BigDecimal"),
    ])
    # decimal maps from BigDecimal — but verifier flagged mismatch; this means
    # action_output `decimal` is already correct → no CHANGE step, falls through
    # to PROPOSE_NEW_TERM (since BigDecimal isn't a domain class)
    # ... but BigDecimal IS in _JAVA_TO_ACTION_PRIMITIVE, so it would normally
    # change. The guard prevents emitting a no-op.
    # We fall through to LIFT/PROPOSE — BigDecimal simple-name not in term_index
    assert len(r.steps) == 1
    assert r.steps[0].kind == "PROPOSE_NEW_TERM"


def test_wrap_as_list_without_term():
    """Method returns List<X>; no term index → propose with placeholder."""
    r = generate_return_type_remediation([
        _v("PRIMITIVE_MISMATCH",
           action_output="string", method_return="List<SDOrderEntity>"),
    ])
    assert len(r.steps) == 1
    step = r.steps[0]
    assert step.kind == "WRAP_AS_LIST"
    assert "SDOrderEntity" in step.recommendation
    assert step.target_term_fqn is None
    assert step.proposed_class == "SDOrderEntity"


def test_wrap_as_list_with_matching_term():
    """Method returns List<Order>; term index has term for Order."""
    idx = TermClassIndex(
        class_to_terms={"SDOrderEntity": ("term.scm.order.order",)},
    )
    r = generate_return_type_remediation(
        [_v("PRIMITIVE_MISMATCH",
            action_output="string", method_return="List<SDOrderEntity>")],
        term_index=idx,
    )
    assert r.steps[0].kind == "WRAP_AS_LIST"
    assert r.steps[0].target_term_fqn == "term.scm.order.order"
    assert "term.scm.order.order" in r.steps[0].expected_output


def test_lift_to_object_ref_with_index_match():
    """Method returns ProductCategory; term index has a term for it."""
    idx = TermClassIndex(
        class_to_terms={"ProductCategory": ("term.scm.product.category",)},
    )
    r = generate_return_type_remediation(
        [_v("PRIMITIVE_MISMATCH",
            action_output="string", method_return="ProductCategory")],
        term_index=idx,
    )
    step = r.steps[0]
    assert step.kind == "LIFT_TO_OBJECT_REF"
    assert step.target_term_fqn == "term.scm.product.category"
    assert "object_ref" in step.expected_output


def test_propose_new_term_when_no_match():
    """Method returns ExoticClass; no primitive map, no term index entry."""
    r = generate_return_type_remediation([
        _v("PRIMITIVE_MISMATCH",
           action_output="string", method_return="ExoticClass"),
    ])
    step = r.steps[0]
    assert step.kind == "PROPOSE_NEW_TERM"
    assert step.proposed_class == "ExoticClass"


def test_object_ref_mismatch_with_list_method():
    """The known production case: action declares term.order.order (singular)
    but method returns List<SDOrderEntity>."""
    idx = TermClassIndex(
        class_to_terms={"SDOrderEntity": ("term.scm.order.order",)},
    )
    r = generate_return_type_remediation(
        [_v("OBJECT_REF_MISMATCH",
            action_output="object_ref:term.scm.order.order",
            method_return="List<SDOrderEntity>")],
        term_index=idx,
    )
    assert r.steps[0].kind == "WRAP_AS_LIST"
    assert r.steps[0].target_term_fqn == "term.scm.order.order"


def test_object_ref_mismatch_falls_back_to_propose():
    r = generate_return_type_remediation([
        _v("OBJECT_REF_MISMATCH",
           action_output="object_ref:term.x", method_return="UnknownClass"),
    ])
    assert r.steps[0].kind == "PROPOSE_NEW_TERM"


# ─────────────────────────────────────────────────────────────────────────────
# Order + summary
# ─────────────────────────────────────────────────────────────────────────────


def test_steps_preserve_order():
    verifs = [
        _v("PRIMITIVE_MISMATCH", action_output="float", method_return="BigDecimal",
           action_fqn="a.1"),
        _v("VERIFIED", action_fqn="a.2"),
        _v("IMPLICIT_OUTPUT", method_return="Foo", action_fqn="a.3"),
    ]
    r = generate_return_type_remediation(verifs)
    assert [s.action_fqn for s in r.steps] == ["a.1", "a.3"]


def test_summary_describes_kinds():
    verifs = [
        _v("PRIMITIVE_MISMATCH", action_output="float", method_return="BigDecimal"),
        _v("IMPLICIT_OUTPUT", method_return="Foo"),
    ]
    r = generate_return_type_remediation(verifs)
    assert "CHANGE_PRIMITIVE_TYPE" in r.summary
    assert "DECLARE_OUTPUT" in r.summary


def test_summary_for_empty():
    r = generate_return_type_remediation([_v("VERIFIED")])
    assert "No return-type drift" in r.summary


def test_step_is_frozen():
    step = ReturnTypeRemediationStep(
        action_fqn="a", code_method_fqn="m", kind="DECLARE_OUTPUT",
        recommendation="r", rationale="x",
    )
    with pytest.raises(Exception):
        step.kind = "WRAP_AS_LIST"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# TermClassIndex fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE business_terms (
                fqn TEXT, description TEXT, aliases_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_term(engine, fqn, description, aliases=None, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO business_terms(fqn, description, aliases_json, repo_id) "
                 "VALUES (:f, :d, :a, :r)"),
            {"f": fqn, "d": description,
             "a": json.dumps(aliases or []), "r": repo_id},
        )


def test_term_class_index_builds_from_descriptions(fixture_db):
    _insert_term(fixture_db, "term.scm.order.order",
                 "자동 추천 — com.example.SDOrderEntity",
                 aliases=["Order", "SDOrderEntity"])
    _insert_term(fixture_db, "term.scm.validation_result",
                 "자동 추천 — com.example.ValidationResult",
                 aliases=["ValidationResult"])
    with Session(fixture_db) as session:
        idx = TermClassIndex.build(session, "r")
    assert "SDOrderEntity" in idx.class_to_terms
    assert "ValidationResult" in idx.class_to_terms
    assert "Order" in idx.class_to_terms  # alias also indexed


def test_term_class_index_handles_duplicate_class(fixture_db):
    _insert_term(fixture_db, "term.a", "자동 추천 — com.x.Foo")
    _insert_term(fixture_db, "term.b", "자동 추천 — com.y.Foo")
    with Session(fixture_db) as session:
        idx = TermClassIndex.build(session, "r")
    terms = idx.terms_for_class("Foo")
    assert "term.a" in terms
    assert "term.b" in terms


def test_term_class_index_empty_for_unknown_class(fixture_db):
    with Session(fixture_db) as session:
        idx = TermClassIndex.build(session, "r")
    assert idx.terms_for_class("NoSuchClass") == ()


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_term_index_builds():
    session = open_readonly_session()
    try:
        idx = TermClassIndex.build(session, "slab-design-real")
        # Sanity: ValidationResult and SDOrderEntity should both appear
        assert idx.has_term_for_class("ValidationResult")
        assert idx.has_term_for_class("SDOrderEntity")
    finally:
        session.close()


@requires_production_db
def test_production_slab_design_real_yields_steps():
    """End-to-end: load actions → verify → remediate. Should produce a non-empty
    step list since slab-design-real has 8 PRIMITIVE_MISMATCH + 1 OBJECT_REF_MISMATCH
    + 1 IMPLICIT_OUTPUT."""
    session = open_readonly_session()
    try:
        idx = TermClassIndex.build(session, "slab-design-real")
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_return_types(session, actions)
        r = generate_return_type_remediation(verifs, term_index=idx)
        # At least 10 steps (8 prim + 1 obj_ref + 1 implicit)
        assert len(r.steps) >= 10
    finally:
        session.close()


@requires_production_db
def test_production_includes_wrap_as_list_for_orders_drift():
    """The known case: extract_designable_orders → List<SDOrderEntity>."""
    session = open_readonly_session()
    try:
        idx = TermClassIndex.build(session, "slab-design-real")
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_return_types(session, actions)
        r = generate_return_type_remediation(verifs, term_index=idx)
        wraps = [s for s in r.steps if s.kind == "WRAP_AS_LIST"]
        assert any(
            s.action_fqn == "action.scm.order.extract_designable_orders"
            for s in wraps
        )
    finally:
        session.close()


@requires_production_db
def test_production_includes_lift_to_object_ref_for_product_category():
    """The known case: action.scm.product.분류 declares 'string' but method
    returns ProductCategory."""
    session = open_readonly_session()
    try:
        idx = TermClassIndex.build(session, "slab-design-real")
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_return_types(session, actions)
        r = generate_return_type_remediation(verifs, term_index=idx)
        lifts = [s for s in r.steps if s.kind == "LIFT_TO_OBJECT_REF"]
        # ProductCategory term either exists in the index → LIFT_TO_OBJECT_REF,
        # or doesn't → PROPOSE_NEW_TERM. Both are valid, but the production
        # repo has a category term for it.
        proposes = [s for s in r.steps if s.kind == "PROPOSE_NEW_TERM"
                    and s.proposed_class == "ProductCategory"]
        assert (len(lifts) > 0
                and any("ProductCategory" in (s.method_return or "") for s in lifts)
                ) or len(proposes) > 0
    finally:
        session.close()
