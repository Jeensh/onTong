"""UC1 real-file demo — actual slab-design v2 SdMaxSplitCountAction.execute().

Differences from `uc1_v2_full_demo`:
  - Reads the real `SdMaxSplitCountAction.java` from sample-repos
  - Pre-populates Code Layer ontology with SDSlabEntity/SDOrderEntity getter
    return types, so chained `slab.getSecondWgtHigh().divide(...)` correctly
    routes through the BigDecimal mapper.
  - Mocks entity classes (SDSlabEntity / SDOrderEntity) for execution.
  - Validates side-effects (slab.maxSplitCountUpper / currentSplitCount setters).

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc1_real_file.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import tree_sitter_java as tsjava
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.modeling.code_layer.orm import CodeFieldRow, CodeMethodRow, CodeTypeRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.contracts.base import (
    DECIMAL64,
    RoundingMode,
    bd_set_scale,
)
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.ontology_type_resolver import OntologyTypeResolver
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    CompositeTypeResolver,
)

JAVA_LANGUAGE = Language(tsjava.language())

# Path to the real Java file under test
REAL_JAVA_FILE = (
    Path(__file__).resolve().parents[4]
    / "sample-repos/slab-design-real_v2/slab-design-feature/src/main/java"
    / "com/example/slabdesign/feature/sd/process/working/action/SdMaxSplitCountAction.java"
)


# ─────────────────────────────────────────────────────────────────────────────
# Mock entities + plugin contract types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SDOrderEntity:
    orderWgtHigh: Decimal
    productivity: Decimal
    def getOrderWgtHigh(self) -> Decimal: return self.orderWgtHigh
    def getProductivity(self) -> Decimal: return self.productivity


@dataclass
class SDSlabEntity:
    secondWgtHigh: Decimal
    maxSplitCountUpper: int | None = None
    currentSplitCount: int | None = None
    def getSecondWgtHigh(self) -> Decimal: return self.secondWgtHigh
    def setMaxSplitCountUpper(self, v: int) -> None:
        self.maxSplitCountUpper = v
    def setCurrentSplitCount(self, v: int) -> None:
        self.currentSplitCount = v


class AlgorithmException(Exception):
    """Plugin-specific exception matching slab-design v2 contract."""
    def __init__(self, step_no: int, step_name: str, code: str, message: str):
        super().__init__(f"[{step_no}/{step_name}] {code}: {message}")
        self.step_no = step_no
        self.step_name = step_name
        self.code = code


@dataclass(frozen=True)
class _SdErrorCodeEnum:
    ALG_ITERATION_NEEDED: str = "ALG_ITERATION_NEEDED"


SdErrorCode = _SdErrorCodeEnum()
STEP_NO = 7
STEP_NAME = "MAX_SPLIT_COUNT"


# ─────────────────────────────────────────────────────────────────────────────
# Ontology population — slab-design v2 entities + getters
# ─────────────────────────────────────────────────────────────────────────────


def build_ontology_session() -> Session:
    """Create an in-memory ontology DB populated with SDSlabEntity + SDOrderEntity."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        CodeMethodRow.__table__,
    ])
    session = Session(engine)

    repo_id = "slab-design-real_v2"

    classes = [
        ("SDSlabEntity", "com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity"),
        ("SDOrderEntity", "com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity"),
    ]
    for simple, fqn in classes:
        session.add(CodeTypeRow(
            fqn=fqn, simple_name=simple,
            package="com.example.slabdesign.store.sd.working.domain.entity",
            kind="CLASS", role="entity", repo_id=repo_id,
        ))

    methods = [
        # SDSlabEntity
        ("SDSlabEntity", "getSecondWgtHigh",        "java.math.BigDecimal"),
        ("SDSlabEntity", "setMaxSplitCountUpper",   "void"),
        ("SDSlabEntity", "setCurrentSplitCount",    "void"),
        # SDOrderEntity
        ("SDOrderEntity", "getOrderWgtHigh",        "java.math.BigDecimal"),
        ("SDOrderEntity", "getProductivity",        "java.math.BigDecimal"),
    ]
    pkg = "com.example.slabdesign.store.sd.working.domain.entity"
    for simple, name, return_type in methods:
        session.add(CodeMethodRow(
            fqn=f"{pkg}.{simple}#{name}",
            name=name,
            parent_type_fqn=f"{pkg}.{simple}",
            return_type=return_type,
            repo_id=repo_id,
        ))
    session.commit()
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Translate + compile
# ─────────────────────────────────────────────────────────────────────────────


