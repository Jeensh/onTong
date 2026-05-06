"""FastAPI router — confirmed=False 후보 큐 처리 (P3-6).

REST:
- GET  /api/ontology/repos/{repo_id}/queue                 — Term/Action/Realization 후보 통합 list
- POST /api/ontology/repos/{repo_id}/terms/{fqn}/confirm
- POST /api/ontology/repos/{repo_id}/terms/{fqn}/reject
- POST /api/ontology/repos/{repo_id}/actions/{fqn}/confirm
- POST /api/ontology/repos/{repo_id}/actions/{fqn}/reject
- POST /api/ontology/repos/{repo_id}/type-realizations/{tr_id}/confirm
- POST /api/ontology/repos/{repo_id}/type-realizations/{tr_id}/reject

confirm: confirmed=True (Action 은 추가로 verification_level: draft → signature_locked).
reject: row 삭제 (recommend 다시 돌리면 재생성됨).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select

from backend.modeling.domain_layer.orm import BusinessTermRow
from backend.modeling.mapping_layer.orm import (
    ActionRow,
    RealizationRow,
    TypeRealizationRow,
)
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-queue"])


# ---------------------------------------------------------------------------
# Queue list (unconfirmed only)
# ---------------------------------------------------------------------------
class QueueTermDTO(BaseModel):
    fqn: str
    label: str
    kind: str
    domain: str
    is_root_entity: bool
    struct_like_hint: bool
    aliases: list[str]


class QueueActionDTO(BaseModel):
    fqn: str
    label: str
    kind: str
    declared_on_term: str | None
    verification_level: str
    realization_count: int


class QueueRealizationDTO(BaseModel):
    id: int
    code_type_fqn: str
    term_fqn: str
    scope: str       # "primary" | "partial"
    confidence: float
    rationale: str


class QueueResponse(BaseModel):
    repo_id: str
    summary: dict[str, int]
    terms: list[QueueTermDTO]
    actions: list[QueueActionDTO]
    type_realizations: list[QueueRealizationDTO]


@router.get("/{repo_id}/queue", response_model=QueueResponse)
def get_queue(repo_id: str, limit: int = Query(200, ge=1, le=2000)) -> QueueResponse:
    with session_scope() as s:
        # Terms
        term_rows = s.execute(
            select(BusinessTermRow)
            .where(BusinessTermRow.repo_id == repo_id, BusinessTermRow.confirmed.is_(False))
            .limit(limit)
        ).scalars().all()
        terms = [
            QueueTermDTO(
                fqn=r.fqn, label=r.label, kind=r.kind, domain=r.domain or "",
                is_root_entity=bool(r.is_root_entity),
                struct_like_hint=bool(r.struct_like_hint),
                aliases=json.loads(r.aliases_json or "[]"),
            )
            for r in term_rows
        ]

        # Actions — confirmed_by IS NULL = 미확정
        action_rows = s.execute(
            select(ActionRow)
            .where(ActionRow.repo_id == repo_id, ActionRow.confirmed_by.is_(None))
            .limit(limit)
        ).scalars().all()

        # 각 action 별 realization count (한 번에 묶어 가져옴)
        action_fqns = [a.fqn for a in action_rows]
        real_counts: dict[str, int] = {}
        if action_fqns:
            for r in s.execute(
                select(RealizationRow).where(RealizationRow.action_fqn.in_(action_fqns))
            ).scalars().all():
                real_counts[r.action_fqn] = real_counts.get(r.action_fqn, 0) + 1

        actions = [
            QueueActionDTO(
                fqn=a.fqn, label=a.label, kind=a.kind,
                declared_on_term=a.declared_on_term,
                verification_level=a.verification_level,
                realization_count=real_counts.get(a.fqn, 0),
            )
            for a in action_rows
        ]

        # TypeRealizations
        tr_rows = s.execute(
            select(TypeRealizationRow)
            .where(TypeRealizationRow.repo_id == repo_id, TypeRealizationRow.confirmed.is_(False))
            .limit(limit)
        ).scalars().all()
        trs = [
            QueueRealizationDTO(
                id=r.id, code_type_fqn=r.code_type_fqn, term_fqn=r.term_fqn,
                scope=r.scope, confidence=float(r.confidence), rationale=r.rationale or "",
            )
            for r in tr_rows
        ]

    summary = {
        "terms": len(terms),
        "actions": len(actions),
        "type_realizations": len(trs),
        "total": len(terms) + len(actions) + len(trs),
    }
    return QueueResponse(
        repo_id=repo_id, summary=summary,
        terms=terms, actions=actions, type_realizations=trs,
    )


# ---------------------------------------------------------------------------
# Confirm / Reject
# ---------------------------------------------------------------------------
class ActionResult(BaseModel):
    ok: bool
    action: str        # "confirmed" | "rejected"
    target: str


@router.post("/{repo_id}/terms/{fqn:path}/confirm", response_model=ActionResult)
def confirm_term(repo_id: str, fqn: str) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(BusinessTermRow).where(
                BusinessTermRow.repo_id == repo_id, BusinessTermRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"term not found: {fqn}")
        row.confirmed = True
        row.source = "user"
    return ActionResult(ok=True, action="confirmed", target=fqn)


@router.post("/{repo_id}/terms/{fqn:path}/reject", response_model=ActionResult)
def reject_term(repo_id: str, fqn: str) -> ActionResult:
    with session_scope() as s:
        # Term 이 사라지면 의존하는 TypeRealization 도 함께 정리 (소속 term 잃은 매핑 → 무의미)
        s.execute(
            delete(TypeRealizationRow).where(
                TypeRealizationRow.repo_id == repo_id,
                TypeRealizationRow.term_fqn == fqn,
            )
        )
        result = s.execute(
            delete(BusinessTermRow).where(
                BusinessTermRow.repo_id == repo_id, BusinessTermRow.fqn == fqn,
            )
        )
        if (result.rowcount or 0) == 0:
            raise HTTPException(status_code=404, detail=f"term not found: {fqn}")
    return ActionResult(ok=True, action="rejected", target=fqn)


@router.post("/{repo_id}/actions/{fqn:path}/confirm", response_model=ActionResult)
def confirm_action(repo_id: str, fqn: str, by: str = Query("user")) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(ActionRow).where(
                ActionRow.repo_id == repo_id, ActionRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"action not found: {fqn}")
        row.confirmed_by = by
        # verification 진척: draft → signature_locked (이미 더 높은 단계면 그대로)
        if row.verification_level == "draft" or row.verification_level == "unmapped":
            row.verification_level = "signature_locked"
    return ActionResult(ok=True, action="confirmed", target=fqn)


@router.post("/{repo_id}/actions/{fqn:path}/reject", response_model=ActionResult)
def reject_action(repo_id: str, fqn: str) -> ActionResult:
    with session_scope() as s:
        # cascade: realizations 도 함께 (RealizationRow.action_fqn FK on ActionRow.fqn 가 있으면 자동.
        # 안전상 명시 delete)
        s.execute(
            delete(RealizationRow).where(RealizationRow.action_fqn == fqn)
        )
        result = s.execute(
            delete(ActionRow).where(
                ActionRow.repo_id == repo_id, ActionRow.fqn == fqn,
            )
        )
        if (result.rowcount or 0) == 0:
            raise HTTPException(status_code=404, detail=f"action not found: {fqn}")
    return ActionResult(ok=True, action="rejected", target=fqn)


@router.post("/{repo_id}/type-realizations/{tr_id}/confirm", response_model=ActionResult)
def confirm_realization(repo_id: str, tr_id: int) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(TypeRealizationRow).where(
                TypeRealizationRow.repo_id == repo_id, TypeRealizationRow.id == tr_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"realization not found: {tr_id}")
        row.confirmed = True
        row.confirmed_by = "user"
        row.source = "user"
    return ActionResult(ok=True, action="confirmed", target=str(tr_id))


@router.post("/{repo_id}/type-realizations/{tr_id}/reject", response_model=ActionResult)
def reject_realization(repo_id: str, tr_id: int) -> ActionResult:
    with session_scope() as s:
        result = s.execute(
            delete(TypeRealizationRow).where(
                TypeRealizationRow.repo_id == repo_id, TypeRealizationRow.id == tr_id,
            )
        )
        if (result.rowcount or 0) == 0:
            raise HTTPException(status_code=404, detail=f"realization not found: {tr_id}")
    return ActionResult(ok=True, action="rejected", target=str(tr_id))


def _check_field(row: Any, attr: str) -> Any:
    """ORM row 의 attribute 안전 접근 (ORM 갱신 후 row 가 detached 일 수 있어 방어)."""
    return getattr(row, attr, None)
