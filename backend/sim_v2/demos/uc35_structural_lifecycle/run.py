"""UC35 — Param + Return-type structural closed-loop (W69).

Completes the closed-loop demonstration for every remediation axis in the
framework. Where UC34 carried effect-shaped steps, UC35 covers the structural
shape mutations:

    UC20/UC23   detect param + return-type drift
    UC22/UC24   remediate (RENAME / CHANGE_PRIMITIVE / WRAP_AS_LIST / etc.)
    UC35        Integrator lifecycle for every step                    ← here

Together with UC28 (term axis) and UC34 (effect axis), this means:
**every kind of remediation step now has a production closed-loop trace.**

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc35_structural_lifecycle.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.integrator.structural_proposal_pipeline import (
    StructuralLifecycleResult,
    param_step_to_axis_step,
    return_type_step_to_axis_step,
    run_structural_lifecycle,
)
from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.drift_remediation import (
    generate_remediation as gen_param_remediation,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    verify_action_param_signatures,
)
from backend.sim_v2.core.verification.return_type_remediation import (
    TermClassIndex,
    generate_return_type_remediation,
)
from backend.sim_v2.core.verification.return_type_verifier import (
    verify_action_return_types,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPOS: tuple[str, ...] = (
    "slab-design-real",
    "slab-design-real-v2",
)


@dataclass(frozen=True)
class RepoStructuralLifecycle:
    repo_id:  str
    results:  tuple[StructuralLifecycleResult, ...]

    @property
    def merged(self) -> int:
        return sum(1 for r in self.results if r.final_state == "MERGED")

    @property
    def rejected(self) -> int:
        return sum(1 for r in self.results if r.final_state == "REJECTED")

    @property
    def needs_human(self) -> int:
        return sum(1 for r in self.results if r.final_state == "DRAFT")


def run_lifecycle_for_repo(
    session: Session, repo_id: str,
) -> RepoStructuralLifecycle:
    actions = load_actions(session, repo_id)

    # Param axis
    param_verifs = verify_action_param_signatures(session, actions)
    param_report = gen_param_remediation(param_verifs)

    # Return-type axis
    rt_verifs = verify_action_return_types(session, actions)
    idx = TermClassIndex.build(session, repo_id)
    rt_report = generate_return_type_remediation(rt_verifs, term_index=idx)

    results: list[StructuralLifecycleResult] = []
    for step in param_report.steps:
        results.append(run_structural_lifecycle(param_step_to_axis_step(step)))
    for step in rt_report.steps:
        results.append(run_structural_lifecycle(return_type_step_to_axis_step(step)))

    return RepoStructuralLifecycle(repo_id=repo_id, results=tuple(results))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_result(r: StructuralLifecycleResult) -> None:
    marker = {"MERGED": "✓", "REJECTED": "✗", "DRAFT": "⚠"}.get(
        r.final_state, "·")
    print(f"  {marker} [{r.final_state:8s}] [{r.source_axis:11s}] "
          f"{r.kind:22s} {r.action_fqn}")
    if r.revision_id:
        print(f"      revision={r.revision_id[:8]}…")
    elif r.rejection_reason:
        print(f"      reason={r.rejection_reason}")


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC35 — Param + Return-type closed-loop (W69)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        for repo_id in repos:
            r = run_lifecycle_for_repo(session, repo_id)
            _banner(f"Repo: {r.repo_id}")
            print(f"  Total lifecycles : {len(r.results)}")
            print(f"  Merged           : {r.merged}")
            print(f"  Rejected         : {r.rejected}")
            print(f"  Needs human      : {r.needs_human}")
            by_axis_kind: Counter[tuple[str, str, str]] = Counter()
            for res in r.results:
                by_axis_kind[(res.source_axis, res.kind, res.final_state)] += 1
            if by_axis_kind:
                print("  Breakdown:")
                for (axis, kind, state), n in sorted(by_axis_kind.items()):
                    print(f"    [{axis:11s}] {kind:25s} {state:8s} {n}")
            print()
            if r.results:
                _banner("Per-step trace")
                for res in r.results:
                    _print_result(res)
                print()

        _banner("✓ Structural axis closed-loop demonstrated")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
