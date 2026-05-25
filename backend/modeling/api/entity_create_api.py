"""FastAPI router — manual entity creation (Term / Action / BusinessRule / AnchorBinding).

배경: Recommend persist + Authoring AI 외에 사용자가 직접 코드와 무관한 entity 를 만들고 싶을 때
(예: 코드에 없는 추상 개념 term, 수동 BR, 자동 추출 누락 anchor) 진입점 제공.

확정 사항:
- POST endpoint 만 (PUT 은 patchXxx 가 이미 있음).
- 자동으로 audit log `change_kind="create"` + `changed_by="user"` 기록.
- 충돌 시 (같은 fqn 존재) HTTP 409.
- 입력값 validation 은 underlying schema (BusinessTerm / Action / BusinessRule / AnchorBinding) 의
  Pydantic validator 에 위임.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.modeling.audit.store import log_change
from backend.modeling.domain_layer.orm import BusinessRuleRow, BusinessTermRow
from backend.modeling.domain_layer.schema import (
    BusinessRule, BusinessTerm, RuleSeverity, TermKind,
)
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer.orm import ActionRow, AnchorBindingRow
from backend.modeling.mapping_layer.schema import Action, ActionKind, AnchorBinding
from backend.modeling.mapping_layer.store import MappingLayerStore
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-create"])


# ---------------------------------------------------------------------------
# DTOs (입력 body) — frontend 가 채우기 쉽도록 필수 필드 최소화
# ---------------------------------------------------------------------------
class TermCreateBody(BaseModel):
    fqn: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: TermKind                                   # atomic | composite
    domain: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    is_abstract: bool = False
    is_interface: bool = False
    is_root_entity: bool = False
    struct_like_hint: bool = False
    value_type: str | None = None
    unit: str | None = None
    enum_values: list[str] | None = None


class ActionCreateBody(BaseModel):
    fqn: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: ActionKind                                 # pure_function | effectful | workflow
    domain: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    declared_on_term: str | None = None


class BusinessRuleCreateBody(BaseModel):
    fqn: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    severity: RuleSeverity = RuleSeverity.HARD
    terms_ref: list[str] = Field(default_factory=list)
    source: str = ""


class AnchorBindingCreateBody(BaseModel):
    anchor_locator: str = Field(min_length=1)        # e.g. "args[0]", "return"
    code_method_fqn: str = Field(min_length=1)
    target_action_fqn: str = Field(min_length=1)
    target_slot: str = Field(min_length=1)           # e.g. "params[0]", "output"
    rationale: str = ""


class CreateResult(BaseModel):
    ok: bool
    fqn: str
    kind: str                                        # "term" | "action" | "business_rule" | "anchor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _exists_in(repo_id: str, model: type, fqn_col: Any, fqn: str) -> bool:
    with session_scope() as s:
        row = s.execute(select(model).where(fqn_col == fqn, model.repo_id == repo_id)).first()
        return row is not None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/terms", response_model=CreateResult, status_code=201)
def create_term(repo_id: str, body: TermCreateBody) -> CreateResult:
    if _exists_in(repo_id, BusinessTermRow, BusinessTermRow.fqn, body.fqn):
        raise HTTPException(status_code=409, detail=f"term {body.fqn} already exists in repo {repo_id}")
    try:
        term = BusinessTerm(
            fqn=body.fqn, label=body.label, aliases=body.aliases,
            domain=body.domain, description=body.description,
            kind=body.kind, is_abstract=body.is_abstract, is_interface=body.is_interface,
            is_root_entity=body.is_root_entity, struct_like_hint=body.struct_like_hint,
            value_type=body.value_type, unit=body.unit, enum_values=body.enum_values,
            confirmed=False, repo_id=repo_id, source="user",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid term: {e}") from e

    DomainLayerStore().upsert_terms(repo_id, [term])
    log_change(repo_id, "term", body.fqn, "create", changed_by="user")
    logger.info("entity create: term %s (repo=%s)", body.fqn, repo_id)
    return CreateResult(ok=True, fqn=body.fqn, kind="term")


@router.post("/{repo_id}/actions", response_model=CreateResult, status_code=201)
def create_action(repo_id: str, body: ActionCreateBody) -> CreateResult:
    if _exists_in(repo_id, ActionRow, ActionRow.fqn, body.fqn):
        raise HTTPException(status_code=409, detail=f"action {body.fqn} already exists in repo {repo_id}")
    try:
        action = Action(
            fqn=body.fqn, label=body.label, aliases=body.aliases,
            domain=body.domain, description=body.description,
            kind=body.kind, declared_on_term=body.declared_on_term,
            repo_id=repo_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid action: {e}") from e

    MappingLayerStore().upsert_action(repo_id, action)
    log_change(repo_id, "action", body.fqn, "create", changed_by="user")
    logger.info("entity create: action %s (repo=%s)", body.fqn, repo_id)
    return CreateResult(ok=True, fqn=body.fqn, kind="action")


@router.post("/{repo_id}/business-rules", response_model=CreateResult, status_code=201)
def create_business_rule(repo_id: str, body: BusinessRuleCreateBody) -> CreateResult:
    if _exists_in(repo_id, BusinessRuleRow, BusinessRuleRow.fqn, body.fqn):
        raise HTTPException(status_code=409, detail=f"business_rule {body.fqn} already exists in repo {repo_id}")
    try:
        rule = BusinessRule(
            fqn=body.fqn, statement=body.statement, severity=body.severity,
            terms_ref=body.terms_ref, source=body.source,
            confirmed=False, repo_id=repo_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid business_rule: {e}") from e

    DomainLayerStore().upsert_rules(repo_id, [rule])
    log_change(repo_id, "business_rule", body.fqn, "create", changed_by="user")
    logger.info("entity create: business_rule %s (repo=%s)", body.fqn, repo_id)
    return CreateResult(ok=True, fqn=body.fqn, kind="business_rule")


def _anchor_id(method_fqn: str, locator: str, action_fqn: str, slot: str) -> str:
    seed = f"{method_fqn}|{locator}|{action_fqn}|{slot}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


@router.post("/{repo_id}/anchor-bindings", response_model=CreateResult, status_code=201)
def create_anchor_binding(repo_id: str, body: AnchorBindingCreateBody) -> CreateResult:
    anchor_id = _anchor_id(body.code_method_fqn, body.anchor_locator, body.target_action_fqn, body.target_slot)
    try:
        anchor = AnchorBinding(
            id=anchor_id,
            anchor_locator=body.anchor_locator,
            code_method_fqn=body.code_method_fqn,
            target_action_fqn=body.target_action_fqn,
            target_slot=body.target_slot,
            rationale=body.rationale,
            source="user",
            confirmed=False,
            repo_id=repo_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid anchor: {e}") from e

    MappingLayerStore().upsert_anchor_bindings(repo_id, [anchor])
    log_change(repo_id, "anchor_binding", anchor_id, "create", changed_by="user")
    logger.info("entity create: anchor %s → %s (repo=%s)",
                body.code_method_fqn, body.target_action_fqn, repo_id)
    return CreateResult(ok=True, fqn=anchor_id, kind="anchor")


__all__ = ["router"]
