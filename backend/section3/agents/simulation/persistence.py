"""시뮬레이션 에이전트 — persistence layer.

multiturn 의 persistence.py 와 거의 동일하나 시뮬레이션 전용 테이블에 매핑.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from backend.modeling.persistence.database import session_scope

from .orm import SimulationDecisionLogRow, SimulationSessionRow


# ─────────────────────────────────────────────────────────────────────────────
# DTOs
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SimulationSession:
    id: str
    repo_id: str
    intent: str | None
    status: str
    user_query: str | None
    created_at: datetime
    last_activity_at: datetime


@dataclass(frozen=True)
class SimulationDecision:
    id: int
    session_id: str
    turn_no: int
    gate_kind: str
    payload: dict[str, Any]
    user_response: dict[str, Any] | None
    created_at: datetime


@dataclass(frozen=True)
class SimulationReplay:
    session: SimulationSession
    decisions: list[SimulationDecision]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _row_to_session(row: SimulationSessionRow) -> SimulationSession:
    return SimulationSession(
        id=row.id,
        repo_id=row.repo_id,
        intent=row.intent,
        status=row.status,
        user_query=row.user_query,
        created_at=row.created_at,
        last_activity_at=row.last_activity_at,
    )


def _row_to_decision(row: SimulationDecisionLogRow) -> SimulationDecision:
    return SimulationDecision(
        id=row.id,
        session_id=row.session_id,
        turn_no=row.turn_no,
        gate_kind=row.gate_kind,
        payload=json.loads(row.payload_json),
        user_response=(
            json.loads(row.user_response_json) if row.user_response_json else None
        ),
        created_at=row.created_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def start_session(
    *, repo_id: str, user_query: str | None = None,
) -> str:
    sid = f"sim-{uuid.uuid4().hex[:12]}"
    with session_scope() as s:
        row = SimulationSessionRow(
            id=sid, repo_id=repo_id, user_query=user_query,
        )
        s.add(row)
    return sid


def get_session(session_id: str) -> SimulationSession | None:
    with session_scope() as s:
        row = s.get(SimulationSessionRow, session_id)
        return _row_to_session(row) if row else None


def update_session(
    session_id: str,
    *, intent: str | None = None, status: str | None = None,
) -> None:
    with session_scope() as s:
        row = s.get(SimulationSessionRow, session_id)
        if not row:
            raise KeyError(f"session not found: {session_id}")
        if intent is not None:
            row.intent = intent
        if status is not None:
            row.status = status
        row.last_activity_at = datetime.now(timezone.utc)


def add_gate_decision(
    session_id: str,
    *, gate_kind: str, payload: dict[str, Any],
) -> int:
    with session_scope() as s:
        # next turn_no
        last = s.execute(
            select(SimulationDecisionLogRow.turn_no)
            .where(SimulationDecisionLogRow.session_id == session_id)
            .order_by(SimulationDecisionLogRow.turn_no.desc())
            .limit(1)
        ).scalar()
        turn_no = (last or 0) + 1
        row = SimulationDecisionLogRow(
            session_id=session_id,
            turn_no=turn_no,
            gate_kind=gate_kind,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        s.add(row)
        s.flush()
        return turn_no


def update_user_response(
    session_id: str,
    turn_no: int,
    user_response: dict[str, Any],
) -> None:
    with session_scope() as s:
        row = s.execute(
            select(SimulationDecisionLogRow)
            .where(SimulationDecisionLogRow.session_id == session_id)
            .where(SimulationDecisionLogRow.turn_no == turn_no)
        ).scalar_one_or_none()
        if not row:
            raise KeyError(f"decision not found: {session_id}/{turn_no}")
        row.user_response_json = json.dumps(user_response, ensure_ascii=False)


def list_sessions(limit: int = 30) -> list[SimulationSession]:
    """최신 세션 list — 생성 시간 역순."""
    with session_scope() as s:
        rows = s.execute(
            select(SimulationSessionRow)
            .order_by(SimulationSessionRow.last_activity_at.desc())
            .limit(limit)
        ).scalars().all()
        return [_row_to_session(r) for r in rows]


def replay_session(session_id: str) -> SimulationReplay | None:
    with session_scope() as s:
        sess_row = s.get(SimulationSessionRow, session_id)
        if not sess_row:
            return None
        dec_rows = s.execute(
            select(SimulationDecisionLogRow)
            .where(SimulationDecisionLogRow.session_id == session_id)
            .order_by(SimulationDecisionLogRow.turn_no.asc())
        ).scalars().all()
        return SimulationReplay(
            session=_row_to_session(sess_row),
            decisions=[_row_to_decision(r) for r in dec_rows],
        )
