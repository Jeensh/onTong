"""UC30 — Exception remediation demo verification — W64.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc30_exception_remediation.run import (
    DEFAULT_REPOS,
    RepoExceptionRemediation,
    main,
    remediate_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc30_exception_remediation import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_remediate_slab_design_real_yields_10_add_steps():
    """10 UNDECLARED_THROWS findings → 10 ADD_RAISES_EFFECT steps."""
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        assert isinstance(r, RepoExceptionRemediation)
        assert r.step_counts.get("ADD_RAISES_EFFECT", 0) >= 10
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_no_remove_steps():
    """Production effects_json is empty so no REMOVE steps."""
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        assert r.step_counts.get("REMOVE_DECLARED_EFFECT", 0) == 0
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_step_payloads_well_formed():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        for s in r.report.steps:
            assert s.kind == "ADD_RAISES_EFFECT"
            assert s.effect_entry == {"kind": "raises", "exception": s.exception}
            assert s.action_fqn.startswith("action.scm.")
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_includes_algorithm_exception():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        excs = {s.exception for s in r.report.steps}
        assert "AlgorithmException" in excs
    finally:
        session.close()


@requires_production_db
def test_remediate_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "no-such-repo")
        assert r.report.steps == []
    finally:
        session.close()


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
