"""Ontology Layer tools — read-only queries over BusinessTerm + Action.

Wraps `DomainLayerStore` and `MappingLayerStore.list_actions/get_action`.
Cold-start safe: when the ontology is empty, tools return [] without
raising — the LLM can interpret "no terms found" as a meaningful signal.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer.store import MappingLayerStore

logger = logging.getLogger(__name__)


# ── Result shaping ────────────────────────────────────────────────────


def _term_view(t: Any) -> dict[str, Any]:
    return {
        "fqn": t.fqn,
        "label": t.label,
        "aliases": list(t.aliases),
        "kind": t.kind.value if hasattr(t.kind, "value") else t.kind,
        "domain": t.domain,
        "description": t.description,
        "is_abstract": t.is_abstract,
        "is_interface": t.is_interface,
        "is_root_entity": t.is_root_entity,
        "struct_like_hint": t.struct_like_hint,
        "value_type": (t.value_type.value if t.value_type else None),
        "unit": t.unit,
        "range": t.range,
        "enum_values": t.enum_values,
        "confirmed": t.confirmed,
    }


def _action_view(a: Any) -> dict[str, Any]:
    return {
        "fqn": a.fqn,
        "label": a.label,
        "aliases": list(a.aliases),
        "domain": a.domain,
        "kind": a.kind.value if hasattr(a.kind, "value") else a.kind,
        "description": a.description,
        "declared_on_term": getattr(a, "declared_on_term", None),
        "verification_level": (
            a.verification_level.value
            if hasattr(getattr(a, "verification_level", ""), "value")
            else getattr(a, "verification_level", "")
        ),
        "realization_count": len(getattr(a, "realizations", []) or []),
    }


def _score(label: str, full: str, q: str) -> float:
    ll, ff = label.lower(), full.lower()
    if ll == q or ff == q:
        return 1.0
    if ll.startswith(q) or ff.startswith(q):
        return 0.85
    if q in ll or q in ff:
        return 0.6
    return 0.0


# ── Tools ─────────────────────────────────────────────────────────────


def domain_search(
    *, query: str, kind: str | None = None, repo_id: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """Substring/prefix search over BusinessTerm + Action.

    `kind` filter: "term" | "action" | None (both).
    """
    if not query.strip():
        return []
    q = query.strip().lower()
    out: list[dict[str, Any]] = []

    if kind in (None, "term"):
        for t in DomainLayerStore().list_terms(repo_id=repo_id):
            s = _score(t.label, t.fqn, q)
            for a in t.aliases:
                s = max(s, _score(a, t.fqn, q))
            if s > 0:
                out.append(
                    {**_term_view(t), "match_kind": "term", "score": round(s, 2)}
                )

    if kind in (None, "action"):
        for a in MappingLayerStore().list_actions(repo_id=repo_id):
            s = _score(a.label, a.fqn, q)
            for al in a.aliases:
                s = max(s, _score(al, a.fqn, q))
            if s > 0:
                out.append(
                    {**_action_view(a), "match_kind": "action", "score": round(s, 2)}
                )

    out.sort(key=lambda h: h["score"], reverse=True)
    return out[:limit]


def term_lookup(*, term_fqn: str) -> dict[str, Any] | None:
    """BusinessTerm + IS_A parents/children + HAS_A children + composed-of summary."""
    store = DomainLayerStore()
    t = store.get_term(term_fqn)
    if t is None:
        return None
    out: dict[str, Any] = _term_view(t)
    out["parents"] = [
        {"parent_fqn": p.parent_fqn, "kind": p.kind.value if hasattr(p.kind, "value") else p.kind}
        for p in store.get_inheritance_parents(term_fqn)
    ]
    out["children"] = [
        {"child_fqn": c.child_fqn, "kind": c.kind.value if hasattr(c.kind, "value") else c.kind}
        for c in store.get_inheritance_children(term_fqn)
    ]
    out["composed_of"] = [
        {
            "child_fqn": c.child_fqn,
            "role_name": c.role_name,
            "cardinality": c.cardinality.value if hasattr(c.cardinality, "value") else c.cardinality,
        }
        for c in store.get_composition_children(term_fqn)
    ]
    return out


def action_lookup(*, action_fqn: str) -> dict[str, Any] | None:
    """Action + realizations (CodeMethod fqn list) summary."""
    store = MappingLayerStore()
    a = store.get_action(action_fqn)
    if a is None:
        return None
    out = _action_view(a)
    out["realizations"] = [
        {
            "code_method_fqn": r.code_method_fqn,
            "applies_to_code_type_fqn": r.applies_to_code_type_fqn,
            "is_override": r.is_override,
            "dispatch_source": r.dispatch_source.value if hasattr(r.dispatch_source, "value") else r.dispatch_source,
            "scope": r.scope.value if hasattr(r.scope, "value") else r.scope,
            "confidence": r.confidence,
            "confirmed": r.confirmed,
        }
        for r in (getattr(a, "realizations", None) or [])
    ]
    return out


def find_term_realizations(*, term_fqn: str) -> list[dict[str, Any]]:
    """CodeTypes that realize this term (PRIMARY/PARTIAL via TypeRealization)."""
    out: list[dict[str, Any]] = []
    for tr in MappingLayerStore().list_type_realizations():
        if tr.term_fqn == term_fqn:
            out.append(
                {
                    "code_type_fqn": tr.code_type_fqn,
                    "term_fqn": tr.term_fqn,
                    "scope": tr.scope.value if hasattr(tr.scope, "value") else tr.scope,
                    "confidence": tr.confidence,
                    "source": tr.source,
                    "confirmed": tr.confirmed,
                }
            )
    return out


def find_action_realizations(
    *, action_fqn: str, applies_to_code_type_fqn: str | None = None
) -> list[dict[str, Any]]:
    """Realizations of an action — optionally filtered by `applies_to_code_type_fqn`
    for the polymorphic-dispatch case (e.g. `RushOrder.validate` overriding the
    base `Order.validate`)."""
    reals = MappingLayerStore().list_realizations(action_fqn)
    out: list[dict[str, Any]] = []
    for r in reals:
        if applies_to_code_type_fqn is not None:
            if r.applies_to_code_type_fqn != applies_to_code_type_fqn:
                continue
        out.append(
            {
                "code_method_fqn": r.code_method_fqn,
                "applies_to_code_type_fqn": r.applies_to_code_type_fqn,
                "is_override": r.is_override,
                "dispatch_source": r.dispatch_source.value if hasattr(r.dispatch_source, "value") else r.dispatch_source,
                "scope": r.scope.value if hasattr(r.scope, "value") else r.scope,
                "confidence": r.confidence,
                "confirmed": r.confirmed,
            }
        )
    return out


def find_terms_in_domain(
    *, domain: str, repo_id: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """All BusinessTerms in a given domain bucket (e.g. "scm", "purchasing")."""
    out: list[dict[str, Any]] = []
    for t in DomainLayerStore().list_terms(repo_id=repo_id):
        if t.domain == domain:
            out.append(_term_view(t))
            if len(out) >= limit:
                break
    return out


ALL_ONTOLOGY_TOOLS: dict[str, Any] = {
    "domain_search": domain_search,
    "term_lookup": term_lookup,
    "action_lookup": action_lookup,
    "find_term_realizations": find_term_realizations,
    "find_action_realizations": find_action_realizations,
    "find_terms_in_domain": find_terms_in_domain,
}


__all__ = list(ALL_ONTOLOGY_TOOLS.keys()) + ["ALL_ONTOLOGY_TOOLS"]
