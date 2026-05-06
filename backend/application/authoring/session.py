"""Authoring AI — session + decision log persistence.

Public API:
    create_session(...)             → str  (session_id, UUID4)
    get_session(session_id)         → AuthoringSession | None
    update_focus(session_id, ...)
    update_status(session_id, ...)
    add_decision(session_id, ...)   → int  (decision_id)
    list_decisions(session_id)      → list[AuthoringDecision]

The Pydantic types here are the *transport* shapes — they cross the API
boundary and the LLM capabilities consume them. The SQLAlchemy rows in
`orm.py` are the *storage* shapes; this module is the only place they meet.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.application.authoring.orm import (
    AuthoringDecisionRow,
    AuthoringSessionRow,
)
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)


SessionStatus = Literal["active", "paused", "merged", "abandoned"]
DecisionKind = Literal[
    "hypothesis_seeded",
    "interview_designed",
    "answer_absorbed",
    "option_selected",
    "naming_confirmed",
    "gap_resolved",
    "archive_saved",
    "next_entity_started",  # P1a-B: marker for cycle boundary in decision log
    "other",
]


# ── Transport schemas ────────────────────────────────────────────────


class AuthoringSession(BaseModel):
    id: str
    branch_name: str
    operator_id: str
    entity_focus: str | None = None
    repo_id: str | None = None
    status: SessionStatus
    meta: dict = Field(default_factory=dict)
    created_at: datetime
    last_activity_at: datetime


class AuthoringDecision(BaseModel):
    id: int
    session_id: str
    turn_no: int
    step_label: str | None = None
    entity_id: str | None = None
    decision_kind: DecisionKind
    payload: dict = Field(default_factory=dict)
    archive_markdown: str | None = None
    created_at: datetime


# ── Row → DTO ────────────────────────────────────────────────────────


def _row_to_session(row: AuthoringSessionRow) -> AuthoringSession:
    return AuthoringSession(
        id=row.id,
        branch_name=row.branch_name,
        operator_id=row.operator_id,
        entity_focus=row.entity_focus,
        repo_id=row.repo_id,
        status=row.status,  # type: ignore[arg-type]
        meta=json.loads(row.meta_json or "{}"),
        created_at=row.created_at,
        last_activity_at=row.last_activity_at,
    )


def _row_to_decision(row: AuthoringDecisionRow) -> AuthoringDecision:
    return AuthoringDecision(
        id=row.id,
        session_id=row.session_id,
        turn_no=row.turn_no,
        step_label=row.step_label,
        entity_id=row.entity_id,
        decision_kind=row.decision_kind,  # type: ignore[arg-type]
        payload=json.loads(row.payload_json or "{}"),
        archive_markdown=row.archive_markdown,
        created_at=row.created_at,
    )


# ── Session CRUD ─────────────────────────────────────────────────────


def create_session(
    *,
    operator_id: str = "default",
    branch_name: str = "main",
    repo_id: str | None = None,
    entity_focus: str | None = None,
    meta: dict | None = None,
) -> str:
    """Create a new authoring session and return its UUID4 id."""
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with session_scope() as s:
        s.add(
            AuthoringSessionRow(
                id=sid,
                branch_name=branch_name,
                operator_id=operator_id,
                entity_focus=entity_focus,
                repo_id=repo_id,
                status="active",
                meta_json=json.dumps(meta or {}, ensure_ascii=False),
                created_at=now,
                last_activity_at=now,
            )
        )
    logger.info(
        "authoring.session created id=%s operator=%s branch=%s repo=%s",
        sid, operator_id, branch_name, repo_id,
    )
    return sid


def get_session(session_id: str) -> AuthoringSession | None:
    with session_scope() as s:
        row = s.get(AuthoringSessionRow, session_id)
        if row is None:
            return None
        return _row_to_session(row)


def update_focus(session_id: str, entity_focus: str | None) -> None:
    with session_scope() as s:
        row = s.get(AuthoringSessionRow, session_id)
        if row is None:
            raise KeyError(f"authoring session not found: {session_id}")
        row.entity_focus = entity_focus
        row.last_activity_at = datetime.now(timezone.utc)


def update_status(session_id: str, status: SessionStatus) -> None:
    with session_scope() as s:
        row = s.get(AuthoringSessionRow, session_id)
        if row is None:
            raise KeyError(f"authoring session not found: {session_id}")
        row.status = status
        row.last_activity_at = datetime.now(timezone.utc)


def list_sessions(
    *,
    operator_id: str | None = None,
    status: SessionStatus | None = None,
) -> list[AuthoringSession]:
    """List sessions, newest activity first. Optional filters."""
    with session_scope() as s:
        stmt = select(AuthoringSessionRow).order_by(
            AuthoringSessionRow.last_activity_at.desc()
        )
        if operator_id is not None:
            stmt = stmt.where(AuthoringSessionRow.operator_id == operator_id)
        if status is not None:
            stmt = stmt.where(AuthoringSessionRow.status == status)
        rows = s.execute(stmt).scalars().all()
        return [_row_to_session(r) for r in rows]


# ── Decision log ─────────────────────────────────────────────────────


def add_decision(
    *,
    session_id: str,
    turn_no: int,
    decision_kind: DecisionKind,
    payload: dict,
    step_label: str | None = None,
    entity_id: str | None = None,
    archive_markdown: str | None = None,
) -> int:
    """Append one decision row, bump session.last_activity_at, return new id."""
    with session_scope() as s:
        # Validate session exists (gives a friendlier error than the FK violation).
        sess_row = s.get(AuthoringSessionRow, session_id)
        if sess_row is None:
            raise KeyError(f"authoring session not found: {session_id}")
        row = AuthoringDecisionRow(
            session_id=session_id,
            turn_no=turn_no,
            step_label=step_label,
            entity_id=entity_id,
            decision_kind=decision_kind,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            archive_markdown=archive_markdown,
        )
        s.add(row)
        sess_row.last_activity_at = datetime.now(timezone.utc)
        s.flush()  # populate row.id without leaving the with-block
        return row.id


def list_decisions(session_id: str) -> list[AuthoringDecision]:
    """All decisions for a session, ordered by (turn_no, id)."""
    with session_scope() as s:
        rows = (
            s.execute(
                select(AuthoringDecisionRow)
                .where(AuthoringDecisionRow.session_id == session_id)
                .order_by(AuthoringDecisionRow.turn_no, AuthoringDecisionRow.id)
            )
            .scalars()
            .all()
        )
        return [_row_to_decision(r) for r in rows]


__all__ = [
    "AuthoringSession",
    "AuthoringDecision",
    "SessionStatus",
    "DecisionKind",
    "create_session",
    "get_session",
    "update_focus",
    "update_status",
    "list_sessions",
    "add_decision",
    "list_decisions",
]
