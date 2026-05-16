"""W68 — Effect (exception + annotation) → Integrator lifecycle pipeline.

Sister to W62 (term_proposal_pipeline). Both exception remediation (W64) and
annotation remediation (W67) produce steps that mutate `action.effects_json`
in the same shape — append a `{"kind": ..., ...}` entry. This module wires
either step type into a unified Two-Engine lifecycle.

    UC29/UC32   Verification Engine surfaces effect drift
    UC30/UC33   Deterministic remediation classifies the fix
    UC34        Integrator carries each step through DRAFT→MERGED      ← here

Inputs: ExceptionRemediationStep / AnnotationRemediationStep.
Output: LifecycleResult with final_state + revision_id (or rejection_reason).

Oracle rules (EffectSchemaOracle):
  - effect_kind        — kind ∈ {raises, transactional, rest_endpoint, …}
  - no_duplicate       — same {kind, exception?, … } not already in effects_json
  - well_formed_payload — for ADD steps, effect_entry has the kind field

Public API:
    - EffectAxisStep                 — common Pydantic shape both axes adapt to
    - EffectLifecycleResult          — final state + diagnostics
    - exception_step_to_axis_step    — adapter
    - annotation_step_to_axis_step   — adapter
    - EffectSchemaOracle             — schema oracle (FixtureRunner Protocol)
    - run_effect_lifecycle(step, existing, ...)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
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
from backend.sim_v2.core.verification.annotation_remediation import (
    AnnotationRemediationStep,
)
from backend.sim_v2.core.verification.exception_remediation import (
    ExceptionRemediationStep,
)
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleResult,
    OutputDiff,
    TraceDiff,
    aggregate_status_from_fixtures,
)


# ─────────────────────────────────────────────────────────────────────────────
# Common axis step (normalizes both source types)
# ─────────────────────────────────────────────────────────────────────────────


EffectAction = Literal["ADD", "REMOVE"]


class EffectAxisStep(BaseModel):
    """Normalized representation of an effects_json mutation step."""
    model_config = ConfigDict(frozen=True)

    source_axis:     Literal["exception", "annotation"]
    action_fqn:      str
    code_method_fqn: str
    action:          EffectAction
    effect_kind:     str                      # raises / transactional / …
    effect_entry:    dict | None = None       # ADD payload; None for REMOVE
    discriminator:   str = ""                 # exception name for raises; "" otherwise
    needs_detail:    bool = False
    recommendation:  str = ""
    rationale:       str = ""


def exception_step_to_axis_step(
    step: ExceptionRemediationStep,
) -> EffectAxisStep:
    return EffectAxisStep(
        source_axis="exception",
        action_fqn=step.action_fqn,
        code_method_fqn=step.code_method_fqn,
        action="ADD" if step.kind == "ADD_RAISES_EFFECT" else "REMOVE",
        effect_kind="raises",
        effect_entry=step.effect_entry,
        discriminator=step.exception,
        needs_detail=False,
        recommendation=step.recommendation,
        rationale=step.rationale,
    )


def annotation_step_to_axis_step(
    step: AnnotationRemediationStep,
) -> EffectAxisStep:
    return EffectAxisStep(
        source_axis="annotation",
        action_fqn=step.action_fqn,
        code_method_fqn=step.code_method_fqn,
        action="ADD" if step.kind == "ADD_ANNOTATION_EFFECT" else "REMOVE",
        effect_kind=step.annotation_kind,
        effect_entry=step.effect_entry,
        discriminator="",
        needs_detail=step.needs_detail,
        recommendation=step.recommendation,
        rationale=step.rationale,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Schema oracle
# ─────────────────────────────────────────────────────────────────────────────


SCHEMA_RULE_KIND_VALID    = "effect.kind_valid"
SCHEMA_RULE_NO_DUPLICATE  = "effect.no_duplicate"
SCHEMA_RULE_WELL_FORMED   = "effect.well_formed_payload"

DEFAULT_SCHEMA_FIXTURES: tuple[str, ...] = (
    SCHEMA_RULE_KIND_VALID,
    SCHEMA_RULE_NO_DUPLICATE,
    SCHEMA_RULE_WELL_FORMED,
)


_VALID_EFFECT_KINDS: frozenset[str] = frozenset({
    "raises",
    "transactional", "overrides", "rest_endpoint",
    "asynchronous", "scheduled", "cacheable", "cache_evicting",
    "event_handler",
    "writes_table", "reads_table",
})


@dataclass(frozen=True)
class ExistingEffectsSnapshot:
    """Snapshot of the action's existing effects_json entries (post-strip).

    `entries` carries normalized `(kind, discriminator)` pairs so the oracle's
    duplicate check is cheap and deterministic.
    """
    pairs: frozenset[tuple[str, str]]

    @classmethod
    def empty(cls) -> "ExistingEffectsSnapshot":
        return cls(pairs=frozenset())

    @classmethod
    def from_session(
        cls, session: Session, action_fqn: str, repo_id: str,
    ) -> "ExistingEffectsSnapshot":
        row = session.execute(
            text(
                "SELECT effects_json FROM actions "
                "WHERE fqn = :fqn AND repo_id = :rid"
            ),
            {"fqn": action_fqn, "rid": repo_id},
        ).fetchone()
        if row is None or not row[0]:
            return cls.empty()
        try:
            parsed = json.loads(row[0])
        except json.JSONDecodeError:
            return cls.empty()
        if not isinstance(parsed, list):
            return cls.empty()
        pairs: set[tuple[str, str]] = set()
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("kind") or entry.get("type") or ""
            if kind == "raises":
                disc = entry.get("exception") or entry.get("error") or ""
            else:
                disc = ""
            if kind:
                pairs.add((kind, disc))
        return cls(pairs=frozenset(pairs))


class EffectSchemaOracle:
    """FixtureRunner — schema-validates one EffectAxisStep against existing
    effects_json snapshot. Each fixture id is a rule id."""

    def __init__(
        self,
        step: EffectAxisStep,
        existing: ExistingEffectsSnapshot | None = None,
    ) -> None:
        self._step = step
        self._existing = existing or ExistingEffectsSnapshot.empty()

    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict[str, Any],
    ) -> FixtureOracleResult:
        if fixture_id == SCHEMA_RULE_KIND_VALID:
            return self._kind_valid()
        if fixture_id == SCHEMA_RULE_NO_DUPLICATE:
            return self._no_duplicate()
        if fixture_id == SCHEMA_RULE_WELL_FORMED:
            return self._well_formed()
        return _error_result(fixture_id, f"unknown schema rule {fixture_id!r}")

    def _kind_valid(self) -> FixtureOracleResult:
        if self._step.effect_kind in _VALID_EFFECT_KINDS:
            return _pass(SCHEMA_RULE_KIND_VALID,
                         f"kind {self._step.effect_kind!r} is in the contract universe")
        return _fail(
            SCHEMA_RULE_KIND_VALID,
            expected=f"kind in {sorted(_VALID_EFFECT_KINDS)}",
            actual=self._step.effect_kind,
            summary=f"unknown effect kind: {self._step.effect_kind!r}",
        )

    def _no_duplicate(self) -> FixtureOracleResult:
        pair = (self._step.effect_kind, self._step.discriminator)
        if self._step.action == "ADD" and pair in self._existing.pairs:
            return _fail(
                SCHEMA_RULE_NO_DUPLICATE,
                expected="effect not already in effects_json",
                actual=f"{pair!r} already present",
                summary=f"duplicate effect entry: {pair!r}",
            )
        if self._step.action == "REMOVE" and pair not in self._existing.pairs:
            return _fail(
                SCHEMA_RULE_NO_DUPLICATE,
                expected="effect already in effects_json",
                actual=f"{pair!r} not present (nothing to remove)",
                summary=f"REMOVE target missing: {pair!r}",
            )
        return _pass(SCHEMA_RULE_NO_DUPLICATE,
                     "no duplicate (ADD) / target present (REMOVE)")

    def _well_formed(self) -> FixtureOracleResult:
        if self._step.action == "REMOVE":
            return _pass(SCHEMA_RULE_WELL_FORMED,
                         "REMOVE step doesn't carry payload")
        payload = self._step.effect_entry
        if not isinstance(payload, dict):
            return _fail(
                SCHEMA_RULE_WELL_FORMED,
                expected="dict payload",
                actual=f"{type(payload).__name__}",
                summary="ADD step missing dict effect_entry",
            )
        if "kind" not in payload:
            return _fail(
                SCHEMA_RULE_WELL_FORMED,
                expected="`kind` field present",
                actual=f"missing kind",
                summary="ADD payload missing 'kind' field",
            )
        if payload["kind"] != self._step.effect_kind:
            return _fail(
                SCHEMA_RULE_WELL_FORMED,
                expected=self._step.effect_kind,
                actual=payload["kind"],
                summary=f"payload kind {payload['kind']!r} disagrees with step kind",
            )
        return _pass(SCHEMA_RULE_WELL_FORMED, "ADD payload well-formed")


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
# Verification engine adapter + dummy recommendation
# ─────────────────────────────────────────────────────────────────────────────


class _EffectVerificationAdapter:
    def __init__(self, oracle: EffectSchemaOracle) -> None:
        self._oracle = oracle

    def run_oracle(self, request):
        by_fixture: dict[str, FixtureOracleResult] = {}
        for fid in request.fixture_subset:
            by_fixture[fid] = self._oracle.run_fixture(
                fid, plugin="effect", apply_diffs={},
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


# ─────────────────────────────────────────────────────────────────────────────
# Proposal conversion + lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def effect_axis_step_to_proposal(
    step: EffectAxisStep, plugin: str = "v2-slab-design",
) -> Proposal:
    payload: dict[str, Any] = {
        "operation":     "ADD_EFFECT" if step.action == "ADD" else "REMOVE_EFFECT",
        "source_axis":   step.source_axis,
        "action_fqn":    step.action_fqn,
        "effect_kind":   step.effect_kind,
        "discriminator": step.discriminator,
        "effect_entry":  step.effect_entry,
        "needs_detail":  step.needs_detail,
    }
    return Proposal(
        type="ontology_evolution",
        description=(
            f"{step.action} effect {step.effect_kind!r} "
            f"({step.discriminator!r}) on {step.action_fqn}"
        ),
        ontology_diff=payload,
        plugin=plugin,
    )


@dataclass(frozen=True)
class EffectLifecycleResult:
    source_axis:      str
    action_fqn:       str
    effect_kind:      str
    discriminator:    str
    proposal_id:      str
    states_visited:   tuple[ProposalState, ...]
    final_state:      ProposalState
    oracle_status:    str | None = None
    revision_id:      str | None = None
    rejection_reason: str | None = None


def auto_review_policy(oracle_status: str, step: EffectAxisStep) -> str:
    """Same shape as W62's policy:

      FAIL_BREAKING / FAIL_DRIFT  → REJECT
      INCONCLUSIVE                → CHANGE_REQUEST
      needs_detail = True         → CHANGE_REQUEST (reviewer fills extra fields)
      otherwise                   → ACCEPT
    """
    if oracle_status in ("FAIL_BREAKING", "FAIL_DRIFT"):
        return "REJECT"
    if oracle_status == "INCONCLUSIVE":
        return "CHANGE_REQUEST"
    if step.needs_detail:
        return "CHANGE_REQUEST"
    return "ACCEPT"


def run_effect_lifecycle(
    step: EffectAxisStep,
    *,
    existing: ExistingEffectsSnapshot | None = None,
    plugin: str = "v2-slab-design",
    fixtures: tuple[str, ...] = DEFAULT_SCHEMA_FIXTURES,
    reviewer: str = "auto-policy",
) -> EffectLifecycleResult:
    oracle = EffectSchemaOracle(step=step, existing=existing)
    integrator = Integrator(
        verification=_EffectVerificationAdapter(oracle),
        recommendation=_NoopRecommendation(),
        proposal_store=ProposalStore(),
        revision_store=RevisionStore(),
    )

    states: list[ProposalState] = []
    proposal = effect_axis_step_to_proposal(step, plugin=plugin)
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
                f"effect-{step.effect_kind}-{step.discriminator or 'noarg'}"
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
            f"change-requested ({decision}) — "
            f"{'needs detail fields' if step.needs_detail else 'needs human refinement'}"
        )

    return EffectLifecycleResult(
        source_axis=step.source_axis,
        action_fqn=step.action_fqn,
        effect_kind=step.effect_kind,
        discriminator=step.discriminator,
        proposal_id=prop_id,
        states_visited=tuple(states),
        final_state=proposal.state,
        oracle_status=oracle_result.aggregate_status,
        revision_id=revision_id,
        rejection_reason=rejection_reason,
    )


__all__ = [
    "DEFAULT_SCHEMA_FIXTURES",
    "EffectAction",
    "EffectAxisStep",
    "EffectLifecycleResult",
    "EffectSchemaOracle",
    "ExistingEffectsSnapshot",
    "SCHEMA_RULE_KIND_VALID",
    "SCHEMA_RULE_NO_DUPLICATE",
    "SCHEMA_RULE_WELL_FORMED",
    "annotation_step_to_axis_step",
    "auto_review_policy",
    "effect_axis_step_to_proposal",
    "exception_step_to_axis_step",
    "run_effect_lifecycle",
]
