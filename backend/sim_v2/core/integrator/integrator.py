"""Integrator — Two-Engine Substrate 의 message bus + state manager.

ADR-003 §1. Verification ↔ Recommendation ↔ User 사이의 통신 protocol enforce.

Public API:
    - Integrator — 8-method class
    - ProposalStore — in-memory store (production = persistent)
    - ProposalRefinement — refine_proposal 의 input
    - VerificationEngine / RecommendationEngine — Protocol (implemented elsewhere)

8 method API:
    submit_proposal       DRAFT → PROPOSED, store entry 등록
    request_oracle        PROPOSED → ORACLED, verification 호출
    refine_proposal       ORACLED/REVIEWED → DRAFT, refinement diff 적용
    review_proposal       ORACLED → REVIEWED → ACCEPTED/DRAFT/REJECTED
    merge_proposal        ACCEPTED → MERGED, Revision 생성 + lineage
    reject_proposal       임의 non-terminal → REJECTED
    get_proposal          조회
    list_proposals        filter (state / plugin)

설계:
- ProposalStore = in-memory dict + simple filtering (W2-W3 sprint)
- VerificationEngine / RecommendationEngine = Protocol (W4-W10 / W8-W16 impl)
- Concurrency = single-thread for now (ADR-003 §6 의 multiple proposal 은 phase 2)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol

from pydantic import BaseModel, Field

from backend.sim_v2.core.integrator.proposal import (
    InvalidTransitionError,
    OracleResult as ProposalOracleResult,
    Proposal,
    ProposalState,
    UserFeedback,
)
from backend.sim_v2.core.integrator.revision import (
    FixtureBaseline,
    Revision,
    RevisionStore,
)
from backend.sim_v2.core.verification.oracle import (
    OracleRequest,
    OracleResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Protocols
# ─────────────────────────────────────────────────────────────────────────────


class VerificationEngine(Protocol):
    """Implemented by `backend.sim_v2.core.verification.engine` (W6+)."""

    def run_oracle(self, request: OracleRequest) -> OracleResult:
        ...


class RecommendationEngine(Protocol):
    """Implemented by `backend.sim_v2.core.recommendation.engine` (W8+)."""

    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Refinement payload
# ─────────────────────────────────────────────────────────────────────────────


class ProposalRefinement(BaseModel):
    """refine_proposal() input — partial diff update."""
    schema_diff_update:   dict | None = None
    code_diff_update:     dict | None = None
    ontology_diff_update: dict | None = None
    description_update:   str | None = None
    reason:               str = ""


# ─────────────────────────────────────────────────────────────────────────────
# In-memory store
# ─────────────────────────────────────────────────────────────────────────────


class ProposalStore:
    """In-memory proposal store. Production 시 SQLite / Postgres-backed."""

    def __init__(self) -> None:
        self._proposals: dict[str, Proposal] = {}

    def add(self, proposal: Proposal) -> None:
        if proposal.id in self._proposals:
            raise ValueError(f"Proposal {proposal.id!r} already exists")
        self._proposals[proposal.id] = proposal

    def get(self, proposal_id: str) -> Proposal | None:
        return self._proposals.get(proposal_id)

    def list(
        self,
        state: ProposalState | None = None,
        plugin: str | None = None,
    ) -> list[Proposal]:
        result = list(self._proposals.values())
        if state is not None:
            result = [p for p in result if p.state == state]
        if plugin is not None:
            result = [p for p in result if p.plugin == plugin]
        return result

    def count(self) -> int:
        return len(self._proposals)


# ─────────────────────────────────────────────────────────────────────────────
# Integrator — 8 method API
# ─────────────────────────────────────────────────────────────────────────────


class ProposalNotFoundError(KeyError):
    pass


class Integrator:
    """ADR-003 의 Integrator — Verification ↔ Recommendation ↔ User 통합."""

    def __init__(
        self,
        verification: VerificationEngine,
        recommendation: RecommendationEngine,
        proposal_store: ProposalStore | None = None,
        revision_store: RevisionStore | None = None,
    ) -> None:
        self._verification = verification
        self._recommendation = recommendation
        self._proposals = proposal_store or ProposalStore()
        self._revisions = revision_store or RevisionStore()
        self._full_oracle_results: dict[str, OracleResult] = {}
        # Proposal.oracle_result 는 placeholder (status+summary only).
        # Full per-fixture detail 은 본 dict 에 보관.

    # ─────────────────────────────────────────────────────────────────────
    # 1. submit_proposal
    # ─────────────────────────────────────────────────────────────────────

    def submit_proposal(self, prop: Proposal) -> str:
        """DRAFT → PROPOSED. Returns proposal_id."""
        if prop.state != "DRAFT":
            raise ValueError(
                f"submit_proposal expects DRAFT, got {prop.state!r}"
            )
        self._proposals.add(prop)
        prop.transition(
            to_state="PROPOSED",
            actor="recommendation_engine",
            notes="submitted via Integrator.submit_proposal",
        )
        return prop.id

    # ─────────────────────────────────────────────────────────────────────
    # 1b. re_propose — after refine, transition DRAFT → PROPOSED in place
    # ─────────────────────────────────────────────────────────────────────

    def re_propose(
        self,
        prop_id: str,
        actor: str = "recommendation_engine",
        notes: str = "re-submit after refinement",
    ) -> None:
        """DRAFT → PROPOSED for a proposal already in the store.

        Used by the refine loop: after `refine_proposal` moves the proposal back
        to DRAFT, the caller invokes this to re-promote without going through
        `submit_proposal` (which would try to re-add to the store and raise).
        """
        prop = self._proposals.get(prop_id)
        if prop is None:
            raise ProposalNotFoundError(prop_id)
        if prop.state != "DRAFT":
            raise InvalidTransitionError(
                f"re_propose expects DRAFT, got {prop.state!r}"
            )
        prop.transition(
            to_state="PROPOSED",
            actor=actor if actor in {"recommendation_engine", "user", "integrator"} else "integrator",
            notes=notes,
        )

    # ─────────────────────────────────────────────────────────────────────
    # 2. request_oracle
    # ─────────────────────────────────────────────────────────────────────

    def request_oracle(
        self,
        prop_id: str,
        fixture_subset: list[str],
    ) -> OracleResult:
        """PROPOSED → ORACLED. Verification engine 호출 + result attach."""
        prop = self._proposals.get(prop_id)
        if prop is None:
            raise ProposalNotFoundError(prop_id)
        if prop.state != "PROPOSED":
            raise InvalidTransitionError(
                f"request_oracle expects PROPOSED, got {prop.state!r}"
            )

        request = OracleRequest(
            proposal_id=prop_id,
            fixture_subset=fixture_subset,
            apply_schema_diff=prop.schema_diff,
            apply_code_diff=prop.code_diff,
            apply_ontology_diff=prop.ontology_diff,
        )
        result = self._verification.run_oracle(request)

        # Store full oracle result + placeholder on Proposal
        self._full_oracle_results[prop_id] = result
        prop.oracle_result = ProposalOracleResult(
            aggregate_status=result.aggregate_status,
            summary=result.summary,
        )
        prop.transition(
            to_state="ORACLED",
            actor="verification_engine",
            notes=f"oracle result: {result.aggregate_status}",
            artifacts={"by_fixture_count": len(result.by_fixture)},
        )
        return result

    def get_full_oracle_result(self, prop_id: str) -> OracleResult | None:
        return self._full_oracle_results.get(prop_id)

    # ─────────────────────────────────────────────────────────────────────
    # 3. refine_proposal
    # ─────────────────────────────────────────────────────────────────────

    def refine_proposal(
        self,
        prop_id: str,
        refinement: ProposalRefinement,
        actor: str = "recommendation_engine",
    ) -> None:
        """Non-terminal → DRAFT (refine loop). Refinement diff 적용."""
        prop = self._proposals.get(prop_id)
        if prop is None:
            raise ProposalNotFoundError(prop_id)
        if prop.state not in {"PROPOSED", "ORACLED", "REVIEWED"}:
            raise InvalidTransitionError(
                f"refine_proposal expects PROPOSED/ORACLED/REVIEWED, got {prop.state!r}"
            )

        # Apply refinement diff (merge — partial update)
        if refinement.schema_diff_update is not None:
            prop.schema_diff = {**(prop.schema_diff or {}), **refinement.schema_diff_update}
        if refinement.code_diff_update is not None:
            prop.code_diff = {**(prop.code_diff or {}), **refinement.code_diff_update}
        if refinement.ontology_diff_update is not None:
            prop.ontology_diff = {**(prop.ontology_diff or {}), **refinement.ontology_diff_update}
        if refinement.description_update is not None:
            prop.description = refinement.description_update

        # Clear stale oracle result
        prop.oracle_result = None
        self._full_oracle_results.pop(prop_id, None)

        # transition: cast actor literal
        prop.transition(
            to_state="DRAFT",
            actor=actor if actor in {"recommendation_engine", "user", "integrator"} else "integrator",
            notes=refinement.reason or "refinement applied",
        )

    # ─────────────────────────────────────────────────────────────────────
    # 4. review_proposal
    # ─────────────────────────────────────────────────────────────────────

    def review_proposal(
        self,
        prop_id: str,
        user_feedback: UserFeedback,
    ) -> ProposalState:
        """ORACLED → REVIEWED → ACCEPTED/REJECTED (or DRAFT for CHANGE_REQUEST).

        Returns the resulting state.
        """
        prop = self._proposals.get(prop_id)
        if prop is None:
            raise ProposalNotFoundError(prop_id)
        if prop.state != "ORACLED":
            raise InvalidTransitionError(
                f"review_proposal expects ORACLED, got {prop.state!r}"
            )

        prop.user_feedback.append(user_feedback)

        # ORACLED → REVIEWED (intermediate)
        prop.transition(
            to_state="REVIEWED",
            actor="user",
            notes=f"user reviewed: {user_feedback.decision}",
        )

        # REVIEWED → terminal (per user decision)
        if user_feedback.decision == "ACCEPT":
            prop.transition(to_state="ACCEPTED", actor="user")
        elif user_feedback.decision == "REJECT":
            prop.transition(to_state="REJECTED", actor="user", notes=user_feedback.comments)
        elif user_feedback.decision == "CHANGE_REQUEST":
            prop.transition(
                to_state="DRAFT",
                actor="user",
                notes=f"CHANGE_REQUEST: {user_feedback.comments}",
            )
        elif user_feedback.decision == "PARTIAL_ACCEPT":
            # PARTIAL_ACCEPT — Phase 2. 현재는 DRAFT 로 회귀
            prop.transition(
                to_state="DRAFT",
                actor="user",
                notes=f"PARTIAL_ACCEPT (phase 2 → refine): {user_feedback.comments}",
                artifacts={"fields_to_change": user_feedback.fields_to_change},
            )

        return prop.state

    # ─────────────────────────────────────────────────────────────────────
    # 5. merge_proposal
    # ─────────────────────────────────────────────────────────────────────

    def merge_proposal(
        self,
        prop_id: str,
        ontology_revision: str,
        code_revision: str,
        schema_revision: str,
        created_by: str,
        parent_revision: str | None = None,
        fixture_baselines: dict[str, FixtureBaseline] | None = None,
    ) -> str:
        """ACCEPTED → MERGED. Revision 생성 + lineage. Returns revision_id."""
        prop = self._proposals.get(prop_id)
        if prop is None:
            raise ProposalNotFoundError(prop_id)
        if prop.state != "ACCEPTED":
            raise InvalidTransitionError(
                f"merge_proposal expects ACCEPTED, got {prop.state!r}"
            )

        revision = Revision(
            proposal_id=prop_id,
            ontology_revision=ontology_revision,
            code_revision=code_revision,
            schema_revision=schema_revision,
            parent_revision=parent_revision,
            fixture_baselines=fixture_baselines or {},
            created_by=created_by,
        )
        self._revisions.add(revision)

        prop.transition(
            to_state="MERGED",
            actor="integrator",
            notes=f"merged → revision {revision.id}",
            artifacts={
                "revision_id": revision.id,
                "ontology_revision": ontology_revision,
                "code_revision": code_revision,
                "schema_revision": schema_revision,
            },
        )
        return revision.id

    # ─────────────────────────────────────────────────────────────────────
    # 6. reject_proposal
    # ─────────────────────────────────────────────────────────────────────

    def reject_proposal(
        self,
        prop_id: str,
        reason: str = "",
        actor: str = "user",
    ) -> None:
        """Non-terminal → REJECTED."""
        prop = self._proposals.get(prop_id)
        if prop is None:
            raise ProposalNotFoundError(prop_id)
        if prop.is_terminal():
            raise InvalidTransitionError(
                f"reject_proposal cannot transition from terminal {prop.state!r}"
            )

        prop.transition(
            to_state="REJECTED",
            actor=actor if actor in {"recommendation_engine", "user", "integrator"} else "user",
            notes=reason,
        )

    # ─────────────────────────────────────────────────────────────────────
    # 7-8. get_proposal / list_proposals
    # ─────────────────────────────────────────────────────────────────────

    def get_proposal(self, prop_id: str) -> Proposal | None:
        return self._proposals.get(prop_id)

    def list_proposals(
        self,
        state: ProposalState | None = None,
        plugin: str | None = None,
    ) -> list[Proposal]:
        return self._proposals.list(state=state, plugin=plugin)

    # ─────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────

    @property
    def proposal_store(self) -> ProposalStore:
        return self._proposals

    @property
    def revision_store(self) -> RevisionStore:
        return self._revisions


__all__ = [
    "Integrator",
    "ProposalNotFoundError",
    "ProposalRefinement",
    "ProposalStore",
    "RecommendationEngine",
    "VerificationEngine",
]
