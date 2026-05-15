"""UC19 — Idiom-level translator coverage survey (W49).

W41 proved 100% of production methods translate cleanly. UC19 goes a step
further: of the methods that USE specific Java idioms (try-with-resources,
Optional, BigDecimal arithmetic, etc.), did the translator emit the
*idiomatic* Python equivalent?

For each idiom rule in `DEFAULT_RULES`, the survey reports:
    applicable   — number of production methods that hit the rule's java pattern
    match        — of those, how many also have the python pattern
    violation    — of those, how many don't (a translator coverage gap)

Result: per-rule match rate over production code.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc19_idiom_coverage.run
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.verification.idiom_verifier import (
    DEFAULT_RULES,
    IdiomCheck,
    IdiomRule,
    verify_idioms,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc11_production_translator.run import (
    fetch_methods,
    parse_method_declaration,
)


DEFAULT_REPO_ID = "slab-design-real"
DEFAULT_SAMPLE_SIZE = 300


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RulePerformance:
    rule_name:    str
    applicable:   int = 0
    match:        int = 0
    violation:    int = 0

    @property
    def match_rate(self) -> float:
        return (self.match / self.applicable) if self.applicable else 0.0


@dataclass(frozen=True)
class IdiomCoverageReport:
    repo_id:        str
    sample_size:    int
    per_rule:       tuple[RulePerformance, ...]
    translate_pass: int = 0


def survey_idiom_coverage(
    session: Session,
    repo_id: str,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    rules: tuple[IdiomRule, ...] = DEFAULT_RULES,
) -> IdiomCoverageReport:
    methods = fetch_methods(session, repo_id, limit=sample_size)
    aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    translate_pass = 0

    for m in methods:
        body_text = m["body_text"].strip()
        if not body_text:
            continue
        try:
            node = parse_method_declaration(body_text)
        except Exception:
            continue
        if node is None:
            continue
        try:
            out = JavaToPythonTranslator().translate(node, indent=0)
        except Exception:
            continue
        if out.signature_locked:
            continue
        translate_pass += 1
        checks = verify_idioms(body_text, out.python_source, rules)
        for check in checks:
            aggregate[check.rule_name][check.status] += 1

    per_rule = tuple(
        RulePerformance(
            rule_name=rule.name,
            applicable=aggregate[rule.name].get("MATCH", 0)
                       + aggregate[rule.name].get("VIOLATION", 0),
            match=aggregate[rule.name].get("MATCH", 0),
            violation=aggregate[rule.name].get("VIOLATION", 0),
        )
        for rule in rules
    )

    return IdiomCoverageReport(
        repo_id=repo_id,
        sample_size=len(methods),
        per_rule=per_rule,
        translate_pass=translate_pass,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def main(
    repo_id: str = DEFAULT_REPO_ID, *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> int:
    print("=" * 78)
    print("UC19 — Idiom-level translator coverage (W49)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        _banner(f"Repo: {repo_id}  (sample size {sample_size})")
        report = survey_idiom_coverage(session, repo_id, sample_size=sample_size)
        print(f"  Methods sampled    : {report.sample_size}")
        print(f"  Translate PASS     : {report.translate_pass}")
        print()
        _banner("Per-rule coverage")
        print(f"  {'Rule':<25s} {'Applic.':>8s} {'Match':>7s} {'Viol.':>6s} {'Rate':>6s}")
        for r in report.per_rule:
            rate_str = f"{r.match_rate * 100:5.1f}%" if r.applicable else "  n/a"
            print(f"  {r.rule_name:<25s} {r.applicable:8d} {r.match:7d} "
                  f"{r.violation:6d} {rate_str}")
        print()

        problem_rules = [r for r in report.per_rule if r.violation > 0]
        if problem_rules:
            _banner("Rules with violations")
            for r in problem_rules:
                print(f"  ! {r.rule_name}: {r.violation}/{r.applicable} VIOLATION")
            print()

        print("✓ Idiom-level survey complete — per-rule MATCH rates above are the")
        print("  translator's *idiomatic* coverage on real production Java.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
