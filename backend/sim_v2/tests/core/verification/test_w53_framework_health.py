"""W53 — framework health report tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.framework_health import (
    GateResult,
    HEALTH_THRESHOLD,
    HealthReport,
    framework_health_check,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# GateResult / HealthReport — unit-level
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_rate_zero_when_no_applicable():
    g = GateResult(name="x")
    assert g.rate == 0.0
    assert g.is_healthy is True   # vacuous


def test_gate_rate_computes_correctly():
    g = GateResult(name="x", applicable=10, verified=8)
    assert g.rate == 0.8


def test_gate_is_healthy_at_or_above_threshold():
    g = GateResult(name="x", applicable=10, verified=8)
    assert g.is_healthy is (0.8 >= HEALTH_THRESHOLD)


def test_gate_below_threshold_is_unhealthy():
    g = GateResult(name="x", applicable=10, verified=5)
    assert g.is_healthy is False


def test_health_report_overall_rate_averages_applicable_gates():
    gates = (
        GateResult(name="a", applicable=10, verified=10),  # 100%
        GateResult(name="b", applicable=10, verified=8),   # 80%
        GateResult(name="c", applicable=0, verified=0),    # not applicable
    )
    report = HealthReport(repo_id="r", gates=gates)
    # Average over applicable gates only ⇒ (1.0 + 0.8) / 2 = 0.9
    assert abs(report.overall_rate - 0.9) < 1e-9


def test_health_report_is_healthy_only_if_every_gate_healthy():
    healthy = HealthReport(repo_id="r", gates=(
        GateResult(name="a", applicable=10, verified=10),
        GateResult(name="b", applicable=10, verified=9),
    ))
    assert healthy.is_healthy is True

    unhealthy = HealthReport(repo_id="r", gates=(
        GateResult(name="a", applicable=10, verified=10),
        GateResult(name="b", applicable=10, verified=5),   # 50% < threshold
    ))
    assert unhealthy.is_healthy is False


def test_health_report_overall_rate_zero_when_no_applicable_gates():
    """All gates have applicable=0 — overall_rate should be 0.0, not raise."""
    report = HealthReport(repo_id="r", gates=(
        GateResult(name="a"),
        GateResult(name="b"),
    ))
    assert report.overall_rate == 0.0


def test_gate_findings_default_empty():
    g = GateResult(name="x")
    assert g.findings == ()


# ─────────────────────────────────────────────────────────────────────────────
# framework_health_check — production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_framework_health_check_returns_four_gates():
    """One gate each for translator / action_method_verification /
    param_signature / idiom_coverage."""
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real",
            translator_sample=20, idiom_sample=20,
        )
        assert isinstance(report, HealthReport)
        assert len(report.gates) == 4
        names = {g.name for g in report.gates}
        assert names == {
            "translator",
            "action_method_verification",
            "param_signature",
            "idiom_coverage",
        }
    finally:
        session.close()


@requires_production_db
def test_slab_design_real_is_healthy():
    """All 4 gates should pass HEALTH_THRESHOLD on slab-design-real."""
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real",
            translator_sample=50, idiom_sample=50,
        )
        assert report.is_healthy is True
    finally:
        session.close()


@requires_production_db
def test_slab_design_v2_param_signature_gate_is_unhealthy():
    """v2 has known NAME_MISMATCH drift — param_signature gate should fail."""
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real-v2",
            translator_sample=50, idiom_sample=50,
        )
        param_gate = next(g for g in report.gates if g.name == "param_signature")
        assert param_gate.is_healthy is False
        # Overall report should also be unhealthy as a consequence
        assert report.is_healthy is False
    finally:
        session.close()


@requires_production_db
def test_translator_gate_at_100_percent_on_production():
    """Post-W41, translator should pass 100% on production samples."""
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real",
            translator_sample=50, idiom_sample=10,
        )
        translator_gate = next(g for g in report.gates if g.name == "translator")
        assert translator_gate.rate == 1.0
    finally:
        session.close()


@requires_production_db
def test_unknown_repo_yields_all_zero_applicable():
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "no-such-repo",
            translator_sample=10, idiom_sample=10,
        )
        for g in report.gates:
            assert g.applicable == 0
            assert g.verified == 0
            assert g.is_healthy is True   # vacuous
    finally:
        session.close()


@requires_production_db
def test_param_signature_findings_surface_action_fqns():
    """v2 NAME_MISMATCH findings should appear in the gate's findings list."""
    session = open_readonly_session()
    try:
        report = framework_health_check(
            session, "slab-design-real-v2",
            translator_sample=20, idiom_sample=20,
        )
        param_gate = next(g for g in report.gates if g.name == "param_signature")
        # At least one NAME_MISMATCH finding should be surfaced
        assert any("NAME_MISMATCH" in f for f in param_gate.findings)
    finally:
        session.close()
