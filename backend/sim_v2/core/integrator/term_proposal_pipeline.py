"""W62 — TermProposal → Integrator lifecycle pipeline.

Wires W61's `BusinessTermProposal` into the existing Two-Engine Substrate
(`Integrator` + `Proposal` + `Revision`). The closed-loop story finally
runs end-to-end on production findings:

    UC23  detect return-type drift                  (Verification Engine)
    UC24  classify into PROPOSE_NEW_TERM            (deterministic remediation)
    UC27  LLM produces BusinessTermProposal         (Recommendation Engine)
    UC28  Integrator carries it through DRAFT →     ← this module
          PROPOSED → ORACLED → REVIEWED → ACCEPTED
          → MERGED (Revision lineage)

What's new vs the existing 8-method Integrator:

  - `term_to_draft_proposal(term)` — converts a BusinessTermProposal into a
    `Proposal(type="ontology_evolution")` whose `ontology_diff` carries the
    term payload. This is the canonical mapping from Recommendation output
    to lifecycle input.

  - `TermSchemaOracle` — implements `FixtureRunner` Protocol from `oracle.py`,
    treating each *schema validation rule* as a "fixture". Production has no
    behavior fixtures for new-term proposals, so we validate the proposal's
    *shape* against the ontology's invariants instead. Rules:
        - fqn-uniqueness         (term FQN must not collide with existing)
        - alias-non-collision    (aliases must not be claimed by other terms)
        - naming-convention      (fqn pattern + non-empty label/description)

  - `run_term_lifecycle(integrator, term, …)` — drives the entire 6-state
    flow for one term proposal. Returns `LifecycleResult` capturing the
    full trace (states visited, oracle status, final revision_id or rejection
    reason).

  - `auto_review_policy(proposal, term)` — encodes the decision rule used by
    the demo: if the LLM marked the term `needs_review=True`, surface for
    human triage by returning `CHANGE_REQUEST`; if oracle FAIL_BREAKING, REJECT;
    otherwise ACCEPT.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import text

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
from backend.sim_v2.core.recommendation.term_proposer import (
    BusinessTermProposal,
)
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleResult,
    OutputDiff,
    TraceDiff,
    aggregate_status_from_fixtures,
)


# ─────────────────────────────────────────────────────────────────────────────
# Term → Proposal conversion
# ─────────────────────────────────────────────────────────────────────────────


_TERM_FQN_RE = re.compile(r"^term\.[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")


def term_to_draft_proposal(
    term: BusinessTermProposal, plugin: str = "v2-slab-design",
) -> Proposal:
    """Convert a BusinessTermProposal into a DRAFT Proposal whose ontology_diff
    embeds the term's full structured payload.

    The plugin is required so the proposal can be filtered per plugin downstream
    (matches the Section 2 multi-plugin partition).
    """
    payload: dict[str, Any] = {
        "operation":   "ADD_BUSINESS_TERM",
        "fqn":         term.fqn,
        "label":       term.label,
        "description": term.description,
        "aliases":     list(term.aliases),
        "domain":      term.domain,
        "kind":        term.kind,
        "confidence":  term.confidence,
        "needs_review": term.needs_review,
        "source":      term.source,
        "target_class": term.target_class,
    }
    return Proposal(
        type="ontology_evolution",
        description=f"Add business_term {term.fqn!r} (from {term.target_class!r})",
        ontology_diff=payload,
        plugin=plugin,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Validation rules — fixtures the schema oracle runs
# ─────────────────────────────────────────────────────────────────────────────


SCHEMA_RULE_FQN_UNIQUE  = "schema.fqn_uniqueness"
SCHEMA_RULE_ALIASES     = "schema.alias_non_collision"
SCHEMA_RULE_NAMING      = "schema.naming_convention"
SCHEMA_RULE_NON_EMPTY   = "schema.non_empty_fields"

DEFAULT_SCHEMA_FIXTURES: tuple[str, ...] = (
    SCHEMA_RULE_FQN_UNIQUE,
    SCHEMA_RULE_ALIASES,
    SCHEMA_RULE_NAMING,
    SCHEMA_RULE_NON_EMPTY,
)


@dataclass(frozen=True)
class _ExistingTermSnapshot:
    """Snapshot of business_terms used as ground truth for the oracle."""
    fqns:    frozenset[str]
    aliases: frozenset[str]

    @classmethod
    def empty(cls) -> "_ExistingTermSnapshot":
        return cls(fqns=frozenset(), aliases=frozenset())

    @classmethod
    def from_session(
        cls, session: Session, repo_id: str,
    ) -> "_ExistingTermSnapshot":
        rows = session.execute(
            text(
                "SELECT fqn, aliases_json FROM business_terms WHERE repo_id = :rid"
            ),
            {"rid": repo_id},
        ).fetchall()
        fqns: set[str] = set()
        aliases: set[str] = set()
        for fqn, aliases_json in rows:
            if fqn:
                fqns.add(fqn)
            try:
                for a in json.loads(aliases_json or "[]"):
                    if isinstance(a, str):
                        aliases.add(a)
            except json.JSONDecodeError:
                pass
        return cls(fqns=frozenset(fqns), aliases=frozenset(aliases))


# ─────────────────────────────────────────────────────────────────────────────
# Term schema oracle (implements FixtureRunner)
# ─────────────────────────────────────────────────────────────────────────────


class TermSchemaOracle:
    """A `FixtureRunner` whose "fixtures" are schema-validation rules.

    Each call to `run_fixture(rule_id, ...)` evaluates one rule against the
    `BusinessTermProposal` currently in flight and yields a `FixtureOracleResult`.
    PASS / FAIL_OUTPUT outcomes map cleanly into the existing oracle 4-tier.
    """

    def __init__(
        self,
        term: BusinessTermProposal,
        existing: _ExistingTermSnapshot | None = None,
    ) -> None:
        self._term = term
        self._existing = existing or _ExistingTermSnapshot.empty()

    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict[str, Any],
    ) -> FixtureOracleResult:
        if fixture_id == SCHEMA_RULE_FQN_UNIQUE:
            return self._fqn_unique_rule()
        if fixture_id == SCHEMA_RULE_ALIASES:
            return self._alias_rule()
        if fixture_id == SCHEMA_RULE_NAMING:
            return self._naming_rule()
        if fixture_id == SCHEMA_RULE_NON_EMPTY:
            return self._non_empty_rule()
        return _error_result(fixture_id, f"unknown schema rule: {fixture_id!r}")

    def _fqn_unique_rule(self) -> FixtureOracleResult:
        if self._term.fqn in self._existing.fqns:
            return _fail_output(
                SCHEMA_RULE_FQN_UNIQUE,
                expected=f"{self._term.fqn!r} is novel",
                actual=f"{self._term.fqn!r} already exists in business_terms",
                summary=f"fqn collision: {self._term.fqn!r}",
            )
        return _pass(SCHEMA_RULE_FQN_UNIQUE, "fqn not in existing snapshot")

    def _alias_rule(self) -> FixtureOracleResult:
        # target_class is always allowed even if it matches an existing alias
        # (the term simply renames an unmapped concept; W61 dedup signals it
        # separately as duplicate_of, not a hard fail here).
        forbidden = {a for a in self._term.aliases
                     if a in self._existing.aliases and a != self._term.target_class}
        if forbidden:
            return _fail_output(
                SCHEMA_RULE_ALIASES,
                expected="all aliases novel (or = target_class)",
                actual=f"alias collision: {sorted(forbidden)}",
                summary=f"alias collision with existing terms: {sorted(forbidden)}",
            )
        return _pass(SCHEMA_RULE_ALIASES, "no alias collision")

    def _naming_rule(self) -> FixtureOracleResult:
        if not _TERM_FQN_RE.fullmatch(self._term.fqn):
            return _fail_output(
                SCHEMA_RULE_NAMING,
                expected="^term\\.[a-z][a-z0-9_]*…",
                actual=self._term.fqn,
                summary=f"fqn does not match naming convention: {self._term.fqn!r}",
            )
        return _pass(SCHEMA_RULE_NAMING, "fqn matches naming convention")

    def _non_empty_rule(self) -> FixtureOracleResult:
        missing: list[str] = []
        if not self._term.label.strip():
            missing.append("label")
        if not self._term.description.strip():
            missing.append("description")
        if not self._term.domain.strip():
            missing.append("domain")
        if missing:
            return _fail_output(
                SCHEMA_RULE_NON_EMPTY,
                expected="all of (label, description, domain) non-empty",
                actual=f"missing/empty: {missing}",
                summary=f"missing required fields: {missing}",
            )
        return _pass(SCHEMA_RULE_NON_EMPTY, "all required fields present")


def _pass(fixture_id: str, summary: str) -> FixtureOracleResult:
    return FixtureOracleResult(
        fixture_id=fixture_id,
        java_baseline_output=None,
        python_proposal_output=None,
        output_diff=OutputDiff(is_equivalent=True, summary=summary),
        trace_diff=TraceDiff(is_equivalent=True),
        status="PASS",
    )


def _fail_output(
    fixture_id: str, *, expected: Any, actual: Any, summary: str,
) -> FixtureOracleResult:
    return FixtureOracleResult(
        fixture_id=fixture_id,
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


def _error_result(fixture_id: str, err: str) -> FixtureOracleResult:
    return FixtureOracleResult(
        fixture_id=fixture_id,
        java_baseline_output=None,
        python_proposal_output=None,
        output_diff=OutputDiff(is_equivalent=False, summary=err),
        trace_diff=TraceDiff(is_equivalent=False),
        status="ERROR",
        error=err,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Verification engine adapter (matches Integrator's VerificationEngine Protocol)
# ─────────────────────────────────────────────────────────────────────────────


class _TermVerificationAdapter:
    """Bridges a TermSchemaOracle to the VerificationEngine Protocol the
    Integrator expects."""

    def __init__(self, oracle: TermSchemaOracle) -> None:
        self._oracle = oracle

    def run_oracle(self, request):
        by_fixture: dict[str, FixtureOracleResult] = {}
        for fid in request.fixture_subset:
            by_fixture[fid] = self._oracle.run_fixture(
                fixture_id=fid, plugin="term", apply_diffs={},
            )
        status = aggregate_status_from_fixtures(by_fixture)
        return OracleResult(
            proposal_id=request.proposal_id,
            by_fixture=by_fixture,
            aggregate_status=status,
            summary=f"{len(by_fixture)} schema rule(s), {status}",
        )


# Stub recommendation engine — only used for refine_proposal which we don't
# call from the term pipeline. Pre-instantiated below.
class _NoopRecommendation:
    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        return proposal


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle driver
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LifecycleResult:
    """Captures one term's journey through the lifecycle."""
    target_class:      str
    term_fqn:          str
    proposal_id:       str
    states_visited:    tuple[ProposalState, ...]
    final_state:       ProposalState
    oracle_status:     str | None = None
    revision_id:       str | None = None
    rejection_reason:  str | None = None


