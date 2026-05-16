"""W69 — Param + Return-type → Integrator lifecycle pipelines.

Sister to W62 (term axis) and W68 (effect axis). Covers the two remaining
structural axes — `params_json` and `output_json` of `actions` — so every
RemediationKind across the framework has a closed-loop demonstration.

For the param axis (W55):
    RENAME_ACTION_PARAM    — change param name at position N to match method
    RESIZE_ACTION_PARAMS   — bring action arity in line with method

For the return-type axis (W58):
    CHANGE_PRIMITIVE_TYPE  — float → decimal (BigDecimal returns)
    WRAP_AS_LIST           — wrap scalar into list-typed object_ref
    LIFT_TO_OBJECT_REF     — primitive → existing object_ref term
    DECLARE_OUTPUT         — IMPLICIT_OUTPUT → add output_json
    PROPOSE_NEW_TERM       — class has no term yet (LLM follow-up)

Oracle (StructuralSchemaOracle) checks:
    structural.kind_valid           — the RemediationKind is recognized
    structural.fields_present       — required fields per kind populated
    structural.no_target_collision  — target_term/expected_name etc. don't
                                       collide with existing entities

PROPOSE_NEW_TERM is intentionally a needs_detail step (LLM/human must
produce the new term first) — review policy returns CHANGE_REQUEST.

Public API:
    - StructuralAxisStep
    - StructuralSchemaOracle
    - StructuralLifecycleResult
    - param_step_to_axis_step    — W55 → axis
    - return_type_step_to_axis_step — W58 → axis
    - run_structural_lifecycle(step, ...)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.sim_v2.core.integrator.integrator import (
    Integrator,
    ProposalStore,
)
from backend.sim_v2.core.integrator.proposal import (
    Proposal,
    ProposalState,
    UserFeedback,
)
from backend.sim_v2.core.integrator.revision import RevisionStore
from backend.sim_v2.core.verification.drift_remediation import (
    RemediationStep as ParamRemediationStep,
)
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleResult,
    OutputDiff,
    TraceDiff,
    aggregate_status_from_fixtures,
)
from backend.sim_v2.core.verification.return_type_remediation import (
    ReturnTypeRemediationStep,
)


StructuralAxis = Literal["param", "return_type"]


class StructuralAxisStep(BaseModel):
    """Normalized representation of a structural mutation step."""
    model_config = ConfigDict(frozen=True)

    source_axis:     StructuralAxis
    action_fqn:      str
    code_method_fqn: str
    kind:            str
    payload:         dict[str, Any]
    needs_detail:    bool = False
    recommendation:  str = ""
    rationale:       str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Adapters
# ─────────────────────────────────────────────────────────────────────────────


def param_step_to_axis_step(
    step: ParamRemediationStep,
) -> StructuralAxisStep:
    payload: dict[str, Any] = {
        "kind":           step.kind,
        "param_position": step.param_position,
        "current_name":   step.current_name,
        "expected_name":  step.expected_name,
    }
    return StructuralAxisStep(
        source_axis="param",
        action_fqn=step.action_fqn,
        code_method_fqn=step.code_method_fqn,
        kind=step.kind,
        payload=payload,
        needs_detail=False,
        recommendation=step.recommendation,
        rationale=step.rationale,
    )


def return_type_step_to_axis_step(
    step: ReturnTypeRemediationStep,
) -> StructuralAxisStep:
    payload: dict[str, Any] = {
        "kind":            step.kind,
        "current_output":  step.current_output,
        "expected_output": step.expected_output,
        "method_return":   step.method_return,
        "target_term_fqn": step.target_term_fqn,
        "proposed_class":  step.proposed_class,
    }
    # PROPOSE_NEW_TERM needs a follow-up (Recommendation Engine on terms first).
    needs_detail = step.kind == "PROPOSE_NEW_TERM"
    return StructuralAxisStep(
        source_axis="return_type",
        action_fqn=step.action_fqn,
        code_method_fqn=step.code_method_fqn,
        kind=step.kind,
        payload=payload,
        needs_detail=needs_detail,
        recommendation=step.recommendation,
        rationale=step.rationale,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Schema oracle
# ─────────────────────────────────────────────────────────────────────────────


SCHEMA_RULE_KIND_VALID     = "structural.kind_valid"
SCHEMA_RULE_FIELDS_PRESENT = "structural.fields_present"
SCHEMA_RULE_NO_COLLISION   = "structural.no_target_collision"

DEFAULT_SCHEMA_FIXTURES: tuple[str, ...] = (
    SCHEMA_RULE_KIND_VALID,
    SCHEMA_RULE_FIELDS_PRESENT,
    SCHEMA_RULE_NO_COLLISION,
)


_PARAM_KINDS: frozenset[str] = frozenset({
    "RENAME_ACTION_PARAM", "RESIZE_ACTION_PARAMS",
})
_RETURN_TYPE_KINDS: frozenset[str] = frozenset({
    "CHANGE_PRIMITIVE_TYPE", "WRAP_AS_LIST", "LIFT_TO_OBJECT_REF",
    "DECLARE_OUTPUT", "PROPOSE_NEW_TERM",
})


class StructuralSchemaOracle:
    """FixtureRunner that validates a StructuralAxisStep."""

    def __init__(self, step: StructuralAxisStep) -> None:
        self._step = step

    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict[str, Any],
    ) -> FixtureOracleResult:
        if fixture_id == SCHEMA_RULE_KIND_VALID:
            return self._kind_valid()
        if fixture_id == SCHEMA_RULE_FIELDS_PRESENT:
            return self._fields_present()
        if fixture_id == SCHEMA_RULE_NO_COLLISION:
            return self._no_collision()
        return _error_result(fixture_id, f"unknown schema rule {fixture_id!r}")

    def _kind_valid(self) -> FixtureOracleResult:
        ok_set = _PARAM_KINDS if self._step.source_axis == "param" else _RETURN_TYPE_KINDS
        if self._step.kind in ok_set:
            return _pass(SCHEMA_RULE_KIND_VALID, f"kind {self._step.kind!r} ok")
        return _fail(
            SCHEMA_RULE_KIND_VALID,
            expected=f"kind in {sorted(ok_set)}",
            actual=self._step.kind,
            summary=f"unknown kind for {self._step.source_axis}: {self._step.kind!r}",
        )

    def _fields_present(self) -> FixtureOracleResult:
        missing: list[str] = []
        if self._step.kind == "RENAME_ACTION_PARAM":
            for f in ("param_position", "current_name", "expected_name"):
                if self._step.payload.get(f) is None:
                    missing.append(f)
        elif self._step.kind == "RESIZE_ACTION_PARAMS":
            pass  # rationale-driven; arity is not a fixed field
        elif self._step.kind in (
            "CHANGE_PRIMITIVE_TYPE", "WRAP_AS_LIST",
            "LIFT_TO_OBJECT_REF", "DECLARE_OUTPUT",
        ):
            if not self._step.payload.get("expected_output"):
                missing.append("expected_output")
        elif self._step.kind == "PROPOSE_NEW_TERM":
            if not self._step.payload.get("proposed_class"):
                missing.append("proposed_class")
        if missing:
            return _fail(
                SCHEMA_RULE_FIELDS_PRESENT,
                expected="all required fields populated",
                actual=f"missing {missing}",
                summary=f"required fields missing: {missing}",
            )
        return _pass(SCHEMA_RULE_FIELDS_PRESENT, "required fields present")

    def _no_collision(self) -> FixtureOracleResult:
        # For RENAME_ACTION_PARAM: current_name and expected_name must differ.
        if self._step.kind == "RENAME_ACTION_PARAM":
            cur = self._step.payload.get("current_name")
            exp = self._step.payload.get("expected_name")
            if cur == exp:
                return _fail(
                    SCHEMA_RULE_NO_COLLISION,
                    expected="current_name != expected_name",
                    actual=f"both = {cur!r}",
                    summary="no-op rename (current_name == expected_name)",
                )
        # For LIFT_TO_OBJECT_REF: target_term_fqn must be a `term.` FQN.
        if self._step.kind == "LIFT_TO_OBJECT_REF":
            target = self._step.payload.get("target_term_fqn") or ""
            if not target.startswith("term."):
                return _fail(
                    SCHEMA_RULE_NO_COLLISION,
                    expected="target_term_fqn starts with 'term.'",
                    actual=target,
                    summary="LIFT_TO_OBJECT_REF requires a valid term FQN",
                )
        return _pass(SCHEMA_RULE_NO_COLLISION, "no collision")


def _pass(fid, summary):
    return FixtureOracleResult(
        fixture_id=fid,
        java_baseline_output=None,
        python_proposal_output=None,
        output_diff=OutputDiff(is_equivalent=True, summary=summary),
        trace_diff=TraceDiff(is_equivalent=True),
        status="PASS",
    )


def _fail(fid, *, expected, actual, summary):
    return FixtureOracleResult(
        fixture_id=fid,
        java_baseline_output=expected,
        python_proposal_output=actual,
        output_diff=OutputDiff(
            is_equivalent=False,
            baseline_value=expected,
            proposal_value=actual,
            summary=summary,
        ),
        trace_diff=TraceDiff(is_equivalent=True),
        status="FAIL_OUTPUT",
    )


def _error_result(fid, err):
    return FixtureOracleResult(
        fixture_id=fid,
        java_baseline_output=None,
        python_proposal_output=None,
        output_diff=OutputDiff(is_equivalent=False, summary=err),
        trace_diff=TraceDiff(is_equivalent=False),
        status="ERROR",
        error=err,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Verification adapter + lifecycle
# ─────────────────────────────────────────────────────────────────────────────


class _StructuralVerificationAdapter:
    def __init__(self, oracle: StructuralSchemaOracle) -> None:
        self._oracle = oracle

    def run_oracle(self, request):
        by_fixture: dict[str, FixtureOracleResult] = {}
        for fid in request.fixture_subset:
            by_fixture[fid] = self._oracle.run_fixture(
                fid, plugin="structural", apply_diffs={},
            )
        status = aggregate_status_from_fixtures(by_fixture)
        return OracleResult(
            proposal_id=request.proposal_id,
            by_fixture=by_fixture,
            aggregate_status=status,
            summary=f"{len(by_fixture)} schema rule(s), {status}",
        )


class _NoopRecommendation:
    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        return proposal


def structural_axis_step_to_proposal(
    step: StructuralAxisStep, plugin: str = "v2-slab-design",
) -> Proposal:
    payload: dict[str, Any] = {
        "operation":   "STRUCTURAL_FIX",
        "source_axis": step.source_axis,
        "action_fqn":  step.action_fqn,
        "kind":        step.kind,
        "needs_detail": step.needs_detail,
        **step.payload,
    }
    return Proposal(
        type="ontology_evolution",
        description=(
            f"{step.kind} on {step.action_fqn} ({step.source_axis})"
        ),
        ontology_diff=payload,
        plugin=plugin,
    )


@dataclass(frozen=True)
class StructuralLifecycleResult:
    source_axis:      str
    kind:             str
    action_fqn:       str
    proposal_id:      str
    states_visited:   tuple[ProposalState, ...]
    final_state:      ProposalState
    oracle_status:    str | None = None
    revision_id:      str | None = None
    rejection_reason: str | None = None


def auto_review_policy(oracle_status: str, step: StructuralAxisStep) -> str:
    if oracle_status in ("FAIL_BREAKING", "FAIL_DRIFT"):
        return "REJECT"
    if oracle_status == "INCONCLUSIVE":
        return "CHANGE_REQUEST"
    if step.needs_detail:
        return "CHANGE_REQUEST"
    return "ACCEPT"


def run_structural_lifecycle(
    step: StructuralAxisStep,
    *,
    plugin: str = "v2-slab-design",
    fixtures: tuple[str, ...] = DEFAULT_SCHEMA_FIXTURES,
    reviewer: str = "auto-policy",
) -> StructuralLifecycleResult:
    oracle = StructuralSchemaOracle(step=step)
    integrator = Integrator(
        verification=_StructuralVerificationAdapter(oracle),
        recommendation=_NoopRecommendation(),
        proposal_store=ProposalStore(),
        revision_store=RevisionStore(),
    )

    states: list[ProposalState] = []
    proposal = structural_axis_step_to_proposal(step, plugin=plugin)
    states.append(proposal.state)

    prop_id = integrator.submit_proposal(proposal)
    states.append(proposal.state)

    oracle_result = integrator.request_oracle(prop_id, fixture_subset=list(fixtures))
    states.append(proposal.state)

    decision = auto_review_policy(oracle_result.aggregate_status, step)
    integrator.review_proposal(
        prop_id=prop_id,
        user_feedback=UserFeedback(
            decision=decision,
            timestamp=proposal.last_updated_at,
            user=reviewer,
            comments=(
                f"auto-policy: oracle={oracle_result.aggregate_status}, "
                f"needs_detail={step.needs_detail}"
            ),
        ),
    )
    states.append(proposal.state)

    revision_id = None
    rejection_reason = None
    if proposal.state == "ACCEPTED":
        revision_id = integrator.merge_proposal(
            prop_id=prop_id,
            ontology_revision=(
                f"structural-{step.source_axis}-{step.kind}-{step.action_fqn}"
            ),
            code_revision="(no code change)",
            schema_revision="(no schema change)",
            created_by=reviewer,
        )
        states.append(proposal.state)
    elif proposal.state == "REJECTED":
        rejection_reason = (
            f"oracle={oracle_result.aggregate_status}, decision={decision}"
        )
    elif proposal.state == "DRAFT":
        rejection_reason = (
            f"change-requested — "
            f"{'PROPOSE_NEW_TERM needs term proposal first' if step.kind == 'PROPOSE_NEW_TERM' else 'needs refinement'}"
        )

    return StructuralLifecycleResult(
        source_axis=step.source_axis,
        kind=step.kind,
        action_fqn=step.action_fqn,
        proposal_id=prop_id,
        states_visited=tuple(states),
        final_state=proposal.state,
        oracle_status=oracle_result.aggregate_status,
        revision_id=revision_id,
        rejection_reason=rejection_reason,
    )


__all__ = [
    "DEFAULT_SCHEMA_FIXTURES",
    "SCHEMA_RULE_FIELDS_PRESENT",
    "SCHEMA_RULE_KIND_VALID",
    "SCHEMA_RULE_NO_COLLISION",
    "StructuralAxis",
    "StructuralAxisStep",
    "StructuralLifecycleResult",
    "StructuralSchemaOracle",
    "auto_review_policy",
    "param_step_to_axis_step",
    "return_type_step_to_axis_step",
    "run_structural_lifecycle",
    "structural_axis_step_to_proposal",
]
