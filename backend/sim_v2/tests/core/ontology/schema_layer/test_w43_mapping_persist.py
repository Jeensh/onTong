"""W43 — code↔schema mapping emission + persistence tests.

Two layers tested:
1. `JpaAnnotationExtractor.extract()` now emits `code_mappings` alongside the
   existing tables/columns/constraints/indexes.
2. `persist_schema_model()` writes a SchemaModel into the ORM and is idempotent
   per (repo_id).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaCodeMappingDef,
    SchemaModel,
    SchemaSource,
)
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaConstraintRow,
    SchemaIndexRow,
    SchemaTableRow,
)
from backend.sim_v2.core.ontology.schema_layer.persistence import (
    PersistCounts,
    persist_schema_model,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mapping emission — JpaAnnotationExtractor
# ─────────────────────────────────────────────────────────────────────────────


def _make_entity(class_fqn, table_name, columns):
    return {
        "class_fqn":   class_fqn,
        "table_name":  table_name,
        "schema_name": "public",
        "columns":     columns,
        "indexes":     [],
        "fks":         [],
    }


def _extract(entities):
    return JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=entities, repo_id="test")
    )


def test_extractor_emits_entity_level_mapping():
    """Every `@Entity + @Table` produces a code_type → schema_table mapping."""
    model = _extract([_make_entity("com.x.Order", "ORDERS", [])])
    type_mappings = [m for m in model.code_mappings if m.code_type_fqn]
    assert len(type_mappings) == 1
    m = type_mappings[0]
    assert m.code_type_fqn == "com.x.Order"
    assert m.schema_table_fqn == "public.ORDERS"
    assert m.code_field_fqn is None
    assert m.schema_column_fqn is None
    assert m.mapping_kind == "entity"
    assert m.confidence == 1.0


def test_extractor_emits_field_level_mapping_for_each_column():
    model = _extract([_make_entity("com.x.Order", "ORDERS", [
        {"field_name": "id", "column_name": "ORDER_ID",
         "data_type": "BIGINT", "nullable": False, "primary_key": True},
        {"field_name": "amount", "column_name": "AMOUNT",
         "data_type": "DECIMAL", "nullable": True, "primary_key": False},
    ])])
    field_mappings = [m for m in model.code_mappings if m.code_field_fqn]
    assert len(field_mappings) == 2
    by_field = {m.code_field_fqn: m for m in field_mappings}
    assert "com.x.Order.id" in by_field
    assert by_field["com.x.Order.id"].schema_column_fqn == "public.ORDERS.ORDER_ID"
    assert "com.x.Order.amount" in by_field
    assert by_field["com.x.Order.amount"].schema_column_fqn == "public.ORDERS.AMOUNT"


def test_pk_field_mapping_has_higher_confidence_than_non_pk():
    """@Id-marked fields are unambiguous mappings (confidence 1.0); non-PK
    fields rely on @Column(name=…) name only (confidence 0.95)."""
    model = _extract([_make_entity("com.x.Order", "ORDERS", [
        {"field_name": "id", "column_name": "ORDER_ID",
         "data_type": "BIGINT", "nullable": False, "primary_key": True},
        {"field_name": "amount", "column_name": "AMOUNT",
         "data_type": "DECIMAL", "nullable": True, "primary_key": False},
    ])])
    by_field = {m.code_field_fqn: m for m in model.code_mappings if m.code_field_fqn}
    assert by_field["com.x.Order.id"].confidence == 1.0
    assert by_field["com.x.Order.amount"].confidence == 0.95


def test_extractor_skips_field_mapping_when_no_field_name():
    """A column dict lacking `field_name` (rare, but possible with DDL-only
    extraction) shouldn't produce a field mapping — keep it column-anchored."""
    model = _extract([_make_entity("com.x.Order", "ORDERS", [
        {"column_name": "AUDIT_TS", "data_type": "TIMESTAMP",
         "nullable": True, "primary_key": False},
    ])])
    field_mappings = [m for m in model.code_mappings if m.code_field_fqn]
    assert len(field_mappings) == 0


def test_extractor_skips_entity_mapping_when_no_class_fqn():
    """A pure-DDL entity dict without `class_fqn` shouldn't produce a type mapping."""
    e = _make_entity("ignored", "ORDERS", [])
    del e["class_fqn"]
    model = _extract([e])
    assert all(m.code_type_fqn is None for m in model.code_mappings)


def test_extractor_mapping_counts_scale_with_entity_count():
    """N entities × M columns → N type mappings + (N*M) field mappings."""
    entities = []
    for i in range(3):
        entities.append(_make_entity(
            f"com.x.Order{i}", f"ORDERS_{i}",
            [
                {"field_name": "id", "column_name": "ID",
                 "data_type": "BIGINT", "nullable": False, "primary_key": True},
                {"field_name": "x", "column_name": "X",
                 "data_type": "VARCHAR", "nullable": True, "primary_key": False},
            ],
        ))
    model = _extract(entities)
    type_count = sum(1 for m in model.code_mappings if m.code_type_fqn)
    field_count = sum(1 for m in model.code_mappings if m.code_field_fqn)
    assert type_count == 3
    assert field_count == 6


