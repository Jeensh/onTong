"""W55 — Drift remediation recommender tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.drift_remediation import (
    RemediationStep,
    generate_remediation,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    ParamVerification,
    verify_action_param_signatures,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def _verif(action_fqn, status, action_params=(), method_params=(),
           code_method_fqn="com.x.A.m()", details=""):
    return ParamVerification(
        action_fqn=action_fqn,
        code_method_fqn=code_method_fqn,
        status=status,
        action_params=action_params,
        method_params=method_params,
        details=details,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Empty / no-drift
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_verifications_yields_empty_report():
    report = generate_remediation([])
    assert report.steps == []
    assert report.summary == "No drift to remediate."


def test_all_verified_yields_empty_report():
    """When every verification is VERIFIED, no steps are emitted."""
    verifs = [
        _verif("a.1", "VERIFIED", ("x", "y"), ("x", "y")),
        _verif("a.2", "VERIFIED", ("a",), ("a",)),
    ]
    report = generate_remediation(verifs)
    assert report.steps == []
    assert "No drift" in report.summary


def test_other_statuses_skipped_for_remediation():
    """METHOD_NOT_FOUND / NO_RECOMMENDATION / NO_ACTION_PARAMS shouldn't
    produce remediation steps — they aren't actionable param fixes."""
    verifs = [
        _verif("a.1", "METHOD_NOT_FOUND"),
        _verif("a.2", "NO_RECOMMENDATION"),
        _verif("a.3", "NO_ACTION_PARAMS"),
    ]
    report = generate_remediation(verifs)
    assert report.steps == []


# ─────────────────────────────────────────────────────────────────────────────
# NAME_MISMATCH → RENAME_ACTION_PARAM steps
# ─────────────────────────────────────────────────────────────────────────────


def test_single_name_mismatch_produces_one_rename_step():
    verifs = [_verif(
        "a.x", "NAME_MISMATCH",
        action_params=("order", "blob"),
        method_params=("order", "slab"),
    )]
    report = generate_remediation(verifs)
    assert len(report.steps) == 1
    s = report.steps[0]
    assert s.kind == "RENAME_ACTION_PARAM"
    assert s.param_position == 1
    assert s.current_name == "blob"
    assert s.expected_name == "slab"


def test_multiple_diverging_positions_yield_step_per_position():
    """Two params differ — two rename steps, in order."""
    verifs = [_verif(
        "a.x", "NAME_MISMATCH",
        action_params=("a1", "b1", "c1"),
        method_params=("a1", "b2", "c2"),
    )]
    report = generate_remediation(verifs)
    assert len(report.steps) == 2
    assert report.steps[0].param_position == 1
    assert report.steps[0].current_name == "b1"
    assert report.steps[0].expected_name == "b2"
    assert report.steps[1].param_position == 2


def test_matching_positions_within_mismatch_are_skipped():
    """If most params match but only one differs, only one step is emitted."""
    verifs = [_verif(
        "a.x", "NAME_MISMATCH",
        action_params=("alpha", "beta", "gamma", "delta"),
        method_params=("alpha", "beta", "gamma_changed", "delta"),
    )]
    report = generate_remediation(verifs)
    assert len(report.steps) == 1
    assert report.steps[0].param_position == 2


def test_rename_step_carries_action_and_method_fqns():
    verifs = [_verif(
        "action.x.foo", "NAME_MISMATCH",
        action_params=("a",), method_params=("b",),
        code_method_fqn="com.x.X.foo(int)",
    )]
    report = generate_remediation(verifs)
    s = report.steps[0]
    assert s.action_fqn == "action.x.foo"
    assert s.code_method_fqn == "com.x.X.foo(int)"


def test_rename_step_recommendation_is_human_readable():
    verifs = [_verif(
        "a.x", "NAME_MISMATCH",
        action_params=("prodKindCd",), method_params=("productCd",),
    )]
    s = generate_remediation(verifs).steps[0]
    assert "prodKindCd" in s.recommendation
    assert "productCd" in s.recommendation
    assert s.rationale  # non-empty


