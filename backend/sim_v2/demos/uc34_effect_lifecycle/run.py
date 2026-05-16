"""UC34 — Effect (exception + annotation) closed-loop on production (W68).

Carries every remediation step produced by W64 + W67 through the Integrator
lifecycle until each reaches a terminal state (MERGED / REJECTED / DRAFT).

Pipeline:
    UC29/UC32   Verification detects effect drift
    UC30/UC33   Deterministic remediation classifies the fix
    UC34        Each step → DRAFT→PROPOSED→ORACLED→…→MERGED          ← here

Aggregates per-axis MERGE / REJECT / NEEDS-HUMAN counts so the operator can
see what fraction of the effect backlog is fully automatable.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc34_effect_lifecycle.run
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
from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.annotation_remediation import (
    generate_annotation_remediation,
)
from backend.sim_v2.core.verification.annotation_verifier import (
    verify_action_annotations_batch,
)
from backend.sim_v2.core.verification.exception_remediation import (
    generate_exception_remediation,
)
from backend.sim_v2.core.verification.exception_verifier import (
    verify_action_exceptions_batch,
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
class RepoEffectLifecycle:
    repo_id:      str
    results:      tuple[EffectLifecycleResult, ...]

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
) -> RepoEffectLifecycle:
    actions = load_actions(session, repo_id)

    # Exception axis
    exc_verifs = verify_action_exceptions_batch(session, actions)
    exc_report = generate_exception_remediation(exc_verifs)

    # Annotation axis
    ann_verifs = verify_action_annotations_batch(session, actions)
    ann_report = generate_annotation_remediation(ann_verifs)

    results: list[EffectLifecycleResult] = []
    for step in exc_report.steps:
        norm = exception_step_to_axis_step(step)
        existing = ExistingEffectsSnapshot.from_session(
            session, norm.action_fqn, repo_id,
        )
        results.append(run_effect_lifecycle(norm, existing=existing))
    for step in ann_report.steps:
        norm = annotation_step_to_axis_step(step)
        existing = ExistingEffectsSnapshot.from_session(
            session, norm.action_fqn, repo_id,
        )
        results.append(run_effect_lifecycle(norm, existing=existing))

    return RepoEffectLifecycle(repo_id=repo_id, results=tuple(results))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_result(r: EffectLifecycleResult) -> None:
    marker = {"MERGED": "✓", "REJECTED": "✗", "DRAFT": "⚠"}.get(
        r.final_state, "·")
    axis_tag = f"[{r.source_axis}]"
    disc = f" / {r.discriminator}" if r.discriminator else ""
    print(f"  {marker} [{r.final_state:8s}] {axis_tag:13s} "
          f"{r.action_fqn:55s} kind={r.effect_kind}{disc}")
    if r.revision_id:
        print(f"      revision={r.revision_id[:8]}…  oracle={r.oracle_status}")
    elif r.rejection_reason:
        print(f"      reason={r.rejection_reason}")


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC34 — Effect closed-loop (exception + annotation, W68)")
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
            print(f"  Needs human      : {r.needs_human}  (change-requested)")
            # Per-axis breakdown
            by_axis: Counter[tuple[str, str]] = Counter()
            for res in r.results:
                by_axis[(res.source_axis, res.final_state)] += 1
            if by_axis:
                print(f"  By axis × state:")
                for (axis, state), n in sorted(by_axis.items()):
                    print(f"    {axis:12s} {state:8s} {n}")
            print()
            if r.results:
                _banner("Per-step trace")
                for res in r.results:
                    _print_result(res)
                print()
        _banner("✓ Effect axis closed-loop demonstrated end-to-end")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
