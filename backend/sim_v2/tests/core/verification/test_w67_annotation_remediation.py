"""W67 — Annotation drift remediation tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.annotation_remediation import (
    AnnotationRemediationStep,
    generate_annotation_remediation,
)
from backend.sim_v2.core.verification.annotation_verifier import (
    AnnotationVerification,
    verify_action_annotations_batch,
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
    present=(),
    undeclared=(),
    missing=(),
):
    return AnnotationVerification(
        action_fqn=action_fqn,
        code_method_fqn=code_method_fqn,
        status=status,
        declared=tuple(declared),
        present=tuple(present),
        undeclared_only=tuple(undeclared),
        missing_only=tuple(missing),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-status step generation
# ─────────────────────────────────────────────────────────────────────────────


def test_no_steps_for_verified():
    r = generate_annotation_remediation([_v("VERIFIED")])
    assert r.steps == []
    assert "No annotation drift" in r.summary


def test_no_steps_for_method_not_found():
    r = generate_annotation_remediation([_v("METHOD_NOT_FOUND")])
    assert r.steps == []


def test_no_steps_for_no_recommendation():
    r = generate_annotation_remediation([_v("NO_RECOMMENDATION")])
    assert r.steps == []


def test_undeclared_transactional_emits_add():
    r = generate_annotation_remediation([
        _v("UNDECLARED_ANNOTATION",
           present=("transactional",), undeclared=("transactional",)),
    ])
    assert len(r.steps) == 1
    step = r.steps[0]
    assert step.kind == "ADD_ANNOTATION_EFFECT"
    assert step.annotation_kind == "transactional"
    assert step.effect_entry == {"kind": "transactional"}
    assert step.needs_detail is False


def test_undeclared_rest_endpoint_needs_detail():
    """rest_endpoint requires extra fields → needs_detail=True."""
    r = generate_annotation_remediation([
        _v("UNDECLARED_ANNOTATION",
           present=("rest_endpoint",), undeclared=("rest_endpoint",)),
    ])
    step = r.steps[0]
    assert step.kind == "ADD_ANNOTATION_EFFECT"
    assert step.annotation_kind == "rest_endpoint"
    assert step.needs_detail is True
    assert "http_method" in step.recommendation


def test_undeclared_scheduled_needs_detail():
    r = generate_annotation_remediation([
        _v("UNDECLARED_ANNOTATION",
           present=("scheduled",), undeclared=("scheduled",)),
    ])
    assert r.steps[0].needs_detail is True
    assert "cron" in r.steps[0].recommendation


def test_undeclared_cacheable_needs_detail():
    r = generate_annotation_remediation([
        _v("UNDECLARED_ANNOTATION",
           present=("cacheable",), undeclared=("cacheable",)),
    ])
    assert r.steps[0].needs_detail is True


def test_undeclared_multiple_kinds_emits_one_per():
    r = generate_annotation_remediation([
        _v("UNDECLARED_ANNOTATION",
           present=("overrides", "transactional"),
           undeclared=("overrides", "transactional")),
    ])
    assert len(r.steps) == 2
    kinds = {s.annotation_kind for s in r.steps}
    assert kinds == {"overrides", "transactional"}


def test_missing_emits_remove_step():
    r = generate_annotation_remediation([
        _v("MISSING_ANNOTATION",
           declared=("transactional",), missing=("transactional",)),
    ])
    assert len(r.steps) == 1
    step = r.steps[0]
    assert step.kind == "REMOVE_ANNOTATION_EFFECT"
    assert step.annotation_kind == "transactional"
    assert step.effect_entry is None


def test_divergent_emits_both_add_and_remove():
    r = generate_annotation_remediation([
        _v("DIVERGENT_ANNOTATIONS",
           declared=("overrides",), present=("transactional",),
           undeclared=("transactional",), missing=("overrides",)),
    ])
    assert len(r.steps) == 2
    kinds_by_kind = {(s.kind, s.annotation_kind) for s in r.steps}
    assert ("ADD_ANNOTATION_EFFECT", "transactional") in kinds_by_kind
    assert ("REMOVE_ANNOTATION_EFFECT", "overrides") in kinds_by_kind


def test_divergent_adds_before_removes():
    r = generate_annotation_remediation([
        _v("DIVERGENT_ANNOTATIONS",
           undeclared=("a_new",), missing=("a_old",)),
    ])
    assert r.steps[0].kind == "ADD_ANNOTATION_EFFECT"
    assert r.steps[1].kind == "REMOVE_ANNOTATION_EFFECT"


# ─────────────────────────────────────────────────────────────────────────────
# Order + summary
# ─────────────────────────────────────────────────────────────────────────────


def test_steps_preserve_order_across_verifications():
    verifs = [
        _v("VERIFIED", action_fqn="a.1"),
        _v("UNDECLARED_ANNOTATION",
           action_fqn="a.2",
           present=("transactional",), undeclared=("transactional",)),
        _v("VERIFIED", action_fqn="a.3"),
        _v("MISSING_ANNOTATION",
           action_fqn="a.4",
           declared=("overrides",), missing=("overrides",)),
    ]
    r = generate_annotation_remediation(verifs)
    fqns = [s.action_fqn for s in r.steps]
    assert fqns == ["a.2", "a.4"]


def test_summary_counts_kinds_and_detail_needed():
    verifs = [
        _v("UNDECLARED_ANNOTATION",
           present=("rest_endpoint",), undeclared=("rest_endpoint",)),
        _v("UNDECLARED_ANNOTATION",
           present=("transactional",), undeclared=("transactional",)),
    ]
    r = generate_annotation_remediation(verifs)
    assert "2 ADD_ANNOTATION_EFFECT" in r.summary
    assert "1 need extra detail" in r.summary  # only rest_endpoint needs detail


def test_summary_when_no_detail_needed():
    verifs = [
        _v("UNDECLARED_ANNOTATION",
           present=("transactional",), undeclared=("transactional",)),
    ]
    r = generate_annotation_remediation(verifs)
    assert "need extra detail" not in r.summary


def test_step_is_frozen():
    step = AnnotationRemediationStep(
        action_fqn="a", code_method_fqn="m",
        kind="ADD_ANNOTATION_EFFECT", annotation_kind="transactional",
        recommendation="r", rationale="x",
    )
    with pytest.raises(Exception):
        step.kind = "REMOVE_ANNOTATION_EFFECT"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_yields_six_add_steps():
    """slab-design-real has 6 UNDECLARED_ANNOTATION → 6 ADD_ANNOTATION_EFFECT."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_annotations_batch(session, actions)
        r = generate_annotation_remediation(verifs)
        adds = [s for s in r.steps if s.kind == "ADD_ANNOTATION_EFFECT"]
        assert len(adds) >= 6
        for s in adds:
            # effect_entry contains the kind in the right shape
            assert s.effect_entry == {"kind": s.annotation_kind}
    finally:
        session.close()


@requires_production_db
def test_production_no_remove_steps():
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_annotations_batch(session, actions)
        r = generate_annotation_remediation(verifs)
        removes = [s for s in r.steps if s.kind == "REMOVE_ANNOTATION_EFFECT"]
        assert len(removes) == 0
    finally:
        session.close()


@requires_production_db
def test_production_includes_transactional_and_rest_endpoint():
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_annotations_batch(session, actions)
        r = generate_annotation_remediation(verifs)
        kinds = {s.annotation_kind for s in r.steps}
        assert "transactional" in kinds
        assert "rest_endpoint" in kinds
    finally:
        session.close()


@requires_production_db
def test_production_rest_endpoint_flagged_needs_detail():
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_annotations_batch(session, actions)
        r = generate_annotation_remediation(verifs)
        rest_steps = [s for s in r.steps if s.annotation_kind == "rest_endpoint"]
        assert all(s.needs_detail for s in rest_steps)
    finally:
        session.close()
