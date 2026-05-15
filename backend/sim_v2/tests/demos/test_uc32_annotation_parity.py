"""UC32 — Annotation parity demo verification — W66.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc32_annotation_parity.run import (
    DEFAULT_REPOS,
    RepoAnnotationSurvey,
    main,
    survey_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc32_annotation_parity import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_survey_slab_design_real_yields_undeclared_findings():
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert isinstance(s, RepoAnnotationSurvey)
        assert s.total == 38
        assert s.counts.get("UNDECLARED_ANNOTATION", 0) >= 5
    finally:
        session.close()


@requires_production_db
def test_survey_finds_transactional_drift():
    """5 actions have @Transactional methods but no documented transactional effect."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert s.by_kind.get("transactional", 0) >= 5
    finally:
        session.close()


@requires_production_db
def test_survey_finds_rest_endpoint_drift():
    """batch_design Controller has @PostMapping → 1 rest_endpoint undeclared."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert s.by_kind.get("rest_endpoint", 0) >= 1
    finally:
        session.close()


@requires_production_db
def test_survey_majority_verified():
    """Most actions don't have contract annotations → VERIFIED."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert s.counts.get("VERIFIED", 0) > s.counts.get("UNDECLARED_ANNOTATION", 0)
    finally:
        session.close()


@requires_production_db
def test_survey_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        s = survey_repo(session, "no-such-repo")
        assert s.total == 0
        assert s.counts == {}
        assert s.by_kind == {}
    finally:
        session.close()


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
