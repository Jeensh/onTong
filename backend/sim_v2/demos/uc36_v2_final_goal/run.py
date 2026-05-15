"""UC36 — slab-design-real-v2 final-goal capstone (W70).

The framework's culminating demo. Wires together every closed-loop axis the
framework supports and shows v2 reaching its projected clean state:

    Verification stack (8 dim)
        ├─ W47/W52/W56-W57/W63    (snapshot — UC31)                  ─┐
        └─ W59/W60 (behavior/trace, fixture-driven)                   │
    Detect → Remediation (5 axis)                                     │
        ├─ W55/UC22  param rename                                     │
        ├─ W58/UC24  return-type fixes                                ├─→  UC36
        ├─ W64/UC30  exception ADD effect                             │
        └─ W67/UC33  annotation ADD effect                            │
    Integrator closed-loop (3 pipelines)                              │
        ├─ W62/UC28  term proposals                                   │
        ├─ W68/UC34  effect axis (exception + annotation)             │
        └─ W69/UC35  structural axis (param + return-type)            │
    Simulated post-merge snapshot (W70)                              ─┘

Pipeline:
    1. Take the baseline snapshot of v2 (UC31's serializable form)
    2. Run all 3 lifecycle pipelines on all remediation steps from v2
    3. Apply MERGED proposals to the snapshot via W70's simulator
    4. Diff baseline vs simulated → final reduction %

Expected outcome for v2:
    - 3 param renames MERGE                 (v2-specific NAME_MISMATCH)
    - 6 return-type structural fixes MERGE  (CHANGE/WRAP/DECLARE/LIFT)
    - 4 PROPOSE_NEW_TERM cases → DRAFT      (need term proposal first;
        2 of those 4 have term lifecycle MERGED via UC28)
    - 10 exception ADD effects MERGE        (UNDECLARED_THROWS for all
        AlgorithmException + IllegalStateException)
    - 5 annotation ADD effects MERGE        (transactional)
    - 1 annotation rest_endpoint → DRAFT    (needs detail fields)

Net: v2 baseline ~26 findings → simulated ~3-5 remaining (the unmergeable
PROPOSE_NEW_TERM cases that need the term axis run first, and METHOD_NOT_FOUND
type cases the framework can't auto-fix). That's the framework's projected
final-goal distance for v2.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc36_v2_final_goal.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.integrator.effect_proposal_pipeline import (
    EffectLifecycleResult,
    ExistingEffectsSnapshot,
    annotation_step_to_axis_step,
    exception_step_to_axis_step,
    run_effect_lifecycle,
)
from backend.sim_v2.core.integrator.structural_proposal_pipeline import (
    StructuralLifecycleResult,
    param_step_to_axis_step,
    return_type_step_to_axis_step,
    run_structural_lifecycle,
)
from backend.sim_v2.core.integrator.term_proposal_pipeline import (
    LifecycleResult as TermLifecycleResult,
    _ExistingTermSnapshot,
    run_term_lifecycle,
)
from backend.sim_v2.demos.uc27_term_proposal.run import propose_terms_for_repo
from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.annotation_remediation import (
    generate_annotation_remediation,
)
from backend.sim_v2.core.verification.annotation_verifier import (
    verify_action_annotations_batch,
)
from backend.sim_v2.core.verification.drift_remediation import (
    generate_remediation as gen_param_remediation,
)
from backend.sim_v2.core.verification.exception_remediation import (
    generate_exception_remediation,
)
from backend.sim_v2.core.verification.exception_verifier import (
    verify_action_exceptions_batch,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    verify_action_param_signatures,
)
from backend.sim_v2.core.verification.post_merge_snapshot import (
    SimulationReport,
    apply_merged_to_snapshot,
)
from backend.sim_v2.core.verification.return_type_remediation import (
    TermClassIndex,
    generate_return_type_remediation,
)
from backend.sim_v2.core.verification.return_type_verifier import (
    verify_action_return_types,
)
from backend.sim_v2.core.verification.snapshot import take_snapshot
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


TARGET_REPO = "slab-design-real-v2"


@dataclass(frozen=True)
class V2FinalGoalResult:
    repo_id:              str
    baseline_findings:    int
    simulated_findings:   int
    reduction_pct:        float
    effect_lifecycles:    tuple[EffectLifecycleResult, ...]
    struct_lifecycles:    tuple[StructuralLifecycleResult, ...]
    term_lifecycles:      tuple[TermLifecycleResult, ...]
    report:               SimulationReport
    # Indirect resolutions: PROPOSE_NEW_TERM structural cases that are
    # *unblocked* once the corresponding term-axis lifecycle MERGES.
    term_unblocked_count: int = 0


def run_v2_final_goal(
    session: Session, repo_id: str = TARGET_REPO,
) -> V2FinalGoalResult:
    actions = load_actions(session, repo_id)

    # ─ Detect (all 4 surface gates carry findings) ─────────────────────────
    param_verifs = verify_action_param_signatures(session, actions)
    rt_verifs    = verify_action_return_types(session, actions)
    exc_verifs   = verify_action_exceptions_batch(session, actions)
    ann_verifs   = verify_action_annotations_batch(session, actions)

    # ─ Remediate ────────────────────────────────────────────────────────────
    param_report = gen_param_remediation(param_verifs)
    idx          = TermClassIndex.build(session, repo_id)
    rt_report    = generate_return_type_remediation(rt_verifs, term_index=idx)
    exc_report   = generate_exception_remediation(exc_verifs)
    ann_report   = generate_annotation_remediation(ann_verifs)

    # ─ Lifecycles ───────────────────────────────────────────────────────────
    effect_lifecycles: list[EffectLifecycleResult] = []
    for step in exc_report.steps:
        norm = exception_step_to_axis_step(step)
        existing = ExistingEffectsSnapshot.from_session(
            session, norm.action_fqn, repo_id,
        )
        effect_lifecycles.append(run_effect_lifecycle(norm, existing=existing))
    for step in ann_report.steps:
        norm = annotation_step_to_axis_step(step)
        existing = ExistingEffectsSnapshot.from_session(
            session, norm.action_fqn, repo_id,
        )
        effect_lifecycles.append(run_effect_lifecycle(norm, existing=existing))

    struct_lifecycles: list[StructuralLifecycleResult] = []
    for step in param_report.steps:
        struct_lifecycles.append(
            run_structural_lifecycle(param_step_to_axis_step(step))
        )
    for step in rt_report.steps:
        struct_lifecycles.append(
            run_structural_lifecycle(return_type_step_to_axis_step(step))
        )

    # ─ Term axis lifecycle (PROPOSE_NEW_TERM cases) ────────────────────────
    term_proposals = propose_terms_for_repo(session, repo_id)
    term_lifecycles: list[TermLifecycleResult] = []
    term_existing = _ExistingTermSnapshot.from_session(session, repo_id)
    for tpr in term_proposals.results:
        if tpr.proposal is None:
            continue
        term_lifecycles.append(
            run_term_lifecycle(tpr.proposal, existing=term_existing)
        )

    # Once a term MERGES, every PROPOSE_NEW_TERM return-type case targeting
    # that class is logically resolvable — the structural axis just needs a
    # re-run with the new term in the index. We model that as an indirect
    # resolution: clear the corresponding GATE_RETURN_TYPE findings whose
    # PRIMITIVE_MISMATCH was due to that class.
    term_unblocked_classes: set[str] = set()
    for tl in term_lifecycles:
        if tl.final_state == "MERGED":
            term_unblocked_classes.add(tl.target_class)

    # Convert term-MERGED → synthetic structural MERGEs against the actions
    # whose PROPOSE_NEW_TERM step's proposed_class is unblocked.
    extra_structural: list[StructuralLifecycleResult] = []
    for step in rt_report.steps:
        if step.kind != "PROPOSE_NEW_TERM":
            continue
        if step.proposed_class in term_unblocked_classes:
            extra_structural.append(StructuralLifecycleResult(
                source_axis="return_type",
                kind="LIFT_TO_OBJECT_REF",  # the eventual resolution
                action_fqn=step.action_fqn,
                proposal_id="(synthetic)",
                states_visited=("DRAFT", "MERGED"),
                final_state="MERGED",
                oracle_status="PASS",
                revision_id=f"term-unblocked-{step.proposed_class}",
            ))

    # ─ Simulated post-merge ─────────────────────────────────────────────────
    baseline = take_snapshot(session, repo_id)
    report = apply_merged_to_snapshot(
        baseline,
        effect_results=effect_lifecycles,
        structural_results=struct_lifecycles + extra_structural,
        term_results=term_lifecycles,
    )

    return V2FinalGoalResult(
        repo_id=repo_id,
        baseline_findings=report.baseline_count,
        simulated_findings=report.simulated_count,
        reduction_pct=report.reduction_pct,
        effect_lifecycles=tuple(effect_lifecycles),
        struct_lifecycles=tuple(struct_lifecycles),
        term_lifecycles=tuple(term_lifecycles),
        report=report,
        term_unblocked_count=len(extra_structural),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print(f"UC36 — {TARGET_REPO} FINAL-GOAL CAPSTONE (W70)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        r = run_v2_final_goal(session)

        _banner("Baseline vs simulated post-merge")
        print(f"  Repo                : {r.repo_id}")
        print(f"  Baseline findings   : {r.baseline_findings}")
        print(f"  Simulated findings  : {r.simulated_findings}")
        print(f"  Reduction           : {r.reduction_pct:.1f}%")
        print(f"  MERGED — effect     : {r.report.effect_merged}")
        print(f"  MERGED — structural : {r.report.structural_merged}")
        print()

        # Per-axis lifecycle outcome
        effect_states = Counter(r.final_state for r in r.effect_lifecycles)
        struct_states = Counter(r.final_state for r in r.struct_lifecycles)
        term_states = Counter(t.final_state for t in r.term_lifecycles)
        _banner("Lifecycle outcomes")
        print(f"  Effect axis ({len(r.effect_lifecycles)}):")
        for s, n in sorted(effect_states.items()):
            print(f"    {s:10s} {n}")
        print(f"  Structural axis ({len(r.struct_lifecycles)}):")
        for s, n in sorted(struct_states.items()):
            print(f"    {s:10s} {n}")
        print(f"  Term axis ({len(r.term_lifecycles)}):")
        for s, n in sorted(term_states.items()):
            print(f"    {s:10s} {n}")
        if r.term_unblocked_count:
            print(f"  Term-unblocked PROPOSE_NEW_TERM resolutions : "
                  f"{r.term_unblocked_count}")
        print()

        # Remaining (unmergeable) findings
        if r.report.remaining_findings:
            _banner("Remaining findings (framework can't auto-fix)")
            grouped: dict[str, list] = {}
            for f in r.report.remaining_findings:
                grouped.setdefault(f.gate, []).append(f)
            for gate, items in grouped.items():
                print(f"  [{gate}] {len(items)}")
                for f in items:
                    print(f"    · {f.action_fqn:55s} {f.status:24s} {f.key}")
            print()

        # Summary
        if r.simulated_findings == 0:
            _banner("✓ v2 FULLY CLEAN — framework projected final goal reached")
        else:
            _banner(
                f"v2 projected distance to clean: {r.simulated_findings} finding(s) — "
                "see remaining list above"
            )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
