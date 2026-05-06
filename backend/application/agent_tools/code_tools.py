"""Code Layer tools — read-only graph queries over CodeType / CodeMethod / CodeField / CallSite.

These tool functions are sync; pydantic_ai accepts both sync and async callables.
Each tool returns a JSON-serialisable structure (dict / list / None) — never raw
SQLAlchemy rows or Pydantic models, so the LLM sees clean shapes.

Tool budget / dedup / logging is applied externally by `make_tracked` in
`tracking.py`. This module just defines the raw query logic.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from sqlalchemy import select

from backend.modeling.code_layer.orm import (
    CallSiteRow,
    CodeMethodRow,
    CodeTypeRow,
)
from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)

# ── Result shaping helpers ────────────────────────────────────────────


def _type_summary(ct_row: CodeTypeRow) -> dict[str, Any]:
    return {
        "fqn": ct_row.fqn,
        "simple_name": ct_row.simple_name,
        "package": ct_row.package,
        "class_kind": ct_row.kind,  # class | interface | enum | annotation | record
        "role": ct_row.role,
        "extends": ct_row.extends,
        "implements": json.loads(ct_row.implements_json or "[]"),
        "annotations": json.loads(ct_row.annotations_json or "[]"),
        "source_file": ct_row.source_file,
        "field_count": len(ct_row.fields),
        "method_count": len(ct_row.methods),
        "repo_id": ct_row.repo_id,
    }


def _type_full(ct_row: CodeTypeRow) -> dict[str, Any]:
    out = _type_summary(ct_row)
    out["fields"] = [
        {
            "name": f.name,
            "type": f.type,
            "annotations": json.loads(f.annotations_json or "[]"),
            "is_collection": f.is_collection,
            "element_type": f.element_type,
            "line": f.line,
        }
        for f in ct_row.fields
    ]
    out["methods"] = [
        {"fqn": m.fqn, "name": m.name, "role": m.role, "return_type": m.return_type}
        for m in ct_row.methods
    ]
    return out


def _method_summary(m_row: CodeMethodRow) -> dict[str, Any]:
    return {
        "fqn": m_row.fqn,
        "name": m_row.name,
        "parent_type_fqn": m_row.parent_type_fqn,
        "params": json.loads(m_row.params_json or "[]"),
        "return_type": m_row.return_type,
        "method_role": m_row.role,
        "annotations": json.loads(m_row.annotations_json or "[]"),
        "is_constructor": m_row.is_constructor,
        "is_override": m_row.is_override,
        "line_start": m_row.line_start,
        "line_end": m_row.line_end,
    }


# ── Tools ─────────────────────────────────────────────────────────────


def code_lookup(*, fqn: str) -> dict[str, Any] | None:
    """Look up a CodeType, CodeMethod, or CodeField by fully-qualified name.

    Returns a dict with `kind` ∈ {"code_type", "code_method", "code_field"}
    and the full payload, or None if not found. CodeField FQNs follow the
    pattern `<typeFqn>#<fieldName>`.
    """
    with session_scope() as s:
        # Try CodeType first.
        ct_row = s.get(CodeTypeRow, fqn)
        if ct_row is not None:
            return {"kind": "code_type", **_type_full(ct_row)}

        # Try CodeMethod.
        m_row = s.get(CodeMethodRow, fqn)
        if m_row is not None:
            return {"kind": "code_method", **_method_summary(m_row)}

        # Try CodeField via "<type>#<name>" convention.
        if "#" in fqn:
            type_fqn, field_name = fqn.split("#", 1)
            parent = s.get(CodeTypeRow, type_fqn)
            if parent is not None:
                for f in parent.fields:
                    if f.name == field_name:
                        return {
                            "kind": "code_field",
                            "fqn": fqn,
                            "name": f.name,
                            "type": f.type,
                            "parent_type_fqn": type_fqn,
                            "annotations": json.loads(f.annotations_json or "[]"),
                            "is_collection": f.is_collection,
                            "element_type": f.element_type,
                            "line": f.line,
                        }
        return None


def code_search(
    *, query: str, kind: str | None = None, repo_id: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """Keyword search across CodeType + CodeMethod (substring + prefix match).

    `kind` filter: "code_type" | "code_method" | None (both).
    Returns up to `limit` hits sorted by score (1.0 exact > 0.85 prefix > 0.6 substring).
    """
    if not query.strip():
        return []
    q = query.strip().lower()
    hits: list[dict[str, Any]] = []

    def _score(label: str, full: str) -> float:
        ll, ff = label.lower(), full.lower()
        if ll == q or ff == q:
            return 1.0
        if ll.startswith(q) or ff.startswith(q):
            return 0.85
        if q in ll or q in ff:
            return 0.6
        return 0.0

    with session_scope() as s:
        if kind in (None, "code_type"):
            stmt = select(CodeTypeRow)
            if repo_id:
                stmt = stmt.where(CodeTypeRow.repo_id == repo_id)
            for row in s.execute(stmt).scalars():
                sc = _score(row.simple_name, row.fqn)
                if sc > 0:
                    hits.append(
                        {
                            "fqn": row.fqn,
                            "label": row.simple_name,
                            "kind": "code_type",
                            "package": row.package,
                            "role": row.role,
                            "score": sc,
                        }
                    )

        if kind in (None, "code_method"):
            stmt = select(CodeMethodRow)
            if repo_id:
                stmt = stmt.where(CodeMethodRow.repo_id == repo_id)
            for row in s.execute(stmt).scalars():
                sc = _score(row.name, row.fqn)
                if sc > 0:
                    hits.append(
                        {
                            "fqn": row.fqn,
                            "label": row.name,
                            "kind": "code_method",
                            "parent_type_fqn": row.parent_type_fqn,
                            "score": sc,
                        }
                    )

    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


def find_subclasses(*, type_fqn: str) -> list[dict[str, Any]]:
    """Direct subclasses (one hop) — types whose `extends` field equals `type_fqn`."""
    with session_scope() as s:
        stmt = select(CodeTypeRow).where(CodeTypeRow.extends == type_fqn)
        return [_type_summary(r) for r in s.execute(stmt).scalars()]


def find_implementations(*, interface_fqn: str) -> list[dict[str, Any]]:
    """Types whose `implements` list contains `interface_fqn`.

    Uses a JSON LIKE prefilter then exact membership check.
    """
    needle = json.dumps(interface_fqn)
    with session_scope() as s:
        stmt = select(CodeTypeRow).where(CodeTypeRow.implements_json.like(f"%{needle}%"))
        out: list[dict[str, Any]] = []
        for row in s.execute(stmt).scalars():
            impls = json.loads(row.implements_json or "[]")
            if interface_fqn in impls:
                out.append(_type_summary(row))
        return out


def find_callers(*, method_fqn: str, limit: int = 20) -> list[dict[str, Any]]:
    """Methods whose body contains a call site that resolves to `method_fqn`.

    A call site resolves when one of its `possible_runtime_types` matches the
    target method's parent type AND `callee_simple_name` matches the target's
    short name. Limit kept small — callers can be long lists in real codebases.
    """
    target = CodeLayerStore().get_method(method_fqn)
    if target is None:
        return []
    target_parent = target.parent_type_fqn
    target_simple = target.name

    with session_scope() as s:
        stmt = select(CallSiteRow).where(
            CallSiteRow.callee_simple_name == target_simple
        )
        out: list[dict[str, Any]] = []
        for cs_row in s.execute(stmt).scalars():
            try:
                candidates = json.loads(cs_row.possible_runtime_types_json or "[]")
            except (TypeError, ValueError):
                candidates = []
            matched = any(
                c.get("code_type_fqn") == target_parent for c in candidates
            )
            if matched or cs_row.callee_receiver_static_type.endswith(
                target_parent.rsplit(".", 1)[-1]
            ):
                out.append(
                    {
                        "caller_method_fqn": cs_row.caller_method_fqn,
                        "line": cs_row.line,
                        "confidence": cs_row.confidence,
                        "callee_simple_name": cs_row.callee_simple_name,
                        "needs_user_confirm": cs_row.needs_user_confirm,
                    }
                )
            if len(out) >= limit:
                break
        return out


def find_callees(*, method_fqn: str, limit: int = 30) -> list[dict[str, Any]]:
    """Methods invoked from `method_fqn`'s body (via static analysis call sites)."""
    sites = CodeLayerStore().get_call_sites(caller_method_fqn=method_fqn)
    out: list[dict[str, Any]] = []
    for cs in sites[:limit]:
        # Pick top-confidence runtime type; report all if multiple.
        candidates = [
            {"code_type_fqn": c.code_type_fqn, "score": c.score, "reason": c.reason}
            for c in cs.possible_runtime_types
        ]
        out.append(
            {
                "callee_simple_name": cs.callee_simple_name,
                "callee_receiver_static_type": cs.callee_receiver_static_type,
                "line": cs.line,
                "confidence": cs.confidence,
                "candidates": candidates,
                "needs_user_confirm": cs.needs_user_confirm,
            }
        )
    return out


