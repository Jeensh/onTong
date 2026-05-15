"""UC27 — Term proposal demo verification — W61.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc27_term_proposal.run import (
    CannedJSONProvider,
    DEFAULT_REPOS,
    RepoTermProposals,
    _CANNED_RESPONSES,
    main,
    propose_terms_for_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc27_term_proposal import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


def test_canned_responses_cover_known_classes():
    """The two production class names that UC24 surfaces must have curated answers."""
    assert "ProductCategory" in _CANNED_RESPONSES
    assert "BatchResult" in _CANNED_RESPONSES


def test_canned_provider_returns_canned_json():
    provider = CannedJSONProvider(_CANNED_RESPONSES)
    from backend.sim_v2.core.recommendation.providers.base import LLMRequest
    response = provider.complete(
        LLMRequest(system="s", user="propose for ProductCategory please"),
    )
    assert "term.scm.product.product_category" in response.text


def test_canned_provider_returns_empty_for_unknown():
    provider = CannedJSONProvider(_CANNED_RESPONSES)
    from backend.sim_v2.core.recommendation.providers.base import LLMRequest
    response = provider.complete(
        LLMRequest(system="s", user="propose for UnknownClass"),
    )
    assert response.text == ""


@requires_production_db
def test_propose_terms_for_slab_design_real_yields_two_validated_proposals():
    """Production has 2 PROPOSE_NEW_TERM unique classes (ProductCategory, BatchResult)
    after dedup; both should be validated via the curated provider."""
    session = open_readonly_session()
    try:
        r = propose_terms_for_repo(session, "slab-design-real")
        assert isinstance(r, RepoTermProposals)
        assert len(r.results) == 2
        assert r.validated == 2
        assert r.failed == 0
    finally:
        session.close()


@requires_production_db
def test_propose_terms_proposals_include_product_category():
    session = open_readonly_session()
    try:
        r = propose_terms_for_repo(session, "slab-design-real")
        target_classes = [
            res.proposal.target_class for res in r.results if res.proposal
        ]
        assert "ProductCategory" in target_classes
    finally:
        session.close()


@requires_production_db
def test_propose_terms_emits_korean_label():
    """LLM should produce Korean labels matching the codebase convention."""
    session = open_readonly_session()
    try:
        r = propose_terms_for_repo(session, "slab-design-real")
        labels = [
            res.proposal.label for res in r.results if res.proposal
        ]
        # At least one Korean label
        assert any(any("가" <= ch <= "힯" for ch in lbl)
                   for lbl in labels)
    finally:
        session.close()


@requires_production_db
def test_propose_terms_for_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        r = propose_terms_for_repo(session, "no-such-repo")
        assert len(r.results) == 0
    finally:
        session.close()


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
