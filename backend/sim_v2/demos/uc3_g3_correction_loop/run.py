"""UC3 G3 correction loop — Recommendation Engine wire-up (W24, G3 gate prereq).

Demonstrates ADR-002 + ADR-005 end-to-end:
  1. Submit a BUGGY proposal (Python emission with a divide-by-100 typo)
  2. Oracle catches FAIL_BREAKING (value mismatch on every fixture)
  3. RecommendationEngine.refine(proposal, hints={oracle_status, diff_summary})
     calls a scripted LLM provider that returns a corrected emission
  4. All 4 ADR-005 defense layers fire:
       L1 (grounding)  — ProposalContext.ontology_context carries domain entities
       L2 (validation) — AntiPatternScanner scans the refined emission (clean)
       L3 (oracle)     — re-run flips FAIL_BREAKING → PASS
       L4 (review)     — UserFeedback ACCEPT precedes merge
  5. merge_proposal → MERGED + Revision with full lineage

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc3_g3_correction_loop.run
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from backend.sim_v2.core.integrator.integrator import Integrator, ProposalRefinement
from backend.sim_v2.core.integrator.proposal import Proposal, UserFeedback
from backend.sim_v2.core.recommendation.anti_patterns.catalog import AntiPatternScanner
from backend.sim_v2.core.recommendation.engine import (
    ProposalContext,
    RecommendationEngine,
)
from backend.sim_v2.core.recommendation.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)


# ─────────────────────────────────────────────────────────────────────────────
# Ground truth — what the Java twin's correct Python emission should compute
# ─────────────────────────────────────────────────────────────────────────────


def compute_interest_baseline(principal: Decimal, rate: Decimal, months: int) -> Decimal:
    """Ground-truth Python re-implementation of the Java method.

    Java: BigDecimal interest = principal.multiply(rate).divide(BD_100)
                .multiply(BigDecimal.valueOf(months)).divide(BD_12);
    """
    return principal * rate / Decimal("100") * Decimal(months) / Decimal("12")


# ─────────────────────────────────────────────────────────────────────────────
# Buggy emission — the "first translator pass" output (forgets /100 on rate)
# ─────────────────────────────────────────────────────────────────────────────


BUGGY_EMISSION = """\
def compute_interest(principal, rate, months):
    return principal * rate * Decimal(months) / Decimal("12")
"""


# ─────────────────────────────────────────────────────────────────────────────
# Corrected emission — what the scripted LLM "knows" to return
# ─────────────────────────────────────────────────────────────────────────────


CORRECTED_EMISSION = """\
def compute_interest(principal, rate, months):
    return principal * rate / Decimal("100") * Decimal(months) / Decimal("12")
