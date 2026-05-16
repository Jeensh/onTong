"""UC14 — Production schema drift detection (W44).

Continues the production-wiring storyline:

    UC10  inspect          (read production code)
    UC11  translate        (code → Python, 100%)
    UC12  schema onboard   (JPA annotations → SchemaModel)
    UC13  cross-layer      (persist + query)
    UC14  drift detect ← here

Demonstrates: when JPA annotations change without a matching DDL migration,
the framework surfaces the drift before runtime failure.

Implementation:
    1. Snapshot v1 — extract production entities verbatim, build SchemaModel.
    2. Snapshot v2 — re-extract from the same entity payload after a synthetic
       mutation (column type change + new column + dropped column). This
       simulates "developer edited @Column without writing a migration".
    3. compute_diff(v1, v2) — surface added/removed/changed.
    4. Report the drift.

The synthetic mutations are applied in-memory to the entity dicts; production
data is never written.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc14_production_schema_drift.run
"""
from __future__ import annotations

import copy
import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaModel,
    SchemaSource,
)
from backend.sim_v2.core.ontology.schema_layer.production_jpa_loader import (
    load_entity_dicts,
)
from backend.sim_v2.core.ontology.schema_layer.schema_diff import (
    SchemaDiff,
    compute_diff,
    diff_is_empty,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPO_ID = "slab-design-real"  # smallest real repo — most readable drift


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic mutations
# ─────────────────────────────────────────────────────────────────────────────


def mutate_entities(entities: list[dict]) -> list[dict]:
    """Apply three orthogonal mutations to simulate uncoordinated code edits:

        1. Drop the second column of the first entity (simulates a removed @Column).
        2. Change the data_type of the first PK column of the second entity
           (simulates a developer narrowing/broadening a type without migration).
        3. Add a brand-new `audit_ts` column to the third entity (simulates an
           added @Column with no DDL backing).

    Returns a deep-copied + mutated list — the input is left untouched. The
    function returns the original list if there aren't enough entities for all
    three mutations to land (it still applies whatever it can).
    """
    mutated = copy.deepcopy(entities)

    # Mutation 1 — drop second column of the first entity
    if mutated and len(mutated[0]["columns"]) >= 2:
        dropped = mutated[0]["columns"].pop(1)
        mutated[0]["_drift_note_drop"] = dropped["column_name"]

    # Mutation 2 — type change on first PK column of the second entity
    if len(mutated) >= 2:
        for col in mutated[1]["columns"]:
            if col.get("primary_key"):
                col["data_type"] = "VARCHAR" if col["data_type"] != "VARCHAR" else "DECIMAL"
                mutated[1]["_drift_note_type"] = col["column_name"]
                break

    # Mutation 3 — added column on third entity
    if len(mutated) >= 3:
        mutated[2]["columns"].append({
            "field_name":  "auditTs",
            "column_name": "AUDIT_TS",
            "data_type":   "TIMESTAMP",
            "nullable":    True,
            "primary_key": False,
        })
        mutated[2]["_drift_note_add"] = "AUDIT_TS"

    return mutated


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DriftReport:
    repo_id:          str
    diff:             SchemaDiff
    v1_table_count:   int
    v2_table_count:   int
    v1_column_count:  int
    v2_column_count:  int

    @property
    def has_drift(self) -> bool:
        return not diff_is_empty(self.diff)


def survey_drift(session: Session, repo_id: str) -> DriftReport:
    entities_v1 = load_entity_dicts(session, repo_id)
    entities_v2 = mutate_entities(entities_v1)

    v1 = JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=entities_v1, repo_id=repo_id)
    )
    v2 = JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=entities_v2, repo_id=repo_id)
    )

    diff = compute_diff(v1, v2)
    return DriftReport(
        repo_id=repo_id,
        diff=diff,
        v1_table_count=len(v1.tables),
        v2_table_count=len(v2.tables),
        v1_column_count=len(v1.columns),
        v2_column_count=len(v2.columns),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def main(repo_id: str = DEFAULT_REPO_ID) -> int:
    print("=" * 78)
    print("UC14 — Production schema drift detection (W44)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        _banner(f"Repo: {repo_id}")
        report = survey_drift(session, repo_id)

        print(f"  Snapshot v1 tables / columns : {report.v1_table_count} / {report.v1_column_count}")
        print(f"  Snapshot v2 tables / columns : {report.v2_table_count} / {report.v2_column_count}")
        print()

        if not report.has_drift:
            print("  ✓ No drift detected — JPA model unchanged between snapshots.")
            return 0

        _banner("DRIFT DETECTED")
        diff = report.diff
        if diff.added_tables:
            print(f"  + Added tables   ({len(diff.added_tables)}):")
            for t in diff.added_tables[:5]:
                print(f"    + {t.fqn}")
        if diff.removed_tables:
            print(f"  - Removed tables ({len(diff.removed_tables)}):")
            for t in diff.removed_tables[:5]:
                print(f"    - {t.fqn}")
        if diff.added_columns:
            print(f"  + Added columns   ({len(diff.added_columns)}):")
            for c in diff.added_columns[:5]:
                print(f"    + {c.fqn}    [{c.data_type}, nullable={c.nullable}]")
        if diff.removed_columns:
            print(f"  - Removed columns ({len(diff.removed_columns)}):")
            for c in diff.removed_columns[:5]:
                print(f"    - {c.fqn}    [{c.data_type}, nullable={c.nullable}]")
        if diff.changed_columns:
            print(f"  ~ Changed columns ({len(diff.changed_columns)}):")
            for ch in diff.changed_columns[:5]:
                print(f"    ~ {ch.column_fqn}  {ch.field}: {ch.before!r} → {ch.after!r}")

        print()
        print("✓ Drift detected on production data — JPA edits were observed without")
        print("  a corresponding DDL migration. Framework would flag for review.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
