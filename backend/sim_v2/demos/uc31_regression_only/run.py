"""UC31 — Regression-only CI mode (W65).

The layered verification stack surfaces drift on every run, but in CI you
only want to flag *newly-introduced* drift — anything inherited from the
previous baseline is noise. UC31 demonstrates the regression-only workflow:

    1.  CI workflow stores a baseline `VerificationSnapshot` in the repo.
    2.  On every commit, take a new snapshot.
    3.  `diff_snapshots(baseline, current)` → `RegressionReport`.
    4.  Fail CI only when `RegressionReport.has_regression` is True.

This demo:
    A.  Captures the **real** baseline from `slab-design-real`.
    B.  Synthesizes a "post-commit" snapshot by **injecting a brand-new
        finding** (an extra UNDECLARED_THROWS on a fictitious action — the
        kind of drift a sloppy commit might introduce).
    C.  Also **removes one finding** to demonstrate that fixes are surfaced
        as `fixed_findings` (the symmetric signal — Section 2 closed a gap).
    D.  Diffs the two snapshots and prints new vs fixed vs unchanged.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc31_regression_only.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.verification.snapshot import (
    FindingKey,
    GATE_EXCEPTION,
    RegressionReport,
    VerificationSnapshot,
    diff_snapshots,
    snapshot_to_json,
    take_snapshot,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPO = "slab-design-real"


def synthesize_post_commit_snapshot(
    baseline: VerificationSnapshot,
) -> VerificationSnapshot:
    """Build a synthetic "after this commit" snapshot from the baseline:

      - Add one brand-new finding (simulated regression).
      - Remove one existing finding (simulated fix).

    The new finding uses a fictitious action FQN so it's unambiguous in
    the diff output. The removed finding is the first one in the baseline
    so the demo is deterministic.
    """
    # 1) brand-new regression — a fictional action throwing a new exception.
    new_finding = FindingKey(
        gate=GATE_EXCEPTION,
        action_fqn="action.scm.demo.uc31_new_action",
        status="UNDECLARED_THROWS",
        key="undeclared:HypotheticalException",
    )

    # 2) one finding "fixed" by the synthetic commit.
    keep: list[FindingKey] = list(baseline.findings)
    removed_finding = keep.pop(0) if keep else None

    return VerificationSnapshot(
        repo_id=baseline.repo_id,
        findings=tuple(sorted(
            keep + [new_finding], key=lambda f: f.as_tuple(),
        )),
    )


@dataclass(frozen=True)
class UC31Result:
    baseline:        VerificationSnapshot
    current:         VerificationSnapshot
    regression:      RegressionReport


def run_demo(session: Session, repo_id: str = DEFAULT_REPO) -> UC31Result:
    baseline = take_snapshot(session, repo_id)
    current  = synthesize_post_commit_snapshot(baseline)
    regression = diff_snapshots(baseline, current)
    return UC31Result(
        baseline=baseline, current=current, regression=regression,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_findings(label: str, findings, marker: str) -> None:
    print(f"  {label} ({len(findings)}):")
    if not findings:
        print(f"    {marker} (none)")
        return
    grouped: dict[str, list[FindingKey]] = {}
    for f in findings:
        grouped.setdefault(f.gate, []).append(f)
    for gate, group in grouped.items():
        print(f"    {marker} [{gate}]")
        for f in group:
            print(f"        {f.action_fqn:50s} {f.status:25s} {f.key}")


def main() -> int:
    print("=" * 78)
    print("UC31 — Regression-only CI mode (W65)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        result = run_demo(session)
        _banner("Baseline snapshot")
        print(f"  Repo            : {result.baseline.repo_id}")
        print(f"  Total findings  : {len(result.baseline.findings)}")
        print(f"  Serialized size : {len(snapshot_to_json(result.baseline))} bytes")
        print()

        _banner("Synthetic post-commit snapshot")
        print(f"  Total findings  : {len(result.current.findings)}")
        print(f"  (added 1 new, removed 1 baseline)")
        print()

        _banner("Regression diff")
        print(f"  has_regression  : {result.regression.has_regression}")
        print(f"  new_findings    : {len(result.regression.new_findings)}")
        print(f"  fixed_findings  : {len(result.regression.fixed_findings)}")
        print(f"  unchanged       : {len(result.regression.unchanged)}")
        print()

        _print_findings(
            "NEW (this commit introduced)", result.regression.new_findings, "+",
        )
        print()
        _print_findings(
            "FIXED (this commit resolved)", result.regression.fixed_findings, "−",
        )
        print()

        _banner(
            "✗ CI would fail — new regression detected"
            if result.regression.has_regression
            else "✓ CI would pass — no new regression"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
