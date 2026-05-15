"""UC21 — Framework health report on production (W53).

UC16 ran every *pipeline stage* (ingest → translate → schema → drift → domain)
in sequence. UC21 reports every *verification gate* (translator quality +
action↔code agreement + param signature + idiom coverage) for each production
repo and surfaces whether the framework considers it healthy.

A repo is healthy when every applicable gate's rate ≥ HEALTH_THRESHOLD (0.80).
Mismatches between repos (e.g., v1 healthy but v2 unhealthy because of action
declaration drift) are the kind of finding the framework is designed to make
visible.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc21_framework_health.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from backend.sim_v2.core.verification.framework_health import (
    HEALTH_THRESHOLD,
    HealthReport,
    framework_health_check,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPOS: tuple[str, ...] = (
    "slab-design-real",
    "slab-design-real-v2",
)
TRANSLATOR_SAMPLE = 100
IDIOM_SAMPLE = 100


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def _format_gate_line(gate) -> str:
    marker = "✓" if gate.is_healthy else "✗"
    if gate.applicable == 0:
        return f"  {marker} {gate.name:30s} (no applicable items)"
    rate_pct = gate.rate * 100
    return (
        f"  {marker} {gate.name:30s} "
        f"{gate.verified:4d}/{gate.applicable:<4d} = {rate_pct:5.1f}%"
    )


def print_report(report: HealthReport) -> None:
    health_marker = "✓ HEALTHY" if report.is_healthy else "✗ UNHEALTHY"
    _banner(f"{report.repo_id}  {health_marker}  (overall {report.overall_rate * 100:.1f}%)")
    for g in report.gates:
        print(_format_gate_line(g))
        if g.findings:
            for f in g.findings[:3]:
                short = f if len(f) <= 70 else f[:67] + "…"
                print(f"      ! {short}")
    print()


def main(
    repos: tuple[str, ...] = DEFAULT_REPOS,
    *,
    translator_sample: int = TRANSLATOR_SAMPLE,
    idiom_sample: int = IDIOM_SAMPLE,
) -> int:
    print("=" * 78)
    print("UC21 — Framework health report (W53)")
    print(f"  (gate threshold: {HEALTH_THRESHOLD * 100:.0f}%)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        all_healthy = True
        for repo_id in repos:
            report = framework_health_check(
                session, repo_id,
                translator_sample=translator_sample,
                idiom_sample=idiom_sample,
            )
            print_report(report)
            if not report.is_healthy:
                all_healthy = False

        _banner(
            "✓ All repos healthy" if all_healthy
            else "✗ At least one repo is unhealthy — see gates above"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
