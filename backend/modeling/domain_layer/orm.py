"""SQLAlchemy ORM — Domain Layer (BusinessTerm + Inheritance + Composition + BusinessRule).

설계:
- 4 테이블 평면 (relationship 없음 — graph 는 fqn 문자열로 자유 traversal)
- repo_id 격리
- inheritance/composition 각각 own ID
- 사이클 / atomic-parts 검사는 store / validator 에서 (DB 단계 X)
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


class BusinessTermRow(Base):
    __tablename__ = "business_terms"

    fqn:         Mapped[str] = mapped_column(String, primary_key=True)
    label:       Mapped[str] = mapped_column(String, nullable=False)
    aliases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    domain:      Mapped[str] = mapped_column(String, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    kind:               Mapped[str] = mapped_column(String, nullable=False)
    is_abstract:        Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_interface:       Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_root_entity:     Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    struct_like_hint:   Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # atomic only
    value_type:        Mapped[str | None] = mapped_column(String, nullable=True)
    unit:              Mapped[str | None] = mapped_column(String, nullable=True)
    range_json:        Mapped[str | None] = mapped_column(Text, nullable=True)
    enum_values_json:  Mapped[str | None] = mapped_column(Text, nullable=True)

    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    repo_id:   Mapped[str] = mapped_column(String, nullable=False, default="", index=True)
    source:    Mapped[str] = mapped_column(String, nullable=False, default="user")

    __table_args__ = (
        Index("ix_business_terms_repo_kind", "repo_id", "kind"),
        Index("ix_business_terms_repo_domain", "repo_id", "domain"),
    )


class InheritanceEdgeRow(Base):
    __tablename__ = "inheritance_edges"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_fqn:  Mapped[str] = mapped_column(String, nullable=False, index=True)
    parent_fqn: Mapped[str] = mapped_column(String, nullable=False, index=True)
    kind:       Mapped[str] = mapped_column(String, nullable=False)   # extends | implements
    repo_id:    Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        UniqueConstraint("child_fqn", "parent_fqn", "kind", name="uq_inheritance_edge"),
    )


class CompositionEdgeRow(Base):
    __tablename__ = "composition_edges"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_fqn:  Mapped[str] = mapped_column(String, nullable=False, index=True)
    child_fqn:   Mapped[str] = mapped_column(String, nullable=False, index=True)
    role_name:   Mapped[str] = mapped_column(String, nullable=False)
    cardinality: Mapped[str] = mapped_column(String, nullable=False, default="1:1")
    required:    Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    repo_id:     Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        UniqueConstraint("parent_fqn", "role_name", name="uq_composition_role"),
    )


class BusinessRuleRow(Base):
    __tablename__ = "business_rules"

    fqn:        Mapped[str] = mapped_column(String, primary_key=True)
    statement:  Mapped[str] = mapped_column(Text, nullable=False)
    severity:   Mapped[str] = mapped_column(String, nullable=False, default="hard")
    terms_ref_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source:     Mapped[str] = mapped_column(String, nullable=False, default="")
    confirmed:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    repo_id:    Mapped[str] = mapped_column(String, nullable=False, default="", index=True)


__all__ = (
    "BusinessTermRow",
    "InheritanceEdgeRow",
    "CompositionEdgeRow",
    "BusinessRuleRow",
)
