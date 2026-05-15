"""UC10 — Production ontology.db inspector (W37).

Prior demos all use in-memory SQLite. This one bridges the framework to the
project's real `data/ontology.db` (populated by Section 2 modeling): a
read-only sanity check that verifies cross-layer queries work against actual
production data, and surfaces which layers are populated vs gaps.

Read-only contract — Section 4 (sim) does NOT mutate Section 2 modeling data.
The session is opened with `?mode=ro` to enforce this at SQLite level.

What it reports per repo:
  - Code Layer counts: code_types / code_methods / code_fields
  - Domain Layer counts: business_terms
  - Schema Layer counts: schema_tables / schema_columns / mappings
  - Sample UC4 cross-layer query against a representative business term

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc10_production_inspector.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


PRODUCTION_DB_PATH = Path("/Users/donghae/workspace/ai/onTong/data/ontology.db")


# ─────────────────────────────────────────────────────────────────────────────
# Connection (read-only)
# ─────────────────────────────────────────────────────────────────────────────


def open_readonly_session(db_path: Path = PRODUCTION_DB_PATH) -> Session | None:
    """Open a read-only SQLAlchemy Session against the production ontology.db.

    Returns None if the DB doesn't exist (so tests / CI without it skip cleanly).
    """
    if not db_path.exists():
        return None
    # SQLite read-only URI mode — prevents accidental writes
    uri = f"sqlite:///file:{db_path}?mode=ro&uri=true"
    engine = create_engine(uri, connect_args={"uri": True})
    return Session(engine)


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo coverage report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RepoSurvey:
    repo_id:            str
    code_types:         int = 0
    code_methods:       int = 0
    code_fields:        int = 0
    business_terms:     int = 0
    schema_tables:      int = 0
    schema_columns:     int = 0
    schema_code_maps:   int = 0
    schema_domain_maps: int = 0
    sample_term_fqns:   list[str] = field(default_factory=list)


def list_repo_ids(session: Session) -> list[str]:
    """Distinct repo_id values across populated layers."""
    rows = session.execute(text(
        "SELECT DISTINCT repo_id FROM code_types "
        "UNION SELECT DISTINCT repo_id FROM business_terms "
        "UNION SELECT DISTINCT repo_id FROM schema_tables "
        "ORDER BY 1"
    )).fetchall()
    return [r[0] for r in rows if r[0]]


def survey_repo(session: Session, repo_id: str) -> RepoSurvey:
    """Per-repo Code + Domain + Schema layer counts."""
    s = RepoSurvey(repo_id=repo_id)
    s.code_types         = session.execute(text("SELECT COUNT(*) FROM code_types       WHERE repo_id = :r"), {"r": repo_id}).scalar() or 0
    s.code_methods       = session.execute(text("SELECT COUNT(*) FROM code_methods     WHERE repo_id = :r"), {"r": repo_id}).scalar() or 0
    s.code_fields        = session.execute(text(
        "SELECT COUNT(*) FROM code_fields f "
        "WHERE EXISTS (SELECT 1 FROM code_types t WHERE t.fqn = f.type_fqn AND t.repo_id = :r)"
    ), {"r": repo_id}).scalar() or 0
    s.business_terms     = session.execute(text("SELECT COUNT(*) FROM business_terms   WHERE repo_id = :r"), {"r": repo_id}).scalar() or 0
    s.schema_tables      = session.execute(text("SELECT COUNT(*) FROM schema_tables    WHERE repo_id = :r"), {"r": repo_id}).scalar() or 0
    s.schema_columns     = session.execute(text("SELECT COUNT(*) FROM schema_columns   WHERE repo_id = :r"), {"r": repo_id}).scalar() or 0
    s.schema_code_maps   = session.execute(text("SELECT COUNT(*) FROM schema_code_mappings   WHERE repo_id = :r"), {"r": repo_id}).scalar() or 0
    s.schema_domain_maps = session.execute(text("SELECT COUNT(*) FROM schema_domain_mappings WHERE repo_id = :r"), {"r": repo_id}).scalar() or 0
    # Sample a few business term FQNs to give the report some color
    rows = session.execute(
        text("SELECT fqn FROM business_terms WHERE repo_id = :r ORDER BY fqn LIMIT 5"),
        {"r": repo_id},
    ).fetchall()
    s.sample_term_fqns = [r[0] for r in rows]
    return s


def schema_layer_gap_for_repo(survey: RepoSurvey) -> str | None:
    """Return a human-readable description of the Schema Layer onboarding gap
    for this repo, or None if Schema Layer is fully populated."""
    if survey.schema_tables == 0 and survey.code_types > 0:
        return (
            f"Schema Layer has 0 tables but {survey.code_types} code_types exist — "
            "JpaAnnotationExtractor onboarding required."
        )
    if survey.schema_code_maps == 0 and survey.schema_tables > 0:
        return "Schema tables exist but no schema↔code mappings — UC4 reasoning partial."
    return None


# ─────────────────────────────────────────────────────────────────────────────
# UC4 sample query against real data (skipped if Schema Layer empty)
# ─────────────────────────────────────────────────────────────────────────────


def sample_cross_layer_query(session: Session, repo_id: str) -> dict[str, Any]:
    """Run a representative cross-layer query against the real data.

    Picks the first business_term in this repo and reports any schema columns
    mapped to it via SchemaDomainMappingRow. Falls back to a code-side query
    if Schema is empty.
    """
    from backend.sim_v2.core.ontology.query import (
        find_schema_columns_for_business_term,
    )
    term_row = session.execute(
        text("SELECT fqn FROM business_terms WHERE repo_id = :r ORDER BY fqn LIMIT 1"),
        {"r": repo_id},
    ).fetchone()
    if term_row is None:
        return {"term_fqn": None, "hits": [], "fallback": "no business_terms in repo"}

    term_fqn = term_row[0]
    hits = find_schema_columns_for_business_term(session, term_fqn, repo_id)
    return {
        "term_fqn": term_fqn,
        "hits": [{"table": h.table_fqn, "column": h.column_fqn, "confirmed": h.confirmed} for h in hits],
        "fallback": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text: str) -> None:
    print("─" * 78)
    print(text)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print("UC10 — Production ontology.db inspector (W37, read-only)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  data/ontology.db not found at {PRODUCTION_DB_PATH}")
        print("  (read-only inspector skipped — this is expected on CI / fresh checkouts)")
        return 0  # not a failure — just no data to inspect
    try:
        repos = list_repo_ids(session)
        if not repos:
            print("  data/ontology.db is empty (no rows in code_types / business_terms / schema_tables)")
            return 0

        _banner(f"Found {len(repos)} repo_id(s) in production ontology.db")
        for repo in repos:
            print(f"  • {repo}")
        print()

        any_gap = False
        for repo in repos:
            survey = survey_repo(session, repo)
            _banner(f"Repo: {repo}")
            print(f"  Code   : types={survey.code_types}, methods={survey.code_methods}, fields={survey.code_fields}")
            print(f"  Domain : business_terms={survey.business_terms}")
            print(f"  Schema : tables={survey.schema_tables}, columns={survey.schema_columns}")
            print(f"  Maps   : schema↔code={survey.schema_code_maps}, schema↔domain={survey.schema_domain_maps}")
            if survey.sample_term_fqns:
                print(f"  Sample terms ({min(5, survey.business_terms)} of {survey.business_terms}):")
                for fqn in survey.sample_term_fqns:
                    print(f"    - {fqn}")

            gap = schema_layer_gap_for_repo(survey)
            if gap:
                any_gap = True
                print(f"  ⚠ Schema Layer gap: {gap}")
            else:
                print(f"  ✓ Schema Layer populated")

            # Try a UC4 cross-layer query
            sample = sample_cross_layer_query(session, repo)
            if sample["fallback"]:
                print(f"  UC4 sample query : skipped ({sample['fallback']})")
            else:
                print(f"  UC4 sample query : term={sample['term_fqn']!r} → {len(sample['hits'])} schema hit(s)")
            print()

        _banner("Summary")
        print(f"  Repos surveyed       : {len(repos)}")
        print(f"  Schema Layer gaps    : {'yes' if any_gap else 'no'}")
        print(f"  Cross-layer reasoning: ready (queries succeeded against real DB)")
        print()
        print("✓ Production ontology.db is reachable + framework queries work against real data")
        print("  Next step: populate Schema Layer via JpaAnnotationExtractor onboarding (gap surfaced above)")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
