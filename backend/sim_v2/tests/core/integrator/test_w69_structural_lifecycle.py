"""W69 — Param + Return-type structural lifecycle tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.integrator.structural_proposal_pipeline import (
    SCHEMA_RULE_FIELDS_PRESENT,
    SCHEMA_RULE_KIND_VALID,
    SCHEMA_RULE_NO_COLLISION,
    StructuralAxisStep,
    StructuralSchemaOracle,
    auto_review_policy,
    param_step_to_axis_step,
    return_type_step_to_axis_step,
    run_structural_lifecycle,
    structural_axis_step_to_proposal,
)
from backend.sim_v2.core.verification.drift_remediation import (
    RemediationStep as ParamStep,
)
from backend.sim_v2.core.verification.return_type_remediation import (
    ReturnTypeRemediationStep,
)


# ─────────────────────────────────────────────────────────────────────────────
# Adapters
# ─────────────────────────────────────────────────────────────────────────────


def test_param_rename_step_to_axis():
    src = ParamStep(
        action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind="RENAME_ACTION_PARAM",
        param_position=3, current_name="prodKindCd", expected_name="productCd",
        recommendation="r", rationale="ra",
    )
    s = param_step_to_axis_step(src)
    assert s.source_axis == "param"
    assert s.kind == "RENAME_ACTION_PARAM"
    assert s.payload["param_position"] == 3
    assert s.payload["expected_name"] == "productCd"
    assert s.needs_detail is False


def test_return_type_change_primitive_step_to_axis():
    src = ReturnTypeRemediationStep(
        action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind="CHANGE_PRIMITIVE_TYPE",
        current_output="float", expected_output='{"type":"decimal"}',
        method_return="BigDecimal",
        recommendation="r", rationale="ra",
    )
    s = return_type_step_to_axis_step(src)
    assert s.source_axis == "return_type"
    assert s.needs_detail is False
    assert s.payload["expected_output"] == '{"type":"decimal"}'


def test_return_type_propose_new_term_needs_detail():
    src = ReturnTypeRemediationStep(
        action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind="PROPOSE_NEW_TERM", current_output="string",
        expected_output="(new term)", method_return="ProductCategory",
        proposed_class="ProductCategory",
        recommendation="r", rationale="ra",
    )
    s = return_type_step_to_axis_step(src)
    assert s.needs_detail is True


# ─────────────────────────────────────────────────────────────────────────────
# Oracle rules
# ─────────────────────────────────────────────────────────────────────────────


def _step(axis="param", kind="RENAME_ACTION_PARAM", payload=None,
          needs_detail=False):
    return StructuralAxisStep(
        source_axis=axis, action_fqn="a.x", code_method_fqn="com.x.foo()",
        kind=kind, payload=payload or {
            "param_position": 0, "current_name": "old", "expected_name": "new",
        },
        needs_detail=needs_detail,
    )


def _run_rule(oracle, rule):
    return oracle.run_fixture(rule, plugin="structural", apply_diffs={})


def test_oracle_kind_valid_param():
    assert _run_rule(StructuralSchemaOracle(_step()),
                     SCHEMA_RULE_KIND_VALID).status == "PASS"


def test_oracle_kind_valid_return_type():
    s = _step(axis="return_type", kind="CHANGE_PRIMITIVE_TYPE",
              payload={"expected_output": "x"})
    assert _run_rule(StructuralSchemaOracle(s),
                     SCHEMA_RULE_KIND_VALID).status == "PASS"


def test_oracle_kind_invalid_for_param_axis():
    s = _step(axis="param", kind="UNKNOWN_KIND")
    assert _run_rule(StructuralSchemaOracle(s),
                     SCHEMA_RULE_KIND_VALID).status == "FAIL_OUTPUT"


def test_oracle_fields_present_rename():
    assert _run_rule(StructuralSchemaOracle(_step()),
                     SCHEMA_RULE_FIELDS_PRESENT).status == "PASS"


def test_oracle_fields_missing_rename():
    s = _step(payload={"param_position": 0})  # missing expected_name
    assert _run_rule(StructuralSchemaOracle(s),
                     SCHEMA_RULE_FIELDS_PRESENT).status == "FAIL_OUTPUT"


def test_oracle_fields_missing_change_primitive():
    s = _step(axis="return_type", kind="CHANGE_PRIMITIVE_TYPE", payload={})
    assert _run_rule(StructuralSchemaOracle(s),
                     SCHEMA_RULE_FIELDS_PRESENT).status == "FAIL_OUTPUT"


def test_oracle_no_collision_noop_rename_fails():
    s = _step(payload={
        "param_position": 0, "current_name": "same", "expected_name": "same",
    })
    assert _run_rule(StructuralSchemaOracle(s),
                     SCHEMA_RULE_NO_COLLISION).status == "FAIL_OUTPUT"


def test_oracle_no_collision_lift_requires_term_fqn():
    s = _step(axis="return_type", kind="LIFT_TO_OBJECT_REF",
              payload={"expected_output": "x", "target_term_fqn": "not-a-term"})
    assert _run_rule(StructuralSchemaOracle(s),
                     SCHEMA_RULE_NO_COLLISION).status == "FAIL_OUTPUT"


def test_oracle_no_collision_lift_passes_with_term_fqn():
    s = _step(axis="return_type", kind="LIFT_TO_OBJECT_REF",
              payload={"expected_output": "x",
                       "target_term_fqn": "term.scm.foo"})
    assert _run_rule(StructuralSchemaOracle(s),
                     SCHEMA_RULE_NO_COLLISION).status == "PASS"


def test_oracle_unknown_rule_errors():
    assert _run_rule(StructuralSchemaOracle(_step()), "nope").status == "ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# auto_review_policy
# ─────────────────────────────────────────────────────────────────────────────


def test_auto_review_accept_clean():
    assert auto_review_policy("PASS", _step()) == "ACCEPT"


def test_auto_review_needs_detail_change_request():
    assert auto_review_policy("PASS", _step(needs_detail=True)) == "CHANGE_REQUEST"


def test_auto_review_reject_fail_breaking():
    assert auto_review_policy("FAIL_BREAKING", _step()) == "REJECT"


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def test_lifecycle_clean_rename_merges():
    r = run_structural_lifecycle(_step())
    assert r.final_state == "MERGED"
    assert r.revision_id is not None


def test_lifecycle_propose_new_term_returns_to_draft():
    s = _step(axis="return_type", kind="PROPOSE_NEW_TERM",
              payload={"proposed_class": "Foo"},
              needs_detail=True)
    r = run_structural_lifecycle(s)
    assert r.final_state == "DRAFT"
    assert "PROPOSE_NEW_TERM" in (r.rejection_reason or "")


def test_lifecycle_noop_rename_rejected():
    s = _step(payload={
        "param_position": 0, "current_name": "x", "expected_name": "x",
    })
    r = run_structural_lifecycle(s)
    assert r.final_state == "REJECTED"


def test_lifecycle_states_traverse_all_stages():
    r = run_structural_lifecycle(_step())
    assert {"DRAFT", "PROPOSED", "ORACLED", "ACCEPTED", "MERGED"} <= set(r.states_visited)


def test_proposal_carries_payload():
    p = structural_axis_step_to_proposal(_step())
    assert p.type == "ontology_evolution"
    assert p.ontology_diff["kind"] == "RENAME_ACTION_PARAM"
    assert p.ontology_diff["source_axis"] == "param"
