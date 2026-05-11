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

Wave 2 (2026-05-10): inline edit (PATCH) + confirm/unconfirm 모두 audit_log 에 기록.
- Pydantic Patch 모델은 `_generated_patch_models` (codegen, SSOT = editable_fields.yaml) 에서 import.
- `audit_patch` context manager 로 PATCH before/after diff → audit row.
- confirm/unconfirm 은 `record_audit` 직접 호출 (entity-level action, field=None).
- user_id 는 `Depends(get_current_user)` 로 plumbing.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select

from backend.core.auth import User, get_current_user
from backend.modeling.api._generated_patch_models import (
    ActionPatch,
    AnchorPatch,
    BRPatch,
    CodeTypePatch,
    TermPatch,
)
from backend.modeling.audit import audit_patch, record_audit
from backend.modeling.code_layer.orm import CodeTypeRow
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
# user_id plumbing — single shared dependency for all PATCH/confirm endpoints.
# ---------------------------------------------------------------------------
def _user_dep(user: User = Depends(get_current_user)) -> str:
    """Resolve the current user's id (string). Falls back to "system" if absent."""
    return user.id if user and user.id else "system"


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
def confirm_term(
    repo_id: str, fqn: str, user_id: str = Depends(_user_dep),
) -> ActionResult:
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
        record_audit(
            s, repo_id=repo_id, entity_kind="term", entity_id=fqn,
            field=None, before=None, after=None,
            action="confirmed", user_id=user_id,
        )
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
def confirm_action(
    repo_id: str, fqn: str,
    by: str = Query("user"),
    user_id: str = Depends(_user_dep),
) -> ActionResult:
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
        record_audit(
            s, repo_id=repo_id, entity_kind="action", entity_id=fqn,
            field=None, before=None, after=None,
            action="confirmed", user_id=user_id,
        )
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


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — BusinessRule confirmed toggle
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/business-rules/{fqn:path}/confirm", response_model=ActionResult)
def confirm_business_rule(
    repo_id: str, fqn: str, user_id: str = Depends(_user_dep),
) -> ActionResult:
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
        record_audit(
            s, repo_id=repo_id, entity_kind="rule", entity_id=fqn,
            field=None, before=None, after=None,
            action="confirmed", user_id=user_id,
        )
    return ActionResult(ok=True, action="confirmed", target=fqn)


@router.post("/{repo_id}/business-rules/{fqn:path}/unconfirm", response_model=ActionResult)
def unconfirm_business_rule(
    repo_id: str, fqn: str, user_id: str = Depends(_user_dep),
) -> ActionResult:
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
        record_audit(
            s, repo_id=repo_id, entity_kind="rule", entity_id=fqn,
            field=None, before=None, after=None,
            action="unconfirmed", user_id=user_id,
        )
    return ActionResult(ok=True, action="unconfirmed", target=fqn)


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — AnchorBinding confirmed toggle
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/anchor-bindings/{anchor_id}/confirm", response_model=ActionResult)
def confirm_anchor_binding(
    repo_id: str, anchor_id: str, user_id: str = Depends(_user_dep),
) -> ActionResult:
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
        record_audit(
            s, repo_id=repo_id, entity_kind="anchor", entity_id=anchor_id,
            field=None, before=None, after=None,
            action="confirmed", user_id=user_id,
        )
    return ActionResult(ok=True, action="confirmed", target=anchor_id)


