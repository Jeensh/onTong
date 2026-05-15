"""W68 — Effect lifecycle tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.integrator.effect_proposal_pipeline import (
    EffectAxisStep,
    EffectLifecycleResult,
    EffectSchemaOracle,
    ExistingEffectsSnapshot,
    SCHEMA_RULE_KIND_VALID,
    SCHEMA_RULE_NO_DUPLICATE,
    SCHEMA_RULE_WELL_FORMED,
    annotation_step_to_axis_step,
    auto_review_policy,
    effect_axis_step_to_proposal,
    exception_step_to_axis_step,
    run_effect_lifecycle,
)
from backend.sim_v2.core.verification.annotation_remediation import (
    AnnotationRemediationStep,
)
from backend.sim_v2.core.verification.exception_remediation import (
    ExceptionRemediationStep,
)


# ─────────────────────────────────────────────────────────────────────────────
# Adapters
# ─────────────────────────────────────────────────────────────────────────────


def test_exception_step_to_axis_step():
    src = ExceptionRemediationStep(
        action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind="ADD_RAISES_EFFECT", exception="AlgorithmException",
        effect_entry={"kind": "raises", "exception": "AlgorithmException"},
        recommendation="r", rationale="ra",
    )
    s = exception_step_to_axis_step(src)
    assert s.source_axis == "exception"
    assert s.action == "ADD"
    assert s.effect_kind == "raises"
    assert s.discriminator == "AlgorithmException"
    assert s.needs_detail is False


def test_exception_remove_step_to_axis_step():
    src = ExceptionRemediationStep(
        action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind="REMOVE_DECLARED_EFFECT", exception="Phantom",
        recommendation="r", rationale="ra",
    )
    s = exception_step_to_axis_step(src)
    assert s.action == "REMOVE"
    assert s.effect_entry is None


def test_annotation_step_to_axis_step_transactional():
    src = AnnotationRemediationStep(
        action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind="ADD_ANNOTATION_EFFECT", annotation_kind="transactional",
        effect_entry={"kind": "transactional"},
        recommendation="r", rationale="ra", needs_detail=False,
    )
    s = annotation_step_to_axis_step(src)
    assert s.source_axis == "annotation"
    assert s.action == "ADD"
    assert s.effect_kind == "transactional"
    assert s.discriminator == ""
    assert s.needs_detail is False


def test_annotation_step_to_axis_step_rest_endpoint_needs_detail():
    src = AnnotationRemediationStep(
        action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind="ADD_ANNOTATION_EFFECT", annotation_kind="rest_endpoint",
        effect_entry={"kind": "rest_endpoint"},
        recommendation="r", rationale="ra", needs_detail=True,
    )
    s = annotation_step_to_axis_step(src)
    assert s.needs_detail is True


# ─────────────────────────────────────────────────────────────────────────────
# Proposal conversion
# ─────────────────────────────────────────────────────────────────────────────


def _step(action="ADD", kind="raises", disc="X",
          entry=None, needs_detail=False, axis="exception"):
    return EffectAxisStep(
        source_axis=axis, action_fqn="a.x", code_method_fqn="com.x.foo()",
        action=action, effect_kind=kind, discriminator=disc,
        effect_entry=entry if entry is not None else ({"kind": kind, "exception": disc} if kind == "raises" else {"kind": kind}),
        needs_detail=needs_detail,
    )


def test_step_to_proposal_carries_payload():
    p = effect_axis_step_to_proposal(_step())
    assert p.type == "ontology_evolution"
    assert p.state == "DRAFT"
    assert p.ontology_diff["operation"] == "ADD_EFFECT"
    assert p.ontology_diff["effect_kind"] == "raises"


def test_step_to_proposal_uses_specified_plugin():
    p = effect_axis_step_to_proposal(_step(), plugin="broadleaf")
    assert p.plugin == "broadleaf"


# ─────────────────────────────────────────────────────────────────────────────
# Oracle rules
# ─────────────────────────────────────────────────────────────────────────────


def _run_rule(oracle, rule):
    return oracle.run_fixture(rule, plugin="effect", apply_diffs={})


def test_oracle_kind_valid_passes_for_raises():
    oracle = EffectSchemaOracle(_step(), ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_KIND_VALID).status == "PASS"


def test_oracle_kind_valid_passes_for_transactional():
    s = _step(kind="transactional", disc="", entry={"kind": "transactional"},
              axis="annotation")
    oracle = EffectSchemaOracle(s, ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_KIND_VALID).status == "PASS"


def test_oracle_kind_valid_fails_for_unknown():
    s = _step(kind="weird_kind", disc="", entry={"kind": "weird_kind"})
    oracle = EffectSchemaOracle(s, ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_KIND_VALID).status == "FAIL_OUTPUT"


def test_oracle_no_duplicate_passes_when_novel():
    oracle = EffectSchemaOracle(_step(), ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_NO_DUPLICATE).status == "PASS"


def test_oracle_no_duplicate_fails_on_ADD_dup():
    existing = ExistingEffectsSnapshot(pairs=frozenset({("raises", "X")}))
    oracle = EffectSchemaOracle(_step(), existing)
    assert _run_rule(oracle, SCHEMA_RULE_NO_DUPLICATE).status == "FAIL_OUTPUT"


def test_oracle_no_duplicate_fails_on_REMOVE_missing():
    """REMOVE expects the target to exist."""
    s = _step(action="REMOVE", entry=None)
    oracle = EffectSchemaOracle(s, ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_NO_DUPLICATE).status == "FAIL_OUTPUT"


def test_oracle_no_duplicate_passes_on_REMOVE_present():
    existing = ExistingEffectsSnapshot(pairs=frozenset({("raises", "X")}))
    s = _step(action="REMOVE", entry=None)
    oracle = EffectSchemaOracle(s, existing)
    assert _run_rule(oracle, SCHEMA_RULE_NO_DUPLICATE).status == "PASS"


def test_oracle_well_formed_passes_for_correct_payload():
    oracle = EffectSchemaOracle(_step(), ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_WELL_FORMED).status == "PASS"


def test_oracle_well_formed_skips_for_REMOVE():
    s = _step(action="REMOVE", entry=None)
    oracle = EffectSchemaOracle(s, ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_WELL_FORMED).status == "PASS"


def test_oracle_well_formed_fails_when_kind_disagrees():
    """Payload `kind` doesn't match step `effect_kind`."""
    s = _step(entry={"kind": "different"})
    oracle = EffectSchemaOracle(s, ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, SCHEMA_RULE_WELL_FORMED).status == "FAIL_OUTPUT"


