"""Entity memo store — 단순 GET/UPSERT."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select

from backend.modeling.persistence.database import session_scope
from backend.modeling.memos.orm import EntityMemoRow

EntityKind = Literal["action", "term", "codeType", "rule", "anchor"]
_VALID_KINDS: frozenset[str] = frozenset({"action", "term", "codeType", "rule", "anchor"})


@dataclass
class Memo:
    repo_id: str
    entity_kind: str
    entity_id: str
    body: str
    updated_at: datetime
    updated_by: str | None


def _row_to_memo(row: EntityMemoRow) -> Memo:
    return Memo(
        repo_id=row.repo_id,
        entity_kind=row.entity_kind,
        entity_id=row.entity_id,
        body=row.body,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


def get_memo(repo_id: str, entity_kind: str, entity_id: str) -> Memo | None:
    if entity_kind not in _VALID_KINDS:
        raise ValueError(f"invalid entity_kind={entity_kind!r}; allowed={sorted(_VALID_KINDS)}")
    with session_scope() as s:
        row = s.execute(
            select(EntityMemoRow).where(
                EntityMemoRow.repo_id == repo_id,
                EntityMemoRow.entity_kind == entity_kind,
                EntityMemoRow.entity_id == entity_id,
            )
        ).scalar_one_or_none()
        return _row_to_memo(row) if row else None


def upsert_memo(
    repo_id: str,
    entity_kind: str,
    entity_id: str,
    body: str,
    updated_by: str | None = None,
) -> Memo:
    if entity_kind not in _VALID_KINDS:
        raise ValueError(f"invalid entity_kind={entity_kind!r}; allowed={sorted(_VALID_KINDS)}")
    now = datetime.utcnow()
    with session_scope() as s:
        row = s.execute(
            select(EntityMemoRow).where(
                EntityMemoRow.repo_id == repo_id,
                EntityMemoRow.entity_kind == entity_kind,
                EntityMemoRow.entity_id == entity_id,
            )
        ).scalar_one_or_none()
        if row is None:
            row = EntityMemoRow(
                repo_id=repo_id,
                entity_kind=entity_kind,
                entity_id=entity_id,
                body=body,
                updated_at=now,
                updated_by=updated_by,
            )
            s.add(row)
        else:
            row.body = body
            row.updated_at = now
            row.updated_by = updated_by
        s.flush()
        return _row_to_memo(row)


__all__ = ["Memo", "get_memo", "upsert_memo"]
