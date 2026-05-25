"""Entity change log ORM — `entity_change_log` 테이블.

PK = autoincrement id. 빠른 조회 위한 인덱스: (repo_id, changed_at), (entity_kind, entity_id).
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


class EntityChangeLogRow(Base):
    __tablename__ = "entity_change_log"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id:     Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_kind: Mapped[str] = mapped_column(String, nullable=False)  # action/term/code_type/business_rule/anchor_binding/realization/type_realization
    entity_id:   Mapped[str] = mapped_column(String, nullable=False)
    change_kind: Mapped[str] = mapped_column(String, nullable=False)  # create / update / confirm / reject / delete
    changed_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    changed_by:  Mapped[str | None] = mapped_column(String, nullable=True)
    details:     Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string or short description

    __table_args__ = (
        Index("ix_entity_change_repo_time", "repo_id", "changed_at"),
        Index("ix_entity_change_entity", "entity_kind", "entity_id"),
    )


__all__ = ["EntityChangeLogRow"]
