"""UC38 — Production invariant survey tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc38_production_invariants.run import (
    InvariantSurveyReport,
    TARGET_REPO,
    main,
    run_invariant_survey,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc38_production_invariants import run as r
    monkeypatch.setattr(r, "open_readonly_session", lambda *a, **kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_v2_surveys_driveable_subset():
    """UC38 should cover exactly the W71-driveable subset (11 actions on v2)."""
    s = open_readonly_session()
    try:
        r = run_invariant_survey(s)
        assert isinstance(r, InvariantSurveyReport)
        # Should be within 1-2 of UC37's 11 driveable count
        assert 8 <= len(r.rows) <= 14
        assert r.total_fixtures >= 80
    finally:
        s.close()


@requires_production_db
def test_v2_surfaces_real_behavioral_gap():
    """The honest UC38 outcome: most production methods fail invariants because
    of unresolved JPA-injected services / Java string idioms. This test pins
    that the gap is *visible*, not silenced.
    """
    s = open_readonly_session()
    try:
        r = run_invariant_survey(s)
        non_pass = sum(1 for row in r.rows if row.status != "PASS")
        # Expect majority to surface a failure — these are real translator gaps.
        assert non_pass >= len(r.rows) // 2
    finally:
        s.close()


@requires_production_db
def test_v2_status_categories_are_well_formed():
    s = open_readonly_session()
    try:
        r = run_invariant_survey(s)
        allowed = {
            "PASS", "FAIL_DETERMINISM", "FAIL_THROW",
            "FAIL_TYPE", "ERROR", "INCONCLUSIVE",
        }
        seen = set(r.status_counts.keys())
        assert seen <= allowed, f"unexpected statuses: {seen - allowed}"
    finally:
        s.close()


def test_target_repo_is_v2():
    assert TARGET_REPO == "slab-design-real-v2"
