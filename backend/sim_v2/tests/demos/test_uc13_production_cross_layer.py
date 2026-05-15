"""UC13 — Production cross-layer demo verification — W43.3.

Validates: production DB → loader → extractor (with mappings) → persist →
cross-layer query. Skips cleanly if production DB missing.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc13_production_cross_layer.run import (
    CrossLayerReport,
    DEFAULT_REPOS,
    build_scratch_schema_db_for_repo,
    find_code_type_for_schema_table,
    find_schema_column_for_code_field,
    find_schema_table_for_code_type,
    main,
    run_cross_layer_survey_for_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


@pytest.fixture
def scratch_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    """main() must exit 0 even when production DB absent."""
    from backend.sim_v2.demos.uc13_production_cross_layer import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Persistence + survey
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_build_scratch_db_persists_tables_and_mappings(scratch_session):
    prod = open_readonly_session()
    try:
        entities, model, counts = build_scratch_schema_db_for_repo(
            prod, scratch_session, "slab-design-real",
        )
        assert counts.tables > 0
        assert counts.columns > 0
        assert counts.code_mappings > 0
        # Mappings count = entities (type→table) + sum of columns (field→column)
        expected_min = len(entities) + sum(len(e["columns"]) for e in entities)
        assert counts.code_mappings >= expected_min - 5  # tolerate field_name-less rows
    finally:
        prod.close()


@requires_production_db
def test_survey_report_has_sample_cross_layer_resolutions(scratch_session):
    prod = open_readonly_session()
    try:
        report = run_cross_layer_survey_for_repo(
            prod, scratch_session, "slab-design-real",
        )
        assert isinstance(report, CrossLayerReport)
        assert report.persisted_tables > 0
        assert report.sample_code_type is not None
        assert report.sample_schema_table is not None
        assert report.sample_code_field is not None
        assert report.sample_schema_column is not None
        # Sample resolutions should be internally consistent
        assert report.sample_schema_table.startswith("public.")
        assert report.sample_schema_column.startswith(report.sample_schema_table + ".")
    finally:
        prod.close()


# ─────────────────────────────────────────────────────────────────────────────
# Cross-layer query primitives — fixture-backed
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_find_schema_table_for_code_type_resolves(scratch_session):
    prod = open_readonly_session()
    try:
        entities, _model, _ = build_scratch_schema_db_for_repo(
            prod, scratch_session, "slab-design-real",
        )
        type_fqn = entities[0]["class_fqn"]
        row = find_schema_table_for_code_type(
            scratch_session, type_fqn, "slab-design-real",
        )
        assert row is not None
        assert row.fqn.startswith("public.")
    finally:
        prod.close()


@requires_production_db
def test_find_schema_column_for_code_field_resolves(scratch_session):
    prod = open_readonly_session()
    try:
        entities, _model, _ = build_scratch_schema_db_for_repo(
            prod, scratch_session, "slab-design-real",
        )
        # Pick the first PK field
        e = next(e for e in entities if e["columns"])
        col_dict = next(c for c in e["columns"] if c["primary_key"])
        field_fqn = f"{e['class_fqn']}.{col_dict['field_name']}"
        row = find_schema_column_for_code_field(
            scratch_session, field_fqn, "slab-design-real",
        )
        assert row is not None
        assert row.column_name == col_dict["column_name"]
    finally:
        prod.close()


@requires_production_db
def test_find_code_type_for_schema_table_resolves(scratch_session):
    prod = open_readonly_session()
    try:
        entities, _model, _ = build_scratch_schema_db_for_repo(
            prod, scratch_session, "slab-design-real",
        )
        e = entities[0]
        schema_table_fqn = f"{e.get('schema_name', 'public')}.{e['table_name']}"
        code_type = find_code_type_for_schema_table(
            scratch_session, schema_table_fqn, "slab-design-real",
        )
        # Many production rows map *multiple* classes to the same physical table
        # (synthetic copies, inheritance). The query returns the first such
        # class — assert it's a real, non-empty class FQN.
        assert code_type is not None
        assert code_type.endswith("Jpo") or "." in code_type
    finally:
        prod.close()


@requires_production_db
def test_query_returns_none_for_unknown_fqn(scratch_session):
    """Unknown FQNs must return None rather than raising."""
    prod = open_readonly_session()
    try:
        build_scratch_schema_db_for_repo(prod, scratch_session, "slab-design-real")
        assert find_schema_table_for_code_type(
            scratch_session, "com.unknown.X", "slab-design-real",
        ) is None
        assert find_schema_column_for_code_field(
            scratch_session, "com.unknown.X.y", "slab-design-real",
        ) is None
        assert find_code_type_for_schema_table(
            scratch_session, "public.UNKNOWN_TABLE", "slab-design-real",
        ) is None
    finally:
        prod.close()


# ─────────────────────────────────────────────────────────────────────────────
# Multi-class → single-table case (synthetic copies)
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_synthetic_5k_has_multiple_classes_per_physical_table(scratch_session):
    """The synthetic-5k repo is built from 41 synthetic prefix copies of the
    same 14 entities. Each unique physical table should therefore have many
    code-mapping rows (one per class copy) even though the schema rows are
    de-duped to the physical count.
    """
    prod = open_readonly_session()
    try:
        _entities, _model, counts = build_scratch_schema_db_for_repo(
            prod, scratch_session, "synthetic-5k",
        )
        # 14 distinct physical tables
        assert counts.tables < 50
        # Many more mappings — every synthetic class copy produces one row
        assert counts.code_mappings > counts.tables * 100
    finally:
        prod.close()
