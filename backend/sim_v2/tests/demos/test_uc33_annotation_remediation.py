"""UC33 — Annotation remediation demo verification — W67.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc33_annotation_remediation.run import (
    DEFAULT_REPOS,
    RepoAnnotationRemediation,
    main,
    remediate_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc33_annotation_remediation import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_remediate_slab_design_real_yields_six_add_steps():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        assert isinstance(r, RepoAnnotationRemediation)
        assert r.step_counts.get("ADD_ANNOTATION_EFFECT", 0) >= 6
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_no_remove_steps():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        assert r.step_counts.get("REMOVE_ANNOTATION_EFFECT", 0) == 0
    finally:
        session.close()


@requires_production_db
def test_remediate_includes_rest_endpoint_with_detail_flag():
    """The @PostMapping action surfaces as rest_endpoint + needs_detail=True."""
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        rest = [s for s in r.report.steps
                if s.annotation_kind == "rest_endpoint"]
        assert len(rest) >= 1
        for s in rest:
            assert s.needs_detail is True
    finally:
        session.close()


@requires_production_db
def test_remediate_includes_transactional_kinds():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        trans = [s for s in r.report.steps
                 if s.annotation_kind == "transactional"]
        assert len(trans) >= 5
        for s in trans:
            assert s.needs_detail is False
    finally:
        session.close()


@requires_production_db
def test_remediate_step_payloads_match_kind():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        for s in r.report.steps:
            assert s.effect_entry == {"kind": s.annotation_kind}
    finally:
        session.close()


@requires_production_db
def test_remediate_needs_detail_counter():
    """needs_detail equals the number of rest_endpoint/scheduled/cache steps."""
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        # Just rest_endpoint in production
        assert r.needs_detail == 1
    finally:
        session.close()


@requires_production_db
def test_remediate_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "no-such-repo")
        assert r.report.steps == []
        assert r.needs_detail == 0
    finally:
        session.close()


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