def auto_review_policy(
    oracle_status: str, term: BusinessTermProposal,
) -> str:
    """Decide the review decision.

    - oracle FAIL_BREAKING / FAIL_DRIFT          → REJECT
    - oracle PASS but term.needs_review=True     → CHANGE_REQUEST
    - oracle PASS and term.needs_review=False    → ACCEPT
    - oracle INCONCLUSIVE                        → CHANGE_REQUEST
    """
    if oracle_status in ("FAIL_BREAKING", "FAIL_DRIFT"):
        return "REJECT"
    if oracle_status == "INCONCLUSIVE":
        return "CHANGE_REQUEST"
    if term.needs_review:
        return "CHANGE_REQUEST"
    return "ACCEPT"


def make_integrator_for_term(
    term: BusinessTermProposal,
    existing: _ExistingTermSnapshot | None = None,
) -> tuple[Integrator, TermSchemaOracle]:
    """Construct a one-shot Integrator wired to a TermSchemaOracle for `term`."""
    oracle = TermSchemaOracle(term=term, existing=existing)
    integrator = Integrator(
        verification=_TermVerificationAdapter(oracle),
        recommendation=_NoopRecommendation(),
        proposal_store=ProposalStore(),
        revision_store=RevisionStore(),
    )
    return integrator, oracle


