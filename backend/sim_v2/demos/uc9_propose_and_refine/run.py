"""UC9 — propose() + refine() composite (W36).

The realistic LLM-driven workflow: an initial `propose()` often gets the
emission wrong, and `refine()` iteratively corrects it. This demo runs both
halves of the LLM defense pipeline against the SAME proposal:

  1. User intent → `RecommendationEngine.propose()` → 1st LLM call → BUGGY
     emission (intentionally — we want to exercise the correction loop)
  2. Submit → request_oracle → FAIL_BREAKING (numeric divergence)
  3. `RecommendationEngine.refine()` → 2nd LLM call → CORRECTED emission
  4. Integrator.refine_proposal applies the fix + re_propose
  5. request_oracle → PASS → review (ACCEPT) → merge

Same ScriptedTwoCallProvider serves both calls — distinguishes propose vs
refine by inspecting the prompt content (propose prompt has the user_intent
verbatim, refine prompt mentions "Refine the following proposal").

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc9_propose_and_refine.run
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
from backend.sim_v2.core.recommendation.providers.base import LLMRequest, LLMResponse
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)


# ─────────────────────────────────────────────────────────────────────────────
# Ground truth + emissions
# ─────────────────────────────────────────────────────────────────────────────


def compute_interest_baseline(principal: Decimal, rate: Decimal, months: int) -> Decimal:
    return principal * rate / Decimal("100") * Decimal(months) / Decimal("12")


BUGGY_EMISSION = """\
def compute_interest(principal, rate, months):
    return principal * rate * Decimal(months) / Decimal("12")
"""

CORRECTED_EMISSION = """\
def compute_interest(principal, rate, months):
    return principal * rate / Decimal("100") * Decimal(months) / Decimal("12")
