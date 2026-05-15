"""UC20 — Action ↔ Method param-signature agreement survey on production (W52).

Refinement of W47's action↔code verification: not just "does the method exist
and translate", but "do the *declared parameter names* on the action match
the actual Java method's parameter names?"

Per-action outcomes (from `param_signature_verifier`):
    VERIFIED          — same arity, same param names, same order
    ARITY_MISMATCH    — action declares N params, method has M
    NAME_MISMATCH     — same count but parameter names diverge
    METHOD_NOT_FOUND  — recommendation refers to a non-existent method
    NO_ACTION_PARAMS  — action.params_json empty
    NO_RECOMMENDATION — action lacks parsed code_method_fqn (manual entry)

Each NAME_MISMATCH / ARITY_MISMATCH is a real cross-layer drift finding that
predates Section 4 — Section 2's authoring used different naming than the
production code.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc20_param_signature_agreement.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    ParamVerification,
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
# Report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParamAgreementReport:
    repo_id:        str
    total:          int
    status_counts:  dict[str, int]
    name_mismatches: tuple[ParamVerification, ...] = field(default_factory=tuple)
    arity_mismatches: tuple[ParamVerification, ...] = field(default_factory=tuple)

    @property
    def verified_count(self) -> int:
        return self.status_counts.get("VERIFIED", 0)

    @property
    def verified_rate(self) -> float:
        return (self.verified_count / self.total) if self.total else 0.0


def survey_repo(session: Session, repo_id: str) -> ParamAgreementReport:
    actions = load_actions(session, repo_id)
    verifications = verify_action_param_signatures(session, actions)
    counts = Counter(v.status for v in verifications)
    name_mismatches = tuple(v for v in verifications if v.status == "NAME_MISMATCH")
    arity_mismatches = tuple(v for v in verifications if v.status == "ARITY_MISMATCH")
    return ParamAgreementReport(
        repo_id=repo_id,
        total=len(verifications),
        status_counts=dict(counts),
        name_mismatches=name_mismatches,
        arity_mismatches=arity_mismatches,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def _short(text: str, length: int = 56) -> str:
    if len(text) <= length:
        return text
    return "…" + text[-(length - 1):]


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC20 — Action ↔ Method param-signature agreement (W52)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        totals = {"total": 0, "verified": 0}
        for repo_id in repos:
            report = survey_repo(session, repo_id)
            _banner(f"Repo: {report.repo_id}")
            print(f"  Total actions     : {report.total}")
            print(f"  VERIFIED          : {report.verified_count} "
                  f"({report.verified_rate * 100:.1f}%)")
            for status, count in sorted(report.status_counts.items()):
                if status != "VERIFIED":
                    print(f"    {status:18s}: {count}")

            if report.name_mismatches:
                print("  NAME_MISMATCH details:")
                for v in report.name_mismatches:
                    print(f"    ! {v.action_fqn}")
                    print(f"      method: {_short(v.code_method_fqn or '')}")
                    # Find the diverging position(s)
                    for i, (a, m) in enumerate(zip(v.action_params, v.method_params)):
                        if a != m:
                            print(f"      param #{i}: action={a!r} method={m!r}")

            if report.arity_mismatches:
                print("  ARITY_MISMATCH details:")
                for v in report.arity_mismatches:
                    print(f"    ! {v.action_fqn}  ({v.details})")
            print()

            totals["total"]    += report.total
            totals["verified"] += report.verified_count

        _banner("Aggregate")
        rate = totals["verified"] / totals["total"] * 100 if totals["total"] else 0
        print(f"  Total actions : {totals['total']}")
        print(f"  VERIFIED      : {totals['verified']} ({rate:.1f}%)")
        print()
        print("✓ Param-signature agreement check operational —")
        print("  surface cross-layer drift between Section 2's action declarations")
        print("  and the actual Java method signatures.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
