"""UC22 — Drift remediation demo on production (W55).

Closes the detect→fix loop on the param-signature gate (mirror of UC18 which
closed the loop on schema drift).

Pipeline per repo:
    UC20  detect drift   (param-signature NAME_MISMATCH / ARITY_MISMATCH)
    UC22  recommend fix  ← here  (concrete rename / resize steps)

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc22_drift_remediation.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.drift_remediation import (
    RemediationReport,
    RemediationStep,
    generate_remediation,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    verify_action_param_signatures,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPOS: tuple[str, ...] = (
    "slab-design-real",
    "slab-design-real-v2",
)


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepoRemediation:
    repo_id:        str
    report:         RemediationReport
    rename_count:   int = 0
    resize_count:   int = 0


def remediate_repo(session: Session, repo_id: str) -> RepoRemediation:
    actions = load_actions(session, repo_id)
    verifs = verify_action_param_signatures(session, actions)
    report = generate_remediation(verifs)
    rename_count = sum(1 for s in report.steps if s.kind == "RENAME_ACTION_PARAM")
    resize_count = sum(1 for s in report.steps if s.kind == "RESIZE_ACTION_PARAMS")
    return RepoRemediation(
        repo_id=repo_id,
        report=report,
        rename_count=rename_count,
        resize_count=resize_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def _print_step(s: RemediationStep) -> None:
    print(f"  [{s.kind:24s}] {s.action_fqn}")
    if s.param_position is not None:
        print(f"    param #{s.param_position}: "
              f"{s.current_name!r} → {s.expected_name!r}")
    print(f"    {s.recommendation}")
    print(f"    rationale: {s.rationale}")


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC22 — Drift remediation recommendations (W55)")
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
            print(f"  Rename steps : {r.rename_count}")
            print(f"  Resize steps : {r.resize_count}")
            print()
            if r.report.steps:
                any_drift = True
                _banner("Remediation steps (Section 2 actionable)")
                for s in r.report.steps:
                    _print_step(s)
                    print()
            else:
                print("  ✓ No drift — no remediation needed.")
                print()

        _banner(
            "✓ All repos clean — no Section 2 changes needed"
            if not any_drift
            else "Section 2 fix path: apply the rename/resize steps above"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
