"""UC21 — Framework health report demo verification — W53.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.framework_health import HealthReport
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc21_framework_health.run import (
    DEFAULT_REPOS,
    main,
    print_report,
)
from backend.sim_v2.core.verification.framework_health import framework_health_check


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc21_framework_health import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    # Small samples so the test stays fast
    assert main(translator_sample=20, idiom_sample=20) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Health report content
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_slab_design_real_is_healthy_at_default_threshold():
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real",
            translator_sample=50, idiom_sample=50,
        )
        assert report.is_healthy
    finally:
        session.close()


@requires_production_db
def test_slab_design_v2_unhealthy_due_to_param_signature():
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real-v2",
            translator_sample=50, idiom_sample=50,
        )
        assert not report.is_healthy
        param_gate = next(g for g in report.gates if g.name == "param_signature")
        assert not param_gate.is_healthy
    finally:
        session.close()


@requires_production_db
def test_overall_rate_is_between_zero_and_one():
    session = open_readonly_session()
    try:
        for repo in DEFAULT_REPOS:
            report = framework_health_check(
                session, repo,
                translator_sample=20, idiom_sample=20,
            )
            assert 0.0 <= report.overall_rate <= 1.0
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Report printing
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_print_report_does_not_raise(capsys):
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real",
            translator_sample=20, idiom_sample=20,
        )
        print_report(report)
        captured = capsys.readouterr()
        # Some marker text should appear
        assert "translator" in captured.out
        assert "action_method_verification" in captured.out
        assert "param_signature" in captured.out
        assert "idiom_coverage" in captured.out
    finally:
        session.close()


def test_print_report_handles_empty_repo_report(capsys):
    report = HealthReport(repo_id="empty-repo", gates=tuple())
    print_report(report)
    captured = capsys.readouterr()
    assert "empty-repo" in captured.out
