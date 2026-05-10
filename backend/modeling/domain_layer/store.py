"""Domain Layer Store — Pydantic ↔ SQLAlchemy + CRUD.

원칙:
- 외부에 ORM row 노출 X (Pydantic DTO 만)
- repo_id 격리
- upsert 패턴 (idempotent)
- composition/inheritance 는 (parent, child, role/kind) 키로 dedup
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

from sqlalchemy import delete, select

from backend.modeling.domain_layer.orm import (
    BusinessRuleRow,
    BusinessTermRow,
    CompositionEdgeRow,
    InheritanceEdgeRow,
)
from backend.modeling.domain_layer.schema import (
    BusinessRule,
    BusinessTerm,
    Cardinality,
    Composition,
    Inheritance,
    InheritanceKind,
    RuleSeverity,
    TermKind,
    ValueType,
)
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BusinessTerm 변환
# ---------------------------------------------------------------------------
def _term_to_row(t: BusinessTerm) -> BusinessTermRow:
    return BusinessTermRow(
        fqn=t.fqn,
        label=t.label,
        aliases_json=json.dumps(t.aliases),
        domain=t.domain,
        description=t.description,
        kind=t.kind.value,
        is_abstract=t.is_abstract,
        is_interface=t.is_interface,
        is_root_entity=t.is_root_entity,
        struct_like_hint=t.struct_like_hint,
        value_type=(t.value_type.value if t.value_type else None),
        unit=t.unit,
        range_json=(json.dumps(t.range) if t.range is not None else None),
        enum_values_json=(json.dumps(t.enum_values) if t.enum_values is not None else None),
        confirmed=t.confirmed,
        repo_id=t.repo_id,
        source=t.source,
    )


def _row_to_term(row: BusinessTermRow) -> BusinessTerm:
    return BusinessTerm(
        fqn=row.fqn,
        label=row.label,
        aliases=json.loads(row.aliases_json or "[]"),
        domain=row.domain,
        description=row.description,
        kind=TermKind(row.kind),
        is_abstract=row.is_abstract,
        is_interface=row.is_interface,
        is_root_entity=row.is_root_entity,
        struct_like_hint=row.struct_like_hint,
        value_type=(ValueType(row.value_type) if row.value_type else None),
        unit=row.unit,
        range=(json.loads(row.range_json) if row.range_json else None),
        enum_values=(json.loads(row.enum_values_json) if row.enum_values_json else None),
        confirmed=row.confirmed,
        repo_id=row.repo_id,
        source=row.source,
    )


def _inh_to_row(i: Inheritance) -> InheritanceEdgeRow:
    return InheritanceEdgeRow(
        child_fqn=i.child_fqn,
        parent_fqn=i.parent_fqn,
        kind=i.kind.value,
        repo_id=i.repo_id,
    )


def _row_to_inh(row: InheritanceEdgeRow) -> Inheritance:
    return Inheritance(
        child_fqn=row.child_fqn,
        parent_fqn=row.parent_fqn,
        kind=InheritanceKind(row.kind),
        repo_id=row.repo_id,
    )


def _comp_to_row(c: Composition) -> CompositionEdgeRow:
    return CompositionEdgeRow(
        parent_fqn=c.parent_fqn,
        child_fqn=c.child_fqn,
        role_name=c.role_name,
        cardinality=c.cardinality.value,
        required=c.required,
        description=c.description,
        repo_id=c.repo_id,
    )


def _row_to_comp(row: CompositionEdgeRow) -> Composition:
    return Composition(
        parent_fqn=row.parent_fqn,
        child_fqn=row.child_fqn,
        role_name=row.role_name,
        cardinality=Cardinality(row.cardinality),
        required=row.required,
        description=row.description,
        repo_id=row.repo_id,
    )


def _rule_to_row(r: BusinessRule) -> BusinessRuleRow:
    return BusinessRuleRow(
        fqn=r.fqn,
        statement=r.statement,
        severity=r.severity.value,
        terms_ref_json=json.dumps(r.terms_ref),
        source=r.source,
        confirmed=r.confirmed,
        repo_id=r.repo_id,
        enforced_by_json=json.dumps(r.enforced_by, ensure_ascii=False),
        violated_at_call_json=json.dumps(r.violated_at_call, ensure_ascii=False),
        operational_history_json=json.dumps(r.operational_history, ensure_ascii=False),
    )


def _row_to_rule(row: BusinessRuleRow) -> BusinessRule:
    return BusinessRule(
        fqn=row.fqn,
        statement=row.statement,
        severity=RuleSeverity(row.severity),
        terms_ref=json.loads(row.terms_ref_json or "[]"),
        source=row.source,
        confirmed=row.confirmed,
        repo_id=row.repo_id,
        enforced_by=json.loads(row.enforced_by_json or "[]"),
        violated_at_call=json.loads(row.violated_at_call_json or "[]"),
        operational_history=json.loads(row.operational_history_json or "[]"),
    )


# ---------------------------------------------------------------------------
# Store API
# ---------------------------------------------------------------------------
class DomainLayerStore:
    """SQLite Store for Domain Layer.

    Sample:
        store = DomainLayerStore()
        store.upsert_terms(repo_id="slab", terms=[...])
        store.upsert_inheritance(repo_id="slab", edges=[...])
        store.upsert_composition(repo_id="slab", edges=[...])
        terms = store.list_terms(repo_id="slab")
        parts = store.get_composition_children(parent_fqn="term.scm.order")
        parents = store.get_inheritance_parents(child_fqn="term.scm.rush_order")
    """

    # ---- write ----
    def upsert_terms(self, repo_id: str, terms: Iterable[BusinessTerm]) -> int:
        count = 0
        with session_scope() as s:
            for t in terms:
                t_dict = t.model_dump()
                t_dict["repo_id"] = repo_id
                t = BusinessTerm(**t_dict)

                existing = s.get(BusinessTermRow, t.fqn)
                if existing is not None:
                    s.delete(existing)
                    s.flush()
                s.add(_term_to_row(t))
                count += 1
        return count

    def upsert_inheritance(self, repo_id: str, edges: Iterable[Inheritance]) -> int:
        count = 0
        with session_scope() as s:
            for e in edges:
                e_dict = e.model_dump()
                e_dict["repo_id"] = repo_id
                e = Inheritance(**e_dict)

                # uniq (child, parent, kind) — 기존 있으면 skip
                existing = s.execute(
                    select(InheritanceEdgeRow).where(
                        InheritanceEdgeRow.child_fqn == e.child_fqn,
                        InheritanceEdgeRow.parent_fqn == e.parent_fqn,
                        InheritanceEdgeRow.kind == e.kind.value,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    continue
                s.add(_inh_to_row(e))
                count += 1
        return count

    def upsert_composition(self, repo_id: str, edges: Iterable[Composition]) -> int:
        count = 0
        with session_scope() as s:
            for e in edges:
                e_dict = e.model_dump()
                e_dict["repo_id"] = repo_id
                e = Composition(**e_dict)

                # uniq (parent, role) — 기존 있으면 갱신
                existing = s.execute(
                    select(CompositionEdgeRow).where(
                        CompositionEdgeRow.parent_fqn == e.parent_fqn,
                        CompositionEdgeRow.role_name == e.role_name,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    s.delete(existing)
                    s.flush()
                s.add(_comp_to_row(e))
                count += 1
        return count

    def upsert_rules(self, repo_id: str, rules: Iterable[BusinessRule]) -> int:
        count = 0
        with session_scope() as s:
            for r in rules:
                r_dict = r.model_dump()
                r_dict["repo_id"] = repo_id
                r = BusinessRule(**r_dict)

                existing = s.get(BusinessRuleRow, r.fqn)
                if existing is not None:
                    s.delete(existing)
                    s.flush()
                s.add(_rule_to_row(r))
                count += 1
        return count

    def delete_repo(self, repo_id: str) -> int:
        with session_scope() as s:
            n_t = s.execute(delete(BusinessTermRow).where(BusinessTermRow.repo_id == repo_id)).rowcount or 0
            n_i = s.execute(delete(InheritanceEdgeRow).where(InheritanceEdgeRow.repo_id == repo_id)).rowcount or 0
            n_c = s.execute(delete(CompositionEdgeRow).where(CompositionEdgeRow.repo_id == repo_id)).rowcount or 0
            n_r = s.execute(delete(BusinessRuleRow).where(BusinessRuleRow.repo_id == repo_id)).rowcount or 0
            return n_t + n_i + n_c + n_r

    # ---- read ----
    def get_term(self, fqn: str) -> BusinessTerm | None:
        with session_scope() as s:
            row = s.get(BusinessTermRow, fqn)
            return _row_to_term(row) if row is not None else None

    def list_terms(
        self, repo_id: str | None = None,
        kind: TermKind | None = None,
        domain: str | None = None,
    ) -> list[BusinessTerm]:
        with session_scope() as s:
            stmt = select(BusinessTermRow)
            if repo_id is not None:
                stmt = stmt.where(BusinessTermRow.repo_id == repo_id)
            if kind is not None:
                stmt = stmt.where(BusinessTermRow.kind == kind.value)
            if domain is not None:
                stmt = stmt.where(BusinessTermRow.domain == domain)
            return [_row_to_term(r) for r in s.execute(stmt).scalars()]

    def get_inheritance_parents(self, child_fqn: str) -> list[Inheritance]:
        """child 의 모든 parent (extends + implements)."""
        with session_scope() as s:
            stmt = select(InheritanceEdgeRow).where(InheritanceEdgeRow.child_fqn == child_fqn)
            return [_row_to_inh(r) for r in s.execute(stmt).scalars()]

    def get_inheritance_children(self, parent_fqn: str) -> list[Inheritance]:
        """parent 의 모든 직접 subtype."""
        with session_scope() as s:
            stmt = select(InheritanceEdgeRow).where(InheritanceEdgeRow.parent_fqn == parent_fqn)
            return [_row_to_inh(r) for r in s.execute(stmt).scalars()]

    def list_inheritance(self, repo_id: str | None = None) -> list[Inheritance]:
        with session_scope() as s:
            stmt = select(InheritanceEdgeRow)
            if repo_id is not None:
                stmt = stmt.where(InheritanceEdgeRow.repo_id == repo_id)
            return [_row_to_inh(r) for r in s.execute(stmt).scalars()]

    def get_composition_children(self, parent_fqn: str) -> list[Composition]:
        """parent 의 직접 part."""
        with session_scope() as s:
            stmt = select(CompositionEdgeRow).where(CompositionEdgeRow.parent_fqn == parent_fqn)
            return [_row_to_comp(r) for r in s.execute(stmt).scalars()]

    def list_composition(self, repo_id: str | None = None) -> list[Composition]:
        with session_scope() as s:
            stmt = select(CompositionEdgeRow)
            if repo_id is not None:
                stmt = stmt.where(CompositionEdgeRow.repo_id == repo_id)
            return [_row_to_comp(r) for r in s.execute(stmt).scalars()]

    def list_rules(self, repo_id: str | None = None) -> list[BusinessRule]:
        with session_scope() as s:
            stmt = select(BusinessRuleRow)
            if repo_id is not None:
                stmt = stmt.where(BusinessRuleRow.repo_id == repo_id)
            return [_row_to_rule(r) for r in s.execute(stmt).scalars()]


__all__ = ("DomainLayerStore",)
