"""Proposal data model + state machine 의 test.

ADR-003 §2-§3 + implementation-plan.md §3.2 Task B2.1 acceptance:
- State machine 의 valid/invalid 전이 test
- Audit log 의 immutable append-only 보장
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.sim_v2.core.integrator.proposal import (
    InvalidTransitionError,
    OracleAggregateStatus,
    OracleResult,
    Proposal,
    ProposalEvent,
    UserFeedback,
)


@pytest.fixture
def fresh_proposal() -> Proposal:
    return Proposal(
        type="schema_change",
        description="Add audit_log table for compliance tracking",
        schema_diff={"add_table": "audit_log"},
        plugin="banking",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Defaults + factory
# ─────────────────────────────────────────────────────────────────────────────


def test_proposal_default_state_is_draft(fresh_proposal: Proposal):
    assert fresh_proposal.state == "DRAFT"
    assert fresh_proposal.history == []
    assert fresh_proposal.oracle_result is None


def test_proposal_id_is_uuid(fresh_proposal: Proposal):
    # uuid.uuid4() 형식 — 36자 (8-4-4-4-12 with hyphens)
    assert len(fresh_proposal.id) == 36
    assert fresh_proposal.id.count("-") == 4


def test_proposal_timestamps_are_utc(fresh_proposal: Proposal):
    assert fresh_proposal.created_at.tzinfo is not None
    assert fresh_proposal.last_updated_at.tzinfo is not None


# ─────────────────────────────────────────────────────────────────────────────
# Valid transitions — happy path
# ─────────────────────────────────────────────────────────────────────────────


def test_happy_path_all_states(fresh_proposal: Proposal):
    """DRAFT → PROPOSED → ORACLED → REVIEWED → ACCEPTED → MERGED."""
    states = ["PROPOSED", "ORACLED", "REVIEWED", "ACCEPTED", "MERGED"]
    actors = ["integrator", "verification_engine", "user", "user", "integrator"]
    for state, actor in zip(states, actors):
        fresh_proposal.transition(to_state=state, actor=actor, notes=f"-> {state}")
    assert fresh_proposal.state == "MERGED"
    assert fresh_proposal.is_terminal()
    assert len(fresh_proposal.history) == 5


def test_history_event_records_transition(fresh_proposal: Proposal):
    fresh_proposal.transition(
        to_state="PROPOSED",
        actor="recommendation_engine",
        notes="initial proposal",
    )
    event = fresh_proposal.history[-1]
    assert event.from_state == "DRAFT"
    assert event.to_state == "PROPOSED"
    assert event.actor == "recommendation_engine"
    assert event.notes == "initial proposal"
    assert event.timestamp <= datetime.now(timezone.utc)


def test_event_is_immutable(fresh_proposal: Proposal):
    fresh_proposal.transition(to_state="PROPOSED", actor="integrator")
    event = fresh_proposal.history[0]
    with pytest.raises(ValidationError):
        event.notes = "tampered"


def test_refine_loop_proposed_to_draft(fresh_proposal: Proposal):
    """PROPOSED → DRAFT (refine loop) — ADR-003 §2 의 refine loop."""
    fresh_proposal.transition(to_state="PROPOSED", actor="recommendation_engine")
    fresh_proposal.transition(to_state="DRAFT", actor="recommendation_engine", notes="refine")
    assert fresh_proposal.state == "DRAFT"
    assert len(fresh_proposal.history) == 2


def test_refine_loop_reviewed_to_draft(fresh_proposal: Proposal):
    """REVIEWED → DRAFT (user CHANGE_REQUEST refine loop)."""
    fresh_proposal.transition(to_state="PROPOSED", actor="recommendation_engine")
    fresh_proposal.transition(to_state="ORACLED", actor="verification_engine")
    fresh_proposal.transition(to_state="REVIEWED", actor="user")
    fresh_proposal.transition(to_state="DRAFT", actor="user", notes="CHANGE_REQUEST")
    assert fresh_proposal.state == "DRAFT"


# ─────────────────────────────────────────────────────────────────────────────
# Invalid transitions
# ─────────────────────────────────────────────────────────────────────────────


def test_invalid_draft_to_oracled(fresh_proposal: Proposal):
    """DRAFT → ORACLED 직행 금지 (PROPOSED 거쳐야 함)."""
    with pytest.raises(InvalidTransitionError, match="DRAFT"):
        fresh_proposal.transition(to_state="ORACLED", actor="verification_engine")


def test_invalid_draft_to_merged(fresh_proposal: Proposal):
    with pytest.raises(InvalidTransitionError):
        fresh_proposal.transition(to_state="MERGED", actor="integrator")


def test_terminal_merged_no_outgoing(fresh_proposal: Proposal):
    # MERGED 도달 후 어디로도 못 감
    for state in ["PROPOSED", "ORACLED", "REVIEWED", "ACCEPTED", "MERGED"]:
        fresh_proposal.transition(to_state=state, actor="integrator")
    with pytest.raises(InvalidTransitionError):
        fresh_proposal.transition(to_state="REJECTED", actor="user")


def test_terminal_rejected_no_outgoing(fresh_proposal: Proposal):
    fresh_proposal.transition(to_state="REJECTED", actor="user", notes="rejected at draft")
    with pytest.raises(InvalidTransitionError):
        fresh_proposal.transition(to_state="DRAFT", actor="user")


# ─────────────────────────────────────────────────────────────────────────────
# REJECTED — from any non-terminal
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "before_reject_states",
    [
        [],
        ["PROPOSED"],
        ["PROPOSED", "ORACLED"],
        ["PROPOSED", "ORACLED", "REVIEWED"],
        ["PROPOSED", "ORACLED", "REVIEWED", "ACCEPTED"],
    ],
)
def test_reject_from_any_non_terminal(fresh_proposal: Proposal, before_reject_states):
    for state in before_reject_states:
        fresh_proposal.transition(to_state=state, actor="integrator")
    fresh_proposal.transition(to_state="REJECTED", actor="user", notes="rejected")
    assert fresh_proposal.state == "REJECTED"
    assert fresh_proposal.is_terminal()


# ─────────────────────────────────────────────────────────────────────────────
# Oracle result + user feedback
# ─────────────────────────────────────────────────────────────────────────────


def test_oracle_result_attach(fresh_proposal: Proposal):
    fresh_proposal.transition(to_state="PROPOSED", actor="recommendation_engine")
    fresh_proposal.oracle_result = OracleResult(
        aggregate_status="PASS",
        summary="all fixtures pass within tolerance",
    )
    fresh_proposal.transition(to_state="ORACLED", actor="verification_engine")
    assert fresh_proposal.oracle_result is not None
    assert fresh_proposal.oracle_result.aggregate_status == "PASS"


def test_user_feedback_attach(fresh_proposal: Proposal):
    fresh_proposal.transition(to_state="PROPOSED", actor="recommendation_engine")
    fresh_proposal.transition(to_state="ORACLED", actor="verification_engine")
    fresh_proposal.user_feedback.append(
        UserFeedback(
            decision="CHANGE_REQUEST",
            timestamp=datetime.now(timezone.utc),
            user="jeensh",
            comments="prefer 2-decimal scale for currency columns",
            fields_to_change=["schema_diff.add_column.precision"],
        )
    )
    fresh_proposal.transition(to_state="REVIEWED", actor="user")
    assert len(fresh_proposal.user_feedback) == 1
    assert fresh_proposal.user_feedback[0].decision == "CHANGE_REQUEST"


# ─────────────────────────────────────────────────────────────────────────────
# Helper API
# ─────────────────────────────────────────────────────────────────────────────


def test_allowed_next_states(fresh_proposal: Proposal):
    assert fresh_proposal.allowed_next_states() == {"PROPOSED", "REJECTED"}
    fresh_proposal.transition(to_state="PROPOSED", actor="integrator")
    assert fresh_proposal.allowed_next_states() == {"ORACLED", "DRAFT", "REJECTED"}


def test_can_transition_to(fresh_proposal: Proposal):
    assert fresh_proposal.can_transition_to("PROPOSED") is True
    assert fresh_proposal.can_transition_to("MERGED") is False
    assert fresh_proposal.can_transition_to("ORACLED") is False


def test_artifacts_in_event(fresh_proposal: Proposal):
    fresh_proposal.transition(
        to_state="PROPOSED",
        actor="recommendation_engine",
        artifacts={"llm_provider": "claude", "tokens_used": 1234},
    )
    event = fresh_proposal.history[0]
    assert event.artifacts["llm_provider"] == "claude"
    assert event.artifacts["tokens_used"] == 1234


# ─────────────────────────────────────────────────────────────────────────────
# Serialization (audit log persistence)
# ─────────────────────────────────────────────────────────────────────────────


def test_proposal_serializes_to_json(fresh_proposal: Proposal):
    fresh_proposal.transition(to_state="PROPOSED", actor="integrator", notes="ready")
    payload = fresh_proposal.model_dump(mode="json")
    serialized = json.dumps(payload)
    assert "PROPOSED" in serialized
    assert "ready" in serialized
    # Round-trip
    revived = Proposal.model_validate_json(serialized)
    assert revived.state == "PROPOSED"
    assert len(revived.history) == 1
    assert revived.history[0].notes == "ready"
