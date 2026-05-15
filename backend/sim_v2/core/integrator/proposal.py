"""Proposal data model + state machine — Two-Engine Substrate (ADR-003).

State machine:
    DRAFT ─→ PROPOSED ─→ ORACLED ─→ REVIEWED ─→ ACCEPTED ─→ MERGED (terminal)
                              │              │
                              ↓              ↓
                          (refine loop)   REJECTED (terminal)

Public API:
    - Proposal — pydantic model with embedded state machine
    - ProposalEvent — immutable audit log entry per state transition
    - ProposalState — Literal type of all valid states
    - InvalidTransitionError — raised on attempted invalid transition

설계:
- State 전이는 Proposal.transition() method 가 enforce — 잘못된 전이는 reject
- 매 전이마다 ProposalEvent 자동 append (audit log immutable)
- pydantic 2.x BaseModel — frozen=False (state mutable), but history append-only
- proposal type 별 diff payload — schema_diff / code_diff / ontology_diff
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProposalState = Literal[
    "DRAFT",
    "PROPOSED",
    "ORACLED",
    "REVIEWED",
    "ACCEPTED",
    "MERGED",
    "REJECTED",
]

ProposalType = Literal["schema_change", "code_change", "ontology_evolution"]

ProposalActor = Literal[
    "recommendation_engine",
    "integrator",
    "verification_engine",
    "user",
]

OracleAggregateStatus = Literal[
    "PASS",
    "FAIL_BREAKING",
    "FAIL_DRIFT",
    "INCONCLUSIVE",
]


# 전이 그래프 — ADR-003 §2
_VALID_TRANSITIONS: dict[ProposalState, set[ProposalState]] = {
    "DRAFT":     {"PROPOSED", "REJECTED"},
    "PROPOSED":  {"ORACLED", "DRAFT", "REJECTED"},
    "ORACLED":   {"REVIEWED", "DRAFT", "REJECTED"},
    "REVIEWED":  {"ACCEPTED", "DRAFT", "REJECTED"},
    "ACCEPTED":  {"MERGED", "REJECTED"},
    "MERGED":    set(),    # terminal
    "REJECTED":  set(),    # terminal
}


class InvalidTransitionError(ValueError):
    """Raised when Proposal.transition() is called with a forbidden state pair."""


class ProposalEvent(BaseModel):
    """Immutable audit log entry — state 전이 1건."""
    model_config = ConfigDict(frozen=True)

    timestamp:  datetime
    from_state: ProposalState
    to_state:   ProposalState
    actor:      ProposalActor
    notes:      str = ""
    artifacts:  dict[str, Any] = Field(default_factory=dict)
    # state 별 첨부 — oracle_result / user_feedback / refinement_diff 등


class OracleResult(BaseModel):
    """ADR-003 §4 — OracleResult skeleton. Detail 은 verification engine 가 채움.

    본 Proposal module 은 status + summary 만 보관 — full structure 는
    backend/sim_v2/core/verification/oracle.py 에서 정의.
    """
    aggregate_status: OracleAggregateStatus
    summary:          str = ""
    # full detail (by_fixture, output_diff, trace_diff 등) 은 verification 의 OracleResult 가 보관.
    # Proposal 은 status pin point 만 .


class UserFeedback(BaseModel):
    """User review feedback (Defense Layer 4 — ADR-005)."""
    decision:    Literal["ACCEPT", "REJECT", "CHANGE_REQUEST", "PARTIAL_ACCEPT"]
    timestamp:   datetime
    user:        str
    comments:    str = ""
    fields_to_change: list[str] = Field(default_factory=list)
    # PARTIAL_ACCEPT case — specific field rejection


class Proposal(BaseModel):
    """Proposal lifecycle entity — ADR-003 §3.

    매 method 가 immutable 의도 (history append-only). state 만 직접 mutate.
    """
    id:           str = Field(default_factory=lambda: str(uuid.uuid4()))
    type:         ProposalType
    description:  str

    # 변경 candidate (type 별 schema)
    schema_diff:   dict[str, Any] | None = None   # for schema_change (ADR-004)
    code_diff:     dict[str, Any] | None = None   # for code_change
    ontology_diff: dict[str, Any] | None = None   # for ontology_evolution

    # Oracle 결과 (state >= ORACLED)
    oracle_result: OracleResult | None = None

    # Lifecycle
    state:           ProposalState = "DRAFT"
    created_at:      datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    history:         list[ProposalEvent] = Field(default_factory=list)

    # Metadata
    plugin:        str
    # 발행 plugin (e.g., "v2-slab-design", "broadleaf", "banking")

    user_feedback: list[UserFeedback] = Field(default_factory=list)

    # ────────────────────────────────────────────────────────────────────
    # State machine
    # ────────────────────────────────────────────────────────────────────

    def transition(
        self,
        to_state: ProposalState,
        actor: ProposalActor,
        notes: str = "",
        artifacts: dict[str, Any] | None = None,
    ) -> ProposalEvent:
        """State 전이 + ProposalEvent append.

        Raises:
            InvalidTransitionError: if (self.state, to_state) not in _VALID_TRANSITIONS.
        """
        from_state = self.state
        allowed = _VALID_TRANSITIONS.get(from_state, set())
        if to_state not in allowed:
            raise InvalidTransitionError(
                f"Invalid transition: {from_state!r} → {to_state!r} "
                f"(allowed from {from_state!r}: {sorted(allowed) or '(terminal)'})"
            )

        event = ProposalEvent(
            timestamp=datetime.now(timezone.utc),
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            notes=notes,
            artifacts=artifacts or {},
        )
        self.history.append(event)
        self.state = to_state
        self.last_updated_at = event.timestamp
        return event

    def is_terminal(self) -> bool:
        return self.state in {"MERGED", "REJECTED"}

    def can_transition_to(self, target: ProposalState) -> bool:
        return target in _VALID_TRANSITIONS.get(self.state, set())

    def allowed_next_states(self) -> set[ProposalState]:
        return set(_VALID_TRANSITIONS.get(self.state, set()))


__all__ = [
    "InvalidTransitionError",
    "OracleAggregateStatus",
    "OracleResult",
    "Proposal",
    "ProposalActor",
    "ProposalEvent",
    "ProposalState",
    "ProposalType",
    "UserFeedback",
]
