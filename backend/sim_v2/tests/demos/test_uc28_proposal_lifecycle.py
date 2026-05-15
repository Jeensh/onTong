"""UC28 — Full closed-loop demo verification — W62.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc28_proposal_lifecycle.run import (
    DEFAULT_REPOS,
    RepoLifecycleReport,
    main,
    run_lifecycle_for_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc28_proposal_lifecycle import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_lifecycle_yields_two_merged_and_one_rejected_per_repo():
    """The closed-loop produces 2 MERGED (UC27's two proposals) + 1 deliberate
    REJECT (the clashing ValidationResult)."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        assert isinstance(r, RepoLifecycleReport)
        assert r.merged == 2
        assert r.rejected == 1
        assert r.needs_human == 0
    finally:
        session.close()


@requires_production_db
def test_lifecycle_merged_carry_revision_ids():
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        merged = [res for res in r.results if res.final_state == "MERGED"]
        assert len(merged) == 2
        for m in merged:
            assert m.revision_id is not None
            assert m.oracle_status == "PASS"
    finally:
        session.close()


@requires_production_db
def test_lifecycle_rejected_carries_fail_breaking_reason():
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        rejected = [res for res in r.results if res.final_state == "REJECTED"]
        assert len(rejected) == 1
        assert rejected[0].oracle_status == "FAIL_BREAKING"
        assert "FAIL_BREAKING" in (rejected[0].rejection_reason or "")
    finally:
        session.close()


@requires_production_db
def test_lifecycle_states_visited_include_all_stages():
    """Each successful proposal traverses DRAFT → PROPOSED → ORACLED → ACCEPTED → MERGED."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        merged = [res for res in r.results if res.final_state == "MERGED"][0]
        # First state captured is DRAFT (initial), then PROPOSED, ORACLED, ACCEPTED, MERGED
        assert merged.states_visited[0] == "DRAFT"
        assert "PROPOSED" in merged.states_visited
        assert "ORACLED" in merged.states_visited
        assert "ACCEPTED" in merged.states_visited
        assert merged.states_visited[-1] == "MERGED"
    finally:
        session.close()


@requires_production_db
def test_lifecycle_proposal_ids_are_unique():
    """Each lifecycle gets a fresh proposal id (UUID)."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        ids = [res.proposal_id for res in r.results]
        assert len(set(ids)) == len(ids)
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
