"""UC38 — Production invariant survey for slab-design-real-v2 (W72).

Composes W71 (fixture synthesizer) with W72 (twin invariant runner) to
answer: of the 11 driveable v2 actions, how many satisfy the baseline-free
invariants — determinism, no-unexpected-throw, declared-return-type?

Pipeline per action:

    1. Load `code_methods.body_text`
    2. Translate to Python with `JavaToPythonTranslator`
    3. Synthesize fixtures via W71
    4. Look up the action's declared `output_json.type` (= declared return)
    5. Run `TwinInvariantRunner` over the synthesized fixtures
    6. Aggregate per-action status

Action-level aggregate status:
    PASS                  — every synthesized fixture satisfies all invariants
    FAIL_DETERMINISM      — at least one fixture had a determinism violation
    FAIL_TYPE             — at least one fixture had a return-type mismatch
    FAIL_THROW            — at least one fixture threw unexpectedly
    INCONCLUSIVE          — no fixtures (action skipped earlier in pipeline)
    ERROR                 — translation succeeded but invariant runner ERRORed

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc38_production_invariants.run
"""
from __future__ import annotations

import json
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
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.verification.twin_invariants import (
    InvariantCheckResult,
    run_invariants_for_fixtures,
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
class ActionInvariantRow:
    action_fqn:       str
    declared_return:  str
    fixtures:         int
    passing:          int
    status:           str
    sample_error:     str = ""


@dataclass(frozen=True)
class InvariantSurveyReport:
    repo_id:        str
    total_actions:  int
    rows:           tuple[ActionInvariantRow, ...]

    @property
    def status_counts(self) -> Counter[str]:
        return Counter(r.status for r in self.rows)

    @property
    def total_fixtures(self) -> int:
        return sum(r.fixtures for r in self.rows)

    @property
    def total_passing(self) -> int:
        return sum(r.passing for r in self.rows)


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


def _load_output_type(
    session: Session, action_fqn: str, repo_id: str,
) -> str:
    row = session.execute(
        text(
            "SELECT output_json FROM actions "
            "WHERE fqn = :f AND repo_id = :r"
        ),
        {"f": action_fqn, "r": repo_id},
    ).fetchone()
    if row is None or not row[0]:
        return "void"
    try:
        parsed = json.loads(row[0])
    except json.JSONDecodeError:
        return "void"
    if not isinstance(parsed, dict):
        return "void"
    return parsed.get("type") or "void"


def _translate_body(body_text: str) -> tuple[str, str] | None:
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
    first = src.splitlines()[0]
    if not first.startswith("def "):
        return None
    fn = first[4:].split("(", 1)[0].strip()
    return src, fn


def _classify_aggregate(
    fixture_results: list[InvariantCheckResult],
) -> tuple[str, str]:
    """Return (status, sample_error)."""
    if not fixture_results:
        return "INCONCLUSIVE", ""
    statuses = {r.status for r in fixture_results}
    if statuses == {"PASS"}:
        return "PASS", ""
    # Pick a single representative failure (the worst one).
    priority = (
        "FAIL_NONDETERMINISTIC",
        "FAIL_UNEXPECTED_THROW",
        "FAIL_RETURN_TYPE",
        "ERROR",
    )
    label_map = {
        "FAIL_NONDETERMINISTIC": "FAIL_DETERMINISM",
        "FAIL_UNEXPECTED_THROW": "FAIL_THROW",
        "FAIL_RETURN_TYPE":      "FAIL_TYPE",
        "ERROR":                 "ERROR",
    }
    for s in priority:
        if s in statuses:
            sample = next(
                (r.error for r in fixture_results if r.status == s and r.error),
                "",
            )
            return label_map[s], sample[:140]
    return "ERROR", ""


def _row_for(
    session: Session, action: ActionView,
) -> ActionInvariantRow | None:
    if not action.code_method_fqn:
        return None
    body = _load_body(session, action.code_method_fqn, action.repo_id)
    if not body:
        return None
    try:
        translated = _translate_body(body)
    except Exception:
        return None
    if translated is None:
        return None
    python_source, function_name = translated
    rep = synthesize_fixtures_for_action(
        session, action,
        function_name=function_name, python_source=python_source,
    )
    if not rep.fixtures:
        return None
    if rep.synthesizable_params == 0:
        # All-null fixtures will throw or no-op depending on body — skip them
        # from the survey since the result reflects how the method tolerates
        # nulls, not whether the twin is well-behaved on real inputs.
        return None

    declared_return = _load_output_type(
        session, action.fqn, action.repo_id,
    )
    agg = run_invariants_for_fixtures(
        rep.fixtures, declared_return=declared_return,
    )
    results = list(agg.fixture_id_to_result.values())
    status, sample = _classify_aggregate(results)
    return ActionInvariantRow(
        action_fqn=action.fqn,
        declared_return=declared_return,
        fixtures=len(results),
        passing=sum(1 for r in results if r.passed),
        status=status,
        sample_error=sample,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry
# ─────────────────────────────────────────────────────────────────────────────


def run_invariant_survey(
    session: Session, repo_id: str = TARGET_REPO,
) -> InvariantSurveyReport:
    actions = load_actions(session, repo_id)
    rows: list[ActionInvariantRow] = []
    for a in actions:
        r = _row_for(session, a)
        if r is not None:
            rows.append(r)
    return InvariantSurveyReport(
        repo_id=repo_id,
        total_actions=len(actions),
        rows=tuple(rows),
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
    print(f"UC38 — Production invariant survey  ({TARGET_REPO})")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        r = run_invariant_survey(session)

        _banner("Aggregate")
        print(f"  Repo               : {r.repo_id}")
        print(f"  Total actions      : {r.total_actions}")
        print(f"  Surveyed actions   : {len(r.rows)} "
              f"(W71-driveable subset)")
        print(f"  Total fixtures     : {r.total_fixtures}")
        print(f"  Passing fixtures   : {r.total_passing} "
              f"({100 * r.total_passing / max(1, r.total_fixtures):.1f}%)")
        print()

        _banner("Action-level status counts")
        for s, n in sorted(r.status_counts.items(), key=lambda x: -x[1]):
            print(f"  {s:18s} {n}")
        print()

        _banner("Per-action")
        for row in r.rows:
            mark = "✓" if row.status == "PASS" else "✗"
            print(f"  {mark} [{row.status:18s}] "
                  f"{row.passing}/{row.fixtures}  "
                  f"return={row.declared_return:10s}  {row.action_fqn}")
            if row.sample_error:
                print(f"      └ {row.sample_error}")
        print()

        passing = r.status_counts.get("PASS", 0)
        _banner(
            f"✓ W72 production reach: {passing}/{len(r.rows)} surveyed "
            "actions invariant-clean"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
