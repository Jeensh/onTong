"""W43 — `persist_schema_model(model, session, repo_id)`.

Writes the contents of a `SchemaModel` into the schema-layer ORM tables. The
counterpart to `JpaAnnotationExtractor.extract()` — together they form the
loop:

    code_types/code_fields (Section 2 modeling)
        ↓ load_entity_dicts
    entity dicts
        ↓ JpaAnnotationExtractor.extract
    SchemaModel
        ↓ persist_schema_model
    schema_tables / schema_columns / schema_constraints / schema_indexes / schema_code_mappings

Idempotent: re-running the persist for the same model + repo_id overwrites
prior rows for that repo (via a clear-then-insert per category) so the demo /
batch ingestion is safely re-runnable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.schema_layer.extractor import SchemaModel
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaConstraintRow,
    SchemaIndexRow,
    SchemaTableRow,
)


@dataclass(frozen=True)
class PersistCounts:
    tables:        int
    columns:       int
    constraints:   int
    indexes:       int
    code_mappings: int


def persist_schema_model(
    model: SchemaModel,
    session: Session,
    repo_id: str,
    *,
    source: str = "jpa_annotation",
) -> PersistCounts:
    """Write the entire `model` to the ORM under `repo_id`.

    Per-category clear-then-insert keeps the operation idempotent for the same
    (repo_id) — re-running the persist replaces prior rows of that repo
    without touching other repos. Caller is responsible for `session.commit()`.
    """
    # Clear prior rows for this repo (idempotency)
    for row_class in (
        SchemaTableRow,
        SchemaColumnRow,
        SchemaConstraintRow,
        SchemaIndexRow,
        SchemaCodeMappingRow,
    ):
        session.query(row_class).filter(row_class.repo_id == repo_id).delete()

    # Tables
    for t in model.tables:
        session.add(SchemaTableRow(
            fqn=t.fqn,
            table_name=t.table_name,
            schema_name=t.schema_name,
            description=t.description,
            source=source,
            repo_id=repo_id,
        ))

    # Columns
    for c in model.columns:
        session.add(SchemaColumnRow(
            fqn=c.fqn,
            table_fqn=c.table_fqn,
            column_name=c.column_name,
            data_type=c.data_type,
            nullable=c.nullable,
            default_value=c.default_value,
            description=c.description,
            position=c.position,
            repo_id=repo_id,
        ))

    # Constraints
    for cons in model.constraints:
        session.add(SchemaConstraintRow(
            table_fqn=cons.table_fqn,
            constraint_name=cons.constraint_name,
            kind=cons.kind,
            columns_json=json.dumps(cons.columns),
            expression=cons.expression,
            referenced_table_fqn=cons.referenced_table_fqn,
            referenced_columns_json=(
                json.dumps(cons.referenced_columns) if cons.referenced_columns else None
            ),
            repo_id=repo_id,
        ))

    # Indexes
    for idx in model.indexes:
        session.add(SchemaIndexRow(
            table_fqn=idx.table_fqn,
            index_name=idx.index_name,
            columns_json=json.dumps(idx.columns),
            is_unique=idx.is_unique,
            kind=idx.kind,
            partial_expression=idx.partial_expression,
            repo_id=repo_id,
        ))

    # Code mappings
    for m in model.code_mappings:
        session.add(SchemaCodeMappingRow(
            schema_table_fqn=m.schema_table_fqn,
            schema_column_fqn=m.schema_column_fqn,
            code_type_fqn=m.code_type_fqn,
            code_field_fqn=m.code_field_fqn,
            code_method_fqn=m.code_method_fqn,
            mapping_kind=m.mapping_kind,
            confidence=m.confidence,
            confirmed=m.confirmed,
            source=m.source,
            repo_id=repo_id,
        ))

    session.flush()
    return PersistCounts(
        tables=len(model.tables),
        columns=len(model.columns),
        constraints=len(model.constraints),
        indexes=len(model.indexes),
        code_mappings=len(model.code_mappings),
    )


__all__ = ["PersistCounts", "persist_schema_model"]