def _scan_anchors_for_field(
    *, field_name: str, parent_type_fqn: str | None, want_mutation: bool | None
) -> list[dict[str, Any]]:
    """Internal helper for find_field_readers/writers.

    Scans CodeMethodRow.anchors_json for `field_access` kind anchors whose
    locator references `field_name`. Optional `parent_type_fqn` narrows the
    search to methods belonging to that type (cheap heuristic).
    """
    out: list[dict[str, Any]] = []
    with session_scope() as s:
        stmt = select(CodeMethodRow)
        if parent_type_fqn is not None:
            stmt = stmt.where(CodeMethodRow.parent_type_fqn == parent_type_fqn)
        for m_row in s.execute(stmt).scalars():
            try:
                anchors = json.loads(m_row.anchors_json or "[]")
            except (TypeError, ValueError):
                continue
            for a in anchors:
                if a.get("kind") != "field_access":
                    continue
                locator = a.get("locator", "")
                if field_name not in locator:
                    continue
                extra = a.get("extra", {}) or {}
                is_mut = bool(extra.get("mutation"))
                if want_mutation is None or want_mutation == is_mut:
                    out.append(
                        {
                            "method_fqn": m_row.fqn,
                            "line": a.get("line"),
                            "snippet": a.get("snippet", "")[:140],
                            "mutation": is_mut,
                            "locator": locator,
                        }
                    )
    return out


