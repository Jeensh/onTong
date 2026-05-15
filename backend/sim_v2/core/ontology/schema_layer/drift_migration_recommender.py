"""W48 — rule-based drift → DDL migration recommender.

Pairs with `schema_diff.py` (W44): given a `SchemaDiff`, produce a structured
`DriftRecommendation` carrying DDL statements that would bring the database
into agreement with the JPA-declared schema.

Deterministic, no LLM dependency — the heuristics map 1:1 to diff entries:
    added_table       → CREATE TABLE
    removed_table     → DROP TABLE
    added_column      → ALTER TABLE … ADD COLUMN
    removed_column    → ALTER TABLE … DROP COLUMN
    changed_column    → ALTER TABLE … ALTER COLUMN … TYPE …
                        or ALTER TABLE … ALTER COLUMN … SET/DROP NOT NULL

For each statement we emit a `MigrationStatement` carrying both the DDL and a
short rationale, so an operator can read the rec without external context.

DDL flavor: PostgreSQL-style. Caller can adapt for other dialects later (SQL
construction is identical across Oracle / MySQL for the core operations the
diff produces).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    SchemaColumnDef,
    SchemaTableDef,
)
from backend.sim_v2.core.ontology.schema_layer.schema_diff import (
    ColumnChange,
    SchemaDiff,
    diff_is_empty,
)


MigrationKind = Literal[
    "CREATE_TABLE",
    "DROP_TABLE",
    "ADD_COLUMN",
    "DROP_COLUMN",
    "ALTER_TYPE",
    "SET_NOT_NULL",
    "DROP_NOT_NULL",
]


class MigrationStatement(BaseModel):
    """One executable DDL statement plus the diff context that motivated it."""
    model_config = ConfigDict(frozen=True)

    kind:        MigrationKind
    ddl:         str
    target_fqn:  str   # table_fqn or column_fqn the statement acts on
    rationale:   str


class DriftRecommendation(BaseModel):
    """All statements needed to close the drift, in deterministic order."""
    model_config = ConfigDict(frozen=True)

    statements:  list[MigrationStatement] = Field(default_factory=list)
    summary:     str = ""


def recommend(diff: SchemaDiff) -> DriftRecommendation:
    """Produce a deterministic migration recommendation for `diff`.

    Statement order (chosen to be safe-by-default for execution):
        1. CREATE TABLE       — new tables first; their columns can then be ADD'd
                                in a single CREATE; existing-table ADD COLUMN's follow
        2. ADD COLUMN         — additive, safe under concurrent reads
        3. ALTER TYPE         — destructive, but precedes column drops
        4. SET / DROP NOT NULL — order-independent, fits with type changes
        5. DROP COLUMN        — destructive, near end
        6. DROP TABLE         — most destructive, last

    Empty diff ⇒ empty recommendation (summary still says "no drift").
    """
    if diff_is_empty(diff):
        return DriftRecommendation(statements=[], summary="No drift detected.")

    stmts: list[MigrationStatement] = []

    # CREATE TABLE for each added table (with its columns inlined when present)
    added_table_fqns = {t.fqn for t in diff.added_tables}
    cols_for_new_table: dict[str, list[SchemaColumnDef]] = {}
    for col in diff.added_columns:
        if col.table_fqn in added_table_fqns:
            cols_for_new_table.setdefault(col.table_fqn, []).append(col)

    for tbl in diff.added_tables:
        cols = sorted(cols_for_new_table.get(tbl.fqn, []), key=lambda c: c.position)
        ddl = _create_table_ddl(tbl, cols)
        stmts.append(MigrationStatement(
            kind="CREATE_TABLE",
            ddl=ddl,
            target_fqn=tbl.fqn,
            rationale=f"new table {tbl.table_name!r} declared in JPA but absent from DB",
        ))

    # ADD COLUMN for added columns on tables that *already exist* (not part of CREATE)
    for col in diff.added_columns:
        if col.table_fqn in added_table_fqns:
            continue
        stmts.append(MigrationStatement(
            kind="ADD_COLUMN",
            ddl=_add_column_ddl(col),
            target_fqn=col.fqn,
            rationale=f"new column {col.column_name!r} on existing table {col.table_fqn!r}",
        ))

    # ALTER TYPE / SET-DROP NOT NULL for changed columns
    for ch in diff.changed_columns:
        if ch.field == "data_type":
            stmts.append(MigrationStatement(
                kind="ALTER_TYPE",
                ddl=_alter_type_ddl(ch),
                target_fqn=ch.column_fqn,
                rationale=(
                    f"column {ch.column_name!r} type drift: "
                    f"{ch.before!r} → {ch.after!r}"
                ),
            ))
        elif ch.field == "nullable":
            if ch.after.lower() == "false":
                stmts.append(MigrationStatement(
                    kind="SET_NOT_NULL",
                    ddl=_set_not_null_ddl(ch),
                    target_fqn=ch.column_fqn,
                    rationale=f"column {ch.column_name!r} became NOT NULL in JPA",
                ))
            else:
                stmts.append(MigrationStatement(
                    kind="DROP_NOT_NULL",
                    ddl=_drop_not_null_ddl(ch),
                    target_fqn=ch.column_fqn,
                    rationale=f"column {ch.column_name!r} became nullable in JPA",
                ))

    # DROP COLUMN — destructive, near end. Skip those whose table is also being
    # dropped (DROP TABLE handles it).
    removed_table_fqns = {t.fqn for t in diff.removed_tables}
    for col in diff.removed_columns:
        if col.table_fqn in removed_table_fqns:
            continue
        stmts.append(MigrationStatement(
            kind="DROP_COLUMN",
            ddl=_drop_column_ddl(col),
            target_fqn=col.fqn,
            rationale=f"column {col.column_name!r} removed from JPA",
        ))

    # DROP TABLE — most destructive, last
    for tbl in diff.removed_tables:
        stmts.append(MigrationStatement(
            kind="DROP_TABLE",
            ddl=_drop_table_ddl(tbl),
            target_fqn=tbl.fqn,
            rationale=f"table {tbl.table_name!r} removed from JPA",
        ))

    summary = _summarize(diff)
    return DriftRecommendation(statements=stmts, summary=summary)


# ─────────────────────────────────────────────────────────────────────────────
# DDL formatters — small, deterministic, PostgreSQL-flavored
# ─────────────────────────────────────────────────────────────────────────────


def _column_clause(col: SchemaColumnDef) -> str:
    null_clause = "" if col.nullable else " NOT NULL"
    return f"{col.column_name} {col.data_type}{null_clause}"


def _create_table_ddl(tbl: SchemaTableDef, cols: list[SchemaColumnDef]) -> str:
    if cols:
        col_lines = ",\n  ".join(_column_clause(c) for c in cols)
        return f"CREATE TABLE {tbl.fqn} (\n  {col_lines}\n);"
    return f"CREATE TABLE {tbl.fqn} ();"


def _drop_table_ddl(tbl: SchemaTableDef) -> str:
    return f"DROP TABLE {tbl.fqn};"


def _add_column_ddl(col: SchemaColumnDef) -> str:
    return f"ALTER TABLE {col.table_fqn} ADD COLUMN {_column_clause(col)};"


def _drop_column_ddl(col: SchemaColumnDef) -> str:
    return f"ALTER TABLE {col.table_fqn} DROP COLUMN {col.column_name};"


def _alter_type_ddl(ch: ColumnChange) -> str:
    return (
        f"ALTER TABLE {ch.table_fqn} "
        f"ALTER COLUMN {ch.column_name} TYPE {ch.after};"
    )


def _set_not_null_ddl(ch: ColumnChange) -> str:
    return (
        f"ALTER TABLE {ch.table_fqn} "
        f"ALTER COLUMN {ch.column_name} SET NOT NULL;"
    )


def _drop_not_null_ddl(ch: ColumnChange) -> str:
    return (
        f"ALTER TABLE {ch.table_fqn} "
        f"ALTER COLUMN {ch.column_name} DROP NOT NULL;"
    )


def _summarize(diff: SchemaDiff) -> str:
    parts: list[str] = []
    if diff.added_tables:
        parts.append(f"{len(diff.added_tables)} new table(s)")
    if diff.removed_tables:
        parts.append(f"{len(diff.removed_tables)} removed table(s)")
    if diff.added_columns:
        # Subtract columns that are part of an added table (they're rolled
        # into the CREATE TABLE, not ADD COLUMN)
        added_table_fqns = {t.fqn for t in diff.added_tables}
        new_table_cols = sum(1 for c in diff.added_columns if c.table_fqn in added_table_fqns)
        external_added = len(diff.added_columns) - new_table_cols
        if external_added:
            parts.append(f"{external_added} added column(s)")
    if diff.removed_columns:
        removed_table_fqns = {t.fqn for t in diff.removed_tables}
        external_removed = sum(
            1 for c in diff.removed_columns if c.table_fqn not in removed_table_fqns
        )
        if external_removed:
            parts.append(f"{external_removed} dropped column(s)")
    if diff.changed_columns:
        parts.append(f"{len(diff.changed_columns)} changed column(s)")
    return "Drift: " + ", ".join(parts) if parts else "No drift detected."


__all__ = [
    "DriftRecommendation",
    "MigrationKind",
    "MigrationStatement",
    "recommend",
]