def find_execute_method(tree):
    """Locate the `execute` method declaration in the parsed Java tree."""
    def walk(n):
        if n.type == "method_declaration":
            name_node = n.child_by_field_name("name")
            if name_node and name_node.text.decode() == "execute":
                return n
        for c in n.named_children:
            r = walk(c)
            if r:
                return r
        return None
    return walk(tree.root_node)


def translate_real_file(session: Session) -> tuple[str, dict[str, Any]]:
    source_bytes = REAL_JAVA_FILE.read_bytes()
    tree = Parser(JAVA_LANGUAGE).parse(source_bytes)
    method = find_execute_method(tree)
    if method is None:
        raise RuntimeError(f"execute method not found in {REAL_JAVA_FILE}")

    resolver = CompositeTypeResolver([
        OntologyTypeResolver(session, "slab-design-real_v2"),
        BigDecimalAwareResolver(),
    ])
    translator = JavaToPythonTranslator(type_resolver=resolver)
    tr = translator.translate(method, indent=0)
    return tr.python_source, {
        "imports":   tr.imports_needed,
        "notes":     tr.notes,
        "locked":    tr.signature_locked,
    }


def compile_to_callable(python_source: str):
    """Compile the emitted `def execute(self, order, slab)` into a callable.

    The emitted source uses Korean string literal in the throw (e.g.
    `"최대분할수상한 < 1 (raw=" + str(raw) + ") — 분할 불가"`). UTF-8 source ok.

    W17: strips `self, ` from the def signature so the returned callable's
    __globals__ exposes the exec() dict — required for ScenarioVerificationEngine
    to inject `_trace` collector per fixture run.
    """
    python_source = python_source.replace("def execute(self, ", "def execute(")
    globals_dict: dict[str, Any] = {
        "Decimal":              Decimal,
        "RoundingMode":         RoundingMode,
        "DECIMAL64":            DECIMAL64,
        "bd_set_scale":         bd_set_scale,
        "AlgorithmException":   AlgorithmException,
        "SdErrorCode":          SdErrorCode,
        "STEP_NO":              STEP_NO,
        "STEP_NAME":            STEP_NAME,
        "_trace":               None,  # placeholder for trace collector injection (W17)
    }
    exec(compile(python_source, "<demo-real>", "exec"), globals_dict)
    return globals_dict["execute"]


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Scenario:
    name: str
    order: SDOrderEntity
    slab: SDSlabEntity
    expected_max_split: int | None
    expected_exception: type | None = None


def make_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="normal (raw=10)",
            order=SDOrderEntity(orderWgtHigh=Decimal("20"), productivity=Decimal("0.5")),
            slab=SDSlabEntity(secondWgtHigh=Decimal("100")),
            expected_max_split=10,
        ),
        Scenario(
            name="boundary (raw=0.3 → ceil 1)",
            order=SDOrderEntity(orderWgtHigh=Decimal("1"), productivity=Decimal("1")),
            slab=SDSlabEntity(secondWgtHigh=Decimal("0.3")),
            expected_max_split=1,
        ),
        Scenario(
            name="error (raw=0 → maxSplit 0 < 1)",
            order=SDOrderEntity(orderWgtHigh=Decimal("1"), productivity=Decimal("1")),
            slab=SDSlabEntity(secondWgtHigh=Decimal("0")),
            expected_max_split=None,
            expected_exception=AlgorithmException,
        ),
    ]


