"""SQLAlchemy ORM — Schema Layer (5번째 ontology layer, ADR-004).

8 table additive — 기존 4 layer (Code/Domain/Mapping/Simulation) 변경 없음.

Models:
    1. SchemaTableRow            DB table 정의
    2. SchemaColumnRow           Column 정의
    3. SchemaConstraintRow       UNIQUE / CHECK / FK / PK 등
    4. SchemaIndexRow            INDEX 정의
    5. SchemaViewRow             VIEW 정의
    6. SchemaMigrationRow        DDL version 관리
    7. SchemaCodeMappingRow      Schema ↔ Code 양방향 매핑
    8. SchemaDomainMappingRow    Schema ↔ BusinessTerm 매핑

설계:
- 기존 modeling Base (backend.modeling.persistence.database.Base) 사용 — 같은 ontology DB
- repo_id 격리 (multi-system: v2 / broadleaf / banking)
- Relationship 없음 — fqn 문자열로 cross-table traversal (기존 modeling pattern 일관)
- table fqn = "<schema_name>.<table_name>" — schema_name default 'public'
- column fqn = "<table_fqn>.<column_name>"
- mapping confirmed flag — auto-derived 와 user-confirmed 분리
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Float,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# 1. SchemaTable
# ─────────────────────────────────────────────────────────────────────────────


class SchemaTableRow(Base):
    """DB table 정의. fqn = '<schema_name>.<table_name>'."""
    __tablename__ = "schema_tables"

    fqn:          Mapped[str] = mapped_column(String)
    table_name:   Mapped[str] = mapped_column(String, nullable=False)
    schema_name:  Mapped[str] = mapped_column(String, nullable=False, default="public")
    description:  Mapped[str] = mapped_column(Text, nullable=False, default="")

    source:       Mapped[str] = mapped_column(String, nullable=False, default="jpa_annotation")
    # source: jpa_annotation / hibernate_xml / ddl_file / liquibase / flyway

    repo_id:      Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        PrimaryKeyConstraint("fqn", "repo_id"),
        Index("ix_schema_tables_repo_table", "repo_id", "table_name"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. SchemaColumn
# ─────────────────────────────────────────────────────────────────────────────


class SchemaColumnRow(Base):
    """Column 정의. fqn = '<table_fqn>.<column_name>'."""
    __tablename__ = "schema_columns"

    fqn:           Mapped[str] = mapped_column(String)
    table_fqn:     Mapped[str] = mapped_column(String, nullable=False)
    column_name:   Mapped[str] = mapped_column(String, nullable=False)
    data_type:     Mapped[str] = mapped_column(String, nullable=False)
    # PostgreSQL: 'VARCHAR(200)', 'NUMERIC(15,2)', 'INTEGER', 'TIMESTAMP', ...
    nullable:      Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description:   Mapped[str] = mapped_column(Text, nullable=False, default="")
    position:      Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    repo_id:       Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        PrimaryKeyConstraint("fqn", "repo_id"),
        Index("ix_schema_columns_repo_table", "repo_id", "table_fqn"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. SchemaConstraint
# ─────────────────────────────────────────────────────────────────────────────


class SchemaConstraintRow(Base):
    """UNIQUE / CHECK / NOT_NULL / FK / PK constraint."""
    __tablename__ = "schema_constraints"

    id:                       Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_fqn:                Mapped[str] = mapped_column(String, nullable=False)
    constraint_name:          Mapped[str] = mapped_column(String, nullable=False)
    kind:                     Mapped[str] = mapped_column(String, nullable=False)
    # kind: UNIQUE / CHECK / NOT_NULL / FK / PK

    columns_json:             Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 참여 column name list (JSON array)

    expression:               Mapped[str | None] = mapped_column(Text, nullable=True)
    # CHECK constraint 의 표현

    referenced_table_fqn:     Mapped[str | None] = mapped_column(String, nullable=True)
    referenced_columns_json:  Mapped[str | None] = mapped_column(Text, nullable=True)
    # FK case — 참조 table + column list

    repo_id:                  Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        UniqueConstraint("table_fqn", "constraint_name", "repo_id", name="uq_schema_constraint_name"),
        Index("ix_schema_constraints_repo_table", "repo_id", "table_fqn"),
        Index("ix_schema_constraints_kind", "repo_id", "kind"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. SchemaIndex
# ─────────────────────────────────────────────────────────────────────────────


class SchemaIndexRow(Base):
    """Index 정의 (BTREE / HASH / GIN 등)."""
    __tablename__ = "schema_indexes"

    id:                  Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_fqn:           Mapped[str] = mapped_column(String, nullable=False)
    index_name:          Mapped[str] = mapped_column(String, nullable=False)
    columns_json:        Mapped[str] = mapped_column(Text, nullable=False)
    # 참여 column list 의 순서 보존 (JSON array of {name, order: 'ASC'|'DESC'})

    is_unique:           Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kind:                Mapped[str] = mapped_column(String, nullable=False, default="BTREE")
    # BTREE / HASH / GIN / GIST / BRIN

    partial_expression:  Mapped[str | None] = mapped_column(Text, nullable=True)
    # partial index — WHERE expression

    repo_id:             Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        UniqueConstraint("table_fqn", "index_name", "repo_id", name="uq_schema_index_name"),
        Index("ix_schema_indexes_repo_table", "repo_id", "table_fqn"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. SchemaView
# ─────────────────────────────────────────────────────────────────────────────


class SchemaViewRow(Base):
    """VIEW 정의. fqn = '<schema_name>.<view_name>'."""
    __tablename__ = "schema_views"

    fqn:          Mapped[str] = mapped_column(String)
    view_name:    Mapped[str] = mapped_column(String, nullable=False)
    schema_name:  Mapped[str] = mapped_column(String, nullable=False, default="public")
    definition:   Mapped[str] = mapped_column(Text, nullable=False)
    # SELECT 표현 자체

    description:  Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_materialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    repo_id:      Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        PrimaryKeyConstraint("fqn", "repo_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. SchemaMigration
# ─────────────────────────────────────────────────────────────────────────────


class SchemaMigrationRow(Base):
    """DDL version 관리. ADR-004 §3.2 — additive only, rollback 가능."""
    __tablename__ = "schema_migrations"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    system:       Mapped[str] = mapped_column(String, nullable=False)
    # system: v2 / broadleaf / banking / sim_v2_core

    version:      Mapped[str] = mapped_column(String, nullable=False)
    # version: 'v1', 'v2', 'v1_initial_schema', 'v2_add_audit_table' etc.

    sha256:       Mapped[str] = mapped_column(String, nullable=False)
    # DDL content hash — drift detection

    applied_at:   Mapped[str] = mapped_column(String, nullable=False)
    # ISO-8601 datetime string. Plain string for SQLite portability

    rollback_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    # optional rollback DDL

    description:  Mapped[str] = mapped_column(Text, nullable=False, default="")

    repo_id:      Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        UniqueConstraint("system", "version", "repo_id", name="uq_schema_migration_version"),
        Index("ix_schema_migrations_system", "repo_id", "system"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. SchemaCodeMapping
# ─────────────────────────────────────────────────────────────────────────────


class SchemaCodeMappingRow(Base):
    """Schema ↔ Code 양방향 매핑.

    예: SchemaTable 'orders' ↔ CodeType 'com.example.Order' (JPA @Entity).
    Cross-layer query — spec.md §3.3 의 UC4 입력.
    """
    __tablename__ = "schema_code_mappings"

    id:                Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_table_fqn:  Mapped[str | None] = mapped_column(String, nullable=True)
    schema_column_fqn: Mapped[str | None] = mapped_column(String, nullable=True)
    # table-level 매핑 또는 column-level 매핑 — 하나는 필수

    code_type_fqn:     Mapped[str | None] = mapped_column(String, nullable=True)
    code_field_fqn:    Mapped[str | None] = mapped_column(String, nullable=True)
    code_method_fqn:   Mapped[str | None] = mapped_column(String, nullable=True)
    # code side — type / field / method 중 하나

    mapping_kind:      Mapped[str] = mapped_column(String, nullable=False, default="entity")
    # mapping_kind: entity / value_object / projection / view / repository_method

    confidence:        Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confirmed:         Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source:            Mapped[str] = mapped_column(String, nullable=False, default="jpa_annotation")

    repo_id:           Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        Index("ix_schema_code_mappings_schema_table", "repo_id", "schema_table_fqn"),
        Index("ix_schema_code_mappings_code_type", "repo_id", "code_type_fqn"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. SchemaDomainMapping
# ─────────────────────────────────────────────────────────────────────────────


class SchemaDomainMappingRow(Base):
    """Schema ↔ BusinessTerm 매핑.

    예: SchemaColumn 'orders.total_amount' ↔ BusinessTerm 'order.total_amount'.
    UC4 (스키마 추천) 의 cross-layer query 의 핵심 (spec.md §3.3).
    """
    __tablename__ = "schema_domain_mappings"

    id:                Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_table_fqn:  Mapped[str | None] = mapped_column(String, nullable=True)
    schema_column_fqn: Mapped[str | None] = mapped_column(String, nullable=True)
    # table-level 또는 column-level — 하나는 필수

    business_term_fqn: Mapped[str] = mapped_column(String, nullable=False)
    # BusinessTerm FK (modeling.domain_layer.business_terms.fqn)

    confidence:        Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confirmed:         Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source:            Mapped[str] = mapped_column(String, nullable=False, default="auto")
    # source: auto / name_match / user / llm

    repo_id:           Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    __table_args__ = (
        Index("ix_schema_domain_mappings_term", "repo_id", "business_term_fqn"),
        Index("ix_schema_domain_mappings_table", "repo_id", "schema_table_fqn"),
        Index("ix_schema_domain_mappings_column", "repo_id", "schema_column_fqn"),
    )


__all__ = [
    "SchemaTableRow",
    "SchemaColumnRow",
    "SchemaConstraintRow",
    "SchemaIndexRow",
    "SchemaViewRow",
    "SchemaMigrationRow",
    "SchemaCodeMappingRow",
    "SchemaDomainMappingRow",
]
