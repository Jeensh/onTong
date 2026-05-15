"""UC35 — Structural closed-loop demo tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc35_structural_lifecycle.run import (
    DEFAULT_REPOS,
    RepoStructuralLifecycle,
    main,
    run_lifecycle_for_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc35_structural_lifecycle import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_lifecycle_v1_yields_10_steps():
    """slab-design-real has 0 param drift + 10 return-type fix steps."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        assert isinstance(r, RepoStructuralLifecycle)
        assert len(r.results) == 10
    finally:
        session.close()


@requires_production_db
def test_lifecycle_v2_yields_13_steps():
    """slab-design-real-v2 has 3 param drift + 10 return-type = 13."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real-v2")
        assert len(r.results) == 13
    finally:
        session.close()


@requires_production_db
def test_lifecycle_v1_propose_new_term_returns_to_draft():
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        drafts = [res for res in r.results if res.final_state == "DRAFT"]
        # All DRAFT cases should be PROPOSE_NEW_TERM
        for d in drafts:
            assert d.kind == "PROPOSE_NEW_TERM"
    finally:
        session.close()


@requires_production_db
def test_lifecycle_v1_change_primitive_and_wrap_merge():
    """CHANGE_PRIMITIVE_TYPE / WRAP_AS_LIST / DECLARE_OUTPUT all MERGE cleanly."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real")
        for res in r.results:
            if res.kind in ("CHANGE_PRIMITIVE_TYPE", "WRAP_AS_LIST",
                            "DECLARE_OUTPUT"):
                assert res.final_state == "MERGED"
    finally:
        session.close()


@requires_production_db
def test_lifecycle_v2_rename_param_steps_merge():
    """The 3 v2-specific NAME_MISMATCH should all MERGE."""
    session = open_readonly_session()
    try:
        r = run_lifecycle_for_repo(session, "slab-design-real-v2")
        renames = [res for res in r.results
                   if res.kind == "RENAME_ACTION_PARAM"]
        assert len(renames) == 3
        assert all(r.final_state == "MERGED" for r in renames)
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
