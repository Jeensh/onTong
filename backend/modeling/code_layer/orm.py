"""SQLAlchemy ORM — Code Layer 테이블.

Base.metadata 에 자동 등록 (database.bootstrap_database() 가 create_all 호출).

설계 원칙:
- 1 table per 핵심 entity (CodeType / CodeField / CodeMethod / CallSite)
- 자유 부가 데이터는 JSON column (SQLite JSON1 활용)
- repo_id 모든 테이블에 — multi-repo 지원
- FK 는 fqn 문자열 (UUID 안 씀, 인간 가독)
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.modeling.persistence.database import Base
from backend.modeling.persistence.database import Base as _Base  # noqa: F401


# ---------------------------------------------------------------------------
# CodeType
# ---------------------------------------------------------------------------
class CodeTypeRow(Base):
    __tablename__ = "code_types"

    fqn:           Mapped[str] = mapped_column(String, primary_key=True)
    simple_name:   Mapped[str] = mapped_column(String, nullable=False)
    package:       Mapped[str] = mapped_column(String, nullable=False, default="")

    kind:          Mapped[str] = mapped_column(String, nullable=False)   # CodeTypeKind value
    role:          Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    is_abstract:   Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    extends:                 Mapped[str | None] = mapped_column(String, nullable=True)
    implements_json:         Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    extends_interfaces_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    modifiers_json:   Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    annotations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    source_file:   Mapped[str] = mapped_column(String, nullable=False, default="")
    line_start:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end:      Mapped[int | None] = mapped_column(Integer, nullable=True)

    repo_id:       Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    fields:  Mapped[list["CodeFieldRow"]]  = relationship(
        back_populates="parent_type", cascade="all, delete-orphan", lazy="selectin",
    )
    methods: Mapped[list["CodeMethodRow"]] = relationship(
        back_populates="parent_type", cascade="all, delete-orphan", lazy="selectin",
    )

    __table_args__ = (
        Index("ix_code_types_repo_kind", "repo_id", "kind"),
        Index("ix_code_types_repo_role", "repo_id", "role"),
    )


# ---------------------------------------------------------------------------
# CodeField
# ---------------------------------------------------------------------------
class CodeFieldRow(Base):
    __tablename__ = "code_fields"

    id:               Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_fqn:         Mapped[str] = mapped_column(String, ForeignKey("code_types.fqn", ondelete="CASCADE"), nullable=False)
    name:             Mapped[str] = mapped_column(String, nullable=False)
    type:             Mapped[str] = mapped_column(String, nullable=False)
    modifiers_json:   Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    annotations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_collection:    Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    element_type:     Mapped[str | None] = mapped_column(String, nullable=True)
    line:             Mapped[int | None] = mapped_column(Integer, nullable=True)

    parent_type: Mapped[CodeTypeRow] = relationship(back_populates="fields", foreign_keys=[type_fqn])

    __table_args__ = (
        UniqueConstraint("type_fqn", "name", name="uq_code_fields_type_name"),
    )


# ---------------------------------------------------------------------------
# CodeMethod
# ---------------------------------------------------------------------------
class CodeMethodRow(Base):
    __tablename__ = "code_methods"

    fqn:              Mapped[str] = mapped_column(String, primary_key=True)
    name:             Mapped[str] = mapped_column(String, nullable=False)
    parent_type_fqn:  Mapped[str] = mapped_column(String, ForeignKey("code_types.fqn", ondelete="CASCADE"), nullable=False)

    return_type:      Mapped[str] = mapped_column(String, nullable=False, default="")
    params_json:      Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    modifiers_json:   Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    annotations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    role:             Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    is_abstract:      Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_override:      Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_constructor:   Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    body_text:        Mapped[str | None] = mapped_column(Text, nullable=True)
    line_start:       Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end:         Mapped[int | None] = mapped_column(Integer, nullable=True)

    anchors_json:     Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    extra_json:       Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    repo_id:          Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    parent_type: Mapped[CodeTypeRow] = relationship(back_populates="methods", foreign_keys=[parent_type_fqn])

    __table_args__ = (
        Index("ix_code_methods_parent", "parent_type_fqn"),
        Index("ix_code_methods_repo_role", "repo_id", "role"),
    )


# ---------------------------------------------------------------------------
# CallSite
# ---------------------------------------------------------------------------
class CallSiteRow(Base):
    __tablename__ = "call_sites"

    id:                              Mapped[str] = mapped_column(String, primary_key=True)
    caller_method_fqn:               Mapped[str] = mapped_column(String, ForeignKey("code_methods.fqn", ondelete="CASCADE"), nullable=False)
    callee_simple_name:              Mapped[str] = mapped_column(String, nullable=False)
    callee_receiver_static_type:     Mapped[str] = mapped_column(String, nullable=False, default="")
    line:                            Mapped[int | None] = mapped_column(Integer, nullable=True)

    possible_runtime_types_json:     Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    confidence:                      Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    analysis_source:                 Mapped[str] = mapped_column(String, nullable=False)

    needs_user_confirm:              Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    user_confirmed_type:             Mapped[str | None] = mapped_column(String, nullable=True)
    user_confirmed_at:               Mapped[str | None] = mapped_column(String, nullable=True)

    repo_id:                         Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        Index("ix_call_sites_caller", "caller_method_fqn"),
        Index("ix_call_sites_repo_source", "repo_id", "analysis_source"),
    )


__all__ = (
    "CodeTypeRow",
    "CodeFieldRow",
    "CodeMethodRow",
    "CallSiteRow",
)
