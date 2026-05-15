"""UC23 — Return-type agreement survey on production (W56).

Third gate in the layered verification stack on production data:
    UC17  action↔method existence       (W47)
    UC20  param-signature agreement     (W52)
    UC23  return-type agreement         (W56)   ← here

Pipeline per repo:
    load_actions → verify_action_return_types → tally by status

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc23_return_type_agreement.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.return_type_verifier import (
    ReturnTypeStatus,
    ReturnTypeVerification,
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


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo survey
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepoReturnTypeSurvey:
    repo_id:        str
    total:          int
    counts:         dict[ReturnTypeStatus, int]
    verifications:  tuple[ReturnTypeVerification, ...] = field(default_factory=tuple)

    @property
    def verified_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.counts.get("VERIFIED", 0) / self.total


def survey_repo(session: Session, repo_id: str) -> RepoReturnTypeSurvey:
    actions = load_actions(session, repo_id)
    verifs = verify_action_return_types(session, actions)
    counts: Counter[ReturnTypeStatus] = Counter(v.status for v in verifs)
    return RepoReturnTypeSurvey(
        repo_id=repo_id,
        total=len(verifs),
        counts=dict(counts),
        verifications=tuple(verifs),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


_STATUS_ORDER: tuple[ReturnTypeStatus, ...] = (
    "VERIFIED",
    "PRIMITIVE_MISMATCH",
    "OBJECT_REF_MISMATCH",
    "OBJECT_REF_UNRESOLVED",
    "VOID_MISMATCH",
    "IMPLICIT_OUTPUT",
    "METHOD_NOT_FOUND",
    "NO_RECOMMENDATION",
)


def _print_status_breakdown(s: RepoReturnTypeSurvey) -> None:
    print(f"  Total actions          : {s.total}")
    print(f"  Verified rate          : {s.verified_rate * 100:.1f}%")
    for status in _STATUS_ORDER:
        n = s.counts.get(status, 0)
        if n == 0:
            continue
        print(f"    {status:22s} {n:4d}")


def _print_mismatch_samples(
    s: RepoReturnTypeSurvey, status: ReturnTypeStatus, limit: int = 5,
) -> None:
    samples = [v for v in s.verifications if v.status == status][:limit]
    if not samples:
        return
    print(f"  Sample {status} findings:")
    for v in samples:
        print(f"    [{v.action_fqn}]")
        print(f"      method        : {v.code_method_fqn}")
        print(f"      action_output : {v.action_output!r}")
        print(f"      method_return : {v.method_return!r}")


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC23 — Return-type agreement survey (W56)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        for repo_id in repos:
            s = survey_repo(session, repo_id)
            _banner(f"Repo: {s.repo_id}")
            _print_status_breakdown(s)
            print()
            _print_mismatch_samples(s, "PRIMITIVE_MISMATCH")
            _print_mismatch_samples(s, "OBJECT_REF_MISMATCH", limit=3)
            _print_mismatch_samples(s, "OBJECT_REF_UNRESOLVED", limit=3)
            _print_mismatch_samples(s, "IMPLICIT_OUTPUT", limit=3)
            _print_mismatch_samples(s, "VOID_MISMATCH", limit=3)
            print()

        _banner("✓ W56 gate exercised end-to-end on production")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
