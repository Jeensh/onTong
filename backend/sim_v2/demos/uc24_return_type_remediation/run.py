"""UC24 — Return-type drift remediation demo (W58).

Closes the detect→fix loop on the return-type axis (sister to UC22 on the
param-signature axis).

Pipeline per repo:
    UC23  detect return-type drift (W56/W57)
    UC24  recommend fix             (W58)   ← here

Each verification in PRIMITIVE_MISMATCH / OBJECT_REF_MISMATCH / IMPLICIT_OUTPUT
becomes one concrete remediation step (CHANGE_PRIMITIVE_TYPE, LIFT_TO_OBJECT_REF,
WRAP_AS_LIST, DECLARE_OUTPUT, or PROPOSE_NEW_TERM).

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc24_return_type_remediation.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.return_type_remediation import (
    ReturnTypeRemediationKind,
    ReturnTypeRemediationReport,
    ReturnTypeRemediationStep,
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
class RepoReturnTypeRemediation:
    repo_id:        str
    report:         ReturnTypeRemediationReport
    step_counts:    dict[ReturnTypeRemediationKind, int]


def remediate_repo(
    session: Session, repo_id: str,
) -> RepoReturnTypeRemediation:
    actions = load_actions(session, repo_id)
    verifs = verify_action_return_types(session, actions)
    index = TermClassIndex.build(session, repo_id)
    report = generate_return_type_remediation(verifs, term_index=index)
    counts: Counter[ReturnTypeRemediationKind] = Counter(
        s.kind for s in report.steps
    )
    return RepoReturnTypeRemediation(
        repo_id=repo_id,
        report=report,
        step_counts=dict(counts),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


_STEP_KIND_ORDER: tuple[ReturnTypeRemediationKind, ...] = (
    "CHANGE_PRIMITIVE_TYPE",
    "LIFT_TO_OBJECT_REF",
    "WRAP_AS_LIST",
    "DECLARE_OUTPUT",
    "PROPOSE_NEW_TERM",
)


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_breakdown(r: RepoReturnTypeRemediation) -> None:
    total = len(r.report.steps)
    print(f"  Total steps              : {total}")
    for k in _STEP_KIND_ORDER:
        n = r.step_counts.get(k, 0)
        if n:
            print(f"    {k:25s} {n:3d}")


def _print_step(s: ReturnTypeRemediationStep) -> None:
    print(f"  [{s.kind:24s}] {s.action_fqn}")
    print(f"    method        : {s.code_method_fqn}")
    print(f"    current       : {s.current_output!r}")
    print(f"    method_return : {s.method_return!r}")
    if s.target_term_fqn:
        print(f"    target_term   : {s.target_term_fqn}")
    if s.proposed_class:
        print(f"    proposed_class: {s.proposed_class}")
    print(f"    {s.recommendation}")
    print(f"    rationale: {s.rationale}")
    print()


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC24 — Return-type drift remediation (W58)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        any_drift = False
        for repo_id in repos:
            r = remediate_repo(session, repo_id)
            _banner(f"Repo: {r.repo_id}")
            print(f"  {r.report.summary}")
            _print_breakdown(r)
            print()
            if r.report.steps:
                any_drift = True
                _banner("Return-type remediation steps (Section 2 actionable)")
                for s in r.report.steps:
                    _print_step(s)

        _banner(
            "✓ All repos clean — no return-type drift"
            if not any_drift
            else "Section 2 fix path: apply the steps above"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