# ─────────────────────────────────────────────────────────────────────────────
# persist_schema_model — round-trip with in-memory DB
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def scratch_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _sample_model() -> SchemaModel:
    return _extract([_make_entity("com.x.Order", "ORDERS", [
        {"field_name": "id", "column_name": "ORDER_ID",
         "data_type": "BIGINT", "nullable": False, "primary_key": True},
        {"field_name": "amount", "column_name": "AMOUNT",
         "data_type": "DECIMAL", "nullable": True, "primary_key": False},
    ])])


def test_persist_returns_counts_matching_model(scratch_session):
    model = _sample_model()
    counts = persist_schema_model(model, scratch_session, "repo1")
    assert isinstance(counts, PersistCounts)
    assert counts.tables == len(model.tables)
    assert counts.columns == len(model.columns)
    assert counts.constraints == len(model.constraints)
    assert counts.code_mappings == len(model.code_mappings)


def test_persist_round_trip_tables(scratch_session):
    persist_schema_model(_sample_model(), scratch_session, "repo1")
    scratch_session.commit()
    rows = scratch_session.query(SchemaTableRow).filter_by(repo_id="repo1").all()
    assert len(rows) == 1
    assert rows[0].fqn == "public.ORDERS"
    assert rows[0].table_name == "ORDERS"


def test_persist_round_trip_columns_with_nullable_flag(scratch_session):
    persist_schema_model(_sample_model(), scratch_session, "repo1")
    scratch_session.commit()
    cols = scratch_session.query(SchemaColumnRow).filter_by(repo_id="repo1").all()
    by_name = {c.column_name: c for c in cols}
    assert by_name["ORDER_ID"].nullable is False
    assert by_name["AMOUNT"].nullable is True
    assert by_name["ORDER_ID"].data_type == "BIGINT"


def test_persist_round_trip_code_mappings(scratch_session):
    persist_schema_model(_sample_model(), scratch_session, "repo1")
    scratch_session.commit()
    type_maps = scratch_session.query(SchemaCodeMappingRow).filter(
        SchemaCodeMappingRow.repo_id == "repo1",
        SchemaCodeMappingRow.code_type_fqn.isnot(None),
    ).all()
    field_maps = scratch_session.query(SchemaCodeMappingRow).filter(
        SchemaCodeMappingRow.repo_id == "repo1",
        SchemaCodeMappingRow.code_field_fqn.isnot(None),
    ).all()
    assert len(type_maps) == 1
    assert type_maps[0].code_type_fqn == "com.x.Order"
    assert type_maps[0].schema_table_fqn == "public.ORDERS"
    assert len(field_maps) == 2
    # PK mapping should be confidence 1.0; non-PK should be 0.95
    by_field = {m.code_field_fqn: m for m in field_maps}
    assert by_field["com.x.Order.id"].confidence == 1.0
    assert by_field["com.x.Order.amount"].confidence == 0.95


def test_persist_constraints_round_trip(scratch_session):
    persist_schema_model(_sample_model(), scratch_session, "repo1")
    scratch_session.commit()
    cons_rows = scratch_session.query(SchemaConstraintRow).filter_by(repo_id="repo1").all()
    kinds = {r.kind for r in cons_rows}
    assert "PK" in kinds
    assert "NOT_NULL" in kinds


def test_persist_is_idempotent_per_repo(scratch_session):
    """Re-running persist for the same repo_id should not double rows."""
    persist_schema_model(_sample_model(), scratch_session, "repo1")
    persist_schema_model(_sample_model(), scratch_session, "repo1")
    scratch_session.commit()
    tables = scratch_session.query(SchemaTableRow).filter_by(repo_id="repo1").count()
    cols = scratch_session.query(SchemaColumnRow).filter_by(repo_id="repo1").count()
    maps = scratch_session.query(SchemaCodeMappingRow).filter_by(repo_id="repo1").count()
    assert tables == 1
    assert cols == 2
    assert maps == 3  # 1 type mapping + 2 field mappings


def test_persist_repo_id_isolation(scratch_session):
    """Persisting under repo A must not delete repo B's rows."""
    persist_schema_model(_sample_model(), scratch_session, "repoA")
    persist_schema_model(_sample_model(), scratch_session, "repoB")
    scratch_session.commit()
    a_count = scratch_session.query(SchemaTableRow).filter_by(repo_id="repoA").count()
    b_count = scratch_session.query(SchemaTableRow).filter_by(repo_id="repoB").count()
    assert a_count == 1
    assert b_count == 1
    # Now re-persist repoA — repoB must be untouched
    persist_schema_model(_sample_model(), scratch_session, "repoA")
    scratch_session.commit()
    assert scratch_session.query(SchemaTableRow).filter_by(repo_id="repoA").count() == 1
    assert scratch_session.query(SchemaTableRow).filter_by(repo_id="repoB").count() == 1


def test_persist_empty_model_is_no_op(scratch_session):
    counts = persist_schema_model(SchemaModel(), scratch_session, "empty")
    scratch_session.commit()
    assert counts.tables == 0
    assert counts.columns == 0
    assert counts.code_mappings == 0
    assert scratch_session.query(SchemaTableRow).filter_by(repo_id="empty").count() == 0
