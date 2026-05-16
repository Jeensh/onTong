"""UC3 G3 correction loop demo verification — W24.3.

Validates ADR-002 + ADR-005 end-to-end correction loop:
  - Scripted LLM provider returns deterministic corrected emission
  - First oracle pass catches FAIL_BREAKING (value mismatch)
  - RecommendationEngine.refine() drives a single LLM roundtrip
  - All 4 defense layers exercised (grounding / validation / oracle / review)
  - Lifecycle reaches MERGED with full audit log + revision lineage
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.sim_v2.core.recommendation.anti_patterns.catalog import AntiPatternScanner
from backend.sim_v2.core.recommendation.engine import RecommendationEngine
from backend.sim_v2.core.recommendation.providers.base import LLMRequest

from backend.sim_v2.demos.uc3_g3_correction_loop.run import (
    BUGGY_EMISSION,
    CORRECTED_EMISSION,
    ScriptedFixProvider,
    build_engine_and_integrator,
    compile_emission,
    compute_interest_baseline,
    main,
    make_fixtures,
    run_correction_loop,
)


def test_demo_main_returns_zero():
    """The W24 demo main() exits 0 — full correction loop closes."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Scripted provider — determinism + signal routing
# ─────────────────────────────────────────────────────────────────────────────


def test_scripted_provider_returns_fix_on_fail_signal():
    p = ScriptedFixProvider()
    req = LLMRequest(system="sys", user="oracle_status: FAIL_BREAKING ...")
    resp = p.complete(req)
    assert resp.text == CORRECTED_EMISSION
    assert resp.provider == "scripted-fix"
    assert len(p.calls) == 1


def test_scripted_provider_returns_placeholder_without_signal():
    p = ScriptedFixProvider()
    req = LLMRequest(system="sys", user="propose a new feature")
    resp = p.complete(req)
    assert resp.text != CORRECTED_EMISSION
    assert "placeholder" in resp.text


def test_scripted_provider_records_each_call():
    p = ScriptedFixProvider()
    for i in range(3):
        p.complete(LLMRequest(system="s", user=f"call {i}"))
    assert len(p.calls) == 3


def test_scripted_provider_validate_true():
    """Provider has no env / network deps, so validate() is unconditionally true."""
    assert ScriptedFixProvider().validate() is True


# ─────────────────────────────────────────────────────────────────────────────
# Buggy + corrected emissions compile + diverge as expected
# ─────────────────────────────────────────────────────────────────────────────


def test_buggy_emission_diverges_from_baseline():
    buggy = compile_emission(BUGGY_EMISSION)
    # Same inputs → different result (forgot /100 on rate)
    args = {"principal": Decimal("1000"), "rate": Decimal("5"), "months": 12}
    assert buggy(**args) != compute_interest_baseline(**args)


def test_corrected_emission_matches_baseline():
    fixed = compile_emission(CORRECTED_EMISSION)
    for scenario in make_fixtures().values():
        assert fixed(**scenario.inputs) == compute_interest_baseline(**scenario.inputs)


# ─────────────────────────────────────────────────────────────────────────────
# Correction loop end-to-end
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def loop_result():
    return run_correction_loop()


def test_first_oracle_fails_breaking(loop_result):
    assert loop_result["first_oracle"].aggregate_status == "FAIL_BREAKING"
    # All 3 fixtures should be FAIL_OUTPUT
    statuses = {r.status for r in loop_result["first_oracle"].by_fixture.values()}
    assert statuses == {"FAIL_OUTPUT"}


def test_second_oracle_passes_after_refine(loop_result):
    assert loop_result["second_oracle"].aggregate_status == "PASS"
    statuses = {r.status for r in loop_result["second_oracle"].by_fixture.values()}
    assert statuses == {"PASS"}


def test_exactly_one_llm_roundtrip(loop_result):
    """Scripted provider called once per refine — no retries / redundant calls."""
    assert loop_result["provider_calls"] == 1


def test_final_state_is_merged(loop_result):
    assert loop_result["final_proposal"].state == "MERGED"
    assert loop_result["revision_id"] is not None


def test_revision_recorded_in_store(loop_result):
    integrator = loop_result["integrator"]
    revision = integrator.revision_store.get(loop_result["revision_id"])
    assert revision is not None
    assert revision.proposal_id == loop_result["prop_id"]


def test_history_has_full_lifecycle(loop_result):
    """Expected 8 events: DRAFT→PROPOSED→ORACLED→DRAFT→PROPOSED→ORACLED→REVIEWED→ACCEPTED→MERGED."""
    history = loop_result["final_proposal"].history
    transitions = [(e.from_state, e.to_state) for e in history]
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


# ─────────────────────────────────────────────────────────────────────────────
# 4 defense layers — explicit per-layer assertions
# ─────────────────────────────────────────────────────────────────────────────


def test_defense_l1_grounding_passes_via_proposal_context():
    """L1 — RecommendationEngine accepts ontology_context grounding payload."""
    from backend.sim_v2.core.recommendation.engine import ProposalContext
    ctx = ProposalContext(
        plugin="banking",
        proposal_type="code_change",
        user_intent="Emit compute_interest",
        ontology_context={
            "method_fqn": "com.bank.InterestService#computeInterest",
            "java_source": "principal.multiply(rate).divide(BD_100)...",
        },
    )
    assert ctx.ontology_context["method_fqn"].startswith("com.bank.")
    # Provider call should include the grounding payload in the rendered prompt
    p = ScriptedFixProvider()
    rec = RecommendationEngine(provider=p, scanner=AntiPatternScanner())
    rec.propose(ctx)
    assert "method_fqn" in p.calls[0].user
    assert "InterestService" in p.calls[0].user


def test_defense_l2_anti_pattern_scan_clean_on_corrected_emission(loop_result):
    """L2 — refined emission carries no anti-pattern hits (no BigDecimal(...) class etc.)."""
    assert loop_result["scan_hits_after"] == []


def test_defense_l2_catches_known_anti_patterns():
    """L2 — sanity: scanner DOES catch known anti-patterns from Phase α."""
    bad = "BigDecimal(100.5)  # class-call form — phase α α2 idiom"
    hits = AntiPatternScanner().scan(bad)
    assert any(h.pattern_id == "phase_alpha_bigdecimal_class_vs_function" for h in hits)


def test_defense_l3_oracle_status_flips(loop_result):
    """L3 — verification engine flips FAIL_BREAKING → PASS after refinement."""
    assert loop_result["first_oracle"].aggregate_status  == "FAIL_BREAKING"
    assert loop_result["second_oracle"].aggregate_status == "PASS"


def test_defense_l4_user_feedback_recorded(loop_result):
    """L4 — UserFeedback ACCEPT precedes the MERGED transition."""
    prop = loop_result["final_proposal"]
    assert len(prop.user_feedback) == 1
    assert prop.user_feedback[0].decision == "ACCEPT"


# ─────────────────────────────────────────────────────────────────────────────
# G3 gate marker
# ─────────────────────────────────────────────────────────────────────────────


def test_g3_gate_correction_loop_prereq_covered():
    """G3 gate prereq — 4-layer LLM defense + correction loop activates here.

    G3 = LLM-driven proposal correction. This demo proves:
      1. Engine + provider abstraction wire up end-to-end
      2. Oracle FAIL drives refine() automatically
      3. Refined emission re-runs through Oracle and converges
      4. All 4 ADR-005 defense layers exercise
    """
    assert main() == 0
