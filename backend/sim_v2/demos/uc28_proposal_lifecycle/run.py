"""UC28 — Full closed-loop production demo (W62).

End-to-end pipeline on production data, closing the Two-Engine framework loop:

    UC23  Verification Engine surfaces return-type drift
    UC24  Deterministic remediation classifies into 5 fix kinds
    UC27  Recommendation Engine (LLM) converts PROPOSE_NEW_TERM placeholders
          into structured BusinessTermProposals
    UC28  Integrator carries each proposal through the 6-state lifecycle:    ← here
          DRAFT → PROPOSED → ORACLED → REVIEWED → ACCEPTED → MERGED
          → Revision lineage entry per merged term

Each new term proposal is also pitted against a "deliberately clashing" baseline
(an already-existing term FQN) to demonstrate the integrator rejects collisions
via the TermSchemaOracle.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc28_proposal_lifecycle.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.integrator.term_proposal_pipeline import (
    LifecycleResult,
    _ExistingTermSnapshot,
    run_term_lifecycle,
)
from backend.sim_v2.core.recommendation.term_proposer import (
    BusinessTermProposal,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc27_term_proposal.run import propose_terms_for_repo


DEFAULT_REPOS: tuple[str, ...] = (
    "slab-design-real",
    "slab-design-real-v2",
)


@dataclass(frozen=True)
class RepoLifecycleReport:
    repo_id:     str
    results:     tuple[LifecycleResult, ...]

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
) -> RepoLifecycleReport:
    proposal_set = propose_terms_for_repo(session, repo_id)
    if not proposal_set.results:
        return RepoLifecycleReport(repo_id=repo_id, results=())

    snapshot = _ExistingTermSnapshot.from_session(session, repo_id)
    lifecycle_results: list[LifecycleResult] = []
    for result in proposal_set.results:
        if result.proposal is None:
            continue
        lifecycle_results.append(
            run_term_lifecycle(result.proposal, existing=snapshot)
        )

    # Demo the rejection path: feed a deliberately clashing term that already
    # exists in production. This shows the Integrator's TermSchemaOracle
    # rejecting the proposal at the request_oracle step.
    if "term.scm.validation_result" in snapshot.fqns:
        clash = BusinessTermProposal(
            fqn="term.scm.validation_result",
            label="검증결과 (의도된 충돌)",
            description="UC28 demo: deliberately collide with existing term to show REJECT path.",
            aliases=("ValidationResult",),
            domain="scm",
            kind="composite",
            confidence=0.95,
            needs_review=False,
            target_class="ValidationResult",
        )
        lifecycle_results.append(
            run_term_lifecycle(clash, existing=snapshot)
        )

    return RepoLifecycleReport(
        repo_id=repo_id, results=tuple(lifecycle_results),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_lifecycle(r: LifecycleResult) -> None:
    marker = {"MERGED": "✓", "REJECTED": "✗", "DRAFT": "⚠"}.get(
        r.final_state, "·",
    )
    print(f"  {marker} [{r.final_state:8s}] target={r.target_class!r:18s} "
          f"fqn={r.term_fqn}")
    print(f"      proposal_id : {r.proposal_id[:8]}…")
    print(f"      states      : {' → '.join(r.states_visited)}")
    print(f"      oracle      : {r.oracle_status}")
    if r.revision_id:
        print(f"      revision    : {r.revision_id[:8]}…")
    if r.rejection_reason:
        print(f"      reason      : {r.rejection_reason}")
    print()


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC28 — Full closed-loop production demo (W62)")
    print("Verification ⇒ Remediation ⇒ Recommendation ⇒ Integrator lifecycle")
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
            print(f"  Merged           : {r.merged}  (term added → Revision)")
            print(f"  Rejected         : {r.rejected}  (oracle fail / clash)")
            print(f"  Needs human      : {r.needs_human}  (change-requested)")
            print()
            if r.results:
                _banner("Per-proposal lifecycle trace")
                for result in r.results:
                    _print_lifecycle(result)

        _banner("✓ Two-Engine framework closed-loop demonstrated end-to-end")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