def run_term_lifecycle(
    term: BusinessTermProposal,
    *,
    existing: _ExistingTermSnapshot | None = None,
    plugin: str = "v2-slab-design",
    fixtures: tuple[str, ...] = DEFAULT_SCHEMA_FIXTURES,
    reviewer: str = "auto-policy",
) -> LifecycleResult:
    """Drive one term proposal through the full lifecycle.

    Returns a LifecycleResult — caller can inspect to see which state the
    proposal terminated in and why.
    """
    integrator, _oracle = make_integrator_for_term(term, existing=existing)
    states: list[ProposalState] = []

    proposal = term_to_draft_proposal(term, plugin=plugin)
    states.append(proposal.state)

    # DRAFT → PROPOSED
    prop_id = integrator.submit_proposal(proposal)
    states.append(proposal.state)

    # PROPOSED → ORACLED
    oracle_result = integrator.request_oracle(prop_id, fixture_subset=list(fixtures))
    states.append(proposal.state)

    decision = auto_review_policy(oracle_result.aggregate_status, term)

    # ORACLED → REVIEWED → terminal (or DRAFT, depending on decision)
    integrator.review_proposal(
        prop_id=prop_id,
        user_feedback=UserFeedback(
            decision=decision,
            timestamp=proposal.last_updated_at,
            user=reviewer,
            comments=f"auto-policy: oracle={oracle_result.aggregate_status}, "
                     f"needs_review={term.needs_review}",
        ),
    )
    # state may now be ACCEPTED / REJECTED / DRAFT depending on decision
    states.append(proposal.state)

    revision_id: str | None = None
    rejection_reason: str | None = None

    if proposal.state == "ACCEPTED":
        revision_id = integrator.merge_proposal(
            prop_id=prop_id,
            ontology_revision=f"term-{term.fqn}",
            code_revision="(no code change)",
            schema_revision="(no schema change)",
            created_by=reviewer,
        )
        states.append(proposal.state)   # MERGED
    elif proposal.state == "REJECTED":
        rejection_reason = (
            f"oracle={oracle_result.aggregate_status}, decision={decision}"
        )
    elif proposal.state == "DRAFT":
        # CHANGE_REQUEST returned to DRAFT — refine would loop in a real flow.
        # For the closed-loop demo, stop here and surface as needs-human.
        rejection_reason = (
            f"change-requested ({decision}) — needs human refinement"
        )

    return LifecycleResult(
        target_class=term.target_class,
        term_fqn=term.fqn,
        proposal_id=prop_id,
        states_visited=tuple(states),
        final_state=proposal.state,
        oracle_status=oracle_result.aggregate_status,
        revision_id=revision_id,
        rejection_reason=rejection_reason,
    )


__all__ = [
    "DEFAULT_SCHEMA_FIXTURES",
    "LifecycleResult",
    "SCHEMA_RULE_ALIASES",
    "SCHEMA_RULE_FQN_UNIQUE",
    "SCHEMA_RULE_NAMING",
    "SCHEMA_RULE_NON_EMPTY",
    "TermSchemaOracle",
    "_ExistingTermSnapshot",
    "auto_review_policy",
    "make_integrator_for_term",
    "run_term_lifecycle",
    "term_to_draft_proposal",
]
