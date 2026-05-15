"""Cross-layer query API test — implementation-plan §3.1 B1.4."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.core.ontology.query import (
    find_business_terms_for_schema_column,
    find_code_types_for_schema_table,
    find_schema_columns_for_business_term,
    find_schema_tables_for_code_type,
    schema_coverage_for_repo,
    schema_tables_in_repo,
)
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaDomainMappingRow,
    SchemaTableRow,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        SchemaTableRow.__table__,
        SchemaColumnRow.__table__,
        SchemaCodeMappingRow.__table__,
        SchemaDomainMappingRow.__table__,
    ])
    with Session(engine) as s:
        yield s


@pytest.fixture
def populated_session(session: Session):
    """Seed: 2 tables (orders, customer) + columns + mappings, repo='banking'."""
    rows = [
        # tables
        SchemaTableRow(fqn="public.orders", table_name="orders", repo_id="banking"),
        SchemaTableRow(fqn="public.customer", table_name="customer", repo_id="banking"),
        # columns
        SchemaColumnRow(
            fqn="public.orders.id", table_fqn="public.orders",
            column_name="id", data_type="BIGINT", nullable=False, position=0, repo_id="banking",
        ),
        SchemaColumnRow(
            fqn="public.orders.total_amount", table_fqn="public.orders",
            column_name="total_amount", data_type="NUMERIC(15,2)", nullable=False, position=1, repo_id="banking",
        ),
        SchemaColumnRow(
            fqn="public.customer.email", table_fqn="public.customer",
            column_name="email", data_type="VARCHAR(200)", nullable=False, position=1, repo_id="banking",
        ),
        # domain mappings
        SchemaDomainMappingRow(
            schema_column_fqn="public.orders.total_amount",
            business_term_fqn="order.total_amount",
            confidence=0.95, confirmed=True, source="name_match", repo_id="banking",
        ),
        SchemaDomainMappingRow(
            schema_table_fqn="public.orders",
            business_term_fqn="order",
            confidence=1.0, confirmed=True, source="user", repo_id="banking",
        ),
        SchemaDomainMappingRow(
            schema_column_fqn="public.customer.email",
            business_term_fqn="customer.email",
            confidence=0.7, confirmed=False, source="auto", repo_id="banking",
        ),
        # code mappings
        SchemaCodeMappingRow(
            schema_table_fqn="public.orders",
            code_type_fqn="com.example.OrderImpl",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id="banking",
        ),
        SchemaCodeMappingRow(
            schema_column_fqn="public.orders.total_amount",
            code_field_fqn="com.example.OrderImpl#totalAmount",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id="banking",
        ),
        # cross-repo row (should NOT leak)
        SchemaTableRow(fqn="public.orders", table_name="orders", repo_id="broadleaf"),
    ]
    session.add_all(rows)
    session.commit()
    return session


# ─────────────────────────────────────────────────────────────────────────────
# find_schema_columns_for_business_term — UC4 핵심
# ─────────────────────────────────────────────────────────────────────────────


def test_term_to_column_basic(populated_session: Session):
    hits = find_schema_columns_for_business_term(
        populated_session, "order.total_amount", "banking"
    )
    assert len(hits) == 1
    assert hits[0].column_fqn == "public.orders.total_amount"
    assert hits[0].confirmed is True


def test_term_to_table_level_mapping(populated_session: Session):
    hits = find_schema_columns_for_business_term(populated_session, "order", "banking")
    assert len(hits) == 1
    assert hits[0].table_fqn == "public.orders"
    assert hits[0].column_fqn is None  # table-level


def test_term_to_column_confirmed_only(populated_session: Session):
    all_hits = find_schema_columns_for_business_term(
        populated_session, "customer.email", "banking", confirmed_only=False
    )
    assert len(all_hits) == 1

    confirmed_hits = find_schema_columns_for_business_term(
        populated_session, "customer.email", "banking", confirmed_only=True
    )
    assert len(confirmed_hits) == 0


def test_term_to_column_repo_isolation(populated_session: Session):
    # 'broadleaf' repo 의 orders table 에는 mapping 없음
    hits = find_schema_columns_for_business_term(
        populated_session, "order.total_amount", "broadleaf"
    )
    assert hits == []


# ─────────────────────────────────────────────────────────────────────────────
# find_business_terms_for_schema_column (reverse)
# ─────────────────────────────────────────────────────────────────────────────


def test_column_to_term(populated_session: Session):
    hits = find_business_terms_for_schema_column(
        populated_session, "public.orders.total_amount", "banking"
    )
    # column-level (order.total_amount) + table-level inherited (order)
    terms = {h.business_term_fqn for h in hits}
    assert "order.total_amount" in terms
    assert "order" in terms  # inherited from table-level mapping


def test_column_to_term_no_table_inherit_if_no_column_exists(populated_session: Session):
    hits = find_business_terms_for_schema_column(
        populated_session, "public.nonexistent.x", "banking"
    )
    assert hits == []


# ─────────────────────────────────────────────────────────────────────────────
# Code ↔ Schema
# ─────────────────────────────────────────────────────────────────────────────


def test_code_type_to_schema(populated_session: Session):
    hits = find_schema_tables_for_code_type(
        populated_session, "com.example.OrderImpl", "banking"
    )
    assert len(hits) == 1
    assert hits[0].schema_table_fqn == "public.orders"
    assert hits[0].mapping_kind == "entity"


def test_schema_table_to_code(populated_session: Session):
    hits = find_code_types_for_schema_table(
        populated_session, "public.orders", "banking"
    )
    assert len(hits) == 1
    assert hits[0].code_type_fqn == "com.example.OrderImpl"


def test_schema_table_to_code_confirmed_only(populated_session: Session):
    hits = find_code_types_for_schema_table(
        populated_session, "public.orders", "banking", confirmed_only=True
    )
    assert len(hits) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Coverage / utility
# ─────────────────────────────────────────────────────────────────────────────


def test_schema_tables_in_repo(populated_session: Session):
    tables = schema_tables_in_repo(populated_session, "banking")
    fqns = [t.fqn for t in tables]
    assert fqns == ["public.customer", "public.orders"]


def test_schema_tables_repo_isolation(populated_session: Session):
    bl_tables = schema_tables_in_repo(populated_session, "broadleaf")
    assert len(bl_tables) == 1


def test_coverage_stats(populated_session: Session):
    coverage = schema_coverage_for_repo(populated_session, "banking")
    assert coverage.table_count == 2
    assert coverage.column_count == 3
    assert coverage.domain_mapped_columns == 2  # total_amount + email
    assert coverage.code_mapped_columns == 1    # total_amount
    assert coverage.confirmed_domain_mappings == 1  # only total_amount confirmed at column level
    assert coverage.confirmed_code_mappings == 1


def test_coverage_empty_repo(session: Session):
    coverage = schema_coverage_for_repo(session, "empty")
    assert coverage.table_count == 0
    assert coverage.column_count == 0
