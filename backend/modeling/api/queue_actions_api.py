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

from backend.modeling.audit.store import log_change
from backend.modeling.domain_layer.orm import BusinessRuleRow, BusinessTermRow
from backend.modeling.mapping_layer.orm import (
    ActionRow,
    AnchorBindingRow,
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
    log_change(repo_id, "term", fqn, "confirm", changed_by="user")
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
    log_change(repo_id, "term", fqn, "reject", changed_by="user")
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
    log_change(repo_id, "action", fqn, "confirm", changed_by=by)
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
    log_change(repo_id, "action", fqn, "reject", changed_by="user")
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
    log_change(repo_id, "type_realization", str(tr_id), "confirm", changed_by="user")
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
    log_change(repo_id, "type_realization", str(tr_id), "reject", changed_by="user")
    return ActionResult(ok=True, action="rejected", target=str(tr_id))


def _check_field(row: Any, attr: str) -> Any:
    """ORM row 의 attribute 안전 접근 (ORM 갱신 후 row 가 detached 일 수 있어 방어)."""
    return getattr(row, attr, None)


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — BusinessRule confirmed toggle
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/business-rules/{fqn:path}/confirm", response_model=ActionResult)
def confirm_business_rule(repo_id: str, fqn: str) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(BusinessRuleRow).where(
                BusinessRuleRow.repo_id == repo_id, BusinessRuleRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"business rule not found: {fqn}")
        row.confirmed = True
        row.source = "user"
    log_change(repo_id, "business_rule", fqn, "confirm", changed_by="user")
    return ActionResult(ok=True, action="confirmed", target=fqn)


@router.post("/{repo_id}/business-rules/{fqn:path}/unconfirm", response_model=ActionResult)
def unconfirm_business_rule(repo_id: str, fqn: str) -> ActionResult:
    """draft 로 되돌림 (BR row 자체는 보존). reject 와 다름 — reject 는 row 삭제."""
    with session_scope() as s:
        row = s.execute(
            select(BusinessRuleRow).where(
                BusinessRuleRow.repo_id == repo_id, BusinessRuleRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"business rule not found: {fqn}")
        row.confirmed = False
    log_change(repo_id, "business_rule", fqn, "unconfirm", changed_by="user")
    return ActionResult(ok=True, action="unconfirmed", target=fqn)


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — AnchorBinding confirmed toggle
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/anchor-bindings/{anchor_id}/confirm", response_model=ActionResult)
def confirm_anchor_binding(repo_id: str, anchor_id: str) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(AnchorBindingRow).where(
                AnchorBindingRow.repo_id == repo_id, AnchorBindingRow.id == anchor_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"anchor not found: {anchor_id}")
        row.confirmed = True
        row.source = "user"
    log_change(repo_id, "anchor_binding", anchor_id, "confirm", changed_by="user")
    return ActionResult(ok=True, action="confirmed", target=anchor_id)


@router.post("/{repo_id}/anchor-bindings/{anchor_id}/unconfirm", response_model=ActionResult)
def unconfirm_anchor_binding(repo_id: str, anchor_id: str) -> ActionResult:
    """draft 로 되돌림 (AnchorBinding row 자체는 보존)."""
    with session_scope() as s:
        row = s.execute(
            select(AnchorBindingRow).where(
                AnchorBindingRow.repo_id == repo_id, AnchorBindingRow.id == anchor_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"anchor not found: {anchor_id}")
        row.confirmed = False
    log_change(repo_id, "anchor_binding", anchor_id, "unconfirm", changed_by="user")
    return ActionResult(ok=True, action="unconfirmed", target=anchor_id)


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — Term unconfirm (기존 confirm 엔드포인트 mate)
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/terms/{fqn:path}/unconfirm", response_model=ActionResult)
def unconfirm_term(repo_id: str, fqn: str) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(BusinessTermRow).where(
                BusinessTermRow.repo_id == repo_id, BusinessTermRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"term not found: {fqn}")
        row.confirmed = False
    log_change(repo_id, "term", fqn, "unconfirm", changed_by="user")
    return ActionResult(ok=True, action="unconfirmed", target=fqn)


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — Action unconfirm (verification_level → draft 로 되돌림)
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/actions/{fqn:path}/unconfirm", response_model=ActionResult)
def unconfirm_action(repo_id: str, fqn: str) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(ActionRow).where(
                ActionRow.repo_id == repo_id, ActionRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"action not found: {fqn}")
        # 진척 단계는 보존 — confirmed_by 만 클리어. 의미: "내가 결정한 게 아니다" 표시.
        # signature_locked 인 채로 두면 안 됨? — 보수적으로 draft 로 되돌림.
        if row.verification_level in ("signature_locked", "body_anchored"):
            row.verification_level = "draft"
        row.confirmed_by = None
    log_change(repo_id, "action", fqn, "unconfirm", changed_by="user")
    return ActionResult(ok=True, action="unconfirmed", target=fqn)


# ---------------------------------------------------------------------------
# 5-ii Stage 2 — inline field edit (Term / Action / BR / Anchor)
# ---------------------------------------------------------------------------
class TermPatch(BaseModel):
    """Term 의 일부 field 갱신. None 인 field 는 변경 안 함."""
    label: str | None = None
    aliases: list[str] | None = None
    description: str | None = None
    domain: str | None = None
    value_type: str | None = None      # atomic 만 의미
    unit: str | None = None
    enum_values: list[str] | None = None


@router.patch("/{repo_id}/terms/{fqn:path}", response_model=ActionResult)
def patch_term(repo_id: str, fqn: str, patch: TermPatch) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(BusinessTermRow).where(
                BusinessTermRow.repo_id == repo_id, BusinessTermRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"term not found: {fqn}")
        if patch.label is not None:       row.label = patch.label
        if patch.aliases is not None:     row.aliases_json = json.dumps(patch.aliases, ensure_ascii=False)
        if patch.description is not None: row.description = patch.description
        if patch.domain is not None:      row.domain = patch.domain
        if patch.value_type is not None:  row.value_type = patch.value_type
        if patch.unit is not None:        row.unit = patch.unit
        if patch.enum_values is not None:
            row.enum_values_json = json.dumps(patch.enum_values, ensure_ascii=False)
    log_change(repo_id, "term", fqn, "update", changed_by="user",
               details={k: v for k, v in patch.model_dump().items() if v is not None})
    return ActionResult(ok=True, action="patched", target=fqn)


class ActionPatch(BaseModel):
    label: str | None = None
    aliases: list[str] | None = None
    description: str | None = None


@router.patch("/{repo_id}/actions/{fqn:path}", response_model=ActionResult)
def patch_action(repo_id: str, fqn: str, patch: ActionPatch) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(ActionRow).where(
                ActionRow.repo_id == repo_id, ActionRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"action not found: {fqn}")
        if patch.label is not None:       row.label = patch.label
        if patch.aliases is not None:     row.aliases_json = json.dumps(patch.aliases, ensure_ascii=False)
        if patch.description is not None: row.description = patch.description
    log_change(repo_id, "action", fqn, "update", changed_by="user",
               details={k: v for k, v in patch.model_dump().items() if v is not None})
    return ActionResult(ok=True, action="patched", target=fqn)


class BRPatch(BaseModel):
    statement: str | None = None
    severity: str | None = None        # "hard" / "soft"


@router.patch("/{repo_id}/business-rules/{fqn:path}", response_model=ActionResult)
def patch_business_rule(repo_id: str, fqn: str, patch: BRPatch) -> ActionResult:
    if patch.severity is not None and patch.severity not in ("hard", "soft"):
        raise HTTPException(status_code=400, detail=f"invalid severity: {patch.severity}")
    with session_scope() as s:
        row = s.execute(
            select(BusinessRuleRow).where(
                BusinessRuleRow.repo_id == repo_id, BusinessRuleRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"business rule not found: {fqn}")
        if patch.statement is not None: row.statement = patch.statement
        if patch.severity is not None:  row.severity = patch.severity
    log_change(repo_id, "business_rule", fqn, "update", changed_by="user",
               details={k: v for k, v in patch.model_dump().items() if v is not None})
    return ActionResult(ok=True, action="patched", target=fqn)


class AnchorPatch(BaseModel):
    anchor_locator: str | None = None
    target_slot: str | None = None
    rationale: str | None = None


@router.patch("/{repo_id}/anchor-bindings/{anchor_id}", response_model=ActionResult)
def patch_anchor_binding(repo_id: str, anchor_id: str, patch: AnchorPatch) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(AnchorBindingRow).where(
                AnchorBindingRow.repo_id == repo_id, AnchorBindingRow.id == anchor_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"anchor not found: {anchor_id}")
        if patch.anchor_locator is not None: row.anchor_locator = patch.anchor_locator
        if patch.target_slot is not None:    row.target_slot = patch.target_slot
        if patch.rationale is not None:      row.rationale = patch.rationale
    log_change(repo_id, "anchor_binding", anchor_id, "update", changed_by="user",
               details={k: v for k, v in patch.model_dump().items() if v is not None})
    return ActionResult(ok=True, action="patched", target=anchor_id)
