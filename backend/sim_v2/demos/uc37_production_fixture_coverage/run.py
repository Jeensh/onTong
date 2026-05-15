"""UC37 — Production fixture coverage for slab-design-real-v2 (W71).

Surfaces *how much* of the production action surface the W71 fixture
synthesizer can drive end-to-end. For every action with a `code_method_fqn`
this demo:

    1. Looks up `code_methods.body_text` in the v2 repo.
    2. Wraps + parses + translates the Java body to Python via
       `JavaToPythonTranslator`.
    3. Runs `synthesize_fixtures_for_action` against the translated source.
    4. Categorises the action into one of:

        NO_LINK         — no code_method_fqn parsed out of description
        NO_BODY         — code_methods row missing or body_text empty
        TRANSLATE_FAIL  — translator raised on this method
        ZERO_FIXTURES   — synth returned 0 fixtures (malformed params)
        ALL_NULL        — every param is object_ref (skipped)
        PARTIAL         — at least one primitive driven; some skipped
        FULL_PRIMITIVE  — every declared param is primitive (no skips)

The aggregate gives the framework's *behavioral-twin reach* on v2 — the
baseline for W72 (twin invariants) and W73 (Java oracle adapter).

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc37_production_fixture_coverage.run
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass

import tree_sitter_java as tsjava
from sqlalchemy import text
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.synthesizer.java_translator import (
    JavaToPythonTranslator,
)
from backend.sim_v2.core.verification.fixture_synthesizer import (
    FixtureSynthesisReport,
    synthesize_fixtures_for_action,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


TARGET_REPO = "slab-design-real-v2"

JAVA_LANGUAGE = Language(tsjava.language())


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ActionFixtureRow:
    action_fqn:       str
    code_method_fqn:  str | None
    status:           str    # NO_LINK / NO_BODY / TRANSLATE_FAIL / ZERO_FIXTURES /
                             # ALL_NULL / PARTIAL / FULL_PRIMITIVE
    fixtures:         int
    primitives:       int    # synthesizable param count
    skipped:          int    # object_ref / unknown param count
    error:            str = ""


@dataclass(frozen=True)
class CoverageReport:
    repo_id:           str
    total_actions:     int
    rows:              tuple[ActionFixtureRow, ...]

    @property
    def status_counts(self) -> Counter[str]:
        return Counter(r.status for r in self.rows)

    @property
    def total_fixtures(self) -> int:
        return sum(r.fixtures for r in self.rows)

    @property
    def directly_driveable(self) -> int:
        """Count of actions where synthesizer drove at least one primitive."""
        return sum(
            1 for r in self.rows
            if r.status in ("FULL_PRIMITIVE", "PARTIAL")
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _load_body(session: Session, fqn: str, repo_id: str) -> str | None:
    row = session.execute(
        text(
            "SELECT body_text FROM code_methods "
            "WHERE fqn = :f AND repo_id = :r"
        ),
        {"f": fqn, "r": repo_id},
    ).fetchone()
    if row is None:
        return None
    return row[0]


def _translate_body(body_text: str) -> tuple[str, str] | None:
    """Wrap body_text in a class shell, parse, translate.

    Returns (python_source, function_name) on success, or None on failure.
    """
    wrapped = f"public class C {{ {body_text} }}"
    tree = Parser(JAVA_LANGUAGE).parse(wrapped.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body_n = next(
                (x for x in c.children if x.type == "class_body"), None,
            )
            if body_n is None:
                return None
            for m in body_n.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    if method is None:
        return None
    result = JavaToPythonTranslator().translate(method, indent=0)
    src = result.python_source
    # First line is `def <name>(self, ...):` — pull the name
    first = src.splitlines()[0]
    if not first.startswith("def "):
        return None
    fn = first[4:].split("(", 1)[0].strip()
    return src, fn


def _classify(report: FixtureSynthesisReport) -> str:
    if not report.fixtures:
        return "ZERO_FIXTURES"
    if report.synthesizable_params == 0:
        return "ALL_NULL"
    if report.skipped_params == 0:
        return "FULL_PRIMITIVE"
    return "PARTIAL"


def _row_for(
    session: Session, action: ActionView,
) -> ActionFixtureRow:
    if not action.code_method_fqn:
        return ActionFixtureRow(
            action_fqn=action.fqn,
            code_method_fqn=None,
            status="NO_LINK",
            fixtures=0,
            primitives=0,
            skipped=0,
        )
    body = _load_body(session, action.code_method_fqn, action.repo_id)
    if not body:
        return ActionFixtureRow(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="NO_BODY",
            fixtures=0,
            primitives=0,
            skipped=0,
        )
    try:
        translated = _translate_body(body)
    except Exception as exc:  # translator coverage is partial; trap & label
        return ActionFixtureRow(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="TRANSLATE_FAIL",
            fixtures=0,
            primitives=0,
            skipped=0,
            error=f"{type(exc).__name__}: {exc}",
        )
    if translated is None:
        return ActionFixtureRow(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="TRANSLATE_FAIL",
            fixtures=0,
            primitives=0,
            skipped=0,
            error="empty translation",
        )
    python_source, function_name = translated
    rep = synthesize_fixtures_for_action(
        session, action,
        function_name=function_name, python_source=python_source,
    )
    return ActionFixtureRow(
        action_fqn=action.fqn,
        code_method_fqn=action.code_method_fqn,
        status=_classify(rep),
        fixtures=len(rep.fixtures),
        primitives=rep.synthesizable_params,
        skipped=rep.skipped_params,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry
# ─────────────────────────────────────────────────────────────────────────────


def run_production_coverage(
    session: Session, repo_id: str = TARGET_REPO,
) -> CoverageReport:
    actions = load_actions(session, repo_id)
    rows = tuple(_row_for(session, a) for a in actions)
    return CoverageReport(
        repo_id=repo_id,
        total_actions=len(actions),
        rows=rows,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print(f"UC37 — Production fixture coverage  ({TARGET_REPO})")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        r = run_production_coverage(session)

        _banner("Aggregate")
        print(f"  Repo               : {r.repo_id}")
        print(f"  Total actions      : {r.total_actions}")
        print(f"  Total fixtures     : {r.total_fixtures}")
        print(f"  Directly driveable : {r.directly_driveable} "
              f"({100 * r.directly_driveable / max(1, r.total_actions):.1f}%)")
        print()

        _banner("By status")
        for s, n in sorted(r.status_counts.items(), key=lambda x: -x[1]):
            print(f"  {s:14s} {n}")
        print()

        # Show driveable actions (the win path)
        driveable = [
            row for row in r.rows
            if row.status in ("FULL_PRIMITIVE", "PARTIAL")
        ]
        if driveable:
            _banner(f"Driveable actions ({len(driveable)})")
            for row in driveable:
                print(f"  {row.status:14s} {row.fixtures:3d} fixtures  "
                      f"prim={row.primitives}/{row.primitives + row.skipped}  "
                      f"{row.action_fqn}")
            print()

        # Show translate failures (next sprint target)
        failures = [r for r in r.rows if r.status == "TRANSLATE_FAIL"]
        if failures:
            _banner(f"Translator failures ({len(failures)})")
            for row in failures[:6]:
                print(f"  • {row.action_fqn}")
                print(f"    {row.error[:120]}")
            if len(failures) > 6:
                print(f"  … and {len(failures) - 6} more")
            print()

        _banner(
            f"✓ W71 production reach: {r.directly_driveable}/{r.total_actions} "
            "actions driveable end-to-end"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
