"""SQLAlchemy ORM — Mapping Layer (4 테이블).

설계:
- type_realizations: CodeType ↔ Term 평면
- actions: Action 1급. params/effects/realizations/sub_actions 는 JSON
  (관계형 분해는 Phase 2 — 지금은 단순함 우선)
- realizations: 별도 테이블로도 빠르게 조회 가능 (action_fqn → realizations)
- anchor_bindings: fragment-level
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


class TypeRealizationRow(Base):
    __tablename__ = "type_realizations"

    id:            Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code_type_fqn: Mapped[str] = mapped_column(String, nullable=False, index=True)
    term_fqn:      Mapped[str] = mapped_column(String, nullable=False, index=True)
    scope:         Mapped[str] = mapped_column(String, nullable=False, default="primary")
    confidence:    Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source:        Mapped[str] = mapped_column(String, nullable=False, default="user")
    confirmed:     Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_by:  Mapped[str | None] = mapped_column(String, nullable=True)
    rationale:     Mapped[str] = mapped_column(Text, nullable=False, default="")
    repo_id:       Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        UniqueConstraint("code_type_fqn", "term_fqn", "scope", name="uq_type_realization"),
    )


class ActionRow(Base):
    __tablename__ = "actions"

    fqn:                 Mapped[str] = mapped_column(String, primary_key=True)
    label:               Mapped[str] = mapped_column(String, nullable=False)
    aliases_json:        Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    domain:              Mapped[str] = mapped_column(String, nullable=False, default="")
    description:         Mapped[str] = mapped_column(Text, nullable=False, default="")

    kind:                Mapped[str] = mapped_column(String, nullable=False)
    is_abstract:         Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    declared_on_term:    Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    params_json:         Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    output_json:         Mapped[str | None] = mapped_column(Text, nullable=True)
    preconditions_json:  Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    postconditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    effects_json:        Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sub_actions_json:    Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    verification_level:  Mapped[str] = mapped_column(String, nullable=False, default="unmapped", index=True)
    signature_locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by:        Mapped[str | None] = mapped_column(String, nullable=True)
    repo_id:             Mapped[str] = mapped_column(String, nullable=False, default="", index=True)


class RealizationRow(Base):
    __tablename__ = "realizations"

    id:                       Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_fqn:               Mapped[str] = mapped_column(String, nullable=False, index=True)
    code_method_fqn:          Mapped[str] = mapped_column(String, nullable=False, index=True)
    applies_to_code_type_fqn: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_override:              Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispatch_source:          Mapped[str] = mapped_column(String, nullable=False)
    confidence:               Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    scope:                    Mapped[str] = mapped_column(String, nullable=False, default="primary")
    confirmed:                Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rationale:                Mapped[str] = mapped_column(Text, nullable=False, default="")
    repo_id:                  Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        UniqueConstraint(
            "action_fqn", "code_method_fqn", "applies_to_code_type_fqn",
            name="uq_realization",
        ),
    )


class AnchorBindingRow(Base):
    __tablename__ = "anchor_bindings"

    id:                Mapped[str] = mapped_column(String, primary_key=True)
    anchor_locator:    Mapped[str] = mapped_column(String, nullable=False)
    code_method_fqn:   Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_action_fqn: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_slot:       Mapped[str] = mapped_column(String, nullable=False)
    confidence:        Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source:            Mapped[str] = mapped_column(String, nullable=False, default="user")
    confirmed:         Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rationale:         Mapped[str] = mapped_column(Text, nullable=False, default="")
    repo_id:           Mapped[str] = mapped_column(String, nullable=False, default="", index=True)
    # 2026-05-10: anchor 의 source code 라인 번호 — fix_action_output_anchor_line.py 가 ALTER TABLE 로 추가.
    line:              Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_anchor_bindings_action_slot", "target_action_fqn", "target_slot"),
    )


__all__ = (
    "TypeRealizationRow",
    "ActionRow",
    "RealizationRow",
    "AnchorBindingRow",
)
