"""UC23 — Return-type agreement demo verification — W56.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc23_return_type_agreement.run import (
    DEFAULT_REPOS,
    RepoReturnTypeSurvey,
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
    from backend.sim_v2.demos.uc23_return_type_agreement import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# survey_repo
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_survey_slab_design_real_returns_38_actions():
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert isinstance(s, RepoReturnTypeSurvey)
        assert s.total == 38
    finally:
        session.close()


@requires_production_db
def test_survey_slab_design_real_yields_majority_verified():
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert s.counts.get("VERIFIED", 0) > 0
        # > 65% verified — W57 term resolver lifted this from 55.3% → 68.4%
        # by closing the OBJECT_REF gap.
        assert s.verified_rate > 0.65
    finally:
        session.close()


@requires_production_db
def test_survey_slab_design_real_includes_primitive_mismatch():
    """The known production case: string→ProductCategory drift."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        prims = [v for v in s.verifications if v.status == "PRIMITIVE_MISMATCH"]
        assert len(prims) > 0
        # The exact ProductCategory case
        assert any(
            v.method_return == "ProductCategory" and v.action_output == "string"
            for v in prims
        )
    finally:
        session.close()


@requires_production_db
def test_survey_slab_design_real_surfaces_object_ref_arity_drift():
    """W57: object_ref now resolves. The known arity drift case
    `extract_designable_orders` (single Order term vs List<SDOrderEntity>)
    should appear as OBJECT_REF_MISMATCH."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        mismatches = [v for v in s.verifications
                      if v.status == "OBJECT_REF_MISMATCH"]
        assert len(mismatches) > 0
        # The exact known case
        assert any(
            "List<" in (v.method_return or "")
            for v in mismatches
        )
    finally:
        session.close()


@requires_production_db
def test_survey_slab_design_real_object_ref_majority_verifies():
    """5 of the 6 OBJECT_REF rows resolve cleanly (matching method's return)."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        object_ref_verified = [
            v for v in s.verifications
            if v.status == "VERIFIED"
            and (v.action_output or "").startswith("object_ref:")
        ]
        assert len(object_ref_verified) >= 5
    finally:
        session.close()


@requires_production_db
def test_survey_slab_design_real_includes_implicit_output():
    """Some actions declare no output but the method returns a value."""
    session = open_readonly_session()
    try:
        s = survey_repo(session, "slab-design-real")
        assert s.counts.get("IMPLICIT_OUTPUT", 0) > 0
    finally:
        session.close()


@requires_production_db
def test_survey_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        s = survey_repo(session, "no-such-repo")
        assert s.total == 0
        assert s.counts == {}
        assert s.verified_rate == 0.0
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Default repos invariant
# ─────────────────────────────────────────────────────────────────────────────


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
