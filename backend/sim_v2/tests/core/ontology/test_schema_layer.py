"""Schema Layer ORM 8 model 의 smoke test.

ADR-004 + implementation-plan.md §3.1 Task B1.1 acceptance:
- 8 ORM class import 성공
- pytest PASS
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaColumnRow,
    SchemaCodeMappingRow,
    SchemaConstraintRow,
    SchemaDomainMappingRow,
    SchemaIndexRow,
    SchemaMigrationRow,
    SchemaTableRow,
    SchemaViewRow,
)


@pytest.fixture
def in_memory_session():
    """SQLite in-memory engine with all Schema Layer tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        SchemaTableRow.__table__,
        SchemaColumnRow.__table__,
        SchemaConstraintRow.__table__,
        SchemaIndexRow.__table__,
        SchemaViewRow.__table__,
        SchemaMigrationRow.__table__,
        SchemaCodeMappingRow.__table__,
        SchemaDomainMappingRow.__table__,
    ])
    with Session(engine) as session:
        yield session


def test_imports_all_eight_models():
    """All 8 ORM classes import 가능."""
    models = [
        SchemaTableRow,
        SchemaColumnRow,
        SchemaConstraintRow,
        SchemaIndexRow,
        SchemaViewRow,
        SchemaMigrationRow,
        SchemaCodeMappingRow,
        SchemaDomainMappingRow,
    ]
    assert len(models) == 8
    for model in models:
        assert model.__tablename__.startswith("schema_")


def test_schema_table_insert(in_memory_session: Session):
    row = SchemaTableRow(
        fqn="public.orders",
        table_name="orders",
        schema_name="public",
        description="주문 root entity",
        source="jpa_annotation",
        repo_id="banking",
    )
    in_memory_session.add(row)
    in_memory_session.commit()

    fetched = in_memory_session.get(SchemaTableRow, ("public.orders", "banking"))
    assert fetched is not None
    assert fetched.table_name == "orders"


def test_schema_column_with_table_fqn(in_memory_session: Session):
    table = SchemaTableRow(fqn="public.orders", table_name="orders", repo_id="banking")
    col = SchemaColumnRow(
        fqn="public.orders.total_amount",
        table_fqn="public.orders",
        column_name="total_amount",
        data_type="NUMERIC(15,2)",
        nullable=False,
        position=5,
        repo_id="banking",
    )
    in_memory_session.add_all([table, col])
    in_memory_session.commit()

    fetched = in_memory_session.get(SchemaColumnRow, ("public.orders.total_amount", "banking"))
    assert fetched is not None
    assert fetched.data_type == "NUMERIC(15,2)"
    assert fetched.nullable is False


def test_schema_constraint_fk(in_memory_session: Session):
    constraint = SchemaConstraintRow(
        table_fqn="public.application",
        constraint_name="fk_application_applicant",
        kind="FK",
        columns_json=json.dumps(["applicant_id"]),
        referenced_table_fqn="public.applicant",
        referenced_columns_json=json.dumps(["id"]),
        repo_id="banking",
    )
    in_memory_session.add(constraint)
    in_memory_session.commit()

    fetched = (
        in_memory_session.query(SchemaConstraintRow)
        .filter_by(constraint_name="fk_application_applicant", repo_id="banking")
        .one()
    )
    assert fetched.kind == "FK"
    assert json.loads(fetched.columns_json) == ["applicant_id"]


def test_schema_index_unique(in_memory_session: Session):
    idx = SchemaIndexRow(
        table_fqn="public.application",
        index_name="idx_application_status",
        columns_json=json.dumps([
            {"name": "tenant_id", "order": "ASC"},
            {"name": "status", "order": "ASC"},
        ]),
        is_unique=False,
        kind="BTREE",
        repo_id="banking",
    )
    in_memory_session.add(idx)
    in_memory_session.commit()

    fetched = (
        in_memory_session.query(SchemaIndexRow)
        .filter_by(index_name="idx_application_status", repo_id="banking")
        .one()
    )
    assert fetched.is_unique is False
    cols = json.loads(fetched.columns_json)
    assert cols[0]["name"] == "tenant_id"


def test_schema_view(in_memory_session: Session):
    view = SchemaViewRow(
        fqn="public.active_loans",
        view_name="active_loans",
        definition="SELECT * FROM loan WHERE status = 'ACTIVE'",
        is_materialized=False,
        repo_id="banking",
    )
    in_memory_session.add(view)
    in_memory_session.commit()

    fetched = in_memory_session.get(SchemaViewRow, ("public.active_loans", "banking"))
    assert fetched is not None
    assert "ACTIVE" in fetched.definition


def test_schema_migration_version_unique(in_memory_session: Session):
    m1 = SchemaMigrationRow(
        system="banking",
        version="v1_initial",
        sha256="abc123",
        applied_at="2026-05-13T01:00:00Z",
        repo_id="banking",
    )
    in_memory_session.add(m1)
    in_memory_session.commit()

    # Duplicate (system, version, repo_id) → UniqueConstraint violation
    m1_dup = SchemaMigrationRow(
        system="banking",
        version="v1_initial",
        sha256="different_hash",
        applied_at="2026-05-13T02:00:00Z",
        repo_id="banking",
    )
    in_memory_session.add(m1_dup)
    with pytest.raises(Exception):
        in_memory_session.commit()


def test_schema_code_mapping(in_memory_session: Session):
    mapping = SchemaCodeMappingRow(
        schema_table_fqn="public.orders",
        code_type_fqn="com.example.OrderEntity",
        mapping_kind="entity",
        confidence=1.0,
        confirmed=True,
        source="jpa_annotation",
        repo_id="broadleaf",
    )
    in_memory_session.add(mapping)
    in_memory_session.commit()

    fetched = (
        in_memory_session.query(SchemaCodeMappingRow)
        .filter_by(schema_table_fqn="public.orders", repo_id="broadleaf")
        .one()
    )
    assert fetched.code_type_fqn == "com.example.OrderEntity"
    assert fetched.confirmed is True


def test_schema_domain_mapping_column_level(in_memory_session: Session):
    mapping = SchemaDomainMappingRow(
        schema_column_fqn="public.orders.total_amount",
        business_term_fqn="order.total_amount",
        confidence=0.95,
        confirmed=False,
        source="name_match",
        repo_id="broadleaf",
    )
    in_memory_session.add(mapping)
    in_memory_session.commit()

    fetched = (
        in_memory_session.query(SchemaDomainMappingRow)
        .filter_by(business_term_fqn="order.total_amount", repo_id="broadleaf")
        .one()
    )
    assert fetched.schema_column_fqn == "public.orders.total_amount"
    assert fetched.schema_table_fqn is None  # column-level only
    assert fetched.confirmed is False


def test_repo_id_isolation(in_memory_session: Session):
    """동일 fqn 의 row 가 서로 다른 repo_id 에서 공존."""
    t1 = SchemaTableRow(fqn="public.orders", table_name="orders", repo_id="broadleaf")
    t2 = SchemaTableRow(fqn="public.orders", table_name="orders", repo_id="banking")
    in_memory_session.add_all([t1, t2])
    in_memory_session.commit()

    rows = in_memory_session.query(SchemaTableRow).filter_by(fqn="public.orders").all()
    assert len(rows) == 2
    repo_ids = {r.repo_id for r in rows}
    assert repo_ids == {"broadleaf", "banking"}
