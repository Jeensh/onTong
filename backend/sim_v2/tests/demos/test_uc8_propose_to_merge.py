"""UC8 — propose() → submit → merge demo verification — W35.2.

Validates the propose() side of the LLM defense pipeline:
  - RecommendationEngine.propose() builds a Proposal from ProposalContext
  - Anti-pattern scanner runs on the raw LLM output
  - Proposal flows through Integrator (submit → oracle → review → merge)
  - Final state is MERGED with revision lineage
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.recommendation.engine import (
    ProposalContext,
    RecommendationEngine,
)
from backend.sim_v2.core.recommendation.providers.base import LLMRequest

from backend.sim_v2.demos.uc8_propose_to_merge.run import (
    CANNED_DIFF_PAYLOAD,
    PROPOSAL_CONTEXT,
    ScriptedProposeProvider,
    build_engine_and_integrator,
    main,
    run_propose_to_merge,
)


@pytest.fixture
def result():
    return run_propose_to_merge()


def test_demo_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Scripted provider
# ─────────────────────────────────────────────────────────────────────────────


def test_provider_returns_canned_diff_on_signal_match():
    p = ScriptedProposeProvider()
    resp = p.complete(LLMRequest(system="s", user="add daily_balance_summary table please"))
    assert resp.text == CANNED_DIFF_PAYLOAD


def test_provider_returns_refusal_without_signal():
    p = ScriptedProposeProvider()
    resp = p.complete(LLMRequest(system="s", user="vague request"))
    assert "no actionable signal" in resp.text


def test_provider_records_each_call():
    p = ScriptedProposeProvider()
    for i in range(3):
        p.complete(LLMRequest(system="s", user=f"call {i}"))
    assert len(p.calls) == 3


# ─────────────────────────────────────────────────────────────────────────────
# propose() output
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_produces_proposal_with_correct_type(result):
    proposal = result["proposal"]
    assert proposal.type == "schema_change"


def test_propose_stuffs_llm_output_into_schema_diff(result):
    proposal = result["proposal"]
    assert proposal.schema_diff is not None
    assert proposal.schema_diff.get("raw_llm_output") == CANNED_DIFF_PAYLOAD


def test_propose_does_not_populate_code_or_ontology_diff(result):
    proposal = result["proposal"]
    assert proposal.code_diff is None
    assert proposal.ontology_diff is None


def test_propose_user_prompt_includes_grounding(result):
    """The LLM prompt should expose ontology_context entries so the model can ground."""
    provider = result["provider"]
    user_prompt = provider.calls[0].user
    assert "existing_tables" in user_prompt
    assert "account" in user_prompt
    assert "primary_aggregate" in user_prompt


def test_propose_user_prompt_includes_user_intent(result):
    provider = result["provider"]
    user_prompt = provider.calls[0].user
    assert "daily_balance_summary" in user_prompt


# ─────────────────────────────────────────────────────────────────────────────
# Anti-pattern validation
# ─────────────────────────────────────────────────────────────────────────────


def test_canned_diff_has_no_anti_pattern_hits(result):
    rec_result = result["rec_result"]
    # The canned diff is clean — no BigDecimal(...) class form, etc.
    assert rec_result.validation.has_errors is False
    assert len(rec_result.validation.hits) == 0


def test_validation_summary_reports_clean(result):
    rec_result = result["rec_result"]
    assert "clean" in rec_result.validation.summary


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle (Integrator)
# ─────────────────────────────────────────────────────────────────────────────


def test_lifecycle_reaches_merged(result):
    assert result["proposal"].state == "MERGED"
    assert result["revision_id"] is not None


def test_oracle_aggregate_pass(result):
    assert result["oracle"].aggregate_status == "PASS"


def test_lifecycle_transitions(result):
    transitions = [(e.from_state, e.to_state) for e in result["proposal"].history]
    assert transitions == [
        ("DRAFT",    "PROPOSED"),
        ("PROPOSED", "ORACLED"),
        ("ORACLED",  "REVIEWED"),
        ("REVIEWED", "ACCEPTED"),
        ("ACCEPTED", "MERGED"),
    ]


def test_exactly_one_provider_call(result):
    """propose() makes exactly one LLM call."""
    assert len(result["provider"].calls) == 1


def test_revision_recorded_with_schema_version(result):
    integrator = result["integrator"]
    rev = integrator.revision_store.get(result["revision_id"])
    assert rev is not None
    assert rev.schema_revision == "v3_add_daily_balance_summary"


def test_proposal_context_immutable():
    """Sanity: ProposalContext is frozen."""
    with pytest.raises(Exception):
        PROPOSAL_CONTEXT.user_intent = "modified"


# ─────────────────────────────────────────────────────────────────────────────
# propose() works with any LLMProvider implementation (LLM-agnostic ADR-012)
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_works_with_arbitrary_provider_subclass():
    """Different provider class with same Protocol → same propose() flow."""
    from backend.sim_v2.core.recommendation.providers.base import LLMResponse

    class _MinimalProvider:
        name = "minimal"
        def complete(self, request, model=None):
            return LLMResponse(text="custom", provider="minimal", model="m1", stop_reason="end_turn")
        def validate(self):
            return True

    from backend.sim_v2.core.recommendation.anti_patterns.catalog import AntiPatternScanner
    engine = RecommendationEngine(provider=_MinimalProvider(), scanner=AntiPatternScanner())
    out = engine.propose(PROPOSAL_CONTEXT)
    assert out.proposal.type == "schema_change"
    assert out.proposal.schema_diff["raw_llm_output"] == "custom"
    assert out.provider_used == "minimal"