@router.post("/{repo_id}/anchor-bindings/{anchor_id}/unconfirm", response_model=ActionResult)
def unconfirm_anchor_binding(
    repo_id: str, anchor_id: str, user_id: str = Depends(_user_dep),
) -> ActionResult:
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
        record_audit(
            s, repo_id=repo_id, entity_kind="anchor", entity_id=anchor_id,
            field=None, before=None, after=None,
            action="unconfirmed", user_id=user_id,
        )
    return ActionResult(ok=True, action="unconfirmed", target=anchor_id)


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — Term unconfirm (기존 confirm 엔드포인트 mate)
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/terms/{fqn:path}/unconfirm", response_model=ActionResult)
def unconfirm_term(
    repo_id: str, fqn: str, user_id: str = Depends(_user_dep),
) -> ActionResult:
    with session_scope() as s:
        row = s.execute(
            select(BusinessTermRow).where(
                BusinessTermRow.repo_id == repo_id, BusinessTermRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"term not found: {fqn}")
        row.confirmed = False
        record_audit(
            s, repo_id=repo_id, entity_kind="term", entity_id=fqn,
            field=None, before=None, after=None,
            action="unconfirmed", user_id=user_id,
        )
    return ActionResult(ok=True, action="unconfirmed", target=fqn)


# ---------------------------------------------------------------------------
# 5-ii Stage 1 — Action unconfirm (verification_level → draft 로 되돌림)
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/actions/{fqn:path}/unconfirm", response_model=ActionResult)
def unconfirm_action(
    repo_id: str, fqn: str, user_id: str = Depends(_user_dep),
) -> ActionResult:
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
        record_audit(
            s, repo_id=repo_id, entity_kind="action", entity_id=fqn,
            field=None, before=None, after=None,
            action="unconfirmed", user_id=user_id,
        )
    return ActionResult(ok=True, action="unconfirmed", target=fqn)


# ---------------------------------------------------------------------------
# 5-ii Stage 2 — inline field edit (Term / Action / BR / Anchor / CodeType)
#
# Pydantic Patch 모델은 codegen module 에서 import — SSOT = editable_fields.yaml.
# 절대 여기서 재정의하지 말 것 (yaml 변경 시 scripts/codegen_patch_models.py 재실행).
# ---------------------------------------------------------------------------
@router.patch("/{repo_id}/terms/{fqn:path}", response_model=ActionResult)
def patch_term(
    repo_id: str, fqn: str, patch: TermPatch,
    user_id: str = Depends(_user_dep),
) -> ActionResult:
    with session_scope() as s, audit_patch(
        session=s, repo_id=repo_id, entity_kind="term",
        entity_id=fqn, user_id=user_id,
    ) as actx:
        row = s.execute(
            select(BusinessTermRow).where(
                BusinessTermRow.repo_id == repo_id, BusinessTermRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"term not found: {fqn}")

        patch_data = patch.model_dump(exclude_none=True)
        # before snapshot — only the fields being patched (codegen YAML field names,
        # mapped to ORM column names where they differ).
        before = _term_snapshot(row, patch_data.keys())

        if patch.label is not None:       row.label = patch.label
        if patch.aliases is not None:     row.aliases_json = json.dumps(patch.aliases, ensure_ascii=False)
        if patch.description is not None: row.description = patch.description
        if patch.domain is not None:      row.domain = patch.domain
        if patch.value_type is not None:  row.value_type = patch.value_type
        if patch.unit is not None:        row.unit = patch.unit
        if patch.range is not None:       row.range_json = json.dumps(patch.range)
        if patch.enum_values is not None:
            row.enum_values_json = json.dumps(patch.enum_values, ensure_ascii=False)

        actx.set_before(before)
        actx.set_after(_term_snapshot(row, patch_data.keys()))
    return ActionResult(ok=True, action="patched", target=fqn)


def _term_snapshot(row: BusinessTermRow, fields: Any) -> dict[str, Any]:
    """ORM row → dict (only requested patch field names — codegen YAML keys)."""
    out: dict[str, Any] = {}
    for f in fields:
        if f == "aliases":
            out["aliases"] = json.loads(row.aliases_json or "[]")
        elif f == "range":
            out["range"] = json.loads(row.range_json) if row.range_json else None
        elif f == "enum_values":
            out["enum_values"] = json.loads(row.enum_values_json) if row.enum_values_json else None
        else:
            out[f] = getattr(row, f, None)
    return out


@router.patch("/{repo_id}/actions/{fqn:path}", response_model=ActionResult)
def patch_action(
    repo_id: str, fqn: str, patch: ActionPatch,
    user_id: str = Depends(_user_dep),
) -> ActionResult:
    with session_scope() as s, audit_patch(
        session=s, repo_id=repo_id, entity_kind="action",
        entity_id=fqn, user_id=user_id,
    ) as actx:
        row = s.execute(
            select(ActionRow).where(
                ActionRow.repo_id == repo_id, ActionRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"action not found: {fqn}")

        patch_data = patch.model_dump(exclude_none=True)
        before = _action_snapshot(row, patch_data.keys())

        if patch.label is not None:       row.label = patch.label
        if patch.aliases is not None:     row.aliases_json = json.dumps(patch.aliases, ensure_ascii=False)
        if patch.description is not None: row.description = patch.description

        actx.set_before(before)
        actx.set_after(_action_snapshot(row, patch_data.keys()))
    return ActionResult(ok=True, action="patched", target=fqn)


def _action_snapshot(row: ActionRow, fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        if f == "aliases":
            out["aliases"] = json.loads(row.aliases_json or "[]")
        else:
            out[f] = getattr(row, f, None)
    return out


@router.patch("/{repo_id}/business-rules/{fqn:path}", response_model=ActionResult)
def patch_business_rule(
    repo_id: str, fqn: str, patch: BRPatch,
    user_id: str = Depends(_user_dep),
) -> ActionResult:
    # severity 는 codegen Literal["hard", "soft"] 로 이미 검증되지만 방어 한 번 더.
    if patch.severity is not None and patch.severity not in ("hard", "soft"):
        raise HTTPException(status_code=400, detail=f"invalid severity: {patch.severity}")
    with session_scope() as s, audit_patch(
        session=s, repo_id=repo_id, entity_kind="rule",
        entity_id=fqn, user_id=user_id,
    ) as actx:
        row = s.execute(
            select(BusinessRuleRow).where(
                BusinessRuleRow.repo_id == repo_id, BusinessRuleRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"business rule not found: {fqn}")

        patch_data = patch.model_dump(exclude_none=True)
        before = {f: getattr(row, f, None) for f in patch_data.keys()}

        if patch.statement is not None: row.statement = patch.statement
        if patch.severity is not None:  row.severity = patch.severity

        actx.set_before(before)
        actx.set_after({f: getattr(row, f, None) for f in patch_data.keys()})
    return ActionResult(ok=True, action="patched", target=fqn)


@router.patch("/{repo_id}/anchor-bindings/{anchor_id}", response_model=ActionResult)
def patch_anchor_binding(
    repo_id: str, anchor_id: str, patch: AnchorPatch,
    user_id: str = Depends(_user_dep),
) -> ActionResult:
    with session_scope() as s, audit_patch(
        session=s, repo_id=repo_id, entity_kind="anchor",
        entity_id=anchor_id, user_id=user_id,
    ) as actx:
        row = s.execute(
            select(AnchorBindingRow).where(
                AnchorBindingRow.repo_id == repo_id, AnchorBindingRow.id == anchor_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"anchor not found: {anchor_id}")

        patch_data = patch.model_dump(exclude_none=True)
        before = {f: getattr(row, f, None) for f in patch_data.keys()}

        if patch.anchor_locator is not None: row.anchor_locator = patch.anchor_locator
        if patch.target_slot is not None:    row.target_slot = patch.target_slot
        if patch.rationale is not None:      row.rationale = patch.rationale

        actx.set_before(before)
        actx.set_after({f: getattr(row, f, None) for f in patch_data.keys()})
    return ActionResult(ok=True, action="patched", target=anchor_id)


# ---------------------------------------------------------------------------
# Wave 2 — CodeType.role inline edit (Decision #8).
#
# CodeType row 는 fqn 이 PK (글로벌). repo_id 에서 lookup 해서 잘못된 repo 의
# CodeType 을 patch 하지 못하도록 방어.
# ---------------------------------------------------------------------------
@router.patch("/{repo_id}/code-types/{fqn:path}", response_model=ActionResult)
def patch_code_type(
    repo_id: str, fqn: str, patch: CodeTypePatch,
    user_id: str = Depends(_user_dep),
) -> ActionResult:
    with session_scope() as s, audit_patch(
        session=s, repo_id=repo_id, entity_kind="code_type",
        entity_id=fqn, user_id=user_id,
    ) as actx:
        row = s.execute(
            select(CodeTypeRow).where(
                CodeTypeRow.repo_id == repo_id, CodeTypeRow.fqn == fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"code type not found: {fqn}")

        patch_data = patch.model_dump(exclude_none=True)
        before = {f: getattr(row, f, None) for f in patch_data.keys()}

        if patch.role is not None: row.role = patch.role

        actx.set_before(before)
        actx.set_after({f: getattr(row, f, None) for f in patch_data.keys()})
    return ActionResult(ok=True, action="patched", target=fqn)