# ─────────────────────────────────────────────────────────────────────────────
# ARITY_MISMATCH → RESIZE_ACTION_PARAMS step
# ─────────────────────────────────────────────────────────────────────────────


def test_arity_mismatch_yields_resize_step():
    verifs = [_verif(
        "a.x", "ARITY_MISMATCH",
        action_params=("a",), method_params=("a", "b"),
        details="action has 1 param, method has 2",
    )]
    report = generate_remediation(verifs)
    assert len(report.steps) == 1
    s = report.steps[0]
    assert s.kind == "RESIZE_ACTION_PARAMS"
    assert s.param_position is None
    assert "Resize" in s.recommendation
    assert s.rationale  # carries details


def test_arity_mismatch_resize_preserves_action_method_fqns():
    verifs = [_verif(
        "action.x.foo", "ARITY_MISMATCH",
        action_params=(), method_params=("a", "b"),
        code_method_fqn="com.x.foo(int,int)",
    )]
    s = generate_remediation(verifs).steps[0]
    assert s.action_fqn == "action.x.foo"
    assert s.code_method_fqn == "com.x.foo(int,int)"


# ─────────────────────────────────────────────────────────────────────────────
# Mixed + ordering
# ─────────────────────────────────────────────────────────────────────────────


def test_mixed_verifications_preserve_input_order():
    verifs = [
        _verif("a.1", "VERIFIED", ("x",), ("x",)),
        _verif("a.2", "NAME_MISMATCH", ("a",), ("b",)),
        _verif("a.3", "ARITY_MISMATCH", ("a",), ("a", "b")),
        _verif("a.4", "NAME_MISMATCH", ("p",), ("q",)),
    ]
    steps = generate_remediation(verifs).steps
    assert [s.action_fqn for s in steps] == ["a.2", "a.3", "a.4"]


def test_summary_describes_drift_counts():
    verifs = [
        _verif("a.1", "NAME_MISMATCH", ("a",), ("b",)),
        _verif("a.2", "NAME_MISMATCH", ("x",), ("y",)),
        _verif("a.3", "ARITY_MISMATCH", (), ("a", "b")),
    ]
    summary = generate_remediation(verifs).summary
    assert "2 NAME_MISMATCH" in summary
    assert "1 ARITY_MISMATCH" in summary


# ─────────────────────────────────────────────────────────────────────────────
# Frozen view
# ─────────────────────────────────────────────────────────────────────────────


def test_remediation_step_is_frozen():
    s = RemediationStep(
        action_fqn="a", code_method_fqn="m",
        kind="RENAME_ACTION_PARAM", recommendation="x", rationale="y",
    )
    with pytest.raises(Exception):
        s.kind = "RESIZE_ACTION_PARAMS"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke — slab-design-real-v2 productCd cluster
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_v2_yields_3_rename_steps():
    """The known v2 NAME_MISMATCH cluster (productCd vs productTypeCd/prodKindCd)
    should produce 3 RENAME_ACTION_PARAM steps."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real-v2")
        verifs = verify_action_param_signatures(session, actions)
        report = generate_remediation(verifs)
        rename_steps = [s for s in report.steps if s.kind == "RENAME_ACTION_PARAM"]
        # 3 NAME_MISMATCH actions, each with exactly 1 diverging position
        assert len(rename_steps) == 3
        # All should suggest renaming to 'productCd'
        for s in rename_steps:
            assert s.expected_name == "productCd"
    finally:
        session.close()


@requires_production_db
def test_production_real_yields_no_remediation_steps():
    """slab-design-real has no NAME_MISMATCH — empty remediation."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_param_signatures(session, actions)
        report = generate_remediation(verifs)
        assert report.steps == []
    finally:
        session.close()
