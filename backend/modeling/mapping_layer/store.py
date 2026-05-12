"""Mapping Layer Store — Pydantic ↔ ORM + CRUD.

원칙:
- 외부 ORM row 노출 X
- Action 의 realizations 는 별도 RealizationRow 에 (action.realizations[] JSON 안 씀)
  → 이 store 가 Action 저장 시 realizations 를 분리 저장 + 조회 시 합쳐 반환
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

from sqlalchemy import delete, select

from backend.modeling.mapping_layer.orm import (
    ActionRow,
    AnchorBindingRow,
    RealizationRow,
    TypeRealizationRow,
)
from backend.modeling.mapping_layer.schema import (
    Action,
    ActionEffect,
    ActionEffectOp,
    ActionKind,
    ActionParam,
    AnchorBinding,
    DispatchSource,
    Realization,
    RealizationScope,
    TypeRealization,
    VerificationLevel,
)
from backend.modeling.mapping_layer.schema import ActionOutput
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TypeRealization
# ---------------------------------------------------------------------------
def _tr_to_row(tr: TypeRealization) -> TypeRealizationRow:
    return TypeRealizationRow(
        code_type_fqn=tr.code_type_fqn,
        term_fqn=tr.term_fqn,
        scope=tr.scope.value,
        confidence=tr.confidence,
        source=tr.source,
        confirmed=tr.confirmed,
        confirmed_by=tr.confirmed_by,
        rationale=tr.rationale,
        repo_id=tr.repo_id,
    )


def _row_to_tr(row: TypeRealizationRow) -> TypeRealization:
    return TypeRealization(
        code_type_fqn=row.code_type_fqn,
        term_fqn=row.term_fqn,
        scope=RealizationScope(row.scope),
        confidence=row.confidence,
        source=row.source,
        confirmed=row.confirmed,
        confirmed_by=row.confirmed_by,
        rationale=row.rationale,
        repo_id=row.repo_id,
    )


# ---------------------------------------------------------------------------
# Action (+ embedded params/effects/output JSON)
# ---------------------------------------------------------------------------
def _action_to_row(a: Action) -> ActionRow:
    return ActionRow(
        fqn=a.fqn,
        label=a.label,
        aliases_json=json.dumps(a.aliases),
        domain=a.domain,
        description=a.description,
        kind=a.kind.value,
        is_abstract=a.is_abstract,
        declared_on_term=a.declared_on_term,
        params_json=json.dumps([p.model_dump() for p in a.params]),
        output_json=(json.dumps(a.output.model_dump()) if a.output else None),
        preconditions_json=json.dumps(a.preconditions),
        postconditions_json=json.dumps(a.postconditions),
        effects_json=json.dumps([e.model_dump() for e in a.effects]),
        sub_actions_json=json.dumps(a.sub_actions),
        verification_level=a.verification_level.value,
        signature_locked_at=a.signature_locked_at,
        confirmed_by=a.confirmed_by,
        repo_id=a.repo_id,
    )


def _row_to_action(row: ActionRow, realizations: list[Realization]) -> Action:
    params = [ActionParam(**p) for p in json.loads(row.params_json or "[]")]
    output_raw = json.loads(row.output_json) if row.output_json else None
    output = ActionOutput(**output_raw) if output_raw else None
    effects = [ActionEffect(**e) for e in json.loads(row.effects_json or "[]")]
    return Action(
        fqn=row.fqn,
        label=row.label,
        aliases=json.loads(row.aliases_json or "[]"),
        domain=row.domain,
        description=row.description,
        kind=ActionKind(row.kind),
        is_abstract=row.is_abstract,
        declared_on_term=row.declared_on_term,
        params=params,
        output=output,
        preconditions=json.loads(row.preconditions_json or "[]"),
        postconditions=json.loads(row.postconditions_json or "[]"),
        effects=effects,
        realizations=realizations,
        sub_actions=json.loads(row.sub_actions_json or "[]"),
        verification_level=VerificationLevel(row.verification_level),
        signature_locked_at=row.signature_locked_at,
        confirmed_by=row.confirmed_by,
        repo_id=row.repo_id,
    )


def _real_to_row(action_fqn: str, repo_id: str, r: Realization) -> RealizationRow:
    return RealizationRow(
        action_fqn=action_fqn,
        code_method_fqn=r.code_method_fqn,
        applies_to_code_type_fqn=r.applies_to_code_type_fqn,
        is_override=r.is_override,
        dispatch_source=r.dispatch_source.value,
        confidence=r.confidence,
        scope=r.scope.value,
        confirmed=r.confirmed,
        rationale=r.rationale,
        repo_id=repo_id,
    )


def _row_to_real(row: RealizationRow) -> Realization:
    return Realization(
        code_method_fqn=row.code_method_fqn,
        applies_to_code_type_fqn=row.applies_to_code_type_fqn,
        is_override=row.is_override,
        dispatch_source=DispatchSource(row.dispatch_source),
        confidence=row.confidence,
        scope=RealizationScope(row.scope),
        confirmed=row.confirmed,
        rationale=row.rationale,
    )


def _ab_to_row(ab: AnchorBinding) -> AnchorBindingRow:
    return AnchorBindingRow(
        id=ab.id,
        anchor_locator=ab.anchor_locator,
        code_method_fqn=ab.code_method_fqn,
        target_action_fqn=ab.target_action_fqn,
        target_slot=ab.target_slot,
        confidence=ab.confidence,
        source=ab.source,
        confirmed=ab.confirmed,
        rationale=ab.rationale,
        repo_id=ab.repo_id,
        line=ab.line,
    )


def _row_to_ab(row: AnchorBindingRow) -> AnchorBinding:
    return AnchorBinding(
        id=row.id,
        anchor_locator=row.anchor_locator,
        code_method_fqn=row.code_method_fqn,
        target_action_fqn=row.target_action_fqn,
        target_slot=row.target_slot,
        confidence=row.confidence,
        source=row.source,
        confirmed=row.confirmed,
        rationale=row.rationale,
        repo_id=row.repo_id,
        line=row.line,
    )


# ---------------------------------------------------------------------------
# Store API
# ---------------------------------------------------------------------------
class MappingLayerStore:
    # ---- TypeRealization ----
    def upsert_type_realizations(
        self, repo_id: str, items: Iterable[TypeRealization],
    ) -> int:
        count = 0
        with session_scope() as s:
            for it in items:
                d = it.model_dump()
                d["repo_id"] = repo_id
                it = TypeRealization(**d)
                # 같은 (code_type, term, scope) 있으면 replace
                existing = s.execute(
                    select(TypeRealizationRow).where(
                        TypeRealizationRow.code_type_fqn == it.code_type_fqn,
                        TypeRealizationRow.term_fqn == it.term_fqn,
                        TypeRealizationRow.scope == it.scope.value,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    s.delete(existing)
                    s.flush()
                s.add(_tr_to_row(it))
                count += 1
        return count

    def list_type_realizations(self, repo_id: str | None = None) -> list[TypeRealization]:
        with session_scope() as s:
            stmt = select(TypeRealizationRow)
            if repo_id is not None:
                stmt = stmt.where(TypeRealizationRow.repo_id == repo_id)
            return [_row_to_tr(r) for r in s.execute(stmt).scalars()]

    def get_term_for_code_type(self, code_type_fqn: str) -> TypeRealization | None:
        """primary scope 의 realization 찾기."""
        with session_scope() as s:
            row = s.execute(
                select(TypeRealizationRow).where(
                    TypeRealizationRow.code_type_fqn == code_type_fqn,
                    TypeRealizationRow.scope == RealizationScope.PRIMARY.value,
                )
            ).scalar_one_or_none()
            return _row_to_tr(row) if row else None

    # ---- Action ----
    def upsert_action(self, repo_id: str, action: Action) -> Action:
        """Action 저장 + realizations 별도 테이블에 분리 저장 → 반환은 합친 Action."""
        with session_scope() as s:
            a_dict = action.model_dump()
            a_dict["repo_id"] = repo_id
            action = Action(**a_dict)

            # delete existing
            existing = s.get(ActionRow, action.fqn)
            if existing is not None:
                s.delete(existing)
                s.flush()
            # 기존 realizations 도 삭제
            s.execute(delete(RealizationRow).where(RealizationRow.action_fqn == action.fqn))

            s.add(_action_to_row(action))
            for r in action.realizations:
                s.add(_real_to_row(action.fqn, repo_id, r))
        # 반환 시 다시 조회해 일관성 보장
        got = self.get_action(action.fqn)
        return got if got is not None else action

    def upsert_actions(self, repo_id: str, actions: Iterable[Action]) -> int:
        c = 0
        for a in actions:
            self.upsert_action(repo_id, a)
            c += 1
        return c

    def get_action(self, fqn: str) -> Action | None:
        with session_scope() as s:
            row = s.get(ActionRow, fqn)
            if row is None:
                return None
            reals = [
                _row_to_real(r) for r in s.execute(
                    select(RealizationRow).where(RealizationRow.action_fqn == fqn)
                ).scalars()
            ]
            return _row_to_action(row, reals)

    def list_actions(
        self, repo_id: str | None = None,
        kind: ActionKind | None = None,
        declared_on_term: str | None = None,
        verification_min: VerificationLevel | None = None,
    ) -> list[Action]:
        # verification_min 은 enum 순서 기준 — 단순화: equality OR
        order = [
            VerificationLevel.UNMAPPED, VerificationLevel.DRAFT,
            VerificationLevel.SIGNATURE_LOCKED, VerificationLevel.BODY_ANCHORED,
            VerificationLevel.SIM_VERIFIED, VerificationLevel.PR_PROVEN,
        ]
        allowed_levels: set[str] | None = None
        if verification_min is not None:
            i = order.index(verification_min)
            allowed_levels = {l.value for l in order[i:]}

        with session_scope() as s:
            stmt = select(ActionRow)
            if repo_id is not None:
                stmt = stmt.where(ActionRow.repo_id == repo_id)
            if kind is not None:
                stmt = stmt.where(ActionRow.kind == kind.value)
            if declared_on_term is not None:
                stmt = stmt.where(ActionRow.declared_on_term == declared_on_term)
            if allowed_levels is not None:
                stmt = stmt.where(ActionRow.verification_level.in_(allowed_levels))

            action_rows = list(s.execute(stmt).scalars())
            if not action_rows:
                return []
            # R4-T1.1 perf fix — N+1 회피. realization 을 action 별 1회 fetch 대신
            # 1 query 로 모두 가져와 in-memory group.
            fqns = [r.fqn for r in action_rows]
            all_reals = list(s.execute(
                select(RealizationRow).where(RealizationRow.action_fqn.in_(fqns))
            ).scalars())
            by_action: dict[str, list[Realization]] = {}
            for r in all_reals:
                by_action.setdefault(r.action_fqn, []).append(_row_to_real(r))
            return [_row_to_action(row, by_action.get(row.fqn, [])) for row in action_rows]

    def list_realizations(self, action_fqn: str) -> list[Realization]:
        with session_scope() as s:
            stmt = select(RealizationRow).where(RealizationRow.action_fqn == action_fqn)
            return [_row_to_real(r) for r in s.execute(stmt).scalars()]

    # ---- AnchorBinding ----
    def upsert_anchor_bindings(self, repo_id: str, items: Iterable[AnchorBinding]) -> int:
        c = 0
        with session_scope() as s:
            for ab in items:
                d = ab.model_dump()
                d["repo_id"] = repo_id
                ab = AnchorBinding(**d)
                existing = s.get(AnchorBindingRow, ab.id)
                if existing is not None:
                    s.delete(existing)
                    s.flush()
                s.add(_ab_to_row(ab))
                c += 1
        return c

    def get_anchor_bindings_for_action(self, action_fqn: str) -> list[AnchorBinding]:
        with session_scope() as s:
            stmt = select(AnchorBindingRow).where(AnchorBindingRow.target_action_fqn == action_fqn)
            return [_row_to_ab(r) for r in s.execute(stmt).scalars()]

    def get_anchor_bindings_for_method(self, code_method_fqn: str) -> list[AnchorBinding]:
        with session_scope() as s:
            stmt = select(AnchorBindingRow).where(AnchorBindingRow.code_method_fqn == code_method_fqn)
            return [_row_to_ab(r) for r in s.execute(stmt).scalars()]

    def list_anchor_bindings(self, repo_id: str | None = None) -> list[AnchorBinding]:
        """모든 AnchorBinding 조회. repo_id 지정 시 그 repo 만."""
        with session_scope() as s:
            stmt = select(AnchorBindingRow)
            if repo_id is not None:
                stmt = stmt.where(AnchorBindingRow.repo_id == repo_id)
            return [_row_to_ab(r) for r in s.execute(stmt).scalars()]

    # ---- delete / cleanup ----
    def delete_repo(self, repo_id: str) -> int:
        with session_scope() as s:
            n_a = s.execute(delete(ActionRow).where(ActionRow.repo_id == repo_id)).rowcount or 0
            n_r = s.execute(delete(RealizationRow).where(RealizationRow.repo_id == repo_id)).rowcount or 0
            n_t = s.execute(delete(TypeRealizationRow).where(TypeRealizationRow.repo_id == repo_id)).rowcount or 0
            n_b = s.execute(delete(AnchorBindingRow).where(AnchorBindingRow.repo_id == repo_id)).rowcount or 0
            return n_a + n_r + n_t + n_b


__all__ = ("MappingLayerStore",)
