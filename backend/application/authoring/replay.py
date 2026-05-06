"""P1a-B — Session resume.

Walk a session's decision log chronologically and rebuild the structured
state the frontend needs to populate its Zustand store. Splits the log
into completed entity cycles (separated by `next_entity_started` markers)
and the current in-progress cycle.

Public API:
    build_resume_state(session_id) -> SessionResumeState
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.application.authoring import session as session_mod

logger = logging.getLogger(__name__)


class CompletedEntitySnapshot(BaseModel):
    """Per-entity snapshot rebuilt from the decisions of one cycle.

    Stays JSON-friendly — payloads are dicts, not Pydantic models, so the
    frontend can parse without sharing models.
    """

    jpo: dict | None = None
    hypothesis: dict | None = None
    accepted_option: dict | None = None
    names: dict | None = None
    archive: dict | None = None
    pattern: dict | None = None
    gaps: dict | None = None
    persisted_fqns: list[str] = Field(default_factory=list)
    completed_at: str | None = None  # ISO timestamp from "next_entity_started" or last archive_saved


class CurrentEntityState(BaseModel):
    """In-progress entity state — every artifact since the last
    `next_entity_started` marker (or session start)."""

    jpo: dict | None = None
    hypothesis: dict | None = None
    batch: dict | None = None
    answers: dict | None = None
    option_table: dict | None = None
    accepted_option: dict | None = None
    gaps: dict | None = None
    pattern: dict | None = None
    names: dict | None = None
    archive: dict | None = None
    persisted_fqns: list[str] = Field(default_factory=list)


class SessionResumeState(BaseModel):
    session: session_mod.AuthoringSession
    completed_entities: list[CompletedEntitySnapshot] = Field(default_factory=list)
    current: CurrentEntityState = Field(default_factory=CurrentEntityState)
    cost_total_usd: float = 0.0
    decision_count: int = 0


def _empty_current() -> dict[str, Any]:
    return {
        "jpo": None,
        "hypothesis": None,
        "batch": None,
        "answers": None,
        "option_table": None,
        "accepted_option": None,
        "gaps": None,
        "pattern": None,
        "names": None,
        "archive": None,
        "persisted_fqns": [],
    }


def _apply_decision(state: dict[str, Any], decision: session_mod.AuthoringDecision) -> None:
    """Mutate `state` to reflect this decision."""
    payload = decision.payload or {}
    cap = payload.get("capability") if isinstance(payload, dict) else None
    result = payload.get("result") if isinstance(payload, dict) else None

    kind = decision.decision_kind
    if kind == "hypothesis_seeded" and result:
        state["hypothesis"] = result
    elif kind == "interview_designed" and result:
        state["batch"] = result
    elif kind == "answer_absorbed" and result:
        state["answers"] = result
    elif kind == "option_selected" and result:
        state["accepted_option"] = result
    elif kind == "naming_confirmed" and result:
        state["names"] = result
    elif kind == "archive_saved" and result:
        # archive_saved comes from cap 9 (single-entity) — store the doc
        state["archive"] = result
    elif kind == "other" and cap:
        if cap == "code_extractor" and result:
            state["jpo"] = result
        elif cap == "option_proposer" and result:
            state["option_table"] = result
        elif cap == "gap_detector" and result:
            state["gaps"] = result
        elif cap == "pattern_checker" and result:
            state["pattern"] = result
        # cap 10 (next_step) / cap 11 (next_entity) / cap 12 (comprehensive_archive)
        # do not contribute to per-entity state — they're advisory snapshots.
    # confirm endpoint also writes a decision; we look for persisted_fqns there.
    if isinstance(payload, dict):
        fqns = payload.get("persisted_fqns")
        if isinstance(fqns, list) and fqns:
            # Confirm response has fqns; merge dedup.
            existing = set(state.get("persisted_fqns") or [])
            for f in fqns:
                if isinstance(f, str):
                    existing.add(f)
            state["persisted_fqns"] = sorted(existing)


def _state_to_completed(state: dict[str, Any], boundary_at_iso: str | None) -> CompletedEntitySnapshot:
    return CompletedEntitySnapshot(
        jpo=state.get("jpo"),
        hypothesis=state.get("hypothesis"),
        accepted_option=state.get("accepted_option"),
        names=state.get("names"),
        archive=state.get("archive"),
        pattern=state.get("pattern"),
        gaps=state.get("gaps"),
        persisted_fqns=state.get("persisted_fqns") or [],
        completed_at=boundary_at_iso,
    )


def build_resume_state(session_id: str) -> SessionResumeState | None:
    """Rebuild the structured session state by walking the decision log.

    Returns None if the session does not exist.
    """
    sess = session_mod.get_session(session_id)
    if sess is None:
        return None

    decisions = session_mod.list_decisions(session_id)
    # list_decisions is ordered by created_at via store implementation.

    current = _empty_current()
    completed: list[CompletedEntitySnapshot] = []
    cost_total = 0.0  # filled below from cost log

    for d in decisions:
        if d.decision_kind == "next_entity_started":
            # Boundary: snapshot the current cycle (only if anything was set)
            if any(current[k] is not None for k in ("jpo", "hypothesis")):
                completed.append(
                    _state_to_completed(current, boundary_at_iso=d.created_at.isoformat())
                )
            current = _empty_current()
            continue
        _apply_decision(current, d)

    # Cost total from cost log (running total). Use the in-memory ring buffer.
    try:
        from backend.application.authoring.cost import session_total_usd

        cost_total = session_total_usd(session_id)
    except Exception:  # noqa: BLE001
        pass

    return SessionResumeState(
        session=sess,
        completed_entities=completed,
        current=CurrentEntityState(**current),
        cost_total_usd=cost_total,
        decision_count=len(decisions),
    )


__all__ = [
    "CompletedEntitySnapshot",
    "CurrentEntityState",
    "SessionResumeState",
    "build_resume_state",
]
