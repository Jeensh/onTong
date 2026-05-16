"""W44 — SchemaModel diff engine tests.

Drift detection between two SchemaModels — added/removed/changed at the table
and column level.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaColumnDef,
    SchemaModel,
    SchemaSource,
    SchemaTableDef,
)
from backend.sim_v2.core.ontology.schema_layer.schema_diff import (
    ColumnChange,
    SchemaDiff,
    compute_diff,
    diff_is_empty,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _entity(class_fqn, table_name, columns):
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
        SchemaSource(kind="jpa_annotation", payload=entities, repo_id="r")
    )


def _col(field_name, column_name, data_type="VARCHAR", nullable=True, pk=False):
    return {
        "field_name":  field_name,
        "column_name": column_name,
        "data_type":   data_type,
        "nullable":    nullable,
        "primary_key": pk,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Empty / no-op diff
# ─────────────────────────────────────────────────────────────────────────────


def test_diff_of_two_empty_models_is_empty():
    diff = compute_diff(SchemaModel(), SchemaModel())
    assert diff_is_empty(diff)
    assert isinstance(diff, SchemaDiff)


def test_diff_of_identical_models_is_empty():
    a = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    diff = compute_diff(a, a)
    assert diff_is_empty(diff)


# ─────────────────────────────────────────────────────────────────────────────
# Table-level adds/removes
# ─────────────────────────────────────────────────────────────────────────────


def test_added_table_surfaces_in_added_tables():
    a = _extract([])
    b = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    diff = compute_diff(a, b)
    assert len(diff.added_tables) == 1
    assert diff.added_tables[0].fqn == "public.ORDERS"
    assert len(diff.removed_tables) == 0


def test_removed_table_surfaces_in_removed_tables():
    a = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    b = _extract([])
    diff = compute_diff(a, b)
    assert len(diff.removed_tables) == 1
    assert diff.removed_tables[0].fqn == "public.ORDERS"
    assert len(diff.added_tables) == 0


def test_table_present_in_both_not_counted_as_added_or_removed():
    a = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    b = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    diff = compute_diff(a, b)
    assert len(diff.added_tables) == 0
    assert len(diff.removed_tables) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Column-level adds/removes/changes
# ─────────────────────────────────────────────────────────────────────────────


def test_added_column_surfaces():
    a = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    b = _extract([_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "BIGINT", False, True),
        _col("note", "NOTE", "VARCHAR", True, False),
    ])])
    diff = compute_diff(a, b)
    added = [c.fqn for c in diff.added_columns]
    assert added == ["public.ORDERS.NOTE"]


def test_removed_column_surfaces():
    a = _extract([_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "BIGINT", False, True),
        _col("legacy", "LEGACY", "VARCHAR", True, False),
    ])])
    b = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    diff = compute_diff(a, b)
    removed = [c.fqn for c in diff.removed_columns]
    assert removed == ["public.ORDERS.LEGACY"]


def test_data_type_change_surfaces_as_changed_column():
    a = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    b = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "VARCHAR", False, True)])])
    diff = compute_diff(a, b)
    assert len(diff.added_columns) == 0
    assert len(diff.removed_columns) == 0
    assert len(diff.changed_columns) == 1
    ch = diff.changed_columns[0]
    assert ch.field == "data_type"
    assert ch.before == "BIGINT"
    assert ch.after == "VARCHAR"
    assert ch.column_fqn == "public.ORDERS.ID"


def test_nullable_change_surfaces_as_changed_column():
    a = _extract([_entity("com.x.O", "ORDERS", [_col("a", "A", "VARCHAR", nullable=True)])])
    b = _extract([_entity("com.x.O", "ORDERS", [_col("a", "A", "VARCHAR", nullable=False)])])
    diff = compute_diff(a, b)
    nullable_changes = [c for c in diff.changed_columns if c.field == "nullable"]
    assert len(nullable_changes) == 1
    assert nullable_changes[0].before == "True"
    assert nullable_changes[0].after == "False"


def test_both_type_and_nullable_change_yield_two_entries():
    a = _extract([_entity("com.x.O", "ORDERS", [_col("a", "A", "INT", nullable=True)])])
    b = _extract([_entity("com.x.O", "ORDERS", [_col("a", "A", "BIGINT", nullable=False)])])
    diff = compute_diff(a, b)
    fields = {c.field for c in diff.changed_columns}
    assert fields == {"data_type", "nullable"}


# ─────────────────────────────────────────────────────────────────────────────
# Order independence
# ─────────────────────────────────────────────────────────────────────────────


def test_diff_is_stable_against_entity_order():
    e1 = _entity("com.x.A", "A", [_col("id", "ID", "BIGINT", False, True)])
    e2 = _entity("com.x.B", "B", [_col("id", "ID", "BIGINT", False, True)])
    diff1 = compute_diff(_extract([e1, e2]), _extract([e2, e1]))
    # Identical content in different order ⇒ no drift
    assert diff_is_empty(diff1)


def test_added_tables_sorted_by_fqn():
    a = _extract([])
    b = _extract([
        _entity("com.x.Z", "Z_TABLE", [_col("id", "ID", "BIGINT", False, True)]),
        _entity("com.x.A", "A_TABLE", [_col("id", "ID", "BIGINT", False, True)]),
    ])
    diff = compute_diff(a, b)
    fqns = [t.fqn for t in diff.added_tables]
    assert fqns == sorted(fqns), "added_tables must be sorted for deterministic reports"


# ─────────────────────────────────────────────────────────────────────────────
# Composite drift: tables + columns + changes in one diff
# ─────────────────────────────────────────────────────────────────────────────


def test_composite_drift_carries_all_categories():
    a = _extract([
        _entity("com.x.O", "ORDERS", [
            _col("id", "ID", "BIGINT", False, True),
            _col("amount", "AMOUNT", "DECIMAL", True, False),
        ]),
        _entity("com.x.L", "LEGACY", [_col("id", "ID", "BIGINT", False, True)]),
    ])
    b = _extract([
        _entity("com.x.O", "ORDERS", [
            _col("id", "ID", "VARCHAR", False, True),               # type change
            _col("note", "NOTE", "VARCHAR", True, False),           # added
        ]),
        _entity("com.x.N", "NEW_TABLE", [_col("id", "ID", "BIGINT", False, True)]),  # new table
        # LEGACY missing ⇒ removed
    ])
    diff = compute_diff(a, b)
    assert {t.fqn for t in diff.added_tables} == {"public.NEW_TABLE"}
    assert {t.fqn for t in diff.removed_tables} == {"public.LEGACY"}
    # Added column on ORDERS
    assert any(c.fqn == "public.ORDERS.NOTE" for c in diff.added_columns)
    # Removed column on ORDERS
    assert any(c.fqn == "public.ORDERS.AMOUNT" for c in diff.removed_columns)
    # Changed column on ORDERS
    assert any(c.column_fqn == "public.ORDERS.ID" and c.field == "data_type"
               for c in diff.changed_columns)


def test_diff_is_empty_helper_recognizes_any_kind_of_drift():
    """The helper must return False for each individual kind of drift."""
    base = _extract([_entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)])])
    plus_table = _extract([
        _entity("com.x.O", "ORDERS", [_col("id", "ID", "BIGINT", False, True)]),
        _entity("com.x.N", "NEW_TABLE", [_col("id", "ID", "BIGINT", False, True)]),
    ])
    assert not diff_is_empty(compute_diff(base, plus_table))
    assert not diff_is_empty(compute_diff(plus_table, base))

    plus_col = _extract([_entity("com.x.O", "ORDERS", [
        _col("id", "ID", "BIGINT", False, True),
        _col("note", "NOTE", "VARCHAR", True, False),
    ])])
    assert not diff_is_empty(compute_diff(base, plus_col))