"""


# ─────────────────────────────────────────────────────────────────────────────
# Scripted two-call provider
# ─────────────────────────────────────────────────────────────────────────────


class ScriptedTwoCallProvider:
    """Distinguishes propose vs refine by inspecting the prompt.

    - propose() prompt has "Propose the change" + user_intent verbatim.
    - refine() prompt begins with "Refine the following proposal".

    Returns BUGGY on propose, CORRECTED on refine.
    """
    name = "scripted-two-call"

    def __init__(self) -> None:
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        self.calls.append(request)
        prompt = request.user
        if prompt.startswith("Refine the following proposal"):
            text = CORRECTED_EMISSION
            kind = "refine"
        else:
            text = BUGGY_EMISSION
            kind = "propose"
        return LLMResponse(
            text=text,
            provider=self.name,
            model=f"scripted-two-call:{kind}",
            input_tokens=len(prompt),
            output_tokens=len(text),
            stop_reason="end_turn",
        )

    def validate(self) -> bool:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures + helpers
# ─────────────────────────────────────────────────────────────────────────────


def compile_emission(source: str) -> Any:
    g: dict[str, Any] = {"Decimal": Decimal}
    exec(compile(source, "<uc9>", "exec"), g)
    return g["compute_interest"]


def make_fixtures() -> dict[str, Scenario]:
    return {
        "F1": Scenario(fixture_id="F1",
                       inputs={"principal": Decimal("1000"),  "rate": Decimal("5"),    "months": 12}),
        "F2": Scenario(fixture_id="F2",
                       inputs={"principal": Decimal("50000"), "rate": Decimal("4.5"),  "months": 36}),
        "F3": Scenario(fixture_id="F3",
                       inputs={"principal": Decimal("250000"),"rate": Decimal("3.25"), "months": 60}),
    }


PROPOSAL_CONTEXT = ProposalContext(
    plugin="banking",
    proposal_type="code_change",
    user_intent="Translate Java InterestService.computeInterest(BigDecimal,BigDecimal,int) to Python",
    ontology_context={
        "method_fqn": "com.bank.InterestService#computeInterest",
        "return_type": "java.math.BigDecimal",
        "params": ["BigDecimal principal", "BigDecimal rate", "int months"],
    },
)


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────


def run_propose_and_refine() -> dict[str, Any]:
    provider = ScriptedTwoCallProvider()
    rec_engine = RecommendationEngine(provider=provider, scanner=AntiPatternScanner())

    fixtures = make_fixtures()
    # translated_fn starts as placeholder — swapped after each propose/refine
    scen_engine = ScenarioVerificationEngine(
        translated_fn=lambda **_: None,  # placeholder; overwritten before first oracle
        baseline_fn=compute_interest_baseline,
        fixtures=fixtures,
    )
    integrator = Integrator(verification=scen_engine, recommendation=rec_engine)

    # 1) propose() → 1st LLM call → BUGGY emission
    rec_out = rec_engine.propose(PROPOSAL_CONTEXT)
    proposal = rec_out.proposal
    # Mirror the buggy source into a place the engine can execute
    scen_engine.translated_fn = compile_emission(proposal.code_diff["raw_llm_output"])

    # 2) Submit + first oracle (expected FAIL_BREAKING)
    prop_id = integrator.submit_proposal(proposal)
    first_oracle = integrator.request_oracle(prop_id, list(fixtures.keys()))

    # 3) refine() → 2nd LLM call → CORRECTED emission
    refined = rec_engine.refine(integrator.get_proposal(prop_id), hints={
        "oracle_status": first_oracle.aggregate_status,
        "diff_summary":  first_oracle.summary,
    })
    refined_source = refined.code_diff["refined_llm_output"]

    # 4) Apply refinement via Integrator + swap engine fn + re-propose
    integrator.refine_proposal(prop_id, ProposalRefinement(
        code_diff_update={"python_source": refined_source},
        reason="propose was buggy; refine fixed /100",
    ))
    scen_engine.translated_fn = compile_emission(refined_source)
    integrator.re_propose(prop_id)

    # 5) Second oracle (expected PASS) → review → merge
    second_oracle = integrator.request_oracle(prop_id, list(fixtures.keys()))
    rev_id = None
    if second_oracle.aggregate_status == "PASS":
        integrator.review_proposal(prop_id, UserFeedback(
            decision="ACCEPT", timestamp=datetime.now(timezone.utc), user="dev",
            comments="refined emission matches baseline",
        ))
        rev_id = integrator.merge_proposal(
            prop_id=prop_id,
            ontology_revision="banking@2026-05-15",
            code_revision="git:propose-refine-demo",
            schema_revision="alembic:v5_schema_layer",
            created_by="dev",
        )

    return {
        "provider":       provider,
        "rec_out":        rec_out,
        "proposal":       integrator.get_proposal(prop_id),
        "first_oracle":   first_oracle,
        "second_oracle":  second_oracle,
        "refined_source": refined_source,
        "revision_id":    rev_id,
        "integrator":     integrator,
    }


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text: str) -> None:
    print("─" * 78)
    print(text)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print("UC9 — propose() + refine() composite (W36)")
    print("=" * 78)
    print()

    s = run_propose_and_refine()
    prop = s["proposal"]

    _banner("Step 1 — propose() → BUGGY emission")
    print(f"  provider calls so far : 1")
    print(f"  proposal type         : {prop.type}")
    print(f"  initial emission (buggy):")
    for line in BUGGY_EMISSION.rstrip().split("\n"):
        print(f"    | {line}")
    print()

    _banner("Step 2 — 1st oracle (expected FAIL_BREAKING)")
    o1 = s["first_oracle"]
    print(f"  aggregate_status = {o1.aggregate_status}")
    print(f"  summary          = {o1.summary}")
    for fid, r in o1.by_fixture.items():
        print(f"    {fid:<4} {r.status:<12} {r.output_diff.summary}")
    print()

    _banner("Step 3 — refine() → CORRECTED emission")
    print(f"  provider calls so far : {len(s['provider'].calls)}")
    print(f"  refined source:")
    for line in s["refined_source"].rstrip().split("\n"):
        print(f"    | {line}")
    print()

    _banner("Step 4 — 2nd oracle (expected PASS)")
    o2 = s["second_oracle"]
    print(f"  aggregate_status = {o2.aggregate_status}")
    for fid, r in o2.by_fixture.items():
        print(f"    {fid:<4} {r.status:<6} baseline={r.java_baseline_output} proposal={r.python_proposal_output}")
    print()

    _banner("Final state — review → merge")
    print(f"  proposal.state : {prop.state}")
    print(f"  revision id    : {s['revision_id']}")
    print(f"  total LLM calls: {len(s['provider'].calls)}")
    print(f"  lifecycle audit ({len(prop.history)} events):")
    for i, ev in enumerate(prop.history, 1):
        print(f"    {i}. {ev.from_state:<10} → {ev.to_state:<10} actor={ev.actor}")
    print()

    success = (
        prop.state == "MERGED"
        and s["revision_id"] is not None
        and s["first_oracle"].aggregate_status  == "FAIL_BREAKING"
        and s["second_oracle"].aggregate_status == "PASS"
        and len(s["provider"].calls) == 2
    )
    if success:
        print("✓ Final verdict: PASS — both halves of LLM pipeline fire in single flow")
        print("    propose() → BUGGY → oracle FAIL → refine() → CORRECTED → oracle PASS → MERGED")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
