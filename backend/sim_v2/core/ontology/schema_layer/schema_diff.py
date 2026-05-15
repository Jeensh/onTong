"""W44 — diff two SchemaModels and surface drift.

Use case: a JPA-extracted schema (`model_b`) drifts from the previously-recorded
schema (`model_a`) because someone edited an `@Column(name=…)` annotation
without writing a corresponding DDL migration. The diff surfaces what's added /
removed / changed at the table and column level, so the framework can flag the
drift before it causes a runtime failure.

Public API:
    - SchemaDiff               — Pydantic, frozen, structured diff report
    - ColumnChange             — one column's data_type / nullable delta
    - compute_diff(a, b)       — pure function; order-independent
    - diff_is_empty(diff)      — convenience for the "no drift" check
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    SchemaColumnDef,
    SchemaModel,
    SchemaTableDef,
)


class ColumnChange(BaseModel):
    """A column whose data_type or nullable flag drifted between models."""
    model_config = ConfigDict(frozen=True)

    column_fqn:   str
    table_fqn:    str
    column_name:  str
    field:        Literal["data_type", "nullable"]
    before:       str
    after:        str


class SchemaDiff(BaseModel):
    """Structured drift report. Empty lists ⇒ no drift on that dimension."""
    model_config = ConfigDict(frozen=True)

    added_tables:    list[SchemaTableDef]  = Field(default_factory=list)
    removed_tables:  list[SchemaTableDef]  = Field(default_factory=list)
    added_columns:   list[SchemaColumnDef] = Field(default_factory=list)
    removed_columns: list[SchemaColumnDef] = Field(default_factory=list)
    changed_columns: list[ColumnChange]    = Field(default_factory=list)


def compute_diff(model_a: SchemaModel, model_b: SchemaModel) -> SchemaDiff:
    """Diff a→b. Order-independent (works off fqn keys).

    Tables and columns are matched by fqn. A column whose fqn exists in both
    but whose `data_type` or `nullable` flag differs counts as *changed*, not
    added/removed.
    """
    tables_a = {t.fqn: t for t in model_a.tables}
    tables_b = {t.fqn: t for t in model_b.tables}
    added_tables   = sorted([tables_b[f] for f in tables_b.keys() - tables_a.keys()],
                            key=lambda t: t.fqn)
    removed_tables = sorted([tables_a[f] for f in tables_a.keys() - tables_b.keys()],
                            key=lambda t: t.fqn)

    columns_a = {c.fqn: c for c in model_a.columns}
    columns_b = {c.fqn: c for c in model_b.columns}
    added_columns   = sorted([columns_b[f] for f in columns_b.keys() - columns_a.keys()],
                             key=lambda c: c.fqn)
    removed_columns = sorted([columns_a[f] for f in columns_a.keys() - columns_b.keys()],
                             key=lambda c: c.fqn)

    changed_columns: list[ColumnChange] = []
    for fqn in columns_a.keys() & columns_b.keys():
        a, b = columns_a[fqn], columns_b[fqn]
        if a.data_type != b.data_type:
            changed_columns.append(ColumnChange(
                column_fqn=fqn, table_fqn=a.table_fqn, column_name=a.column_name,
                field="data_type", before=a.data_type, after=b.data_type,
            ))
        if a.nullable != b.nullable:
            changed_columns.append(ColumnChange(
                column_fqn=fqn, table_fqn=a.table_fqn, column_name=a.column_name,
                field="nullable", before=str(a.nullable), after=str(b.nullable),
            ))
    changed_columns.sort(key=lambda ch: (ch.column_fqn, ch.field))

    return SchemaDiff(
        added_tables=added_tables,
        removed_tables=removed_tables,
        added_columns=added_columns,
        removed_columns=removed_columns,
        changed_columns=changed_columns,
    )


def diff_is_empty(diff: SchemaDiff) -> bool:
    return not (
        diff.added_tables
        or diff.removed_tables
        or diff.added_columns
        or diff.removed_columns
        or diff.changed_columns
    )


__all__ = ["ColumnChange", "SchemaDiff", "compute_diff", "diff_is_empty"]
