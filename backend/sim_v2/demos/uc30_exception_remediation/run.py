"""UC30 — Exception drift remediation demo (W64).

Closes the detect→fix loop on the exception axis — sister to UC22 (param
drift) and UC24 (return-type drift):

    UC29  detect exception drift             (W63)
    UC30  recommend exception fix             (W64)   ← here

Each UNDECLARED_THROWS finding becomes one ADD_RAISES_EFFECT step (the
exact JSON entry Section 2 should append to `effects_json`). MISSING_THROWS
becomes REMOVE_DECLARED_EFFECT. DIVERGENT_THROWS emits both per disagreement.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc30_exception_remediation.run
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.exception_remediation import (
    ExceptionRemediationKind,
    ExceptionRemediationReport,
    ExceptionRemediationStep,
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
class RepoExceptionRemediation:
    repo_id:        str
    report:         ExceptionRemediationReport
    step_counts:    dict[ExceptionRemediationKind, int]


def remediate_repo(
    session: Session, repo_id: str,
) -> RepoExceptionRemediation:
    actions = load_actions(session, repo_id)
    verifs = verify_action_exceptions_batch(session, actions)
    report = generate_exception_remediation(verifs)
    counts: Counter[ExceptionRemediationKind] = Counter(
        s.kind for s in report.steps
    )
    return RepoExceptionRemediation(
        repo_id=repo_id, report=report, step_counts=dict(counts),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_step(s: ExceptionRemediationStep) -> None:
    marker = "+" if s.kind == "ADD_RAISES_EFFECT" else "−"
    print(f"  {marker} [{s.kind:24s}] {s.action_fqn}")
    print(f"      method        : {s.code_method_fqn}")
    print(f"      exception     : {s.exception}")
    if s.effect_entry is not None:
        print(f"      effect_entry  : {json.dumps(s.effect_entry, ensure_ascii=False)}")
    print(f"      {s.recommendation}")
    print(f"      rationale: {s.rationale}")
    print()


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC30 — Exception drift remediation (W64)")
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
            print(f"  Total steps              : {len(r.report.steps)}")
            for k in ("ADD_RAISES_EFFECT", "REMOVE_DECLARED_EFFECT"):
                n = r.step_counts.get(k, 0)
                if n:
                    print(f"    {k:25s} {n:3d}")
            print()
            if r.report.steps:
                any_drift = True
                _banner("Exception remediation steps (Section 2 actionable)")
                for s in r.report.steps:
                    _print_step(s)

        _banner(
            "✓ All exceptions are documented"
            if not any_drift
            else "Section 2 fix path: append/remove effects_json entries above"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
