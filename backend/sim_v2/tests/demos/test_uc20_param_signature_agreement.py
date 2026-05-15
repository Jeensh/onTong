"""UC20 — Param-signature agreement demo verification — W52.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc20_param_signature_agreement.run import (
    DEFAULT_REPOS,
    ParamAgreementReport,
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
    from backend.sim_v2.demos.uc20_param_signature_agreement import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# survey_repo
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_survey_slab_design_real_high_verified_rate():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real")
        assert isinstance(report, ParamAgreementReport)
        assert report.total > 0
        assert report.verified_rate >= 0.80
    finally:
        session.close()


@requires_production_db
def test_survey_slab_design_v2_surfaces_3_name_mismatches():
    """The known v2 productCd / productTypeCd / prodKindCd drift."""
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real-v2")
        assert len(report.name_mismatches) >= 1
        # Each NAME_MISMATCH should expose both sides of the drift
        for v in report.name_mismatches:
            assert v.action_params != v.method_params
            assert len(v.action_params) == len(v.method_params)
    finally:
        session.close()


@requires_production_db
def test_survey_status_counts_sum_to_total():
    session = open_readonly_session()
    try:
        for repo in DEFAULT_REPOS:
            report = survey_repo(session, repo)
            assert sum(report.status_counts.values()) == report.total
    finally:
        session.close()


@requires_production_db
def test_survey_verified_rate_matches_count_over_total():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real")
        expected = report.verified_count / report.total
        assert abs(report.verified_rate - expected) < 1e-9
    finally:
        session.close()


@requires_production_db
def test_survey_unknown_repo_yields_empty_report():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "no-such-repo")
        assert report.total == 0
        assert report.verified_rate == 0.0
        assert report.name_mismatches == ()
        assert report.arity_mismatches == ()
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# v2 NAME_MISMATCH content
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_v2_name_mismatches_reference_productcd_cluster():
    """The three v2 NAME_MISMATCH cases all hinge on the productCd /
    productTypeCd / prodKindCd naming inconsistency."""
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real-v2")
        all_params = set()
        for v in report.name_mismatches:
            all_params.update(v.action_params)
            all_params.update(v.method_params)
        assert "productCd" in all_params
        assert "productTypeCd" in all_params or "prodKindCd" in all_params
    finally:
        session.close()
