"""UC29 — Exception agreement demo verification — W63.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc29_exception_agreement.run import (
    DEFAULT_REPOS,
    RepoExceptionSurvey,
    main,
    survey_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc29_exception_agreement import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_survey_slab_design_real_surfaces_undeclared_throws():
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert isinstance(s, RepoExceptionSurvey)
        assert s.total == 38
        assert s.counts.get("UNDECLARED_THROWS", 0) >= 10
    finally:
        session.close()


@requires_production_db
def test_survey_slab_design_real_dominant_exception_is_algorithm_exception():
    """Vast majority of undeclared throws are AlgorithmException (9 of 10 in
    current prod; one outlier is `find_spec` with IllegalStateException)."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        undeclared = [v for v in s.verifications
                      if v.status == "UNDECLARED_THROWS"]
        algorithm_hits = sum(
            1 for v in undeclared if "AlgorithmException" in v.undeclared_only
        )
        # ≥ 80% of undeclared cases are AlgorithmException
        assert algorithm_hits / max(len(undeclared), 1) >= 0.8
    finally:
        session.close()


@requires_production_db
def test_survey_has_majority_verified():
    """Most actions don't throw → VERIFIED (both sets empty)."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert s.counts.get("VERIFIED", 0) > s.counts.get("UNDECLARED_THROWS", 0)
    finally:
        session.close()


@requires_production_db
def test_survey_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        s = survey_repo(session, "no-such-repo")
        assert s.total == 0
        assert s.counts == {}
    finally:
        session.close()


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
