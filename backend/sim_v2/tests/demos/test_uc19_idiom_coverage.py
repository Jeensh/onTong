"""UC19 — Idiom coverage demo verification — W49.3.

Validates: production methods → translator → idiom verifier → coverage report.
Skips cleanly if production DB missing.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.idiom_verifier import DEFAULT_RULES
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc19_idiom_coverage.run import (
    DEFAULT_REPO_ID,
    DEFAULT_SAMPLE_SIZE,
    IdiomCoverageReport,
    RulePerformance,
    main,
    survey_idiom_coverage,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc19_idiom_coverage import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    # Small sample for fast test
    assert main(sample_size=50) == 0


# ─────────────────────────────────────────────────────────────────────────────
# survey_idiom_coverage
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_survey_returns_report_with_one_entry_per_rule():
    """The report's per_rule tuple must be aligned to DEFAULT_RULES."""
    session = open_readonly_session()
    try:
        report = survey_idiom_coverage(session, DEFAULT_REPO_ID, sample_size=50)
        assert isinstance(report, IdiomCoverageReport)
        assert len(report.per_rule) == len(DEFAULT_RULES)
        rule_names = {rp.rule_name for rp in report.per_rule}
        expected = {r.name for r in DEFAULT_RULES}
        assert rule_names == expected
    finally:
        session.close()


@requires_production_db
def test_survey_translate_pass_should_match_sample_size_post_w41():
    """W41 brought translator pass rate to 100% on production. The UC19
    survey should see every sampled method PASS translate."""
    session = open_readonly_session()
    try:
        report = survey_idiom_coverage(session, DEFAULT_REPO_ID, sample_size=100)
        assert report.translate_pass == report.sample_size
    finally:
        session.close()


@requires_production_db
def test_survey_match_plus_violation_equals_applicable():
    """Each rule's applicable count is by definition match + violation."""
    session = open_readonly_session()
    try:
        report = survey_idiom_coverage(session, DEFAULT_REPO_ID, sample_size=50)
        for r in report.per_rule:
            assert r.applicable == r.match + r.violation
    finally:
        session.close()


@requires_production_db
def test_survey_surfaces_at_least_one_applicable_rule():
    """At least one of the rules in DEFAULT_RULES should fire on a slab-design
    sample (bigdecimal_arith or increment_to_augadd are the likely candidates)."""
    session = open_readonly_session()
    try:
        report = survey_idiom_coverage(session, DEFAULT_REPO_ID, sample_size=200)
        total_applicable = sum(r.applicable for r in report.per_rule)
        assert total_applicable > 0
    finally:
        session.close()


@requires_production_db
def test_match_rate_is_zero_for_zero_applicable():
    """The match_rate property must short-circuit when applicable=0."""
    session = open_readonly_session()
    try:
        report = survey_idiom_coverage(session, DEFAULT_REPO_ID, sample_size=10)
        for r in report.per_rule:
            if r.applicable == 0:
                assert r.match_rate == 0.0
    finally:
        session.close()


@requires_production_db
def test_match_rate_bounded_between_zero_and_one():
    session = open_readonly_session()
    try:
        report = survey_idiom_coverage(session, DEFAULT_REPO_ID, sample_size=100)
        for r in report.per_rule:
            assert 0.0 <= r.match_rate <= 1.0
    finally:
        session.close()


@requires_production_db
def test_unknown_repo_returns_empty_report():
    session = open_readonly_session()
    try:
        report = survey_idiom_coverage(session, "no-such-repo", sample_size=10)
        assert report.sample_size == 0
        assert report.translate_pass == 0
        for r in report.per_rule:
            assert r.applicable == 0
            assert r.match == 0
            assert r.violation == 0
    finally:
        session.close()


def test_rule_performance_match_rate_handles_zero():
    """Unit: RulePerformance.match_rate must not divide by zero."""
    r = RulePerformance(rule_name="x", applicable=0, match=0, violation=0)
    assert r.match_rate == 0.0


def test_rule_performance_match_rate_computes_correctly():
    r = RulePerformance(rule_name="x", applicable=10, match=7, violation=3)
    assert r.match_rate == 0.7
