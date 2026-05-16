"""W64 — Exception drift remediation tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.verification.exception_remediation import (
    ExceptionRemediationStep,
    generate_exception_remediation,
)
from backend.sim_v2.core.verification.exception_verifier import (
    ExceptionVerification,
    verify_action_exceptions_batch,
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
# Builder
# ─────────────────────────────────────────────────────────────────────────────


def _v(
    status,
    *,
    action_fqn="a.x",
    code_method_fqn="com.x.foo()",
    declared=(),
    thrown=(),
    undeclared=(),
    missing=(),
):
    return ExceptionVerification(
        action_fqn=action_fqn,
        code_method_fqn=code_method_fqn,
        status=status,
        declared=tuple(declared),
        thrown=tuple(thrown),
        undeclared_only=tuple(undeclared),
        missing_only=tuple(missing),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-status step generation
# ─────────────────────────────────────────────────────────────────────────────


def test_no_steps_for_verified():
    r = generate_exception_remediation([_v("VERIFIED")])
    assert r.steps == []
    assert "No exception drift" in r.summary


def test_no_steps_for_method_not_found():
    r = generate_exception_remediation([_v("METHOD_NOT_FOUND")])
    assert r.steps == []


def test_no_steps_for_no_recommendation():
    r = generate_exception_remediation([_v("NO_RECOMMENDATION")])
    assert r.steps == []


def test_undeclared_throws_emits_add_step():
    r = generate_exception_remediation([
        _v("UNDECLARED_THROWS",
           thrown=("AlgorithmException",),
           undeclared=("AlgorithmException",)),
    ])
    assert len(r.steps) == 1
    step = r.steps[0]
    assert step.kind == "ADD_RAISES_EFFECT"
    assert step.exception == "AlgorithmException"
    assert step.effect_entry == {
        "kind": "raises", "exception": "AlgorithmException",
    }
    assert "Add" in step.recommendation
    assert "AlgorithmException" in step.rationale


def test_undeclared_throws_with_multiple_exceptions_emits_one_per():
    """Each undeclared exception gets its own step (per-position granularity)."""
    r = generate_exception_remediation([
        _v("UNDECLARED_THROWS",
           thrown=("A", "B", "C"),
           undeclared=("A", "B", "C")),
    ])
    assert len(r.steps) == 3
    assert {s.exception for s in r.steps} == {"A", "B", "C"}
    assert all(s.kind == "ADD_RAISES_EFFECT" for s in r.steps)


def test_missing_throws_emits_remove_step():
    r = generate_exception_remediation([
        _v("MISSING_THROWS",
           declared=("PhantomException",),
           missing=("PhantomException",)),
    ])
    assert len(r.steps) == 1
    step = r.steps[0]
    assert step.kind == "REMOVE_DECLARED_EFFECT"
    assert step.exception == "PhantomException"
    assert step.effect_entry is None
    assert "Remove" in step.recommendation


def test_divergent_throws_emits_both_add_and_remove():
    """Both sides non-empty: action declares A, method throws B → REMOVE A + ADD B."""
    r = generate_exception_remediation([
        _v("DIVERGENT_THROWS",
           declared=("A",),
           thrown=("B",),
           undeclared=("B",),
           missing=("A",)),
    ])
    assert len(r.steps) == 2
    kinds = {s.kind for s in r.steps}
    assert kinds == {"ADD_RAISES_EFFECT", "REMOVE_DECLARED_EFFECT"}


def test_divergent_throws_emits_adds_before_removes():
    """Convention: ADDs come first so reviewers see "add this" before "remove that"."""
    r = generate_exception_remediation([
        _v("DIVERGENT_THROWS",
           undeclared=("Add1",),
           missing=("Rem1",)),
    ])
    assert r.steps[0].kind == "ADD_RAISES_EFFECT"
    assert r.steps[1].kind == "REMOVE_DECLARED_EFFECT"


def test_divergent_with_partial_overlap_only_diffs_emit():
    """Action declares {A, B}, method throws {A, C} → undeclared=C, missing=B.
    A overlaps → no step. Steps: ADD C + REMOVE B."""
    r = generate_exception_remediation([
        _v("DIVERGENT_THROWS",
           declared=("A", "B"),
           thrown=("A", "C"),
           undeclared=("C",),
           missing=("B",)),
    ])
    excs = {s.exception for s in r.steps}
    assert excs == {"B", "C"}
    assert "A" not in excs


# ─────────────────────────────────────────────────────────────────────────────
# Mixed batch ordering + summary
# ─────────────────────────────────────────────────────────────────────────────


def test_steps_preserve_order_across_verifications():
    verifs = [
        _v("VERIFIED", action_fqn="a.1"),
        _v("UNDECLARED_THROWS",
           action_fqn="a.2",
           thrown=("X",), undeclared=("X",)),
        _v("VERIFIED", action_fqn="a.3"),
        _v("MISSING_THROWS",
           action_fqn="a.4",
           declared=("Y",), missing=("Y",)),
    ]
    r = generate_exception_remediation(verifs)
    fqns = [s.action_fqn for s in r.steps]
    assert fqns == ["a.2", "a.4"]


def test_summary_counts_kinds():
    verifs = [
        _v("UNDECLARED_THROWS", thrown=("X",), undeclared=("X",)),
        _v("UNDECLARED_THROWS", thrown=("Y",), undeclared=("Y",)),
        _v("MISSING_THROWS", declared=("Z",), missing=("Z",)),
    ]
    r = generate_exception_remediation(verifs)
    assert "2 ADD_RAISES_EFFECT" in r.summary
    assert "1 REMOVE_DECLARED_EFFECT" in r.summary


def test_empty_input_yields_no_steps():
    r = generate_exception_remediation([])
    assert r.steps == []
    assert "No exception drift" in r.summary


def test_step_is_frozen():
    step = ExceptionRemediationStep(
        action_fqn="a", code_method_fqn="m",
        kind="ADD_RAISES_EFFECT", exception="X",
        recommendation="r", rationale="x",
    )
    with pytest.raises(Exception):
        step.kind = "REMOVE_DECLARED_EFFECT"  # type: ignore[misc]


def test_step_carries_code_method_fqn():
    r = generate_exception_remediation([
        _v("UNDECLARED_THROWS",
           code_method_fqn="com.example.Foo.bar(int)",
           thrown=("X",), undeclared=("X",)),
    ])
    assert r.steps[0].code_method_fqn == "com.example.Foo.bar(int)"


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_slab_design_yields_add_steps():
    """slab-design-real has 10 UNDECLARED_THROWS → 10 ADD_RAISES_EFFECT steps."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_exceptions_batch(session, actions)
        r = generate_exception_remediation(verifs)
        adds = [s for s in r.steps if s.kind == "ADD_RAISES_EFFECT"]
        # 10 undeclared findings → 10 add steps
        assert len(adds) >= 10
        # All have valid effect_entry payloads
        for s in adds:
            assert s.effect_entry == {
                "kind": "raises", "exception": s.exception,
            }
    finally:
        session.close()


@requires_production_db
def test_production_no_remove_steps_in_slab_design_real():
    """Production effects_json is empty so MISSING_THROWS doesn't occur."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_exceptions_batch(session, actions)
        r = generate_exception_remediation(verifs)
        removes = [s for s in r.steps if s.kind == "REMOVE_DECLARED_EFFECT"]
        assert len(removes) == 0
    finally:
        session.close()


@requires_production_db
def test_production_includes_algorithm_exception_add_step():
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_exceptions_batch(session, actions)
        r = generate_exception_remediation(verifs)
        assert any(s.exception == "AlgorithmException" for s in r.steps)
    finally:
        session.close()
