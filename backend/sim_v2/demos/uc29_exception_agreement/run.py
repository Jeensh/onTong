"""UC29 — Exception agreement survey on production (W63).

Seventh dimension of the layered verification stack. Where W56/W57 compare
return-type contracts and W59/W60 compare execution behavior, W63 compares
the *exception flows* — what an action declares it can raise (via
`effects_json`) versus what the Java method body actually `throw new …`s.

Production reality on slab-design-real: the Section 2 authoring pipeline
has not yet documented any exception effects, so every throwing method
surfaces UNDECLARED_THROWS. This is *the* signal Section 2 needs to add
exception documentation to those actions — a concrete authoring backlog.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc29_exception_agreement.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.exception_verifier import (
    ExceptionStatus,
    ExceptionVerification,
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
class RepoExceptionSurvey:
    repo_id:        str
    total:          int
    counts:         dict[ExceptionStatus, int]
    verifications:  tuple[ExceptionVerification, ...] = field(default_factory=tuple)

    @property
    def undeclared_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.counts.get("UNDECLARED_THROWS", 0) / self.total


def survey_repo(session: Session, repo_id: str) -> RepoExceptionSurvey:
    actions = load_actions(session, repo_id)
    verifs = verify_action_exceptions_batch(session, actions)
    counts: Counter[ExceptionStatus] = Counter(v.status for v in verifs)
    return RepoExceptionSurvey(
        repo_id=repo_id, total=len(verifs),
        counts=dict(counts), verifications=tuple(verifs),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


_STATUS_ORDER: tuple[ExceptionStatus, ...] = (
    "VERIFIED",
    "UNDECLARED_THROWS",
    "MISSING_THROWS",
    "DIVERGENT_THROWS",
    "METHOD_NOT_FOUND",
    "NO_RECOMMENDATION",
)


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_breakdown(s: RepoExceptionSurvey) -> None:
    print(f"  Total actions       : {s.total}")
    print(f"  Undeclared rate     : {s.undeclared_rate * 100:.1f}%")
    for status in _STATUS_ORDER:
        n = s.counts.get(status, 0)
        if n:
            print(f"    {status:22s} {n:4d}")


def _print_findings(s: RepoExceptionSurvey, status: ExceptionStatus,
                    limit: int = 8) -> None:
    samples = [v for v in s.verifications if v.status == status][:limit]
    if not samples:
        return
    print(f"  Sample {status} findings:")
    for v in samples:
        print(f"    [{v.action_fqn}]")
        print(f"      method        : {v.code_method_fqn}")
        if v.thrown:
            print(f"      method throws : {list(v.thrown)}")
        if v.declared:
            print(f"      declared      : {list(v.declared)}")
        if v.undeclared_only:
            print(f"      undeclared    : {list(v.undeclared_only)}")
        if v.missing_only:
            print(f"      missing       : {list(v.missing_only)}")


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC29 — Exception agreement survey (W63)")
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
            _print_breakdown(s)
            print()
            _print_findings(s, "UNDECLARED_THROWS")
            _print_findings(s, "MISSING_THROWS")
            _print_findings(s, "DIVERGENT_THROWS")
            print()
        _banner("✓ W63 exception gate exercised on production")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
