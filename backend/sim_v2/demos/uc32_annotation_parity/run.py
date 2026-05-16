"""UC32 — Annotation parity survey on production (W66).

Eighth dimension of the layered verification stack. Where W63 checks
exception flows (throw new …), W66 checks cross-cutting annotations
(@Transactional / @Override / @PostMapping) that materially shape the
action contract but live outside the method signature.

Production reality on slab-design-real:
    @Override:       22 methods
    @Autowired:      18 methods   (implementation-only — filtered out by verifier)
    @Transactional:   5 methods
    @PostMapping:     1 method
    @Query:           1 method    (implementation-only — filtered out)

Since `effects_json` is empty in production, every contract annotation
above surfaces as UNDECLARED_ANNOTATION (per-action), giving Section 2
a concrete authoring backlog: "these N actions need to declare X effect".

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc32_annotation_parity.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.annotation_verifier import (
    AnnotationStatus,
    AnnotationVerification,
    verify_action_annotations_batch,
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
class RepoAnnotationSurvey:
    repo_id:        str
    total:          int
    counts:         dict[AnnotationStatus, int]
    by_kind:        dict[str, int]
    verifications:  tuple[AnnotationVerification, ...] = field(default_factory=tuple)


def survey_repo(session: Session, repo_id: str) -> RepoAnnotationSurvey:
    actions = load_actions(session, repo_id)
    verifs = verify_action_annotations_batch(session, actions)
    counts: Counter[AnnotationStatus] = Counter(v.status for v in verifs)
    kind_counts: Counter[str] = Counter()
    for v in verifs:
        for k in v.undeclared_only:
            kind_counts[k] += 1
        for k in v.missing_only:
            kind_counts[k] += 1
    return RepoAnnotationSurvey(
        repo_id=repo_id, total=len(verifs),
        counts=dict(counts), by_kind=dict(kind_counts),
        verifications=tuple(verifs),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


_STATUS_ORDER: tuple[AnnotationStatus, ...] = (
    "VERIFIED",
    "UNDECLARED_ANNOTATION",
    "MISSING_ANNOTATION",
    "DIVERGENT_ANNOTATIONS",
    "METHOD_NOT_FOUND",
    "NO_RECOMMENDATION",
)


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_breakdown(s: RepoAnnotationSurvey) -> None:
    print(f"  Total actions       : {s.total}")
    for status in _STATUS_ORDER:
        n = s.counts.get(status, 0)
        if n:
            print(f"    {status:22s} {n:4d}")
    if s.by_kind:
        print(f"  Drift by annotation kind:")
        for kind, n in sorted(s.by_kind.items(), key=lambda x: -x[1]):
            print(f"    {kind:22s} {n:4d}")


def _print_samples(s: RepoAnnotationSurvey, status: AnnotationStatus,
                   limit: int = 6) -> None:
    samples = [v for v in s.verifications if v.status == status][:limit]
    if not samples:
        return
    print(f"  Sample {status} findings:")
    for v in samples:
        print(f"    [{v.action_fqn}]")
        print(f"      method        : {v.code_method_fqn}")
        if v.present:
            print(f"      present       : {list(v.present)}")
        if v.declared:
            print(f"      declared      : {list(v.declared)}")
        if v.undeclared_only:
            print(f"      undeclared    : {list(v.undeclared_only)}")
        if v.missing_only:
            print(f"      missing       : {list(v.missing_only)}")


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC32 — Annotation parity survey (W66)")
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
            _print_samples(s, "UNDECLARED_ANNOTATION")
            _print_samples(s, "MISSING_ANNOTATION")
            _print_samples(s, "DIVERGENT_ANNOTATIONS")
            print()
        _banner("✓ W66 annotation gate exercised on production")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
