"""UC17 — Production action ↔ code verification demo verification — W47.3.

Validates: load production actions → verify against code_methods + translator
→ classified report. Skips cleanly if production DB missing.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc17_action_verification.run import (
    DEFAULT_REPOS,
    VerificationReport,
    main,
    survey_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc17_action_verification import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# survey_repo on each known production repo
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_survey_repo_slab_design_real_has_high_verified_rate():
    """slab-design-real should verify at ≥90% (post-W41 translator is 100% on its code,
    most actions have parseable method FQNs)."""
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real")
        assert isinstance(report, VerificationReport)
        assert report.total > 0
        assert report.verified_rate >= 0.90
        assert len(report.sample_verified) > 0
    finally:
        session.close()


@requires_production_db
def test_survey_repo_synthetic_5k_surfaces_method_not_found_systemic_drift():
    """synthetic-5k's actions reference non-prefixed FQNs while code_methods are
    prefix-stamped — this is a real data drift the verifier should surface
    (a meaningful production finding, not a bug)."""
    session = open_readonly_session()
    try:
        report = survey_repo(session, "synthetic-5k")
        method_not_found = report.status_counts.get("METHOD_NOT_FOUND", 0)
        # Most synthetic-5k actions land in METHOD_NOT_FOUND
        assert method_not_found >= report.total * 0.9, (
            f"expected ≥90% METHOD_NOT_FOUND on synthetic-5k, got "
            f"{method_not_found}/{report.total}"
        )
    finally:
        session.close()


@requires_production_db
def test_survey_repo_findings_include_action_fqn_and_status():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real")
        # Findings (non-VERIFIED) should carry the action_fqn + a status
        for v in report.sample_findings:
            assert v.action_fqn
            assert v.status != "VERIFIED"
    finally:
        session.close()


@requires_production_db
def test_survey_unknown_repo_returns_empty_report():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "no-such-repo")
        assert report.total == 0
        assert report.verified_rate == 0.0
        assert report.sample_verified == ()
        assert report.sample_findings == ()
    finally:
        session.close()


@requires_production_db
def test_survey_status_counts_sum_to_total():
    """The status_counts must partition the action set exactly."""
    session = open_readonly_session()
    try:
        for repo in DEFAULT_REPOS:
            report = survey_repo(session, repo)
            counted = sum(report.status_counts.values())
            assert counted == report.total
    finally:
        session.close()


@requires_production_db
def test_survey_verified_rate_matches_verified_count_over_total():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real")
        expected = report.verified_count / report.total
        assert abs(report.verified_rate - expected) < 1e-9
    finally:
        session.close()