def find_field_readers(*, field_fqn: str, limit: int = 20) -> list[dict[str, Any]]:
    """Methods that read this field (via field_access anchors, mutation=False)."""
    parent, _, name = field_fqn.partition("#")
    if not name:
        return []
    parent_fqn = parent or None
    return _scan_anchors_for_field(
        field_name=name, parent_type_fqn=parent_fqn, want_mutation=False
    )[:limit]


def find_field_writers(*, field_fqn: str, limit: int = 20) -> list[dict[str, Any]]:
    """Methods that write this field (via field_access anchors with mutation=True)."""
    parent, _, name = field_fqn.partition("#")
    if not name:
        return []
    parent_fqn = parent or None
    return _scan_anchors_for_field(
        field_name=name, parent_type_fqn=parent_fqn, want_mutation=True
    )[:limit]


def get_method_body(*, method_fqn: str) -> dict[str, Any] | None:
    """Raw Java method body source. Returns None if not found or no body stored."""
    method = CodeLayerStore().get_method(method_fqn)
    if method is None:
        return None
    return {
        "fqn": method.fqn,
        "name": method.name,
        "params": [p.model_dump() for p in method.params],
        "return_type": method.return_type,
        "body_text": method.body_text,
        "line_start": method.line_start,
        "line_end": method.line_end,
    }


