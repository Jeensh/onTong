"""UC39 — B-level (behavioral fidelity) capstone for sim_v2 (W73).

Where UC36 closed the **contract-level** loop (snapshots, lifecycles, simulated
post-merge) and UC37/UC38 surveyed the **production reach** of synthesized
fixtures + invariants, UC39 closes the **behavioral** loop by wiring W71→W73→W59:

    W71  synthesize_fixtures_for_action   →  N fixtures with expected_output=None
    W73  attach_baselines                  →  fixtures with Java baseline attached
    W59  BehaviorTwinRunner                →  PASS / FAIL_OUTPUT / ERROR per fixture

Two-part demo:

    PART A — Synthetic proof-of-pipeline
    ─────────────────────────────────────
    A self-contained Python-translatable method (`add_positives`) with three
    hand-authored baseline entries, run through the full pipeline. Surfaces
    the green path that the framework can deliver *today* on any method whose
    translation is sound and whose dependencies are sandbox-resolvable.

    PART B — Production gap diagnosis
    ─────────────────────────────────────
    For each of the 11 W71-driveable v2 actions, this demo:

        1. Generates fixtures via W71
        2. Attaches whatever baseline annotations exist (empty by default)
        3. Runs the twin runner
        4. Categorises the failure cause:
             - TRANSLATOR_NAMERROR    (Java symbol not in Python sandbox)
             - TRANSLATOR_ATTRERROR   (str.length() etc.)
             - TRANSLATOR_SYNTAX      (translation gap)
             - SANDBOX_DEPENDENCY     (JPA repo / Spring bean missing)
             - NO_BASELINE            (W73 baselines not authored yet)

The output is the framework's honest B-level distance — every production
method's failure has a named, addressable cause.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc39_b_level_capstone.run
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
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
    BehaviorFixtureStore,
    BehaviorTwinRunner,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.verification.java_oracle_adapter import (
    JavaBaselineEntry,
    JavaBaselineMap,
    attach_baselines,
)
from backend.sim_v2.core.verification.oracle import OracleRequest
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


TARGET_REPO = "slab-design-real-v2"
JAVA_LANGUAGE = Language(tsjava.language())


# ─────────────────────────────────────────────────────────────────────────────
# PART A — Synthetic proof-of-pipeline
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SyntheticCapstoneResult:
    fixtures_generated: int
    fixtures_matched:   int
    fixtures_passed:    int
    aggregate_status:   str


# A method whose translation actually runs in the W59 sandbox.
_SYNTHETIC_JAVA = """
public class Calc {
    public int addPositives(int a, int b) {
        int x = a;
        if (x < 0) { x = 0; }
        int y = b;
        if (y < 0) { y = 0; }
        return x + y;
    }
}
"""


def _translate_synthetic() -> tuple[str, str]:
    tree = Parser(JAVA_LANGUAGE).parse(_SYNTHETIC_JAVA.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body_n = next(x for x in c.children if x.type == "class_body")
            for m in body_n.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    if method is None:
        raise RuntimeError("could not find synthetic method")
    result = JavaToPythonTranslator().translate(method, indent=0)
    return result.python_source, "addPositives"


def run_synthetic_capstone() -> SyntheticCapstoneResult:
    """Build N synthetic fixtures, attach baselines, run W59, return aggregate."""
    src, fn_name = _translate_synthetic()

    # Build synthesized-style fixtures manually (no DB needed)
    fixtures = []
    for i, (a, b) in enumerate([(1, 2), (-3, 5), (0, 0), (4, 4)]):
        fixtures.append(BehaviorFixture(
            fixture_id=f"synthetic.addPos#{i}",
            python_source=src,
            function_name=fn_name,
            input_args=(None, a, b),
            input_kwargs={},
            expected_output=None,        # W71-style placeholder
        ))

    # Java baseline annotations (truth: max(0,a)+max(0,b))
    baseline = JavaBaselineMap([
        JavaBaselineEntry("test.add_positives", (None, 1, 2), 3),
        JavaBaselineEntry("test.add_positives", (None, -3, 5), 5),
        JavaBaselineEntry("test.add_positives", (None, 0, 0), 0),
        JavaBaselineEntry("test.add_positives", (None, 4, 4), 8),
    ])

    rep = attach_baselines("test.add_positives", tuple(fixtures), baseline)
    store = BehaviorFixtureStore(list(rep.matched_fixtures))
    runner = BehaviorTwinRunner(store)
    engine = VerificationEngine(fixture_runner=runner, plugin="uc39.synthetic")

    req = OracleRequest(
        proposal_id="uc39.synthetic.addPos",
        fixture_subset=[f.fixture_id for f in rep.matched_fixtures],
    )
    result = engine.run_oracle(req)
    passes = sum(1 for r in result.by_fixture.values() if r.status == "PASS")
    return SyntheticCapstoneResult(
        fixtures_generated=len(fixtures),
        fixtures_matched=len(rep.matched_fixtures),
        fixtures_passed=passes,
        aggregate_status=result.aggregate_status,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PART B — Production gap diagnosis
# ─────────────────────────────────────────────────────────────────────────────


_NAMEERR_TAG       = "TRANSLATOR_NAMERROR"
_ATTRERR_TAG       = "TRANSLATOR_ATTRERROR"
_SYNTAX_TAG        = "TRANSLATOR_SYNTAX"
_NO_BASELINE_TAG   = "NO_BASELINE"
_GREEN_TAG         = "GREEN"
_OTHER_TAG         = "OTHER"


@dataclass(frozen=True)
class ProductionGapRow:
    action_fqn:       str
    fixtures:         int
    matched:          int
    passes:           int
    failure_cause:    str
    sample_error:     str = ""


@dataclass(frozen=True)
class ProductionGapReport:
    total_actions:     int
    rows:              tuple[ProductionGapRow, ...]

    @property
    def cause_counts(self) -> Counter[str]:
        return Counter(r.failure_cause for r in self.rows)


def _load_body(session: Session, fqn: str, repo_id: str) -> str | None:
    row = session.execute(
        text(
            "SELECT body_text FROM code_methods "
            "WHERE fqn = :f AND repo_id = :r"
        ),
        {"f": fqn, "r": repo_id},
    ).fetchone()
    return row[0] if row else None


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


def _classify_failure(error_text: str) -> str:
    if not error_text:
        return _GREEN_TAG
    if "did not compile" in error_text or "SyntaxError" in error_text:
        return _SYNTAX_TAG
    if "NameError" in error_text:
        return _NAMEERR_TAG
    if "AttributeError" in error_text:
        return _ATTRERR_TAG
    return _OTHER_TAG


def _row_for_production(
    session: Session,
    action: ActionView,
    baselines: JavaBaselineMap,
) -> ProductionGapRow | None:
    if not action.code_method_fqn:
        return None
    body = _load_body(session, action.code_method_fqn, action.repo_id)
    if not body:
        return None
    try:
        translated = _translate_body(body)
    except Exception as exc:
        return ProductionGapRow(
            action_fqn=action.fqn, fixtures=0, matched=0, passes=0,
            failure_cause=_SYNTAX_TAG,
            sample_error=f"{type(exc).__name__}: {exc}"[:140],
        )
    if translated is None:
        return ProductionGapRow(
            action_fqn=action.fqn, fixtures=0, matched=0, passes=0,
            failure_cause=_SYNTAX_TAG, sample_error="empty translation",
        )
    src, fn_name = translated
    rep = synthesize_fixtures_for_action(
        session, action,
        function_name=fn_name, python_source=src,
    )
    if not rep.fixtures or rep.synthesizable_params == 0:
        return None

    # Attach (almost always 0 matches today — baselines aren't authored yet).
    attached = attach_baselines(action.fqn, rep.fixtures, baselines)
    if not attached.matched_fixtures:
        # Run the runner without a baseline to discover the failure cause.
        # We pick the first fixture and surface its exception class.
        store = BehaviorFixtureStore(list(rep.fixtures))
        runner = BehaviorTwinRunner(store)
        first = rep.fixtures[0]
        r = runner.run_fixture(first.fixture_id, plugin="uc39", apply_diffs={})
        cause = (
            _classify_failure(r.error or "") if r.status == "ERROR"
            else _NO_BASELINE_TAG
        )
        sample = (r.error or "").splitlines()[0][:140] if r.error else ""
        return ProductionGapRow(
            action_fqn=action.fqn,
            fixtures=len(rep.fixtures),
            matched=0,
            passes=0,
            failure_cause=cause,
            sample_error=sample,
        )

    store = BehaviorFixtureStore(list(attached.matched_fixtures))
    runner = BehaviorTwinRunner(store)
    engine = VerificationEngine(fixture_runner=runner, plugin="uc39")
    req = OracleRequest(
        proposal_id=f"uc39.prod.{action.fqn}",
        fixture_subset=[f.fixture_id for f in attached.matched_fixtures],
    )
    result = engine.run_oracle(req)
    passes = sum(1 for r in result.by_fixture.values() if r.status == "PASS")
    cause = _GREEN_TAG if passes == len(attached.matched_fixtures) else _OTHER_TAG
    return ProductionGapRow(
        action_fqn=action.fqn,
        fixtures=len(rep.fixtures),
        matched=len(attached.matched_fixtures),
        passes=passes,
        failure_cause=cause,
    )


def run_production_gap(
    session: Session,
    baselines: JavaBaselineMap | None = None,
    repo_id: str = TARGET_REPO,
) -> ProductionGapReport:
    actions = load_actions(session, repo_id)
    baselines = baselines or JavaBaselineMap()
    rows: list[ProductionGapRow] = []
    for a in actions:
        r = _row_for_production(session, a, baselines)
        if r is not None:
            rows.append(r)
    return ProductionGapReport(
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
    print("UC39 — B-LEVEL CAPSTONE  (behavioral fidelity)")
    print("=" * 78)
    print()

    _banner("PART A — Synthetic pipeline proof")
    a = run_synthetic_capstone()
    print(f"  Fixtures generated  : {a.fixtures_generated}")
    print(f"  Baselines attached  : {a.fixtures_matched}")
    print(f"  Behavioral PASSes   : {a.fixtures_passed}")
    print(f"  Aggregate status    : {a.aggregate_status}")
    if a.fixtures_passed == a.fixtures_matched and a.fixtures_matched > 0:
        print("  → W71 ➜ W73 ➜ W59 pipeline closes the loop on translatable code.")
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping production survey")
        return 0

    try:
        _banner("PART B — Production gap diagnosis")
        b = run_production_gap(session)
        print(f"  Total actions          : {b.total_actions}")
        print(f"  Diagnosed actions      : {len(b.rows)}")
        print()
        print("  Failure-cause breakdown:")
        for c, n in sorted(b.cause_counts.items(), key=lambda x: -x[1]):
            print(f"    {c:24s} {n}")
        print()

        for row in b.rows:
            mark = "✓" if row.failure_cause == _GREEN_TAG else "·"
            print(f"  {mark} [{row.failure_cause:24s}] "
                  f"fx={row.fixtures} match={row.matched} pass={row.passes}  "
                  f"{row.action_fqn}")
            if row.sample_error:
                print(f"      └ {row.sample_error}")
        print()

        # Verdict
        green = b.cause_counts.get(_GREEN_TAG, 0)
        nameerr = b.cause_counts.get(_NAMEERR_TAG, 0)
        attrerr = b.cause_counts.get(_ATTRERR_TAG, 0)
        no_baseline = b.cause_counts.get(_NO_BASELINE_TAG, 0)
        _banner("B-level verdict")
        if green == len(b.rows) and len(b.rows) > 0:
            print(f"  ✓ FULL behavioral fidelity reached on {green} actions")
        else:
            print(f"  Behavioral PASS rate    : {green}/{len(b.rows)}")
            print()
            print("  Translator gaps blocking B-level reach:")
            if nameerr:
                print(f"    NAMERROR  ({nameerr}) — Java refs (JPA repos / Entity ctors)")
                print("                                not resolvable in sandbox; need")
                print("                                stub-injection layer (future W74).")
            if attrerr:
                print(f"    ATTRERROR ({attrerr}) — Java idioms (str.length(), etc.)")
                print("                                require translator rewrites.")
            if no_baseline:
                print(f"    NO_BASELINE ({no_baseline}) — fixtures translate cleanly but")
                print("                                lack Java reference outputs.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
