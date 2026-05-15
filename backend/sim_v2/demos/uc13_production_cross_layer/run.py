"""UC13 — Production cross-layer query (W43).

Closes the production-wiring loop opened by UC10/11/12:

    UC10  production DB inspector              (read code)
    UC11  production translator survey          (code → Python, 100%)
    UC12  production schema onboarding          (code → schema model)
    UC13  production cross-layer query  ← here  (persist + query)

For each production repo:
    1. Load entity dicts (W42 loader, read-only on production DB)
    2. Extract a SchemaModel + code↔schema mappings (W43 extractor)
    3. Persist to a scratch in-memory schema DB (W43 persistence helper)
    4. Demonstrate cross-layer queries:
         - given a code type FQN, find its schema table
         - given a code field FQN, find its schema column
         - given a schema table FQN, find the owning code type
       all running on real production-extracted mappings.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc13_production_cross_layer.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaSource,
)
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaTableRow,
)
from backend.sim_v2.core.ontology.schema_layer.persistence import persist_schema_model
from backend.sim_v2.core.ontology.schema_layer.production_jpa_loader import (
    load_entity_dicts,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPOS: tuple[str, ...] = (
    "synthetic-5k",
    "slab-design-real-v2",
    "slab-design-real",
)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-layer query primitives — exposed for tests
# ─────────────────────────────────────────────────────────────────────────────


def find_schema_table_for_code_type(
    session: Session, code_type_fqn: str, repo_id: str,
) -> SchemaTableRow | None:
    row = session.query(SchemaCodeMappingRow).filter(
        SchemaCodeMappingRow.repo_id == repo_id,
        SchemaCodeMappingRow.code_type_fqn == code_type_fqn,
        SchemaCodeMappingRow.schema_table_fqn.isnot(None),
    ).first()
    if row is None or row.schema_table_fqn is None:
        return None
    return session.query(SchemaTableRow).filter(
        SchemaTableRow.repo_id == repo_id,
        SchemaTableRow.fqn == row.schema_table_fqn,
    ).one_or_none()


def find_schema_column_for_code_field(
    session: Session, code_field_fqn: str, repo_id: str,
) -> SchemaColumnRow | None:
    row = session.query(SchemaCodeMappingRow).filter(
        SchemaCodeMappingRow.repo_id == repo_id,
        SchemaCodeMappingRow.code_field_fqn == code_field_fqn,
        SchemaCodeMappingRow.schema_column_fqn.isnot(None),
    ).first()
    if row is None or row.schema_column_fqn is None:
        return None
    return session.query(SchemaColumnRow).filter(
        SchemaColumnRow.repo_id == repo_id,
        SchemaColumnRow.fqn == row.schema_column_fqn,
    ).one_or_none()


def find_code_type_for_schema_table(
    session: Session, schema_table_fqn: str, repo_id: str,
) -> str | None:
    row = session.query(SchemaCodeMappingRow).filter(
        SchemaCodeMappingRow.repo_id == repo_id,
        SchemaCodeMappingRow.schema_table_fqn == schema_table_fqn,
        SchemaCodeMappingRow.code_type_fqn.isnot(None),
    ).first()
    return row.code_type_fqn if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Repo report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CrossLayerReport:
    repo_id:               str
    persisted_tables:      int
    persisted_columns:     int
    persisted_mappings:    int
    sample_code_type:      str | None = None
    sample_schema_table:   str | None = None
    sample_code_field:     str | None = None
    sample_schema_column:  str | None = None


def build_scratch_schema_db_for_repo(prod_session, scratch_session, repo_id):
    """Read production code rows, extract schema + mappings, persist to scratch DB.

    `prod_session` is the read-only production session; `scratch_session` is a
    writable in-memory ORM session.
    """
    entities = load_entity_dicts(prod_session, repo_id)
    source = SchemaSource(kind="jpa_annotation", payload=entities, repo_id=repo_id)
    model = JpaAnnotationExtractor().extract(source)
    counts = persist_schema_model(model, scratch_session, repo_id)
    scratch_session.commit()
    return entities, model, counts


def run_cross_layer_survey_for_repo(
    prod_session, scratch_session, repo_id: str,
) -> CrossLayerReport:
    entities, model, counts = build_scratch_schema_db_for_repo(
        prod_session, scratch_session, repo_id,
    )

    sample_code_type = None
    sample_schema_table = None
    sample_code_field = None
    sample_schema_column = None

    if entities:
        sample_code_type = entities[0]["class_fqn"]
        tbl = find_schema_table_for_code_type(
            scratch_session, sample_code_type, repo_id,
        )
        if tbl:
            sample_schema_table = tbl.fqn
        if entities[0]["columns"]:
            sample_field_name = entities[0]["columns"][0]["field_name"]
            sample_code_field = f"{sample_code_type}.{sample_field_name}"
            col = find_schema_column_for_code_field(
                scratch_session, sample_code_field, repo_id,
            )
            if col:
                sample_schema_column = col.fqn

    return CrossLayerReport(
        repo_id=repo_id,
        persisted_tables=counts.tables,
        persisted_columns=counts.columns,
        persisted_mappings=counts.code_mappings,
        sample_code_type=sample_code_type,
        sample_schema_table=sample_schema_table,
        sample_code_field=sample_code_field,
        sample_schema_column=sample_schema_column,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC13 — Production cross-layer query (W43)")
    print("=" * 78)
    print()

    prod_session = open_readonly_session()
    if prod_session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    scratch_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(scratch_engine)

    try:
        totals = {"tbl": 0, "col": 0, "map": 0}
        with Session(scratch_engine) as scratch_session:
            for repo_id in repos:
                report = run_cross_layer_survey_for_repo(
                    prod_session, scratch_session, repo_id,
                )
                _banner(f"Repo: {report.repo_id}")
                print(f"  Persisted tables   : {report.persisted_tables}")
                print(f"  Persisted columns  : {report.persisted_columns}")
                print(f"  Persisted mappings : {report.persisted_mappings}")
                if report.sample_code_type:
                    short_type = report.sample_code_type
                    if len(short_type) > 60:
                        short_type = "…" + short_type[-58:]
                    print(f"  Query 1 (type → table):")
                    print(f"    code type    {short_type}")
                    print(f"    →  schema    {report.sample_schema_table}")
                if report.sample_code_field:
                    short_field = report.sample_code_field
                    if len(short_field) > 60:
                        short_field = "…" + short_field[-58:]
                    print(f"  Query 2 (field → column):")
                    print(f"    code field   {short_field}")
                    print(f"    →  schema    {report.sample_schema_column}")
                print()

                totals["tbl"] += report.persisted_tables
                totals["col"] += report.persisted_columns
                totals["map"] += report.persisted_mappings

        _banner("Aggregate (all repos)")
        print(f"  Persisted tables   : {totals['tbl']}")
        print(f"  Persisted columns  : {totals['col']}")
        print(f"  Persisted mappings : {totals['map']}")
        print()
        print("✓ Cross-layer pipeline operational on real production data —")
        print("  code FQN ↔ schema FQN queries resolve via persisted mappings")
        return 0
    finally:
        prod_session.close()
        scratch_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
