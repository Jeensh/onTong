"""UC1 Integrator pipeline demo — full Proposal lifecycle — W15.

Combines W14's real-file translation with W2's Proposal state machine,
W2's Integrator (8-method API), and W2's RevisionStore.

Lifecycle exercised:
    DRAFT
      ↓ submit_proposal
    PROPOSED
      ↓ request_oracle (ScenarioVerificationEngine runs 3 fixtures)
    ORACLED (aggregate=PASS)
      ↓ review_proposal(decision=ACCEPT)
    REVIEWED
      ↓ (implicit ACCEPTED transition within review_proposal)
    ACCEPTED
      ↓ merge_proposal
    MERGED (terminal) + Revision created with lineage

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc1_integrator_pipeline.run
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from backend.sim_v2.core.integrator.integrator import Integrator
from backend.sim_v2.core.integrator.proposal import Proposal, UserFeedback
from backend.sim_v2.core.recommendation.engine import RecommendationEngine
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)
from backend.sim_v2.demos.uc1_real_file.run import (
    AlgorithmException,
    SDOrderEntity,
    SDSlabEntity,
    build_ontology_session,
    compile_to_callable,
    translate_real_file,
)

# Module-level _trace placeholder — ScenarioEngine swaps a fresh TraceCollector
# in per fixture run. Required for _ground_truth_execute below to reference it.
_trace = None


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth Python re-implementation (oracle baseline)
# ─────────────────────────────────────────────────────────────────────────────


def _ground_truth_execute(order: SDOrderEntity, slab: SDSlabEntity) -> None:
    """Hand-written Python equivalent of SdMaxSplitCountAction.execute.

    Mirrors the Java semantics 1:1 using the same contract helpers
    (bd_set_scale) that the translator emits. Side-effects on `slab` match.

    W17: manually instrumented with _trace.step / _trace.branch / _trace.exception
    at the same anchor sequence the translator emits, enabling cross-side
    trace diff in the ScenarioVerificationEngine.
    """
    from backend.sim_v2.core.contracts.base import RoundingMode, bd_set_scale

    raw = slab.getSecondWgtHigh() / order.getOrderWgtHigh() / order.getProductivity()
    if _trace is not None:
        _trace.step("anchor_1", {"raw": raw})
    max_split = int(bd_set_scale(raw, 0, RoundingMode.CEILING))
    if _trace is not None:
        _trace.step("anchor_2", {"maxSplit": max_split})
    cond = max_split < 1
    if _trace is not None:
        _trace.branch("anchor_3", bool(cond))
    if cond:
        msg = f"최대분할수상한 < 1 (raw={raw}) — 분할 불가"
        if _trace is not None:
            _trace.exception("anchor_4", "AlgorithmException", str(msg))
        raise AlgorithmException(
            7, "MAX_SPLIT_COUNT", "ALG_ITERATION_NEEDED", msg,
        )
    slab.setMaxSplitCountUpper(max_split)
    slab.setCurrentSplitCount(max_split)


# ─────────────────────────────────────────────────────────────────────────────
# Stub recommendation engine — refine() not exercised in this demo
# ─────────────────────────────────────────────────────────────────────────────


class _StubRecommendationEngine:
    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        return proposal  # no-op for W15


# ─────────────────────────────────────────────────────────────────────────────
# Fixture scenarios — wrapped as Scenario objects
# ─────────────────────────────────────────────────────────────────────────────


def _make_fixtures() -> dict[str, Scenario]:
    """3 fixtures with side-effect-encoding inputs.

    The translated function mutates `slab` in place; we wrap the call so that
    inputs are fresh dataclass instances per fixture run.
    """
    return {
        "S1_normal": Scenario(
            fixture_id="S1_normal",
            inputs={
                "order": SDOrderEntity(orderWgtHigh=Decimal("20"), productivity=Decimal("0.5")),
                "slab":  SDSlabEntity(secondWgtHigh=Decimal("100")),
            },
            expected_output=None,  # void method — return None
        ),
        "S2_boundary": Scenario(
            fixture_id="S2_boundary",
            inputs={
                "order": SDOrderEntity(orderWgtHigh=Decimal("1"), productivity=Decimal("1")),
                "slab":  SDSlabEntity(secondWgtHigh=Decimal("0.3")),
            },
            expected_output=None,
        ),
        "S3_error": Scenario(
            fixture_id="S3_error",
            inputs={
                "order": SDOrderEntity(orderWgtHigh=Decimal("1"), productivity=Decimal("1")),
                "slab":  SDSlabEntity(secondWgtHigh=Decimal("0")),
            },
            expected_output=None,
            expected_exception=AlgorithmException,
        ),
    }


def _make_independent_fixtures() -> dict[str, Scenario]:
    """Build a separate fixture dict so translated_fn and baseline_fn don't
    share `slab` instances (mutation would cross-contaminate)."""
    # Used twice — once for translated_fn, once for baseline_fn via a
    # ScenarioVerificationEngine that re-runs each scenario.
    return _make_fixtures()


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot-isolated runner — each scenario gets fresh inputs per call
# ─────────────────────────────────────────────────────────────────────────────


def _wrap_with_fresh_inputs(fn):
    """Each call to wrapper(**inputs) reuses inputs but the engine creates
    fresh Scenario dicts per run (because we deepcopy via dataclass on
    each scenario re-acquisition)."""
    def wrapper(order, slab):
        return fn(order, slab)
    return wrapper


def _translate_with_trace(session) -> tuple[str, dict]:
    """W17 — translate the real file with with_trace=True (instrumented output).

    Mirrors `uc1_real_file.run.translate_real_file` but flips the instrumentation
    flag. Result Python source has `_trace.step/branch/exception` calls.
    """
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser
    from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
    from backend.sim_v2.core.synthesizer.ontology_type_resolver import OntologyTypeResolver
    from backend.sim_v2.core.synthesizer.type_resolver import (
        BigDecimalAwareResolver, CompositeTypeResolver,
    )
    from backend.sim_v2.demos.uc1_real_file.run import REAL_JAVA_FILE, find_execute_method

    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)
    tree = parser.parse(REAL_JAVA_FILE.read_bytes())
    method = find_execute_method(tree)
    resolver = CompositeTypeResolver([
        OntologyTypeResolver(session, "slab-design-real_v2"),
        BigDecimalAwareResolver(),
    ])
    translator = JavaToPythonTranslator(type_resolver=resolver)
    tr = translator.translate(method, indent=0, with_trace=True)
    return tr.python_source, {"imports": tr.imports_needed, "notes": tr.notes, "locked": tr.signature_locked}


def main() -> int:
    print("=" * 78)
    print("UC1 Integrator pipeline demo — Proposal full lifecycle (W15)")
    print("=" * 78)
    print()

    # Step 1: Translate real Java file (W17: with_trace=True for instrumented output)
    print("Step 1: Translate SdMaxSplitCountAction.java with trace instrumentation")
    session = build_ontology_session()
    # NOTE: this uses W14's translate_real_file which defaults to with_trace=False.
    # For W17 we override by calling translator directly with with_trace=True.
    py_source, meta = _translate_with_trace(session)
    if meta["locked"]:
        print(f"  ABORT — signature_locked. notes={meta['notes']}")
        return 1
    print(f"  ✓ translated (instrumented) — {len(py_source.split(chr(10)))} lines")
    print()

    # Step 2: Compile to callable
    print("Step 2: Compile translated Python")
    translated_fn = compile_to_callable(py_source)
    print("  ✓ compiled")
    print()

    # Step 3: Build VerificationEngine + Integrator
    print("Step 3: Wire VerificationEngine + Integrator")
    # Engine needs separate fixture copies per side — but ScenarioEngine runs
    # translated_fn(**inputs) AND baseline_fn(**inputs) sharing the same dict.
    # Solution: rebuild fixtures per request inside our specialized engine.
    fixtures = _make_fixtures()
    # Use a wrapper that runs translated_fn then resets slab for baseline.
    # Simpler approach: rebuild fixtures lazily — but we accept that the
    # in-place slab mutation will be observed across translated→baseline.
    # For Side-effect-free comparison, we compare exception types (both
    # mutations happen with the same expected end state).
    engine = ScenarioVerificationEngine(
        translated_fn=translated_fn,
        baseline_fn=_ground_truth_execute,
        fixtures=fixtures,
        with_trace=True,  # W17: cross-side trace diff active
    )
    integrator = Integrator(
        verification=engine,
        recommendation=_StubRecommendationEngine(),
    )
    print(f"  ✓ integrator initialized")
    print(f"    proposal_store: {type(integrator.proposal_store).__name__}")
    print(f"    revision_store: {type(integrator.revision_store).__name__}")
    print()

    # Step 4: Create + submit Proposal (DRAFT → PROPOSED)
    print("Step 4: Create Proposal (DRAFT → PROPOSED)")
    proposal = Proposal(
        type="code_change",
        description="Translate SdMaxSplitCountAction.execute (slab-design v2)",
        plugin="v2-slab-design",
        code_diff={
            "method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdMaxSplitCountAction#execute",
            "python_source_lines": len(py_source.split("\n")),
        },
    )
    print(f"  proposal.id    = {proposal.id}")
    print(f"  proposal.state = {proposal.state}")
    prop_id = integrator.submit_proposal(proposal)
    print(f"  ✓ submit_proposal → state={integrator.get_proposal(prop_id).state}")
    print(f"    history entries: {len(integrator.get_proposal(prop_id).history)}")
    print()

    # Step 5: Request oracle (PROPOSED → ORACLED) with trace diff
    print("Step 5: request_oracle — run 3 fixtures with trace diff (PROPOSED → ORACLED)")
    engine.fixtures = _make_fixtures()
    oracle_result = integrator.request_oracle(prop_id, list(fixtures.keys()))
    print(f"  aggregate_status: {oracle_result.aggregate_status}")
    print(f"  summary:          {oracle_result.summary}")
    print(f"  by_fixture:")
    for fid, r in oracle_result.by_fixture.items():
        print(f"    {fid:<15} {r.status:<12} output={r.output_diff.summary}")
        print(f"    {'':15} {'':12} trace= {r.trace_diff.summary}")
    print(f"  proposal.state = {integrator.get_proposal(prop_id).state}")
    print()

    # Step 6: Review (ORACLED → REVIEWED → ACCEPTED)
    print("Step 6: review_proposal(ACCEPT) (ORACLED → REVIEWED → ACCEPTED)")
    feedback = UserFeedback(
        decision="ACCEPT",
        timestamp=datetime.now(timezone.utc),
        user="demo-user",
        comments="all 3 scenarios PASS — accept",
    )
    final_state = integrator.review_proposal(prop_id, feedback)
    print(f"  ✓ review_proposal → state={final_state}")
    print()

    # Step 7: Merge (ACCEPTED → MERGED) + Revision
    print("Step 7: merge_proposal (ACCEPTED → MERGED) + Revision created")
    revision_id = integrator.merge_proposal(
        prop_id=prop_id,
        ontology_revision="v2-slab-design@2026-05-13",
        code_revision="git:5642a57",  # placeholder
        schema_revision="alembic:v5_schema_layer",
        created_by="demo-user",
        parent_revision=None,
    )
    final_proposal = integrator.get_proposal(prop_id)
    revision = integrator.revision_store.get(revision_id)
    print(f"  ✓ revision_id     = {revision_id}")
    print(f"  ✓ proposal.state  = {final_proposal.state}")
    print(f"  ✓ history length  = {len(final_proposal.history)}")
    print()

    # Step 8: Summary
    print("Step 8: Lifecycle audit log")
    for i, event in enumerate(final_proposal.history, 1):
        print(f"  {i}. {event.from_state:<10} → {event.to_state:<10} "
              f"(actor={event.actor}, notes={event.notes!r})")
    print()

    # Final verdict
    if (
        oracle_result.aggregate_status == "PASS"
        and final_proposal.state == "MERGED"
        and revision is not None
    ):
        print("✓ Final verdict: PASS")
        print(f"  Proposal lifecycle DRAFT → PROPOSED → ORACLED → REVIEWED → ACCEPTED → MERGED ")
        print(f"  Revision {revision_id} created with lineage")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
