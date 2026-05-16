"""UC18 — Drift → DDL migration recommendation on production (W48).

Closes the detection→fix loop:

    UC14  detect drift   (SchemaDiff between two snapshots)
    UC18  recommend fix  ← here  (SchemaDiff → DDL migration)

Per repo, the demo:
    1. Loads production entity dicts (W42 loader, read-only)
    2. Applies synthetic mutations (UC14's mutate_entities)
    3. Extracts v1 & v2 SchemaModels, computes diff
    4. Calls `recommend(diff)` for a deterministic DDL migration plan
    5. Prints each statement with its rationale, in safe execution order

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc18_drift_migration_recommend.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.schema_layer.drift_migration_recommender import (
    DriftRecommendation,
    MigrationStatement,
    recommend,
)
from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaSource,
)
from backend.sim_v2.core.ontology.schema_layer.production_jpa_loader import (
    load_entity_dicts,
)
from backend.sim_v2.core.ontology.schema_layer.schema_diff import compute_diff
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc14_production_schema_drift.run import mutate_entities


DEFAULT_REPO_ID = "slab-design-real"


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RecommendationReport:
    repo_id:            str
    recommendation:     DriftRecommendation
    statement_count:    int = 0
    statement_kinds:    dict[str, int] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        return self.recommendation.summary


def recommend_for_repo(session: Session, repo_id: str) -> RecommendationReport:
    entities_v1 = load_entity_dicts(session, repo_id)
    entities_v2 = mutate_entities(entities_v1)

    v1 = JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=entities_v1, repo_id=repo_id)
    )
    v2 = JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=entities_v2, repo_id=repo_id)
    )
    diff = compute_diff(v1, v2)
    rec = recommend(diff)
    kinds = Counter(s.kind for s in rec.statements)
    return RecommendationReport(
        repo_id=repo_id,
        recommendation=rec,
        statement_count=len(rec.statements),
        statement_kinds=dict(kinds),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def _print_statement(s: MigrationStatement) -> None:
    print(f"  [{s.kind:14s}] {s.ddl}")
    print(f"    rationale: {s.rationale}")


def main(repo_id: str = DEFAULT_REPO_ID) -> int:
    print("=" * 78)
    print("UC18 — Drift → DDL migration recommendation (W48)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        _banner(f"Repo: {repo_id}")
        report = recommend_for_repo(session, repo_id)

        print(f"  {report.summary}")
        if report.statement_kinds:
            kinds_summary = ", ".join(f"{k}={v}" for k, v in sorted(report.statement_kinds.items()))
            print(f"  Statement kinds: {kinds_summary}")
        print()

        if not report.recommendation.statements:
            print("  ✓ No drift — nothing to recommend.")
            return 0

        _banner("Migration plan (safe execution order)")
        for s in report.recommendation.statements:
            _print_statement(s)
        print()
        print("✓ Migration plan generated end-to-end from production drift detection.")
        print("  Operator can apply the DDL block as a Flyway / Liquibase migration.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
