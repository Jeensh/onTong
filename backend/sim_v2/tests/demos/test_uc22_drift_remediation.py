"""UC22 — Drift remediation demo verification — W55.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc22_drift_remediation.run import (
    DEFAULT_REPOS,
    RepoRemediation,
    main,
    remediate_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc22_drift_remediation import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# remediate_repo
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_remediate_slab_design_real_no_steps():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        assert isinstance(r, RepoRemediation)
        assert r.rename_count == 0
        assert r.resize_count == 0
        assert r.report.steps == []
    finally:
        session.close()


@requires_production_db
def test_remediate_v2_yields_three_rename_steps():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real-v2")
        assert r.rename_count == 3
        assert r.resize_count == 0
        # All three should align toward productCd
        for s in r.report.steps:
            assert s.expected_name == "productCd"
    finally:
        session.close()


@requires_production_db
def test_remediate_v2_steps_carry_action_and_method_fqns():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real-v2")
        for s in r.report.steps:
            assert s.action_fqn.startswith("action.scm.")
            assert "com.example.slabdesign" in s.code_method_fqn
    finally:
        session.close()


@requires_production_db
def test_remediate_v2_summary_describes_3_name_mismatches():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real-v2")
        assert "3 NAME_MISMATCH" in r.report.summary
    finally:
        session.close()


@requires_production_db
def test_remediate_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "no-such-repo")
        assert r.rename_count == 0
        assert r.resize_count == 0
    finally:
        session.close()
