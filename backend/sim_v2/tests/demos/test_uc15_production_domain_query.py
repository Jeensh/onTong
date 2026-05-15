"""UC15 — Production domain ↔ code query demo verification — W45.3.

Validates the demo: production DB → loaders → domain query primitives.
Skips cleanly if production DB missing.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
    load_anchor_bindings,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc15_production_domain_query.run import (
    DEFAULT_REPOS,
    DomainQueryReport,
    find_actions_for_business_term,
    find_actions_for_method,
    find_anchor_bindings_for_action,
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
    from backend.sim_v2.demos.uc15_production_domain_query import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Query primitives — purely functional, exercised on lists built from production
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_find_actions_for_business_term_on_production(monkeypatch):
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        # `term.scm.order.order` is a known root term — many actions declare on it
        result = find_actions_for_business_term(actions, "term.scm.order.order")
        assert len(result) >= 1
        for a in result:
            assert a.declared_on_term == "term.scm.order.order"
    finally:
        session.close()


@requires_production_db
def test_find_actions_for_method_on_production():
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        # Pick a known production method
        target = "com.example.slabdesign.feature.sd.designer.SdDesigner.design(SDOrderEntity)"
        result = find_actions_for_method(actions, target)
        # SdDesigner.design is a real production method → must produce ≥1 action
        assert len(result) >= 1
        for a in result:
            assert a.code_method_fqn == target
    finally:
        session.close()


@requires_production_db
def test_find_anchor_bindings_for_action_on_production():
    """slab-design-real-v2 has 163 bindings, most targeting a few cluster actions."""
    session = open_readonly_session()
    try:
        bindings = load_anchor_bindings(session, "slab-design-real-v2")
        assert len(bindings) > 0
        # Pick a target_action_fqn that actually appears in the bindings
        target = next(b.target_action_fqn for b in bindings if b.target_action_fqn)
        result = find_anchor_bindings_for_action(bindings, target)
        assert len(result) >= 1
        for b in result:
            assert b.target_action_fqn == target
    finally:
        session.close()


def test_query_primitives_return_empty_on_no_match():
    """All three primitives are pure filters — unknown FQN ⇒ empty list."""
    assert find_actions_for_business_term([], "term.unknown") == []
    assert find_actions_for_method([], "com.unknown.X.bar()") == []
    assert find_anchor_bindings_for_action([], "action.unknown") == []


# ─────────────────────────────────────────────────────────────────────────────
# survey_repo
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_survey_repo_returns_report_with_counts():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real")
        assert isinstance(report, DomainQueryReport)
        assert report.term_count > 0
        assert report.action_count > 0
        # Most actions in production have an auto-recommended method FQN parsed
        assert report.actions_with_method_fqn >= report.action_count * 0.5
    finally:
        session.close()


@requires_production_db
def test_survey_repo_resolves_sample_queries():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "slab-design-real")
        # Sample term → actions count must be >= 1 (we picked the most-common term)
        assert report.sample_term is not None
        assert report.actions_for_sample_term >= 1
        # Sample method → actions count must be >= 1 (we picked an action with FQN)
        assert report.sample_action is not None
        assert report.sample_method_fqn is not None
        assert report.actions_for_sample_meth >= 1
    finally:
        session.close()


@requires_production_db
def test_synthetic_5k_has_no_anchor_bindings():
    """synthetic-5k is built from auto-recommend only — anchor bindings (manual
    fragment-level mappings) come from real authoring sessions and are absent."""
    session = open_readonly_session()
    try:
        report = survey_repo(session, "synthetic-5k")
        assert report.binding_count == 0
        # But terms + actions are still substantial
        assert report.term_count > 1000
        assert report.action_count > 1000
    finally:
        session.close()


@requires_production_db
def test_survey_repo_unknown_repo_yields_empty_counts():
    session = open_readonly_session()
    try:
        report = survey_repo(session, "no-such-repo")
        assert report.term_count == 0
        assert report.action_count == 0
        assert report.binding_count == 0
        assert report.sample_term is None
        assert report.sample_action is None
    finally:
        session.close()