def run_scenario(translated_fn, scenario: Scenario) -> tuple[str, str]:
    """Run translated execute(order, slab) — return (value_verdict, side_effect_verdict)."""
    exc: Exception | None = None
    try:
        translated_fn(scenario.order, scenario.slab)
    except Exception as e:
        exc = e

    # Value verdict
    if scenario.expected_exception is not None:
        if exc is not None and isinstance(exc, scenario.expected_exception):
            value_verdict = f"PASS ({type(exc).__name__} raised)"
        elif exc is not None:
            value_verdict = f"FAIL_DRIFT (got {type(exc).__name__}, expected {scenario.expected_exception.__name__})"
        else:
            value_verdict = f"FAIL_BREAKING (expected {scenario.expected_exception.__name__}, none raised)"
    else:
        if exc is not None:
            value_verdict = f"FAIL_BREAKING (raised {type(exc).__name__}: {exc})"
        else:
            value_verdict = "PASS"

    # Side-effect verdict (slab.maxSplitCountUpper / currentSplitCount)
    if scenario.expected_exception is not None:
        # Error path — slab setters not called
        if scenario.slab.maxSplitCountUpper is None and scenario.slab.currentSplitCount is None:
            side_effect_verdict = "PASS (setters not called)"
        else:
            side_effect_verdict = (
                f"FAIL (setters called: maxSplitCountUpper="
                f"{scenario.slab.maxSplitCountUpper}, currentSplitCount={scenario.slab.currentSplitCount})"
            )
    else:
        expected = scenario.expected_max_split
        if scenario.slab.maxSplitCountUpper == expected and scenario.slab.currentSplitCount == expected:
            side_effect_verdict = f"PASS (both set to {expected})"
        else:
            side_effect_verdict = (
                f"FAIL_DRIFT (maxSplitCountUpper={scenario.slab.maxSplitCountUpper}, "
                f"currentSplitCount={scenario.slab.currentSplitCount}, expected {expected})"
            )

    return value_verdict, side_effect_verdict


def main() -> int:
    print("=" * 78)
    print("UC1 real-file demo — actual SdMaxSplitCountAction.execute() (slab-design v2)")
    print("=" * 78)
    print()

    # Step 1: Build ontology session
    print("Step 1: Populate Code Layer ontology with SDSlabEntity + SDOrderEntity getters")
    session = build_ontology_session()
    method_count = session.query(CodeMethodRow).count()
    print(f"  OK — {method_count} CodeMethodRow rows seeded")
    print()

    # Step 2: Translate
    print(f"Step 2: Read + translate {REAL_JAVA_FILE.name}")
    py_source, meta = translate_real_file(session)
    print(f"  signature_locked: {meta['locked']}")
    if meta["notes"]:
        print(f"  translator notes: {meta['notes']}")
    print()
    print("Generated Python source:")
    for line in py_source.split("\n"):
        print(f"  | {line}")
    print()

    if meta["locked"]:
        print("ABORT: translator reported signature_locked")
        return 1

    # Step 3: Compile
    print("Step 3: Compile to callable")
    try:
        translated_fn = compile_to_callable(py_source)
        print("  OK — compiled")
    except SyntaxError as e:
        print(f"  FAIL — SyntaxError: {e}")
        return 2
    print()

    # Step 4: Run scenarios
    print("Step 4: Run 3 scenarios + verify side effects on slab")
    print()
    scenarios = make_scenarios()
    rows = [(s.name, *run_scenario(translated_fn, s)) for s in scenarios]
    print(f"  {'Scenario':<35} {'Value':<30} {'Side-effects':<35}")
    print(f"  {'-' * 35} {'-' * 30} {'-' * 35}")
    for name, value, side in rows:
        print(f"  {name:<35} {value:<30} {side:<35}")

    all_pass = all(value.startswith("PASS") and side.startswith("PASS") for _, value, side in rows)
    print()
    if all_pass:
        print("✓ Final verdict: PASS — translated Python matches expected on all scenarios + side effects")
        return 0
    print("✗ Final verdict: FAIL — see per-scenario detail above")
    return 3


if __name__ == "__main__":
    sys.exit(main())
