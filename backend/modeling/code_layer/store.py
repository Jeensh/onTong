"""Code Layer Store — Pydantic ↔ SQLAlchemy 변환 + CRUD.

설계 원칙:
- 외부에 ORM row 노출 X (Pydantic DTO 만 반환)
- session_scope() 안에서 read/write
- repo_id 별 격리 (multi-repo)
- upsert pattern (parser 가 동일 repo 재파싱 시 idempotent)
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

from sqlalchemy import delete, select

from backend.modeling.code_layer.orm import (
    CallSiteRow,
    CodeFieldRow,
    CodeMethodRow,
    CodeTypeRow,
)
from backend.modeling.code_layer.schema import (
    CallAnalysisSource,
    CallCandidate,
    CallSite,
    CodeField,
    CodeMethod,
    CodeMethodAnchor,
    CodeMethodParam,
    CodeType,
    CodeTypeKind,
    CodeTypeRole,
    MethodRole,
)
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CodeType ↔ row 변환
# ---------------------------------------------------------------------------
def _ct_to_row(ct: CodeType) -> CodeTypeRow:
    return CodeTypeRow(
        fqn=ct.fqn,
        simple_name=ct.simple_name,
        package=ct.package,
        kind=ct.kind.value,
        role=ct.role.value,
        is_abstract=ct.is_abstract,
        extends=ct.extends,
        implements_json=json.dumps(ct.implements),
        extends_interfaces_json=json.dumps(ct.extends_interfaces),
        modifiers_json=json.dumps(ct.modifiers),
        annotations_json=json.dumps(ct.annotations),
        source_file=ct.source_file,
        line_start=ct.line_start,
        line_end=ct.line_end,
        repo_id=ct.repo_id,
        fields=[_field_to_row(f) for f in ct.fields],
        methods=[_method_to_row(m) for m in ct.methods],
    )


def _row_to_ct(row: CodeTypeRow) -> CodeType:
    return CodeType(
        fqn=row.fqn,
        simple_name=row.simple_name,
        package=row.package,
        kind=CodeTypeKind(row.kind),
        role=CodeTypeRole(row.role),
        is_abstract=row.is_abstract,
        extends=row.extends,
        implements=json.loads(row.implements_json or "[]"),
        extends_interfaces=json.loads(row.extends_interfaces_json or "[]"),
        modifiers=json.loads(row.modifiers_json or "[]"),
        annotations=json.loads(row.annotations_json or "[]"),
        source_file=row.source_file,
        line_start=row.line_start,
        line_end=row.line_end,
        repo_id=row.repo_id,
        fields=[_row_to_field(f) for f in row.fields],
        methods=[_row_to_method(m) for m in row.methods],
    )


def _field_to_row(f: CodeField) -> CodeFieldRow:
    return CodeFieldRow(
        name=f.name,
        type=f.type,
        modifiers_json=json.dumps(f.modifiers),
        annotations_json=json.dumps(f.annotations),
        is_collection=f.is_collection,
        element_type=f.element_type,
        line=f.line,
        repo_id="",  # filled by caller from parent CodeType.repo_id (same pattern as methods)
    )


def _row_to_field(row: CodeFieldRow) -> CodeField:
    return CodeField(
        name=row.name,
        type=row.type,
        modifiers=json.loads(row.modifiers_json or "[]"),
        annotations=json.loads(row.annotations_json or "[]"),
        is_collection=row.is_collection,
        element_type=row.element_type,
        line=row.line,
    )


def _method_to_row(m: CodeMethod) -> CodeMethodRow:
    return CodeMethodRow(
        fqn=m.fqn,
        name=m.name,
        parent_type_fqn=m.parent_type_fqn,
        return_type=m.return_type,
        params_json=json.dumps([p.model_dump() for p in m.params]),
        modifiers_json=json.dumps(m.modifiers),
        annotations_json=json.dumps(m.annotations),
        role=m.role.value,
        is_abstract=m.is_abstract,
        is_override=m.is_override,
        is_constructor=m.is_constructor,
        body_text=m.body_text,
        line_start=m.line_start,
        line_end=m.line_end,
        anchors_json=json.dumps([a.model_dump() for a in m.anchors]),
        extra_json=json.dumps(m.extra),
        repo_id="",  # filled by caller from parent CodeType.repo_id
    )


def _row_to_method(row: CodeMethodRow) -> CodeMethod:
    params_raw = json.loads(row.params_json or "[]")
    anchors_raw = json.loads(row.anchors_json or "[]")
    return CodeMethod(
        fqn=row.fqn,
        name=row.name,
        parent_type_fqn=row.parent_type_fqn,
        return_type=row.return_type,
        params=[CodeMethodParam(**p) for p in params_raw],
        modifiers=json.loads(row.modifiers_json or "[]"),
        annotations=json.loads(row.annotations_json or "[]"),
        role=MethodRole(row.role),
        is_abstract=row.is_abstract,
        is_override=row.is_override,
        is_constructor=row.is_constructor,
        body_text=row.body_text,
        line_start=row.line_start,
        line_end=row.line_end,
        anchors=[CodeMethodAnchor(**a) for a in anchors_raw],
        extra=json.loads(row.extra_json or "{}"),
    )


def _cs_to_row(cs: CallSite) -> CallSiteRow:
    return CallSiteRow(
        id=cs.id,
        caller_method_fqn=cs.caller_method_fqn,
        callee_simple_name=cs.callee_simple_name,
        callee_receiver_static_type=cs.callee_receiver_static_type,
        line=cs.line,
        possible_runtime_types_json=json.dumps([c.model_dump() for c in cs.possible_runtime_types]),
        confidence=cs.confidence,
        analysis_source=cs.analysis_source.value,
        needs_user_confirm=cs.needs_user_confirm,
        user_confirmed_type=cs.user_confirmed_type,
        user_confirmed_at=cs.user_confirmed_at,
        repo_id=cs.repo_id,
    )


def _row_to_cs(row: CallSiteRow) -> CallSite:
    cands_raw = json.loads(row.possible_runtime_types_json or "[]")
    # 미래 호환 — DB 에 enum 미등록 값이 있으면 STATIC_UNRESOLVED 로 fallback (400 안 내고).
    try:
        src = CallAnalysisSource(row.analysis_source)
    except ValueError:
        src = CallAnalysisSource.STATIC_UNRESOLVED
    return CallSite(
        id=row.id,
        caller_method_fqn=row.caller_method_fqn,
        callee_simple_name=row.callee_simple_name,
        callee_receiver_static_type=row.callee_receiver_static_type,
        line=row.line,
        possible_runtime_types=[CallCandidate(**c) for c in cands_raw],
        confidence=row.confidence,
        analysis_source=src,
        needs_user_confirm=row.needs_user_confirm,
        user_confirmed_type=row.user_confirmed_type,
        user_confirmed_at=row.user_confirmed_at,
        repo_id=row.repo_id,
    )


# ---------------------------------------------------------------------------
# Store API
# ---------------------------------------------------------------------------
class CodeLayerStore:
    """SQLite Store for Code Layer (CodeType + CodeField + CodeMethod + CallSite).

    Sample usage:
        store = CodeLayerStore()
        store.upsert_types(repo_id="slab", code_types=[...])
        types = store.list_types(repo_id="slab")
        method = store.get_method(fqn="com.scm.Order.validate")
    """

    # ---- write ----
    def upsert_types(self, repo_id: str, code_types: Iterable[CodeType]) -> int:
        """Replace + insert. 같은 fqn 이면 cascade 로 fields/methods 도 교체."""
        count = 0
        with session_scope() as s:
            for ct in code_types:
                # repo_id 강제 (Schema 에 안 박혀도 store 호출 시 인자로)
                ct_dict = ct.model_dump()
                ct_dict["repo_id"] = repo_id
                ct = CodeType(**ct_dict)

                existing = s.get(CodeTypeRow, ct.fqn)
                if existing is not None:
                    s.delete(existing)
                    s.flush()

                row = _ct_to_row(ct)
                # method/field row 의 repo_id 채우기 (DB UNIQUE 가 repo_id 포함)
                for mrow in row.methods:
                    mrow.repo_id = repo_id
                for frow in row.fields:
                    frow.repo_id = repo_id
                s.add(row)
                count += 1
        return count

    def delete_repo(self, repo_id: str) -> int:
        """repo 의 모든 CodeType + 자식 (fields/methods/call_sites) 삭제.

        DB DDL 에 FK 가 없어서 bulk delete 는 자동 cascade 안 됨 —
        명시적으로 자식 정리 + 안전망으로 orphan 도 한 번 청소.
        """
        with session_scope() as s:
            n_fields = s.execute(
                delete(CodeFieldRow).where(CodeFieldRow.repo_id == repo_id)
            ).rowcount or 0
            n_methods = s.execute(
                delete(CodeMethodRow).where(CodeMethodRow.repo_id == repo_id)
            ).rowcount or 0
            n_types = s.execute(
                delete(CodeTypeRow).where(CodeTypeRow.repo_id == repo_id)
            ).rowcount or 0
            n_cs = s.execute(
                delete(CallSiteRow).where(CallSiteRow.repo_id == repo_id)
            ).rowcount or 0
            # 안전망: 부모 사라진 자식 row 남아있으면 정리 (historical residue 대응)
            s.execute(
                delete(CodeFieldRow).where(
                    ~CodeFieldRow.type_fqn.in_(select(CodeTypeRow.fqn))
                )
            )
            s.execute(
                delete(CodeMethodRow).where(
                    ~CodeMethodRow.parent_type_fqn.in_(select(CodeTypeRow.fqn))
                )
            )
            s.execute(
                delete(CallSiteRow).where(
                    ~CallSiteRow.caller_method_fqn.in_(select(CodeMethodRow.fqn))
                )
            )
            return n_types + n_methods + n_fields + n_cs

    def upsert_call_sites(self, repo_id: str, call_sites: Iterable[CallSite]) -> int:
        """call_sites 갱신 — id 매칭으로 replace."""
        count = 0
        with session_scope() as s:
            for cs in call_sites:
                cs_dict = cs.model_dump()
                cs_dict["repo_id"] = repo_id
                cs = CallSite(**cs_dict)

                existing = s.get(CallSiteRow, cs.id)
                if existing is not None:
                    s.delete(existing)
                    s.flush()
                s.add(_cs_to_row(cs))
                count += 1
        return count

    # ---- read ----
    def get_type(self, fqn: str) -> CodeType | None:
        with session_scope() as s:
            row = s.get(CodeTypeRow, fqn)
            return _row_to_ct(row) if row is not None else None

    def list_types(
        self, repo_id: str | None = None,
        kind: CodeTypeKind | None = None,
        role: CodeTypeRole | None = None,
    ) -> list[CodeType]:
        with session_scope() as s:
            stmt = select(CodeTypeRow)
            if repo_id is not None:
                stmt = stmt.where(CodeTypeRow.repo_id == repo_id)
            if kind is not None:
                stmt = stmt.where(CodeTypeRow.kind == kind.value)
            if role is not None:
                stmt = stmt.where(CodeTypeRow.role == role.value)
            return [_row_to_ct(r) for r in s.execute(stmt).scalars()]

    def list_types_summary(
        self, repo_id: str | None = None,
    ) -> list[dict]:
        """R4-T1.1 perf — methods/fields/anchors/body_text 제외 가벼운 fetch.
        graph_api / modules_api 등 metadata 만 필요한 곳용. 5K 클래스에서 ~10x faster.
        반환: dict (fqn, simple_name, role, kind, package, is_abstract, method_count)
        """
        from sqlalchemy import func
        from backend.modeling.code_layer.orm import CodeMethodRow

        with session_scope() as s:
            # CodeType + method 카운트 만 join 조회 — body_text/anchors 안 로드
            stmt = (
                select(
                    CodeTypeRow.fqn,
                    CodeTypeRow.simple_name,
                    CodeTypeRow.role,
                    CodeTypeRow.kind,
                    CodeTypeRow.package,
                    CodeTypeRow.is_abstract,
                    func.count(CodeMethodRow.fqn).label("method_count"),
                )
                .outerjoin(CodeMethodRow, CodeMethodRow.parent_type_fqn == CodeTypeRow.fqn)
                .group_by(CodeTypeRow.fqn)
            )
            if repo_id is not None:
                stmt = stmt.where(CodeTypeRow.repo_id == repo_id)
            out: list[dict] = []
            for row in s.execute(stmt).all():
                out.append({
                    "fqn": row.fqn,
                    "simple_name": row.simple_name,
                    "role": row.role,
                    "kind": row.kind,
                    "package": row.package,
                    "is_abstract": row.is_abstract,
                    "method_count": row.method_count,
                })
            return out

    def get_method(self, fqn: str) -> CodeMethod | None:
        with session_scope() as s:
            row = s.get(CodeMethodRow, fqn)
            return _row_to_method(row) if row is not None else None

    def list_methods(
        self, repo_id: str | None = None, role: MethodRole | None = None,
    ) -> list[CodeMethod]:
        with session_scope() as s:
            stmt = select(CodeMethodRow)
            if repo_id is not None:
                stmt = stmt.where(CodeMethodRow.repo_id == repo_id)
            if role is not None:
                stmt = stmt.where(CodeMethodRow.role == role.value)
            return [_row_to_method(r) for r in s.execute(stmt).scalars()]

    def get_call_sites(self, caller_method_fqn: str) -> list[CallSite]:
        with session_scope() as s:
            stmt = select(CallSiteRow).where(
                CallSiteRow.caller_method_fqn == caller_method_fqn
            )
            return [_row_to_cs(r) for r in s.execute(stmt).scalars()]

    def list_ambiguous_call_sites(self, repo_id: str | None = None) -> list[CallSite]:
        """needs_user_confirm=True 인 사이트만 — 사용자 큐 데이터."""
        with session_scope() as s:
            stmt = select(CallSiteRow).where(CallSiteRow.needs_user_confirm.is_(True))
            if repo_id is not None:
                stmt = stmt.where(CallSiteRow.repo_id == repo_id)
            return [_row_to_cs(r) for r in s.execute(stmt).scalars()]


__all__ = ("CodeLayerStore",)
