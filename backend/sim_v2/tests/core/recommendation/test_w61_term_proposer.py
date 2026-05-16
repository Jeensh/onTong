"""W61 — TermProposer + LLM 4-layer defense tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.recommendation.providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)
from backend.sim_v2.core.recommendation.term_proposer import (
    BusinessTermProposal,
    TermProposalResult,
    TermProposer,
    existing_terms_for_grounding,
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
# FakeStructuredProvider — returns canned LLM JSON per target_class
# ─────────────────────────────────────────────────────────────────────────────


class FakeStructuredProvider:
    """Test double — looks up the target_class in `responses` and echoes its JSON.

    The provider matches by substring against `request.user` (which contains
    the target class name) so callers can author responses keyed by class name.
    """
    name = "fake"

    def __init__(self, responses: dict[str, str],
                 *, raise_error: bool = False) -> None:
        self._responses = responses
        self._raise_error = raise_error
        self.last_request: LLMRequest | None = None

    def complete(self, request: LLMRequest,
                 model: str | None = None) -> LLMResponse:
        self.last_request = request
        if self._raise_error:
            raise LLMProviderError("simulated network failure")
        for needle, text_payload in self._responses.items():
            if needle in request.user:
                return LLMResponse(
                    text=text_payload, provider="fake", model="fake-1",
                    input_tokens=0, output_tokens=0,
                )
        return LLMResponse(
            text="", provider="fake", model="fake-1",
            input_tokens=0, output_tokens=0,
        )

    def validate(self) -> bool:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_returns_proposal_for_valid_json():
    canned = {
        "ProductCategory": json.dumps({
            "fqn": "term.scm.product.product_category",
            "label": "제품 카테고리",
            "description": "제품의 분류 카테고리.",
            "aliases": ["ProductCategory", "ProdCategory"],
            "domain": "scm",
            "kind": "enum",
            "confidence": 0.9,
            "needs_review": False,
        }),
    }
    proposer = TermProposer(FakeStructuredProvider(canned))
    result = proposer.propose(
        "ProductCategory",
        method_fqn="com.x.classify(SDOrder)",
        domain="scm",
    )
    assert result.proposal is not None
    assert result.proposal.fqn == "term.scm.product.product_category"
    assert "ProductCategory" in result.proposal.aliases
    assert result.proposal.confidence == 0.9
    assert result.proposal.needs_review is False
    assert result.proposal.target_class == "ProductCategory"
    assert result.validation_errors == ()


def test_propose_extracts_json_from_markdown_fences():
    """LLMs often wrap JSON in ```json ... ``` fences — proposer should strip them."""
    canned = {
        "X": "```json\n" + json.dumps({
            "fqn": "term.scm.x",
            "label": "X",
            "description": "X term.",
            "aliases": ["X"],
            "domain": "scm",
            "kind": "composite",
            "confidence": 0.8,
            "needs_review": False,
        }) + "\n```",
    }
    proposer = TermProposer(FakeStructuredProvider(canned))
    r = proposer.propose("X", method_fqn="m()", domain="scm")
    assert r.proposal is not None


def test_propose_extracts_json_from_surrounding_text():
    """LLMs sometimes prefix/suffix with commentary — extract first {…}."""
    canned = {
        "X": "Sure! Here's the proposal:\n" + json.dumps({
            "fqn": "term.scm.x",
            "label": "X",
            "description": "X term.",
            "aliases": ["X"],
            "domain": "scm",
            "kind": "composite",
            "confidence": 0.8,
            "needs_review": False,
        }) + "\n\nLet me know if you need anything else.",
    }
    proposer = TermProposer(FakeStructuredProvider(canned))
    r = proposer.propose("X", method_fqn="m()", domain="scm")
    assert r.proposal is not None


# ─────────────────────────────────────────────────────────────────────────────
# Validation failures (Layer 2)
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_rejects_invalid_fqn_pattern():
    canned = {
        "X": json.dumps({
            "fqn": "InvalidPattern",   # missing term. prefix
            "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm",
            "kind": "composite", "confidence": 0.9, "needs_review": False,
        }),
    }
    proposer = TermProposer(FakeStructuredProvider(canned))
    r = proposer.propose("X", method_fqn="m()", domain="scm")
    assert r.proposal is None
    assert any("fqn" in e for e in r.validation_errors)


def test_propose_rejects_empty_label():
    canned = {
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "",
            "description": "x", "aliases": ["X"], "domain": "scm",
            "kind": "composite", "confidence": 0.9, "needs_review": False,
        }),
    }
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
    )
    assert r.proposal is None
    assert any("label" in e for e in r.validation_errors)


def test_propose_rejects_invalid_kind():
    canned = {
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm",
            "kind": "INVALID_KIND",
            "confidence": 0.9, "needs_review": False,
        }),
    }
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
    )
    assert r.proposal is None
    assert any("kind" in e for e in r.validation_errors)


def test_propose_rejects_confidence_out_of_range():
    canned = {
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm",
            "kind": "composite",
            "confidence": 1.5, "needs_review": False,
        }),
    }
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
    )
    assert r.proposal is None
    assert any("confidence" in e for e in r.validation_errors)


def test_propose_handles_unparseable_response():
    canned = {"X": "this is not json"}
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
    )
    assert r.proposal is None
    assert any("JSON" in e for e in r.validation_errors)


def test_propose_handles_empty_response():
    canned = {"X": ""}
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
    )
    assert r.proposal is None


def test_propose_handles_provider_exception():
    proposer = TermProposer(FakeStructuredProvider({}, raise_error=True))
    r = proposer.propose("X", method_fqn="m()", domain="scm")
    assert r.proposal is None
    assert any("provider error" in e for e in r.validation_errors)


# ─────────────────────────────────────────────────────────────────────────────
# Auto-correction & review flags (Layer 4)
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_injects_target_class_into_aliases_when_missing():
    canned = {
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "X", "description": "x",
            "aliases": ["AliasOnly"],          # X not in aliases
            "domain": "scm", "kind": "composite",
            "confidence": 0.9, "needs_review": False,
        }),
    }
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
    )
    assert r.proposal is not None
    assert "X" in r.proposal.aliases
    # injected at position 0
    assert r.proposal.aliases[0] == "X"


def test_propose_auto_flags_needs_review_for_low_confidence():
    canned = {
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm", "kind": "composite",
            "confidence": 0.5,                   # below 0.7
            "needs_review": False,               # LLM claims OK
        }),
    }
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
    )
    assert r.proposal is not None
    assert r.proposal.needs_review is True   # auto-flag overrides LLM


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3 — duplicate detection (oracle)
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_flags_duplicate_when_existing_term_covers_class():
    existing = [
        ("term.scm.existing_x", "기존 X 카테고리", json.dumps(["X", "XClass"])),
    ]
    canned = {
        "X": json.dumps({
            "fqn": "term.scm.new_x", "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm", "kind": "composite",
            "confidence": 0.9, "needs_review": False,
        }),
    }
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
        existing_terms=existing,
    )
    assert r.proposal is not None
    assert r.duplicate_of == "term.scm.existing_x"
    # needs_review auto-flagged on dup
    assert r.proposal.needs_review is True


def test_propose_no_duplicate_when_class_is_novel():
    existing = [("term.scm.other", "다른 것", json.dumps(["Other"]))]
    canned = {
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm", "kind": "composite",
            "confidence": 0.9, "needs_review": False,
        }),
    }
    r = TermProposer(FakeStructuredProvider(canned)).propose(
        "X", method_fqn="m()", domain="scm",
        existing_terms=existing,
    )
    assert r.duplicate_of is None
    assert r.proposal.needs_review is False  # not dup, high confidence → OK


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1 — grounding (prompt contains existing terms)
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_includes_existing_terms_in_prompt():
    existing = [
        ("term.scm.foo", "푸", json.dumps(["Foo"])),
        ("term.scm.bar", "바", json.dumps(["Bar"])),
    ]
    provider = FakeStructuredProvider({
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm", "kind": "composite",
            "confidence": 0.9, "needs_review": False,
        }),
    })
    TermProposer(provider).propose(
        "X", method_fqn="m()", domain="scm", existing_terms=existing,
    )
    assert provider.last_request is not None
    user = provider.last_request.user
    assert "term.scm.foo" in user
    assert "term.scm.bar" in user
    assert "푸" in user
    assert "바" in user


def test_propose_handles_empty_grounding():
    provider = FakeStructuredProvider({
        "X": json.dumps({
            "fqn": "term.scm.x", "label": "X", "description": "x",
            "aliases": ["X"], "domain": "scm", "kind": "composite",
            "confidence": 0.9, "needs_review": False,
        }),
    })
    r = TermProposer(provider).propose("X", method_fqn="m()", domain="scm")
    assert r.proposal is not None
    assert "no existing terms" in provider.last_request.user


# ─────────────────────────────────────────────────────────────────────────────
# existing_terms_for_grounding — database accessor
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE business_terms (
                fqn TEXT, label TEXT, aliases_json TEXT,
                domain TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_term(engine, fqn, label, aliases, domain, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO business_terms(fqn, label, aliases_json, "
                 "domain, repo_id) VALUES (:f, :l, :a, :d, :r)"),
            {"f": fqn, "l": label, "a": json.dumps(aliases),
             "d": domain, "r": repo_id},
        )


def test_grounding_filters_by_domain(fixture_db):
    _insert_term(fixture_db, "term.scm.a", "에이", ["A"], "scm")
    _insert_term(fixture_db, "term.banking.b", "비", ["B"], "banking")
    with Session(fixture_db) as session:
        scm_only = existing_terms_for_grounding(session, "r", domain="scm")
    assert len(scm_only) == 1
    assert scm_only[0][0] == "term.scm.a"


def test_grounding_returns_all_when_no_domain(fixture_db):
    _insert_term(fixture_db, "term.scm.a", "에이", ["A"], "scm")
    _insert_term(fixture_db, "term.banking.b", "비", ["B"], "banking")
    with Session(fixture_db) as session:
        all_terms = existing_terms_for_grounding(session, "r")
    assert len(all_terms) == 2


def test_grounding_respects_limit(fixture_db):
    for i in range(10):
        _insert_term(fixture_db, f"term.scm.t{i}", f"t{i}", [], "scm")
    with Session(fixture_db) as session:
        out = existing_terms_for_grounding(session, "r", limit=3)
    assert len(out) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Frozen views
# ─────────────────────────────────────────────────────────────────────────────


def test_proposal_is_frozen():
    p = BusinessTermProposal(
        fqn="term.x", label="X", description="x", target_class="X",
    )
    with pytest.raises(Exception):
        p.fqn = "other"  # type: ignore[misc]


def test_result_is_frozen():
    r = TermProposalResult(
        proposal=None, raw_response="", provider_used="x",
    )
    with pytest.raises(Exception):
        r.raw_response = "y"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production grounding smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_grounding_returns_scm_terms():
    session = open_readonly_session()
    try:
        terms = existing_terms_for_grounding(
            session, "slab-design-real", domain="scm", limit=5,
        )
        assert len(terms) > 0
        for fqn, label, aliases in terms:
            assert fqn.startswith("term.")
    finally:
        session.close()
