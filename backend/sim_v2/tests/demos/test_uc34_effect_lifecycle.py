"""UC34 — Effect closed-loop demo tests — W68.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc34_effect_lifecycle.run import (
    DEFAULT_REPOS,
    RepoEffectLifecycle,
    main,
    run_lifecycle_for_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc34_effect_lifecycle import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_lifecycle_for_slab_design_real_yields_16_steps():
    """10 exception + 6 annotation = 16 lifecycles."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        assert isinstance(r, RepoEffectLifecycle)
        assert len(r.results) == 16
    finally:
        session.close()


@requires_production_db
def test_lifecycle_majority_merge():
    """All 10 exception + 5 annotation should MERGE (1 rest_endpoint needs detail)."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        assert r.merged == 15
        assert r.needs_human == 1
        assert r.rejected == 0
    finally:
        session.close()


@requires_production_db
def test_lifecycle_rest_endpoint_returns_to_draft():
    """The @PostMapping rest_endpoint step has needs_detail=True → DRAFT."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        drafts = [res for res in r.results if res.final_state == "DRAFT"]
        assert len(drafts) == 1
        assert drafts[0].effect_kind == "rest_endpoint"
    finally:
        session.close()


@requires_production_db
def test_lifecycle_merged_have_revisions():
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        merged = [res for res in r.results if res.final_state == "MERGED"]
        for m in merged:
            assert m.revision_id is not None
            assert m.oracle_status == "PASS"
    finally:
        session.close()


@requires_production_db
def test_lifecycle_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "no-such-repo")
        assert len(r.results) == 0
    finally:
        session.close()


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
