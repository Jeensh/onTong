"""UC17 — Action ↔ Code verification on production (W47).

The first sprint where Section 4 actually *verifies* Section 2's authoring
claims. UC10-16 demonstrated ingestion + cross-layer queries; UC17 closes the
loop: for each action recorded with `자동 추천 — <method FQN>`, does the
method exist and translate cleanly?

Per-action classification:
    VERIFIED          — method found, translator passed
    NO_RECOMMENDATION — action has no parsed code_method_fqn (manual entry)
    METHOD_NOT_FOUND  — recommendation references a method absent in code_methods
    EMPTY             — method exists but body is whitespace
    PARSE_ERROR       — body didn't parse as a Java method declaration
    SIGNATURE_LOCKED  — translator hit an unsupported construct

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc17_action_verification.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.action_method_verifier import (
    ActionVerification,
    verify_actions,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPOS: tuple[str, ...] = (
    "slab-design-real",
    "slab-design-real-v2",
    "synthetic-5k",
)


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VerificationReport:
    repo_id:            str
    total:              int
    status_counts:      dict[str, int]
    sample_verified:    tuple[ActionVerification, ...] = field(default_factory=tuple)
    sample_findings:    tuple[ActionVerification, ...] = field(default_factory=tuple)

    @property
    def verified_count(self) -> int:
        return self.status_counts.get("VERIFIED", 0)

    @property
    def verified_rate(self) -> float:
        return (self.verified_count / self.total) if self.total else 0.0


def survey_repo(session: Session, repo_id: str) -> VerificationReport:
    actions = load_actions(session, repo_id)
    verifications = verify_actions(session, actions)
    counts = Counter(v.status for v in verifications)

    sample_verified = tuple(v for v in verifications if v.status == "VERIFIED")[:3]
    sample_findings = tuple(v for v in verifications if v.status != "VERIFIED")[:3]

    return VerificationReport(
        repo_id=repo_id,
        total=len(verifications),
        status_counts=dict(counts),
        sample_verified=sample_verified,
        sample_findings=sample_findings,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def _short(text: str, length: int = 64) -> str:
    if len(text) <= length:
        return text
    return "…" + text[-(length - 1):]


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC17 — Action ↔ Code verification on production (W47)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        totals = {"total": 0, "verified": 0}
        aggregate_counts: Counter[str] = Counter()
        for repo_id in repos:
            report = survey_repo(session, repo_id)
            _banner(f"Repo: {report.repo_id}")
            print(f"  Total actions     : {report.total}")
            print(f"  VERIFIED          : {report.verified_count} "
                  f"({report.verified_rate * 100:.1f}%)")
            for status, count in sorted(report.status_counts.items()):
                if status != "VERIFIED":
                    print(f"    {status:18s}: {count}")
            if report.sample_verified:
                print("  Sample VERIFIED:")
                for v in report.sample_verified:
                    print(f"    ✓ {v.action_fqn[:36]:36s}  → {_short(v.code_method_fqn or '')}")
            if report.sample_findings:
                print("  Sample findings (non-VERIFIED):")
                for v in report.sample_findings:
                    print(f"    ! {v.action_fqn[:36]:36s}  [{v.status}]")
                    if v.code_method_fqn:
                        print(f"      → {_short(v.code_method_fqn)}")
            print()

            totals["total"]    += report.total
            totals["verified"] += report.verified_count
            aggregate_counts.update(report.status_counts)

        _banner("Aggregate (all repos)")
        print(f"  Total actions  : {totals['total']}")
        print(f"  VERIFIED       : {totals['verified']} "
              f"({totals['verified'] / totals['total'] * 100 if totals['total'] else 0:.1f}%)")
        for status, count in sorted(aggregate_counts.items()):
            if status != "VERIFIED":
                print(f"    {status:18s}: {count}")
        print()
        print("✓ Action ↔ code agreement check operational on production data —")
        print("  Section 4 surfaces drift between Section 2's authoring and the real code")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
