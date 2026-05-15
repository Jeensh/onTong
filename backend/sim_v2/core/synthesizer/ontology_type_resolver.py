"""OntologyTypeResolver — Section 2 Code Layer 통한 plugin-specific type lookup.

W9.1. CodeMethodRow + CodeFieldRow 조회로 W8 의 `slab.getSecondWgtHigh()` 같은
plugin-specific receiver type 한계 해소.

Public API:
  - OntologyTypeResolver(session, repo_id)
  - resolve_method_return_type(receiver_type_fqn, method_name) — CodeMethodRow lookup
  - resolve_field_type(owner_type_fqn, field_name) — CodeFieldRow lookup
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.modeling.code_layer.orm import CodeFieldRow, CodeMethodRow


class OntologyTypeResolver:
    """Query Section 2 Code Layer for Java method/field types.

    Constructor takes a SQLAlchemy session + repo_id (multi-repo isolation).
    All queries are scoped to that repo. Caches lookup results to avoid repeated
    queries within one translate() invocation.
    """

    def __init__(self, session: Session, repo_id: str) -> None:
        self.session = session
        self.repo_id = repo_id
        self._method_cache: dict[tuple[str, str], str | None] = {}
        self._field_cache: dict[tuple[str, str], str | None] = {}

    def resolve_method_return_type(
        self,
        receiver_type_fqn: str | None,
        method_name: str,
    ) -> str | None:
        """Look up `receiver_type_fqn.method_name(*)` 의 return type.

        Returns None when receiver type unknown or no matching method in ontology.
        Multi-overload methods: returns the first match (Section 2 doesn't dedupe).
        """
        if not receiver_type_fqn or not method_name:
            return None

        cache_key = (receiver_type_fqn, method_name)
        if cache_key in self._method_cache:
            return self._method_cache[cache_key]

        # Match on parent_type_fqn + name, scoped to repo_id.
        # First try exact FQN, fall back to simple-name suffix (`*.X`) for unqualified receivers.
        candidates = self._lookup_method(receiver_type_fqn, method_name)
        if not candidates:
            # Receiver might be a simple class name — try suffix match
            candidates = self._lookup_method_by_simple_name(receiver_type_fqn, method_name)

        result = None
        if candidates:
            row = candidates[0]
            return_type = (row.return_type or "").strip()
            result = return_type or None

        self._method_cache[cache_key] = result
        return result

    def resolve_field_type(
        self,
        owner_type_fqn: str | None,
        field_name: str,
    ) -> str | None:
        """Look up `owner_type_fqn.field_name` 의 type."""
        if not owner_type_fqn or not field_name:
            return None

        cache_key = (owner_type_fqn, field_name)
        if cache_key in self._field_cache:
            return self._field_cache[cache_key]

        candidates = self._lookup_field(owner_type_fqn, field_name)
        if not candidates:
            candidates = self._lookup_field_by_simple_name(owner_type_fqn, field_name)

        result = None
        if candidates:
            row = candidates[0]
            field_type = (row.type or "").strip()
            result = field_type or None

        self._field_cache[cache_key] = result
        return result

    # ─────────────────────────────────────────────────────────────────────
    # Private — query helpers
    # ─────────────────────────────────────────────────────────────────────

    def _lookup_method(self, parent_fqn: str, method_name: str) -> list[CodeMethodRow]:
        stmt = select(CodeMethodRow).where(
            CodeMethodRow.parent_type_fqn == parent_fqn,
            CodeMethodRow.name == method_name,
            CodeMethodRow.repo_id == self.repo_id,
        )
        return list(self.session.execute(stmt).scalars().all())

    def _lookup_method_by_simple_name(
        self,
        simple_name: str,
        method_name: str,
    ) -> list[CodeMethodRow]:
        """Match when receiver is unqualified (e.g., `SDSlabEntity` not full FQN)."""
        suffix = f".{simple_name}"
        stmt = select(CodeMethodRow).where(
            CodeMethodRow.parent_type_fqn.like(f"%{suffix}"),
            CodeMethodRow.name == method_name,
            CodeMethodRow.repo_id == self.repo_id,
        )
        return list(self.session.execute(stmt).scalars().all())

    def _lookup_field(self, type_fqn: str, field_name: str) -> list[CodeFieldRow]:
        stmt = select(CodeFieldRow).where(
            CodeFieldRow.type_fqn == type_fqn,
            CodeFieldRow.name == field_name,
        )
        return list(self.session.execute(stmt).scalars().all())

    def _lookup_field_by_simple_name(
        self,
        simple_name: str,
        field_name: str,
    ) -> list[CodeFieldRow]:
        suffix = f".{simple_name}"
        stmt = select(CodeFieldRow).where(
            CodeFieldRow.type_fqn.like(f"%{suffix}"),
            CodeFieldRow.name == field_name,
        )
        return list(self.session.execute(stmt).scalars().all())


__all__ = ["OntologyTypeResolver"]