def test_oracle_unknown_rule_returns_error():
    oracle = EffectSchemaOracle(_step(), ExistingEffectsSnapshot.empty())
    assert _run_rule(oracle, "no.such.rule").status == "ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# auto_review_policy
# ─────────────────────────────────────────────────────────────────────────────


def test_auto_review_accepts_clean_pass():
    assert auto_review_policy("PASS", _step()) == "ACCEPT"


def test_auto_review_change_request_when_needs_detail():
    assert auto_review_policy("PASS", _step(needs_detail=True)) == "CHANGE_REQUEST"


def test_auto_review_rejects_fail_breaking():
    assert auto_review_policy("FAIL_BREAKING", _step()) == "REJECT"


def test_auto_review_change_request_when_inconclusive():
    assert auto_review_policy("INCONCLUSIVE", _step()) == "CHANGE_REQUEST"


# ─────────────────────────────────────────────────────────────────────────────
# Full lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def test_lifecycle_clean_add_merges():
    r = run_effect_lifecycle(_step())
    assert r.final_state == "MERGED"
    assert r.oracle_status == "PASS"
    assert r.revision_id is not None


def test_lifecycle_duplicate_add_rejected():
    existing = ExistingEffectsSnapshot(pairs=frozenset({("raises", "X")}))
    r = run_effect_lifecycle(_step(), existing=existing)
    assert r.final_state == "REJECTED"
    assert r.oracle_status == "FAIL_BREAKING"


def test_lifecycle_rest_endpoint_returns_to_draft():
    """needs_detail=True → CHANGE_REQUEST → DRAFT."""
    s = _step(kind="rest_endpoint", disc="", entry={"kind": "rest_endpoint"},
              needs_detail=True, axis="annotation")
    r = run_effect_lifecycle(s)
    assert r.final_state == "DRAFT"
    assert "needs detail" in (r.rejection_reason or "")


def test_lifecycle_remove_existing_merges():
    existing = ExistingEffectsSnapshot(pairs=frozenset({("raises", "X")}))
    s = _step(action="REMOVE", entry=None)
    r = run_effect_lifecycle(s, existing=existing)
    assert r.final_state == "MERGED"


def test_lifecycle_states_traverse_all_stages():
    r = run_effect_lifecycle(_step())
    assert "DRAFT" in r.states_visited
    assert "PROPOSED" in r.states_visited
    assert "ORACLED" in r.states_visited
    assert "ACCEPTED" in r.states_visited
    assert "MERGED" in r.states_visited


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot accessor
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE actions (
                fqn TEXT, effects_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def test_snapshot_loads_existing_effects(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(
            text("INSERT INTO actions VALUES (:fqn, :ej, 'r')"),
            {"fqn": "a.x",
             "ej": json.dumps([
                 {"kind": "raises", "exception": "X"},
                 {"kind": "transactional"},
             ])},
        )
    with Session(fixture_db) as session:
        snap = ExistingEffectsSnapshot.from_session(session, "a.x", "r")
    assert ("raises", "X") in snap.pairs
    assert ("transactional", "") in snap.pairs


def test_snapshot_empty_for_action_with_no_effects(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(
            text("INSERT INTO actions VALUES (:fqn, '[]', 'r')"),
            {"fqn": "a.x"},
        )
    with Session(fixture_db) as session:
        snap = ExistingEffectsSnapshot.from_session(session, "a.x", "r")
    assert snap.pairs == frozenset()
