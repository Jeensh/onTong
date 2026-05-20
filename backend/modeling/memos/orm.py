"""Entity memo ORM — `entity_memos` 테이블.

PK = (repo_id, entity_kind, entity_id) composite. UPSERT 시 단순 lookup.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


class EntityMemoRow(Base):
    __tablename__ = "entity_memos"

    repo_id:     Mapped[str] = mapped_column(String, primary_key=True)
    entity_kind: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id:   Mapped[str] = mapped_column(String, primary_key=True)
    body:        Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by:  Mapped[str | None] = mapped_column(String, nullable=True)


__all__ = ["EntityMemoRow"]
