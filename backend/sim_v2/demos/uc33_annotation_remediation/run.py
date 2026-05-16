"""UC33 — Annotation drift remediation demo (W67).

Closes the detect→fix loop on the annotation axis — sister to UC22/UC24/UC30.

    UC32  detect annotation drift            (W66)
    UC33  recommend annotation fix           (W67)   ← here

Each UNDECLARED_ANNOTATION finding becomes one ADD_ANNOTATION_EFFECT step
with a minimal `effect_entry` payload Section 2 can paste directly into
`effects_json`. Detail-needing kinds (rest_endpoint / scheduled / cacheable)
carry a flag so reviewers know to fill extra fields.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc33_annotation_remediation.run
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
from backend.sim_v2.core.verification.annotation_remediation import (
    AnnotationRemediationKind,
    AnnotationRemediationReport,
    AnnotationRemediationStep,
    generate_annotation_remediation,
)
from backend.sim_v2.core.verification.annotation_verifier import (
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
class RepoAnnotationRemediation:
    repo_id:        str
    report:         AnnotationRemediationReport
    step_counts:    dict[AnnotationRemediationKind, int]
    needs_detail:   int


def remediate_repo(
    session: Session, repo_id: str,
) -> RepoAnnotationRemediation:
    actions = load_actions(session, repo_id)
    verifs = verify_action_annotations_batch(session, actions)
    report = generate_annotation_remediation(verifs)
    counts: Counter[AnnotationRemediationKind] = Counter(
        s.kind for s in report.steps
    )
    detail_count = sum(1 for s in report.steps if s.needs_detail)
    return RepoAnnotationRemediation(
        repo_id=repo_id, report=report,
        step_counts=dict(counts), needs_detail=detail_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_step(s: AnnotationRemediationStep) -> None:
    marker = "+" if s.kind == "ADD_ANNOTATION_EFFECT" else "−"
    detail = " ⚙" if s.needs_detail else ""
    print(f"  {marker}{detail} [{s.kind:26s}] {s.action_fqn}")
    print(f"        method        : {s.code_method_fqn}")
    print(f"        kind          : {s.annotation_kind}")
    if s.effect_entry is not None:
        print(f"        effect_entry  : {json.dumps(s.effect_entry, ensure_ascii=False)}")
    print(f"        {s.recommendation}")
    print(f"        rationale: {s.rationale}")
    print()


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC33 — Annotation drift remediation (W67)")
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
            for k in ("ADD_ANNOTATION_EFFECT", "REMOVE_ANNOTATION_EFFECT"):
                n = r.step_counts.get(k, 0)
                if n:
                    print(f"    {k:25s} {n:3d}")
            if r.needs_detail:
                print(f"  Needs extra detail       : {r.needs_detail}")
            print()
            if r.report.steps:
                any_drift = True
                _banner("Annotation remediation steps (⚙ = needs extra detail)")
                for s in r.report.steps:
                    _print_step(s)

        _banner(
            "✓ All contract annotations documented"
            if not any_drift
            else "Section 2 fix path: append/remove effects_json entries above"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
