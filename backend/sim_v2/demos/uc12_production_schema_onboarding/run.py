"""UC12 — Production schema onboarding (W42).

Sister demo to UC11. While UC11 proves the translator handles production
**code**, UC12 proves the framework can ingest production **schema** via
JPA annotations on production `code_types` / `code_fields`.

For each of the 3 production repos (`slab-design-real`, `slab-design-real-v2`,
`synthetic-5k`) the demo:
  1. Opens `data/ontology.db` read-only (same path as UC10/11).
  2. Calls `load_entity_dicts(session, repo_id)` to assemble JPA payloads.
  3. Feeds the payload through `JpaAnnotationExtractor` to a `SchemaModel`.
  4. Reports per-repo table / column / constraint counts + a sample table.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc12_production_schema_onboarding.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaModel,
    SchemaSource,
)
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
# Per-repo report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepoReport:
    repo_id:            str
    entity_count:       int
    table_count:        int
    column_count:       int
    constraint_count:   int
    constraint_kinds:   dict[str, int]
    fk_count:           int
    sample_table_fqn:   str | None = None
    sample_columns:     tuple[str, ...] = field(default_factory=tuple)


def onboard_repo(session: Session, repo_id: str) -> RepoReport:
    """Read production entities for `repo_id`, run them through the JPA
    extractor, and summarize. Empty / no-entity repos yield an empty report.
    """
    entities = load_entity_dicts(session, repo_id)
    source = SchemaSource(kind="jpa_annotation", payload=entities, repo_id=repo_id)
    model: SchemaModel = JpaAnnotationExtractor().extract(source)

    constraint_kinds = Counter(c.kind for c in model.constraints)
    fk_count = sum(1 for c in model.constraints if c.kind == "FK")

    sample_fqn: str | None = None
    sample_cols: tuple[str, ...] = ()
    if model.tables:
        sample = model.tables[0]
        sample_fqn = sample.fqn
        sample_cols = tuple(
            c.column_name for c in model.columns if c.table_fqn == sample.fqn
        )[:6]

    return RepoReport(
        repo_id=repo_id,
        entity_count=len(entities),
        table_count=len(model.tables),
        column_count=len(model.columns),
        constraint_count=len(model.constraints),
        constraint_kinds=dict(constraint_kinds),
        fk_count=fk_count,
        sample_table_fqn=sample_fqn,
        sample_columns=sample_cols,
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
    print("UC12 — Production schema onboarding (W42)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        totals = {"entity": 0, "table": 0, "column": 0, "constraint": 0, "fk": 0}
        for repo_id in repos:
            report = onboard_repo(session, repo_id)
            _banner(f"Repo: {report.repo_id}")
            print(f"  Entities (@Entity + @Table) : {report.entity_count}")
            print(f"  Schema tables emitted        : {report.table_count}")
            print(f"  Schema columns emitted       : {report.column_count}")
            print(f"  Constraints emitted          : {report.constraint_count} "
                  f"({report.constraint_kinds})")
            print(f"  Foreign keys                 : {report.fk_count}")
            if report.sample_table_fqn:
                print(f"  Sample table                 : {report.sample_table_fqn}")
                print(f"  Sample columns               : {', '.join(report.sample_columns)}")
            print()

            totals["entity"]     += report.entity_count
            totals["table"]      += report.table_count
            totals["column"]     += report.column_count
            totals["constraint"] += report.constraint_count
            totals["fk"]         += report.fk_count

        _banner("Aggregate (all repos)")
        print(f"  Entities    : {totals['entity']}")
        print(f"  Tables      : {totals['table']}")
        print(f"  Columns     : {totals['column']}")
        print(f"  Constraints : {totals['constraint']}")
        print(f"  FKs         : {totals['fk']}")
        print()
        print("✓ Production schema onboarding complete — JPA annotations on "
              "production code_types/code_fields → schema layer payload")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
