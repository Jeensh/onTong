"""W48 — drift → DDL migration recommender tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaModel,
    SchemaSource,
)
from backend.sim_v2.core.ontology.schema_layer.drift_migration_recommender import (
    DriftRecommendation,
    MigrationStatement,
    recommend,
)
from backend.sim_v2.core.ontology.schema_layer.schema_diff import compute_diff


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _entity(class_fqn, table_name, cols):
    return {
        "class_fqn":   class_fqn,
        "table_name":  table_name,
        "schema_name": "public",
        "columns":     cols,
        "indexes":     [],
        "fks":         [],
    }


def _col(field_name, column_name, data_type="VARCHAR", nullable=True, pk=False):
    return {
        "field_name":  field_name,
        "column_name": column_name,
        "data_type":   data_type,
        "nullable":    nullable,
        "primary_key": pk,
    }


def _extract(entities):
    return JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=entities, repo_id="r")
    )


def _diff(a, b):
    return compute_diff(_extract(a), _extract(b))


# ─────────────────────────────────────────────────────────────────────────────
# Empty diff
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_diff_yields_empty_recommendation():
    rec = recommend(compute_diff(SchemaModel(), SchemaModel()))
    assert isinstance(rec, DriftRecommendation)
    assert rec.statements == []
    assert rec.summary == "No drift detected."


# ─────────────────────────────────────────────────────────────────────────────
# Per-diff-kind DDL
# ─────────────────────────────────────────────────────────────────────────────


def test_added_table_yields_create_table_with_columns_inlined():
    a: list = []
    b = [_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "BIGINT", False, True),
        _col("amount", "AMOUNT", "DECIMAL", True, False),
    ])]
    rec = recommend(_diff(a, b))
    assert len(rec.statements) == 1
    s = rec.statements[0]
    assert s.kind == "CREATE_TABLE"
    assert "CREATE TABLE public.ORDERS" in s.ddl
    assert "ID BIGINT NOT NULL" in s.ddl
    assert "AMOUNT DECIMAL" in s.ddl
    assert s.target_fqn == "public.ORDERS"


def test_removed_table_yields_drop_table():
    a = [_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])]
    b: list = []
    rec = recommend(_diff(a, b))
    drop_stmts = [s for s in rec.statements if s.kind == "DROP_TABLE"]
    assert len(drop_stmts) == 1
    assert "DROP TABLE public.ORDERS" in drop_stmts[0].ddl


def test_added_column_yields_add_column_on_existing_table():
    a = [_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])]
    b = [_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "BIGINT", False, True),
        _col("note", "NOTE", "VARCHAR", True, False),
    ])]
    rec = recommend(_diff(a, b))
    add_stmts = [s for s in rec.statements if s.kind == "ADD_COLUMN"]
    assert len(add_stmts) == 1
    assert "ALTER TABLE public.ORDERS ADD COLUMN NOTE VARCHAR" in add_stmts[0].ddl


def test_removed_column_yields_drop_column():
    a = [_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "BIGINT", False, True),
        _col("legacy", "LEGACY", "VARCHAR", True, False),
    ])]
    b = [_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])]
    rec = recommend(_diff(a, b))
    drop_stmts = [s for s in rec.statements if s.kind == "DROP_COLUMN"]
    assert len(drop_stmts) == 1
    assert "ALTER TABLE public.ORDERS DROP COLUMN LEGACY" in drop_stmts[0].ddl


def test_type_change_yields_alter_type():
    a = [_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])]
    b = [_entity("com.x.O", "ORDERS", [_col("id", "ID", "VARCHAR", False, True)])]
    rec = recommend(_diff(a, b))
    alter_stmts = [s for s in rec.statements if s.kind == "ALTER_TYPE"]
    assert len(alter_stmts) == 1
    assert (
        "ALTER TABLE public.ORDERS ALTER COLUMN ID TYPE VARCHAR"
        in alter_stmts[0].ddl
    )


def test_nullable_to_not_null_yields_set_not_null():
    a = [_entity("com.x.O", "ORDERS", [_col("amount", "AMOUNT", "DECIMAL", nullable=True)])]
    b = [_entity("com.x.O", "ORDERS", [_col("amount", "AMOUNT", "DECIMAL", nullable=False)])]
    rec = recommend(_diff(a, b))
    set_stmts = [s for s in rec.statements if s.kind == "SET_NOT_NULL"]
    assert len(set_stmts) == 1
    assert "SET NOT NULL" in set_stmts[0].ddl


def test_not_null_to_nullable_yields_drop_not_null():
    a = [_entity("com.x.O", "ORDERS", [_col("amount", "AMOUNT", "DECIMAL", nullable=False)])]
    b = [_entity("com.x.O", "ORDERS", [_col("amount", "AMOUNT", "DECIMAL", nullable=True)])]
    rec = recommend(_diff(a, b))
    drop_stmts = [s for s in rec.statements if s.kind == "DROP_NOT_NULL"]
    assert len(drop_stmts) == 1
    assert "DROP NOT NULL" in drop_stmts[0].ddl


# ─────────────────────────────────────────────────────────────────────────────
# Ordering — safe-by-default execution sequence
# ─────────────────────────────────────────────────────────────────────────────


def test_recommendation_orders_create_before_alter_before_drop():
    """When a single diff combines CREATE / ADD / ALTER / DROP, the recommendation
    orders them: CREATE → ADD → ALTER_TYPE → SET/DROP_NOT_NULL → DROP_COLUMN → DROP_TABLE."""
    a = [
        _entity("com.x.A", "A", [
            _col("id", "ID", "INT", False, True),
            _col("legacy", "LEGACY", "VARCHAR", True, False),
        ]),
        _entity("com.x.L", "L", [_col("id", "ID", "INT", False, True)]),
    ]
    b = [
        _entity("com.x.A", "A", [
            _col("id", "ID", "BIGINT", False, True),     # type change
            _col("note", "NOTE", "VARCHAR", True, False),  # added column
        ]),
        _entity("com.x.N", "N", [_col("id", "ID", "INT", False, True)]),  # added table
        # L removed → removed_table
    ]
    rec = recommend(_diff(a, b))
    kinds = [s.kind for s in rec.statements]
    # CREATE_TABLE must precede everything else
    assert kinds.index("CREATE_TABLE") == 0
    # DROP_COLUMN before DROP_TABLE
    drop_col_idx = next((i for i, k in enumerate(kinds) if k == "DROP_COLUMN"), None)
    drop_tbl_idx = next((i for i, k in enumerate(kinds) if k == "DROP_TABLE"), None)
    if drop_col_idx is not None and drop_tbl_idx is not None:
        assert drop_col_idx < drop_tbl_idx
    # ALTER_TYPE before DROP_COLUMN
    alter_idx = next((i for i, k in enumerate(kinds) if k == "ALTER_TYPE"), None)
    if alter_idx is not None and drop_col_idx is not None:
        assert alter_idx < drop_col_idx


# ─────────────────────────────────────────────────────────────────────────────
# DROP_COLUMN skipped when its table is also dropped
# ─────────────────────────────────────────────────────────────────────────────


def test_drop_table_skips_drop_column_for_same_table():
    """When a table is removed, individual DROP COLUMN statements for it are
    redundant — DROP TABLE handles it."""
    a = [_entity("com.x.L", "L", [
        _col("a", "A", "INT", False, True),
        _col("b", "B", "VARCHAR", True, False),
    ])]
    b: list = []
    rec = recommend(_diff(a, b))
    drop_col_stmts = [s for s in rec.statements if s.kind == "DROP_COLUMN"]
    assert len(drop_col_stmts) == 0  # all rolled into the DROP TABLE
    drop_tbl_stmts = [s for s in rec.statements if s.kind == "DROP_TABLE"]
    assert len(drop_tbl_stmts) == 1


def test_create_table_rolls_in_new_columns_no_separate_add_column():
    """When a table is being added, its columns should be inlined in the
    CREATE TABLE, not duplicated as ADD COLUMN."""
    a: list = []
    b = [_entity("com.x.N", "N", [
        _col("id", "ID", "INT", False, True),
        _col("x", "X", "VARCHAR", True, False),
    ])]
    rec = recommend(_diff(a, b))
    add_col_stmts = [s for s in rec.statements if s.kind == "ADD_COLUMN"]
    assert len(add_col_stmts) == 0
    create_stmts = [s for s in rec.statements if s.kind == "CREATE_TABLE"]
    assert len(create_stmts) == 1
    # Both columns inlined
    assert "ID INT" in create_stmts[0].ddl
    assert "X VARCHAR" in create_stmts[0].ddl


# ─────────────────────────────────────────────────────────────────────────────
# Rationale + structure
# ─────────────────────────────────────────────────────────────────────────────


def test_every_statement_has_rationale_and_target_fqn():
    a = [_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])]
    b = [_entity("com.x.O", "ORDERS", [_col("id", "ID", "VARCHAR", False, True)])]
    rec = recommend(_diff(a, b))
    for s in rec.statements:
        assert s.rationale
        assert s.target_fqn


def test_summary_describes_drift_kinds():
    a = [_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "INT", False, True),
        _col("legacy", "LEGACY", "VARCHAR", True, False),
    ])]
    b = [_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "BIGINT", False, True),
        _col("note", "NOTE", "VARCHAR", True, False),
    ])]
    rec = recommend(_diff(a, b))
    assert "added column" in rec.summary
    assert "dropped column" in rec.summary
    assert "changed column" in rec.summary


def test_migration_statement_is_frozen():
    s = MigrationStatement(
        kind="ADD_COLUMN", ddl="ALTER X ADD …",
        target_fqn="public.X.Y", rationale="…",
    )
    with pytest.raises(Exception):
        s.kind = "DROP_TABLE"  # type: ignore[misc]
