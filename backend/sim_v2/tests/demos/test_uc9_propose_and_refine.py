"""UC9 — propose() + refine() composite demo verification — W36.2.

Validates the realistic LLM-driven workflow:
  - propose() generates initial proposal (intentionally buggy here)
  - Oracle catches the divergence
  - refine() corrects it via a 2nd LLM call
  - Re-oracle PASSes and the proposal merges

Exactly 2 LLM calls; full 8-event lifecycle DRAFT→…→MERGED.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.recommendation.providers.base import LLMRequest

from backend.sim_v2.demos.uc9_propose_and_refine.run import (
    BUGGY_EMISSION,
    CORRECTED_EMISSION,
    PROPOSAL_CONTEXT,
    ScriptedTwoCallProvider,
    main,
    run_propose_and_refine,
)


@pytest.fixture
def result():
    return run_propose_and_refine()


def test_demo_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Scripted provider — discriminates propose vs refine prompts
# ─────────────────────────────────────────────────────────────────────────────


def test_provider_returns_buggy_on_propose_prompt():
    p = ScriptedTwoCallProvider()
    resp = p.complete(LLMRequest(
        system="s",
        user="Plugin: banking\nProposal type: code_change\n...\nPropose the change.",
    ))
    assert resp.text == BUGGY_EMISSION


def test_provider_returns_corrected_on_refine_prompt():
    p = ScriptedTwoCallProvider()
    resp = p.complete(LLMRequest(
        system="s",
        user="Refine the following proposal based on hints.\n\nOriginal description: ...",
    ))
    assert resp.text == CORRECTED_EMISSION


def test_provider_records_both_calls():
    p = ScriptedTwoCallProvider()
    p.complete(LLMRequest(system="s", user="Propose the change."))
    p.complete(LLMRequest(system="s", user="Refine the following proposal."))
    assert len(p.calls) == 2


def test_provider_model_carries_call_kind():
    p = ScriptedTwoCallProvider()
    r1 = p.complete(LLMRequest(system="s", user="Propose the change."))
    r2 = p.complete(LLMRequest(system="s", user="Refine the following proposal."))
    assert "propose" in r1.model
    assert "refine"  in r2.model


# ─────────────────────────────────────────────────────────────────────────────
# Composite flow — propose → oracle FAIL → refine → oracle PASS → merge
# ─────────────────────────────────────────────────────────────────────────────


def test_first_oracle_fails_breaking(result):
    assert result["first_oracle"].aggregate_status == "FAIL_BREAKING"
    statuses = {r.status for r in result["first_oracle"].by_fixture.values()}
    assert statuses == {"FAIL_OUTPUT"}


def test_second_oracle_passes_after_refine(result):
    assert result["second_oracle"].aggregate_status == "PASS"


def test_refined_source_matches_corrected_emission(result):
    assert result["refined_source"] == CORRECTED_EMISSION


def test_exactly_two_llm_calls(result):
    """propose + refine = 2 calls. No extras / no retries."""
    assert len(result["provider"].calls) == 2


def test_call_ordering_propose_then_refine(result):
    """First call is propose-style; second is refine-style."""
    calls = result["provider"].calls
    assert not calls[0].user.startswith("Refine the following proposal")
    assert calls[1].user.startswith("Refine the following proposal")


def test_final_state_is_merged(result):
    assert result["proposal"].state == "MERGED"
    assert result["revision_id"] is not None


def test_lifecycle_transitions_match_refine_loop(result):
    """The composite flow goes through ORACLED→DRAFT→PROPOSED twice (refine + re_propose)."""
    transitions = [(e.from_state, e.to_state) for e in result["proposal"].history]
    assert transitions == [
        ("DRAFT",    "PROPOSED"),
        ("PROPOSED", "ORACLED"),
        ("ORACLED",  "DRAFT"),
        ("DRAFT",    "PROPOSED"),
        ("PROPOSED", "ORACLED"),
        ("ORACLED",  "REVIEWED"),
        ("REVIEWED", "ACCEPTED"),
        ("ACCEPTED", "MERGED"),
    ]


def test_revision_recorded_in_store(result):
    integrator = result["integrator"]
    rev = integrator.revision_store.get(result["revision_id"])
    assert rev is not None


# ─────────────────────────────────────────────────────────────────────────────
# Grounding + validation
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_prompt_carries_grounding(result):
    """propose() should expose the ontology_context entries in the LLM prompt."""
    propose_prompt = result["provider"].calls[0].user
    assert "method_fqn" in propose_prompt
    assert "InterestService" in propose_prompt
    assert "return_type"  in propose_prompt


def test_refine_prompt_carries_hints(result):
    """refine() should include the FAIL_BREAKING hint so the LLM knows to fix the numeric."""
    refine_prompt = result["provider"].calls[1].user
    assert "FAIL_BREAKING" in refine_prompt or "value mismatch" in refine_prompt


def test_proposal_context_is_code_change(result):
    """Sanity: the demo's ProposalContext targets code_change."""
    assert PROPOSAL_CONTEXT.proposal_type == "code_change"
    assert result["proposal"].type == "code_change"