def get_method_anchors(*, method_fqn: str) -> list[dict[str, Any]]:
    """7-kind anchor list (param/local/return/branch/literal/field/field_access)."""
    method = CodeLayerStore().get_method(method_fqn)
    if method is None:
        return []
    return [
        {
            "kind": a.kind,
            "locator": a.locator,
            "line": a.line,
            "snippet": a.snippet,
            "extra": a.extra,
        }
        for a in method.anchors
    ]


def find_related_jpos(*, jpo_fqn: str, limit: int = 10) -> list[dict[str, Any]]:
    """Other JPO entities that share at least one PK field name with `jpo_fqn`.

    Uses @Id annotation as the PK signal. Returns same-repo JPOs ranked by
    overlapping PK count.
    """
    store = CodeLayerStore()
    target = store.get_type(jpo_fqn)
    if target is None:
        return []
    target_pks = {
        f.name
        for f in target.fields
        if any("Id" in a or "@Id" in a for a in f.annotations)
    }
    if not target_pks:
        return []

    out: list[dict[str, Any]] = []
    for ct in store.list_types(repo_id=target.repo_id):
        if ct.fqn == target.fqn:
            continue
        pks = {
            f.name
            for f in ct.fields
            if any("Id" in a or "@Id" in a for a in f.annotations)
        }
        overlap = pks & target_pks
        if not overlap:
            continue
        out.append(
            {
                "fqn": ct.fqn,
                "simple_name": ct.simple_name,
                "kind": ct.kind.value if hasattr(ct.kind, "value") else ct.kind,
                "role": ct.role.value if hasattr(ct.role, "value") else ct.role,
                "shared_pk_columns": sorted(overlap),
                "overlap_size": len(overlap),
                "source_file": ct.source_file,
            }
        )
    out.sort(key=lambda x: x["overlap_size"], reverse=True)
    return out[:limit]


def find_in_same_package(
    *, fqn: str, kind: str | None = None, limit: int = 30
) -> list[dict[str, Any]]:
    """Sibling code types in the same Java package as `fqn`."""
    store = CodeLayerStore()
    target = store.get_type(fqn)
    if target is None:
        # Maybe `fqn` is a method — drop the trailing segment.
        if "(" in fqn or fqn.count(".") > 0:
            type_fqn = fqn.rsplit(".", 1)[0] if "(" not in fqn else fqn.split("(")[0].rsplit(".", 1)[0]
            target = store.get_type(type_fqn)
        if target is None:
            return []
    pkg = target.package
    out: list[dict[str, Any]] = []
    with session_scope() as s:
        stmt = select(CodeTypeRow).where(
            CodeTypeRow.package == pkg, CodeTypeRow.fqn != target.fqn
        )
        if kind is not None:
            stmt = stmt.where(CodeTypeRow.kind == kind)
        for r in s.execute(stmt).scalars():
            out.append(_type_summary(r))
            if len(out) >= limit:
                break
    return out


# Public registry: (tool_name, callable, default kwargs description for LLM)
ALL_CODE_TOOLS: dict[str, Any] = {
    "code_lookup": code_lookup,
    "code_search": code_search,
    "find_subclasses": find_subclasses,
    "find_implementations": find_implementations,
    "find_callers": find_callers,
    "find_callees": find_callees,
    "find_field_readers": find_field_readers,
    "find_field_writers": find_field_writers,
    "get_method_body": get_method_body,
    "get_method_anchors": get_method_anchors,
    "find_related_jpos": find_related_jpos,
    "find_in_same_package": find_in_same_package,
}


__all__ = list(ALL_CODE_TOOLS.keys()) + ["ALL_CODE_TOOLS"]
