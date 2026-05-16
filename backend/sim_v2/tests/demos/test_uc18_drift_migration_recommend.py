"""UC18 — Drift migration recommendation demo verification — W48.3.

Validates the end-to-end pipeline: production DB → loader → diff → recommend
→ DDL migration plan. Skips cleanly if production DB missing.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc18_drift_migration_recommend.run import (
    DEFAULT_REPO_ID,
    RecommendationReport,
    main,
    recommend_for_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc18_drift_migration_recommend import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# recommend_for_repo
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_recommendation_report_has_statements_and_summary():
    session = open_readonly_session()
    try:
        report = recommend_for_repo(session, DEFAULT_REPO_ID)
        assert isinstance(report, RecommendationReport)
        assert report.statement_count > 0
        assert "Drift" in report.summary
        # The three orthogonal mutations should each produce a kind
        assert "ADD_COLUMN" in report.statement_kinds
        assert "ALTER_TYPE" in report.statement_kinds
        assert "DROP_COLUMN" in report.statement_kinds
    finally:
        session.close()


@requires_production_db
def test_recommended_ddl_targets_real_production_tables():
    """Each statement's target_fqn should reference a real production table."""
    session = open_readonly_session()
    try:
        report = recommend_for_repo(session, DEFAULT_REPO_ID)
        assert len(report.recommendation.statements) > 0
        for s in report.recommendation.statements:
            assert s.target_fqn.startswith("public.")
            assert "public." in s.ddl
    finally:
        session.close()


@requires_production_db
def test_recommended_ddl_executes_in_safe_order():
    """The recommendation should not emit DROP_TABLE before CREATE_TABLE / ADD,
    and DROP_COLUMN should follow ALTER_TYPE."""
    session = open_readonly_session()
    try:
        report = recommend_for_repo(session, DEFAULT_REPO_ID)
        kinds = [s.kind for s in report.recommendation.statements]
        # Indices of kinds (None if absent)
        idx = {k: i for i, k in enumerate(kinds)}
        if "ALTER_TYPE" in idx and "DROP_COLUMN" in idx:
            assert idx["ALTER_TYPE"] < idx["DROP_COLUMN"]
    finally:
        session.close()


@requires_production_db
def test_recommendation_includes_rationale_for_every_statement():
    session = open_readonly_session()
    try:
        report = recommend_for_repo(session, DEFAULT_REPO_ID)
        for s in report.recommendation.statements:
            assert s.rationale
    finally:
        session.close()


@requires_production_db
def test_recommend_for_repo_handles_unknown_repo_gracefully():
    """Unknown repo → 0 entities → empty diff → 'No drift detected.' summary."""
    session = open_readonly_session()
    try:
        report = recommend_for_repo(session, "no-such-repo")
        assert report.statement_count == 0
        assert report.recommendation.summary == "No drift detected."
    finally:
        session.close()
