"""Mapping Layer tools — read-only queries over TypeRealization + AnchorBinding.

Lets the agent ask:
  - "is this CodeType already realized as a domain term?"
  - "what anchors does this method already have bound?"
  - "what methods in this class are still unmapped?"
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from backend.modeling.code_layer.orm import CodeMethodRow
from backend.modeling.mapping_layer.store import MappingLayerStore
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)


def _ab_view(ab: Any) -> dict[str, Any]:
    return {
        "id": ab.id,
        "anchor_locator": ab.anchor_locator,
        "code_method_fqn": ab.code_method_fqn,
        "target_action_fqn": ab.target_action_fqn,
        "target_slot": ab.target_slot,
        "confidence": ab.confidence,
        "source": ab.source,
        "confirmed": ab.confirmed,
    }


def find_existing_mapping(*, code_fqn: str) -> dict[str, Any] | None:
    """If `code_fqn` is a CodeType, return its primary realization (term + scope).

    Returns None if no realization exists. Use this BEFORE proposing a new
    BusinessTerm, to avoid duplicates.
    """
    store = MappingLayerStore()
    tr = store.get_term_for_code_type(code_fqn)
    if tr is None:
        return None
    return {
        "code_type_fqn": tr.code_type_fqn,
        "term_fqn": tr.term_fqn,
        "scope": tr.scope.value if hasattr(tr.scope, "value") else tr.scope,
        "confidence": tr.confidence,
        "source": tr.source,
        "confirmed": tr.confirmed,
        "rationale": getattr(tr, "rationale", ""),
    }


def lookup_anchor_binding(
    *, method_fqn: str, anchor_locator: str | None = None
) -> list[dict[str, Any]]:
    """All AnchorBinding rows for `method_fqn`. Optionally filter by anchor_locator."""
    bindings = MappingLayerStore().get_anchor_bindings_for_method(
        code_method_fqn=method_fqn
    )
    out: list[dict[str, Any]] = []
    for ab in bindings:
        if anchor_locator is not None and ab.anchor_locator != anchor_locator:
            continue
        out.append(_ab_view(ab))
    return out


def find_unmapped_methods_in_class(
    *, type_fqn: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Methods in `type_fqn` that have no AnchorBinding yet.

    Useful when proposing new actions for a class — prefer methods not
    already mapped.
    """
    store = MappingLayerStore()
    out: list[dict[str, Any]] = []
    with session_scope() as s:
        stmt = select(CodeMethodRow).where(CodeMethodRow.parent_type_fqn == type_fqn)
        for m_row in s.execute(stmt).scalars():
            existing = store.get_anchor_bindings_for_method(code_method_fqn=m_row.fqn)
            if existing:
                continue
            out.append(
                {
                    "method_fqn": m_row.fqn,
                    "name": m_row.name,
                    "role": m_row.role,
                    "return_type": m_row.return_type,
                    "is_constructor": m_row.is_constructor,
                }
            )
            if len(out) >= limit:
                break
    return out


ALL_MAPPING_TOOLS: dict[str, Any] = {
    "find_existing_mapping": find_existing_mapping,
    "lookup_anchor_binding": lookup_anchor_binding,
    "find_unmapped_methods_in_class": find_unmapped_methods_in_class,
}


__all__ = list(ALL_MAPPING_TOOLS.keys()) + ["ALL_MAPPING_TOOLS"]
