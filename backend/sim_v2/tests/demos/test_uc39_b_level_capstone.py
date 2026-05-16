"""UC39 — B-level capstone tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc39_b_level_capstone.run import (
    ProductionGapReport,
    SyntheticCapstoneResult,
    TARGET_REPO,
    main,
    run_production_gap,
    run_synthetic_capstone,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# PART A — Synthetic pipeline proof
# ─────────────────────────────────────────────────────────────────────────────


def test_synthetic_pipeline_yields_all_pass():
    """W71 ➜ W73 ➜ W59 on a translatable method should pass every fixture."""
    r = run_synthetic_capstone()
    assert isinstance(r, SyntheticCapstoneResult)
    assert r.fixtures_generated == 4
    assert r.fixtures_matched == 4
    assert r.fixtures_passed == 4
    assert r.aggregate_status == "PASS"


# ─────────────────────────────────────────────────────────────────────────────
# PART B — Production gap diagnosis
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc39_b_level_capstone import run as r
    monkeypatch.setattr(r, "open_readonly_session", lambda *a, **kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_production_gap_diagnoses_all_driveable_actions():
    s = open_readonly_session()
    try:
        r = run_production_gap(s)
        assert isinstance(r, ProductionGapReport)
        assert r.total_actions == 38
        # ~11 W71-driveable + non-empty-primitives → diagnosable
        assert 8 <= len(r.rows) <= 14
    finally:
        s.close()


@requires_production_db
def test_production_gap_surfaces_named_failure_causes():
    s = open_readonly_session()
    try:
        r = run_production_gap(s)
        causes = set(r.cause_counts.keys())
        allowed = {
            "GREEN", "TRANSLATOR_NAMERROR", "TRANSLATOR_ATTRERROR",
            "TRANSLATOR_SYNTAX", "NO_BASELINE", "OTHER",
        }
        assert causes <= allowed, f"unknown causes: {causes - allowed}"
        # Today's production has known translator gaps — expect majority
        # to be in NAMERROR / SYNTAX / ATTRERROR.
        translator_gaps = sum(
            r.cause_counts.get(k, 0)
            for k in ("TRANSLATOR_NAMERROR", "TRANSLATOR_ATTRERROR",
                      "TRANSLATOR_SYNTAX")
        )
        assert translator_gaps >= len(r.rows) // 2
    finally:
        s.close()


@requires_production_db
def test_production_gap_no_silent_others():
    """Most failures should be categorised; "OTHER" should be rare."""
    s = open_readonly_session()
    try:
        r = run_production_gap(s)
        others = r.cause_counts.get("OTHER", 0)
        assert others <= 2  # noise budget for unforeseen exception classes
    finally:
        s.close()


def test_target_repo_is_v2():
    assert TARGET_REPO == "slab-design-real-v2"
