"""Perspective CRUD store (R4-T2.2)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import delete, select

from backend.modeling.persistence.database import session_scope
from backend.modeling.view_layer.orm import PerspectiveRow
from backend.modeling.view_layer.schema import Perspective, PerspectiveSpec

logger = logging.getLogger(__name__)


def _row_to_dto(row: PerspectiveRow) -> Perspective:
    spec = PerspectiveSpec.model_validate_json(row.spec_json)
    return Perspective(
        id=row.id,
        name=row.name,
        repo_id=row.repo_id,
        description=row.description,
        spec=spec,
        owner_id=row.owner_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ViewLayerStore:
    """Perspective CRUD."""

    def list(self, repo_id: str | None = None) -> list[Perspective]:
        with session_scope() as s:
            stmt = select(PerspectiveRow).order_by(PerspectiveRow.updated_at.desc())
            if repo_id:
                stmt = stmt.where(PerspectiveRow.repo_id == repo_id)
            return [_row_to_dto(r) for r in s.execute(stmt).scalars().all()]

    def get(self, perspective_id: int) -> Perspective | None:
        with session_scope() as s:
            row = s.get(PerspectiveRow, perspective_id)
            return _row_to_dto(row) if row else None

    def create(self, p: Perspective) -> Perspective:
        if p.id is not None:
            raise ValueError("Perspective.id should be None for create")
        row = PerspectiveRow(
            name=p.name,
            repo_id=p.repo_id,
            description=p.description,
            spec_json=p.spec.model_dump_json(),
            owner_id=p.owner_id,
        )
        with session_scope() as s:
            s.add(row)
            s.flush()
            new_id = row.id
            return _row_to_dto(row)
        # 위 with 안에서 row.id 가 채워짐 — flush 로

    def update(self, perspective_id: int, *, name: str | None = None,
               description: str | None = None,
               spec: PerspectiveSpec | None = None) -> Perspective | None:
        with session_scope() as s:
            row = s.get(PerspectiveRow, perspective_id)
            if row is None:
                return None
            if name is not None:
                row.name = name
            if description is not None:
                row.description = description
            if spec is not None:
                row.spec_json = spec.model_dump_json()
            row.updated_at = datetime.now(timezone.utc)
            s.flush()
            return _row_to_dto(row)

    def delete(self, perspective_id: int) -> bool:
        with session_scope() as s:
            row = s.get(PerspectiveRow, perspective_id)
            if row is None:
                return False
            s.delete(row)
            return True