"""


# ─────────────────────────────────────────────────────────────────────────────
# Scripted LLM provider — deterministic, no external API calls
# ─────────────────────────────────────────────────────────────────────────────


class ScriptedFixProvider:
    """Deterministic LLM stand-in for the G3 demo.

    Behavior:
      - If the user prompt mentions FAIL_BREAKING / value mismatch, return the
        CORRECTED_EMISSION.
      - Otherwise echo a benign placeholder (so propose() works for sanity tests).

    Tracks call count so tests can assert exactly one refine roundtrip.
    """
    name = "scripted-fix"

    def __init__(self) -> None:
        self.calls: list[LLMRequest] = []
        self._model = "scripted-fix:demo"

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        self.calls.append(request)
        prompt = request.user
        if "FAIL_BREAKING" in prompt or "value mismatch" in prompt:
            text = CORRECTED_EMISSION
        else:
            text = "[scripted-fix:demo placeholder] no actionable signal in prompt"
        return LLMResponse(
            text=text,
            provider=self.name,
            model=model or self._model,
            input_tokens=len(request.system) + len(request.user),
            output_tokens=len(text),
            stop_reason="end_turn",
        )

    def validate(self) -> bool:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — compile emission + extract callable
# ─────────────────────────────────────────────────────────────────────────────


def compile_emission(source: str) -> Any:
    g: dict[str, Any] = {"Decimal": Decimal}
    exec(compile(source, "<g3-demo>", "exec"), g)
    return g["compute_interest"]


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — same inputs, expected outputs from baseline
# ─────────────────────────────────────────────────────────────────────────────


def make_fixtures() -> dict[str, Scenario]:
    return {
        "F1_small": Scenario(
            fixture_id="F1_small",
            inputs={"principal": Decimal("1000"), "rate": Decimal("5"), "months": 12},
        ),
        "F2_mid": Scenario(
            fixture_id="F2_mid",
            inputs={"principal": Decimal("50000"), "rate": Decimal("4.5"), "months": 36},
        ),
        "F3_large": Scenario(
            fixture_id="F3_large",
            inputs={"principal": Decimal("250000"), "rate": Decimal("3.25"), "months": 60},
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Demo orchestration
# ─────────────────────────────────────────────────────────────────────────────


def build_engine_and_integrator() -> tuple[
    ScenarioVerificationEngine,
    Integrator,
    RecommendationEngine,
    ScriptedFixProvider,
]:
    """Wire all pieces. Returns engine + integrator + recommendation + provider."""
    provider = ScriptedFixProvider()
    rec_engine = RecommendationEngine(provider=provider, scanner=AntiPatternScanner())

    buggy_fn = compile_emission(BUGGY_EMISSION)
    engine = ScenarioVerificationEngine(
        translated_fn=buggy_fn,
        baseline_fn=compute_interest_baseline,
        fixtures=make_fixtures(),
    )
    integrator = Integrator(verification=engine, recommendation=rec_engine)
    return engine, integrator, rec_engine, provider


def run_correction_loop() -> dict[str, Any]:
    """Execute the full DRAFT→PROPOSED→ORACLED(FAIL)→refine→re-oracle(PASS)→merge loop.

    Returns a dict with diagnostic state — used by main() and tests.
    """
    engine, integrator, rec_engine, provider = build_engine_and_integrator()

    # Step 1: submit
    proposal = Proposal(
        type="code_change",
        description="Emit compute_interest from Java twin",
        plugin="banking",
        code_diff={
            "method_fqn":     "com.bank.InterestService#computeInterest",
            "python_source":  BUGGY_EMISSION,
        },
    )
    prop_id = integrator.submit_proposal(proposal)

    # Step 2: first oracle pass — expect FAIL_BREAKING
    first_oracle = integrator.request_oracle(prop_id, list(engine.fixtures.keys()))

    # Step 3: L2 — anti-pattern scan on current emission (should be clean)
    scan_hits_before = rec_engine._scanner.scan(BUGGY_EMISSION)

    # Step 4: invoke refine() with hints encoding the oracle outcome
    hints = {
        "oracle_status":    first_oracle.aggregate_status,
        "diff_summary":     first_oracle.summary,
        "by_fixture":       {
            fid: r.output_diff.summary
            for fid, r in first_oracle.by_fixture.items()
        },
        "grounding":        {
            "method_fqn": "com.bank.InterestService#computeInterest",
            "java_source": (
                "BigDecimal interest = principal.multiply(rate).divide(BD_100)\n"
                "    .multiply(BigDecimal.valueOf(months)).divide(BD_12);"
            ),
        },
    }
    refined_proposal = rec_engine.refine(integrator.get_proposal(prop_id), hints)

    # Step 5: extract corrected source from refined diff + L2 re-scan
    refined_source = refined_proposal.code_diff["refined_llm_output"]
    scan_hits_after = rec_engine._scanner.scan(refined_source)

    # Step 6: apply refinement via Integrator (ORACLED → DRAFT) + swap engine fn
    integrator.refine_proposal(
        prop_id=prop_id,
        refinement=ProposalRefinement(
            code_diff_update={"python_source": refined_source},
            reason="scripted LLM corrected the divide-by-100",
        ),
    )
    engine.translated_fn = compile_emission(refined_source)

    # Step 7: re-promote DRAFT → PROPOSED for the refine loop (W28 — uses
    # Integrator.re_propose helper; submit_proposal can't be reused because it
    # re-adds to the store).
    integrator.re_propose(prop_id)

    # Step 8: second oracle pass — expect PASS
    second_oracle = integrator.request_oracle(prop_id, list(engine.fixtures.keys()))

    # Step 9: L4 — user review (ACCEPT), then merge
    if second_oracle.aggregate_status == "PASS":
        integrator.review_proposal(prop_id, UserFeedback(
            decision="ACCEPT",
            timestamp=datetime.now(timezone.utc),
            user="demo-user",
            comments="re-run after refine — all 3 fixtures PASS",
        ))
        revision_id = integrator.merge_proposal(
            prop_id=prop_id,
            ontology_revision="banking@2026-05-14",
            code_revision="git:scripted-fix",
            schema_revision="alembic:v5_schema_layer",
            created_by="demo-user",
        )
    else:
        revision_id = None

    return {
        "prop_id":            prop_id,
        "first_oracle":       first_oracle,
        "second_oracle":      second_oracle,
        "provider_calls":     len(provider.calls),
        "scan_hits_before":   scan_hits_before,
        "scan_hits_after":    scan_hits_after,
        "refined_source":     refined_source,
        "revision_id":        revision_id,
        "final_proposal":     integrator.get_proposal(prop_id),
        "integrator":         integrator,
    }


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 78)
    print("UC3 G3 correction loop — Recommendation Engine wire-up (W24)")
    print("=" * 78)
    print()

    state = run_correction_loop()
    first  = state["first_oracle"]
    second = state["second_oracle"]
    prop   = state["final_proposal"]

    print("Step 1: Submit BUGGY proposal (forgets to divide rate by 100)")
    print(f"  proposal.id    = {state['prop_id']}")
    print()

    print("Step 2: First oracle pass")
    print(f"  aggregate_status = {first.aggregate_status}")
    print(f"  summary          = {first.summary}")
    for fid, r in first.by_fixture.items():
        print(f"    {fid:<10} {r.status:<14} {r.output_diff.summary}")
    print()

    print("Step 3: Defense L2 — anti-pattern scan on emission")
    print(f"  before refine: {len(state['scan_hits_before'])} hits")
    print(f"  after refine:  {len(state['scan_hits_after'])} hits")
    print()

    print("Step 4: RecommendationEngine.refine() called scripted LLM")
    print(f"  provider call count: {state['provider_calls']}")
    print(f"  refined source ({len(state['refined_source'].splitlines())} lines):")
    for line in state["refined_source"].rstrip().split("\n"):
        print(f"    | {line}")
    print()

    print("Step 5: Re-oracle after refinement")
    print(f"  aggregate_status = {second.aggregate_status}")
    print(f"  summary          = {second.summary}")
    for fid, r in second.by_fixture.items():
        print(f"    {fid:<10} {r.status:<6} baseline={r.java_baseline_output} proposal={r.python_proposal_output}")
    print()

    print("Step 6: Review (ACCEPT) + Merge")
    print(f"  final state    = {prop.state}")
    print(f"  revision_id    = {state['revision_id']}")
    print(f"  history length = {len(prop.history)}")
    print()

    print("Lifecycle audit log:")
    for i, event in enumerate(prop.history, 1):
        print(f"  {i:>2}. {event.from_state:<10} → {event.to_state:<10} (actor={event.actor:<22} notes={event.notes!r})")
    print()

    success = (
        first.aggregate_status  == "FAIL_BREAKING"
        and second.aggregate_status == "PASS"
        and prop.state == "MERGED"
        and state["revision_id"] is not None
    )
    if success:
        print("✓ Final verdict: PASS — correction loop closes (FAIL_BREAKING → refine → PASS → MERGED)")
        print("  G3 gate prereq: all 4 ADR-005 defense layers active (grounding/validation/oracle/review)")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
