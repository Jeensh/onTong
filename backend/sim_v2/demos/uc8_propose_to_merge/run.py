"""UC8 — propose() → submit → merge end-to-end (W35).

Prior demos (uc3, uc5) exercise `RecommendationEngine.refine()` — the
correction-loop side of the LLM defense pipeline. This demo closes the other
half: `RecommendationEngine.propose()` generates a fresh proposal from a
`ProposalContext` (user intent + ontology grounding) and the proposal flows
through the same Integrator lifecycle to MERGED.

Banking scenario:
  - User intent: "Add a daily_balance_summary table for reporting"
  - Ontology grounding: existing account/transaction baseline
  - ScriptedProposeProvider returns canned structured response describing the
    additive schema diff
  - propose() builds a Proposal in DRAFT with the LLM output stashed in
    schema_diff["raw_llm_output"]
  - Anti-pattern scanner runs (Layer 2 defense)
  - Integrator.submit_proposal → ORACLED → REVIEWED → MERGED

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc8_propose_to_merge.run
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

from backend.sim_v2.core.integrator.integrator import Integrator
from backend.sim_v2.core.integrator.proposal import (
    OracleResult as ProposalOracleResult,
    Proposal,
    UserFeedback,
)
from backend.sim_v2.core.recommendation.anti_patterns.catalog import AntiPatternScanner
from backend.sim_v2.core.recommendation.engine import (
    ProposalContext,
    RecommendationEngine,
)
from backend.sim_v2.core.recommendation.providers.base import (
    LLMRequest,
    LLMResponse,
)
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleRequest,
    OracleResult,
    OutputDiff,
    TraceDiff,
)


# ─────────────────────────────────────────────────────────────────────────────
# Scripted provider — returns a structured schema diff payload
# ─────────────────────────────────────────────────────────────────────────────


CANNED_DIFF_PAYLOAD = """\
{
  "kind": "schema_change",
  "migration_version": "v3_add_daily_balance_summary",
  "new_tables": [
    {
      "table_name": "daily_balance_summary",
      "columns": [
        {"name": "id",            "type": "BIGINT",        "primary_key": true},
        {"name": "account_id",    "type": "BIGINT",        "nullable": false},
        {"name": "as_of_date",    "type": "DATE",          "nullable": false},
        {"name": "closing_balance","type": "NUMERIC(15,2)", "nullable": false}
      ],
      "indexes": [
        {"name": "idx_dbs_account_date", "columns": ["account_id", "as_of_date"], "unique": true}
      ]
    }
  ],
  "forward_ddl": "CREATE TABLE daily_balance_summary (...);",
  "backward_ddl": "DROP TABLE daily_balance_summary;",
  "rationale": "Reporting workload requires pre-aggregated daily balances. Additive only — no impact on existing reads."
}"""


class ScriptedProposeProvider:
    """Deterministic LLM stand-in for the propose() demo.

    Behavior:
      - If user prompt mentions "daily_balance_summary", return the canned
        structured diff.
      - Otherwise return a benign refusal so the test for clean validation
        can still cover the no-actionable-signal case.
    """
    name = "scripted-propose"

    def __init__(self) -> None:
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        self.calls.append(request)
        prompt = request.user
        if "daily_balance_summary" in prompt:
            text = CANNED_DIFF_PAYLOAD
        else:
            text = "(no actionable signal — provide a concrete user_intent)"
        return LLMResponse(
            text=text,
            provider=self.name,
            model="scripted-propose:demo",
            input_tokens=len(prompt),
            output_tokens=len(text),
            stop_reason="end_turn",
        )

    def validate(self) -> bool:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Verification engine — schema_change auto-passes (we're not running fixtures)
# ─────────────────────────────────────────────────────────────────────────────


class _AutoPassSchemaEngine:
    """Trivial VerificationEngine that returns PASS — schema_change demos don't
    have R3/R4 fixtures wired here; the focus is propose() → merge."""

    def run_oracle(self, request: OracleRequest) -> OracleResult:
        results: dict[str, FixtureOracleResult] = {}
        for fid in request.fixture_subset or ["smoke"]:
            results[fid] = FixtureOracleResult(
                fixture_id=fid,
                java_baseline_output=None,
                python_proposal_output=None,
                output_diff=OutputDiff(is_equivalent=True, summary="auto-pass (no fixture exercise)"),
                trace_diff=TraceDiff(is_equivalent=True, summary="auto-pass trace"),
                status="PASS",
            )
        return OracleResult(
            proposal_id=request.proposal_id,
            by_fixture=results,
            aggregate_status="PASS",
            summary=f"{len(results)} fixture(s) auto-pass",
        )


class _NoopRecommendation:
    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        return proposal


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────


def build_engine_and_integrator() -> tuple[
    RecommendationEngine,
    ScriptedProposeProvider,
    Integrator,
]:
    provider = ScriptedProposeProvider()
    rec_engine = RecommendationEngine(provider=provider, scanner=AntiPatternScanner())
    integrator = Integrator(
        verification=_AutoPassSchemaEngine(),
        recommendation=_NoopRecommendation(),
    )
    return rec_engine, provider, integrator


PROPOSAL_CONTEXT = ProposalContext(
    plugin="banking",
    proposal_type="schema_change",
    user_intent=(
        "Add a daily_balance_summary table that aggregates account balances "
        "by day for reporting. Should be additive — no impact on existing reads."
    ),
    ontology_context={
        "existing_tables": ["public.account", "public.transaction"],
        "primary_aggregate": "account.balance",
        "freq": "daily snapshot",
    },
)


def run_propose_to_merge() -> dict[str, Any]:
    rec_engine, provider, integrator = build_engine_and_integrator()

    # 1) propose() — LLM generates the proposal
    rec_result = rec_engine.propose(PROPOSAL_CONTEXT)
    proposal = rec_result.proposal

    # 2) Submit to integrator
    prop_id = integrator.submit_proposal(proposal)

    # 3) Oracle (auto-pass for schema_change in this demo)
    oracle_result = integrator.request_oracle(prop_id, ["smoke"])

    # 4) Review (ACCEPT) → Merge
    if oracle_result.aggregate_status == "PASS":
        integrator.review_proposal(prop_id, UserFeedback(
            decision="ACCEPT",
            timestamp=datetime.now(timezone.utc),
            user="dba",
            comments="canned diff looks clean — accept",
        ))
        rev_id = integrator.merge_proposal(
            prop_id=prop_id,
            ontology_revision="banking@2026-05-15",
            code_revision="git:propose-demo",
            schema_revision="v3_add_daily_balance_summary",
            created_by="dba",
        )
    else:
        rev_id = None

    return {
        "rec_result":   rec_result,
        "proposal":     integrator.get_proposal(prop_id),
        "provider":     provider,
        "oracle":       oracle_result,
        "revision_id":  rev_id,
        "integrator":   integrator,
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
    print("UC8 — propose() → submit → merge end-to-end (W35)")
    print("=" * 78)
    print()

    state = run_propose_to_merge()
    prop = state["proposal"]
    rec_result = state["rec_result"]

    _banner("Step 1 — ProposalContext + propose()")
    print(f"  plugin         : {PROPOSAL_CONTEXT.plugin}")
    print(f"  proposal_type  : {PROPOSAL_CONTEXT.proposal_type}")
    print(f"  user_intent    : {PROPOSAL_CONTEXT.user_intent}")
    print(f"  grounding keys : {list(PROPOSAL_CONTEXT.ontology_context.keys())}")
    print()

    _banner("Step 2 — RecommendationEngine.propose() output")
    print(f"  provider_used  : {rec_result.provider_used}")
    print(f"  validation     : {rec_result.validation.summary}")
    print(f"  raw response ({len(rec_result.raw_response.splitlines())} lines, snippet):")
    snippet = rec_result.raw_response.split("\n", 6)[:6]
    for line in snippet:
        print(f"    | {line}")
    print(f"  proposal.id    : {prop.id}")
    print(f"  proposal.state : {prop.state} (post-submit, expected PROPOSED→ORACLED→REVIEWED→ACCEPTED→MERGED)")
    print()

    _banner("Step 3 — Lifecycle audit")
    for i, ev in enumerate(prop.history, 1):
        print(f"  {i}. {ev.from_state:<10} → {ev.to_state:<10} (actor={ev.actor})")
    print()

    _banner("Final state")
    print(f"  proposal.state : {prop.state}")
    print(f"  revision id    : {state['revision_id']}")
    print(f"  provider calls : {len(state['provider'].calls)}")
    print(f"  anti-pattern hits in LLM output : {len(rec_result.validation.hits)}")
    print()

    success = (
        prop.state == "MERGED"
        and state["revision_id"] is not None
        and len(state["provider"].calls) == 1
        and state["oracle"].aggregate_status == "PASS"
    )
    if success:
        print("✓ Final verdict: PASS — propose() → merge full cycle closes")
        print("  Closes the other half of the LLM defense pipeline (refine() in uc3/uc5)")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
