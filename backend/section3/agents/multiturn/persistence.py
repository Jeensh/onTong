"""Section 3 multiturn — persistence layer.

차용 원본: `backend/application/authoring/session.py:190-233` (add_decision/list).
Source-of-truth replay (CHAT_REDESIGN_SPEC.md v2 §5) — payload_json 자체가
완결, sim_v2 tool 재실행 없음.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import select

from backend.modeling.persistence.database import session_scope

from .orm import Section3DecisionLogRow, Section3SessionRow
from .schemas import GatePayload


# ─────────────────────────────────────────────────────────────────────────────
# DTOs (frozen) — caller 가 row 직접 안 보게
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Section3Session:
    id: str
    repo_id: str
    status: str
    user_query: str | None
    created_at: datetime
    last_activity_at: datetime


@dataclass(frozen=True)
class Section3Decision:
    id: int
    session_id: str
    turn_no: int
    gate_kind: str
    payload: dict[str, Any]
    user_response: dict[str, Any] | None
    created_at: datetime

    @property
    def typed_payload(self):
        """Hydrate payload dict → typed Pydantic model (discriminated union)."""
        return TypeAdapter(GatePayload).validate_python(self.payload)


@dataclass(frozen=True)
class SessionReplay:
    session: Section3Session
    decisions: list[Section3Decision]


@dataclass(frozen=True)
class SessionSummary:
    """history browser 용 — Section3Session + 누적 카운트 + 최종 게이트."""
    id: str
    repo_id: str
    status: str
    user_query: str | None
    created_at: datetime
    last_activity_at: datetime
    turn_count: int
    last_gate_kind: str | None


def _row_to_session(row: Section3SessionRow) -> Section3Session:
    return Section3Session(
        id=row.id,
        repo_id=row.repo_id,
        status=row.status,
        user_query=row.user_query,
        created_at=row.created_at,
        last_activity_at=row.last_activity_at,
    )


def _row_to_decision(row: Section3DecisionLogRow) -> Section3Decision:
    return Section3Decision(
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
# Session lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def start_session(*, repo_id: str, user_query: str | None = None) -> str:
    """새 세션 생성 → UUID 반환."""
    session_id = str(uuid.uuid4())
    with session_scope() as s:
        s.add(Section3SessionRow(
            id=session_id,
            repo_id=repo_id,
            status="active",
            user_query=user_query,
        ))
    return session_id


def get_session(session_id: str) -> Section3Session | None:
    with session_scope() as s:
        row = s.get(Section3SessionRow, session_id)
        return _row_to_session(row) if row else None


def update_session_status(session_id: str, status: str) -> None:
    """status: "active" | "done" | "blocked"."""
    with session_scope() as s:
        row = s.get(Section3SessionRow, session_id)
        if row is None:
            raise KeyError(f"section3 session not found: {session_id}")
        row.status = status
        row.last_activity_at = datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Decision log
# ─────────────────────────────────────────────────────────────────────────────


def add_gate_decision(
    *,
    session_id: str,
    turn_no: int,
    gate_payload: dict[str, Any],
) -> int:
    """payload 한 행 append + session.last_activity 갱신. row id 반환."""
    with session_scope() as s:
        sess_row = s.get(Section3SessionRow, session_id)
        if sess_row is None:
            raise KeyError(f"section3 session not found: {session_id}")
        gate_kind = gate_payload.get("kind")
        if not gate_kind:
            raise ValueError("gate_payload missing 'kind' field")
        row = Section3DecisionLogRow(
            session_id=session_id,
            turn_no=turn_no,
            gate_kind=gate_kind,
            payload_json=json.dumps(gate_payload, ensure_ascii=False, default=str),
        )
        s.add(row)
        sess_row.last_activity_at = datetime.now(timezone.utc)
        s.flush()
        return row.id


def list_gate_decisions(session_id: str) -> list[Section3Decision]:
    """turn_no asc, id asc 정렬."""
    with session_scope() as s:
        rows = (
            s.execute(
                select(Section3DecisionLogRow)
                .where(Section3DecisionLogRow.session_id == session_id)
                .order_by(
                    Section3DecisionLogRow.turn_no,
                    Section3DecisionLogRow.id,
                )
            )
            .scalars()
            .all()
        )
        return [_row_to_decision(r) for r in rows]


def update_user_response(
    decision_id: int, user_response: dict[str, Any],
) -> None:
    """카드 버튼 응답 ([confirm] / [modify] / [retry]) 저장."""
    with session_scope() as s:
        row = s.get(Section3DecisionLogRow, decision_id)
        if row is None:
            raise KeyError(f"section3 decision not found: {decision_id}")
        row.user_response_json = json.dumps(
            user_response, ensure_ascii=False, default=str,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Replay — source-of-truth (sim_v2 재호출 X, payload 자체로 완결)
# ─────────────────────────────────────────────────────────────────────────────


def replay_session(session_id: str) -> SessionReplay | None:
    sess = get_session(session_id)
    if sess is None:
        return None
    decisions = list_gate_decisions(session_id)
    return SessionReplay(session=sess, decisions=decisions)


# ─────────────────────────────────────────────────────────────────────────────
# Recent sessions browser — Option B (Phase 11)
# ─────────────────────────────────────────────────────────────────────────────


def list_recent_sessions(
    *,
    limit: int = 50,
    repo_id: str | None = None,
    search: str | None = None,
) -> list[SessionSummary]:
    """최근 N 세션 + per-session turn_count + last_gate_kind.

    정렬: last_activity_at desc.
    Filters:
      - repo_id: equality
      - search: user_query substring (case-insensitive)
    """
    with session_scope() as s:
        stmt = select(Section3SessionRow).order_by(
            Section3SessionRow.last_activity_at.desc(),
        )
        if repo_id:
            stmt = stmt.where(Section3SessionRow.repo_id == repo_id)
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(Section3SessionRow.user_query.ilike(like))
        stmt = stmt.limit(limit)
        sess_rows = list(s.execute(stmt).scalars().all())
        if not sess_rows:
            return []

        ids = [r.id for r in sess_rows]
        # 모든 decision rows 한 번에 fetch — session 별 turn desc 정렬
        dec_rows = s.execute(
            select(
                Section3DecisionLogRow.session_id,
                Section3DecisionLogRow.gate_kind,
                Section3DecisionLogRow.turn_no,
                Section3DecisionLogRow.id,
            )
            .where(Section3DecisionLogRow.session_id.in_(ids))
            .order_by(
                Section3DecisionLogRow.session_id,
                Section3DecisionLogRow.turn_no.desc(),
                Section3DecisionLogRow.id.desc(),
            ),
        ).all()
        counts: dict[str, int] = {}
        last_kind: dict[str, str] = {}
        for sid, kind, _turn, _id in dec_rows:
            counts[sid] = counts.get(sid, 0) + 1
            # 정렬상 첫 row 가 latest turn
            if sid not in last_kind:
                last_kind[sid] = kind

        return [
            SessionSummary(
                id=r.id,
                repo_id=r.repo_id,
                status=r.status,
                user_query=r.user_query,
                created_at=r.created_at,
                last_activity_at=r.last_activity_at,
                turn_count=counts.get(r.id, 0),
                last_gate_kind=last_kind.get(r.id),
            )
            for r in sess_rows
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 16L — integrity_warning 발화율 metric (운영 dashboard)
# ─────────────────────────────────────────────────────────────────────────────


_WARNING_RE = re.compile(r"integrity_warning=([a-z_]+)")


@dataclass(frozen=True)
class WarningRates:
    """최근 N 세션의 integrity_warning 발화 통계.

    Phase 16L — modeling 시드 품질 회귀 지표. by_kind 는 각 warning 종류가
    **한 세션에서 한 번이라도** 발화한 session count (per-session dedupe).
    """
    total_sessions: int
    by_kind: dict[str, int]
    by_kind_pct: dict[str, float]


def compute_warning_rates(
    *,
    repo_id: str | None = None,
    limit: int = 50,
) -> WarningRates:
    """최근 `limit` 세션의 모든 decision payload 에서 integrity_warning 빈도 집계.

    구현:
      1. last_activity_at desc 로 최근 N session
      2. 그 session 들의 모든 decision payload_json 에서 `integrity_warning=KIND` 추출
      3. session 별 dedupe 후 KIND 별 session count
    """
    with session_scope() as s:
        sess_stmt = select(Section3SessionRow.id).order_by(
            Section3SessionRow.last_activity_at.desc(),
        )
        if repo_id:
            sess_stmt = sess_stmt.where(Section3SessionRow.repo_id == repo_id)
        sess_stmt = sess_stmt.limit(limit)
        sess_ids = list(s.execute(sess_stmt).scalars().all())
        if not sess_ids:
            return WarningRates(total_sessions=0, by_kind={}, by_kind_pct={})

        dec_rows = s.execute(
            select(
                Section3DecisionLogRow.session_id,
                Section3DecisionLogRow.payload_json,
            ).where(Section3DecisionLogRow.session_id.in_(sess_ids)),
        ).all()

        sess_kinds: dict[str, set[str]] = {sid: set() for sid in sess_ids}
        for sid, pj in dec_rows:
            if not pj:
                continue
            for m in _WARNING_RE.finditer(pj):
                sess_kinds[sid].add(m.group(1))

        by_kind: dict[str, int] = {}
        for kinds in sess_kinds.values():
            for k in kinds:
                by_kind[k] = by_kind.get(k, 0) + 1

        total = len(sess_ids)
        by_kind_pct = {
            k: round(100 * n / total, 1) for k, n in by_kind.items()
        }
        return WarningRates(
            total_sessions=total, by_kind=by_kind, by_kind_pct=by_kind_pct,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 16O — 0-candidate query 추적 (매핑 갭 자동 탐지)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ZeroCandQuery:
    """0-candidate Gate I 가 반환된 session 의 user_query.

    Phase 16O — 15C PM 권장 "사용자 query 로그 기반 매핑 갭 자동 탐지".
    modeling team 이 어떤 단어로 매칭 실패했는지 인지 → BusinessTerm 시드 보강.
    """
    session_id: str
    user_query: str
    repo_id: str
    created_at: datetime
    suggestions: list[str]


def list_zero_cand_queries(
    *,
    repo_id: str | None = None,
    limit: int = 20,
) -> list[ZeroCandQuery]:
    """최근 N 세션 중 Gate I 가 0-candidate 반환한 query 들.

    구현:
      - target_selected payload 에서 candidates 가 [] 인 decision 찾기
      - intent=ambiguous + candidates=[] 인 stub 은 제외 (Phase 2 start stub)
        → real Gate I 의 0-cand 만 (intent ∈ {simulate, impact, locate, explain, hypothesis})
    """
    with session_scope() as s:
        sess_stmt = select(Section3SessionRow).order_by(
            Section3SessionRow.last_activity_at.desc(),
        )
        if repo_id:
            sess_stmt = sess_stmt.where(Section3SessionRow.repo_id == repo_id)
        # 충분히 큰 범위에서 끌어와 필터
        sess_stmt = sess_stmt.limit(max(limit * 5, 100))
        sess_rows = list(s.execute(sess_stmt).scalars().all())
        if not sess_rows:
            return []

        sess_by_id = {r.id: r for r in sess_rows}
        ids = [r.id for r in sess_rows]
        dec_rows = s.execute(
            select(
                Section3DecisionLogRow.session_id,
                Section3DecisionLogRow.gate_kind,
                Section3DecisionLogRow.payload_json,
                Section3DecisionLogRow.created_at,
                Section3DecisionLogRow.turn_no,
            )
            .where(Section3DecisionLogRow.session_id.in_(ids))
            .order_by(Section3DecisionLogRow.created_at.desc()),
        ).all()

        out: list[ZeroCandQuery] = []
        seen_sessions: set[str] = set()
        for sid, gate_kind, pj, created_at, turn_no in dec_rows:
            if sid in seen_sessions:
                continue
            if gate_kind != "target_selected":
                continue
            try:
                payload = json.loads(pj or "{}")
            except Exception:  # noqa: BLE001
                continue
            candidates = payload.get("candidates") or []
            if len(candidates) > 0:
                continue
            intent = payload.get("intent")
            # ambiguous stub (Phase 2 /start 직후) 는 제외
            if intent == "ambiguous":
                continue
            sess = sess_by_id.get(sid)
            if not sess or not sess.user_query:
                continue
            seen_sessions.add(sid)
            out.append(ZeroCandQuery(
                session_id=sid,
                user_query=sess.user_query,
                repo_id=sess.repo_id,
                created_at=created_at,
                suggestions=list(payload.get("suggestions") or []),
            ))
            if len(out) >= limit:
                break
        return out


__all__ = [
    "Section3Decision",
    "Section3Session",
    "SessionReplay",
    "SessionSummary",
    "WarningRates",
    "ZeroCandQuery",
    "add_gate_decision",
    "compute_warning_rates",
    "get_session",
    "list_gate_decisions",
    "list_recent_sessions",
    "list_zero_cand_queries",
    "replay_session",
    "start_session",
    "update_session_status",
    "update_user_response",
]
