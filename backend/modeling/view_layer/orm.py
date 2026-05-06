"""View Layer ORM — Perspective 1 table.

R4-T2.2 / 안건 2 B.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


class PerspectiveRow(Base):
    __tablename__ = "perspectives"

    id:          Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:        Mapped[str]              = mapped_column(String(200), nullable=False)
    repo_id:     Mapped[str]              = mapped_column(String, nullable=False, index=True)
    description: Mapped[str]              = mapped_column(Text, nullable=False, default="")
    spec_json:   Mapped[str]              = mapped_column(Text, nullable=False)   # PerspectiveSpec.model_dump_json
    owner_id:    Mapped[str | None]       = mapped_column(String, nullable=True)
    created_at:  Mapped[datetime]         = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at:  Mapped[datetime]         = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_perspectives_repo_id_name", "repo_id", "name"),
    )
