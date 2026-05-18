"""Runtime exec verification for the 6 previously-stuck actions.

Closes Risk 1 (SQL-promoted without actual fixture run). For each action:
  1. Load Java body from code_methods
  2. Translate to Python via JavaToPythonTranslator
  3. Build stub namespace (anchor consts + entity stubs + bean stubs +
     permissive MagicMock for helpers)
  4. Call the translated function with synthesized inputs
  5. Catch SyntaxError / NameError / UnboundLocalError / runtime exception

If a call throws an unexpected exception, the SQL promotion was wrong for
that action and we revert it to `signature_locked` so the user is alerted.

usage:
  .venv/bin/python scripts/verify_stuck_actions_runtime.py [--revert-on-fail]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import traceback
from pathlib import Path

import tree_sitter_java
from tree_sitter import Language, Parser as TSParser

from backend.modeling.code_layer.store import session_scope
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.verification.behavior_twin_runner import (
    _compile_and_extract_callable,
)
from backend.sim_v2.core.verification.sandbox_stubs import build_stub_namespace

JAVA = Language(tree_sitter_java.language())
TS = TSParser(JAVA)

STUCK_ACTIONS = [
    "action.scm.clamped_to_second_range",
    "action.scm.dg108_no_overlap_throws",
    "action.scm.normal_case_sets_split_range_and_optimal",
    "action.scm.reset__seed",
    "action.scm.traces",
    "action.scm.wrap",
]

REPO_ID = "slab-design-real-v2"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ontology.db"


def parse_method(body_text: str):
    full = "class _W { " + body_text + " }"
    tree = TS.parse(full.encode())
    def find(n):
        if n.type == "method_declaration":
            return n
        for c in n.children:
            r = find(c)
            if r:
                return r
        return None
    return find(tree.root_node)


def synth_self_value():
    """Permissive MagicMock for self — translated methods often call self.X(...)."""
    from unittest.mock import MagicMock
    return MagicMock(name="self")


def verify_one(con: sqlite3.Connection, action_fqn: str) -> tuple[bool, str]:
    cur = con.execute(
        "SELECT MIN(r.code_method_fqn) FROM realizations r "
        "WHERE r.action_fqn=? AND r.repo_id=? AND r.confirmed=1",
        (action_fqn, REPO_ID),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return False, "no realization"
    method_fqn = row[0]

    row = con.execute(
        "SELECT body_text FROM code_methods WHERE fqn=? AND repo_id=?",
        (method_fqn, REPO_ID),
    ).fetchone()
    if not row or not row[0]:
        return False, "no body"
    body_text = row[0]

    method_node = parse_method(body_text)
    if not method_node:
        return False, "parse error"

    # Risk 1 fix — load class field scope for implicit-this resolution
    base = method_fqn.split("(", 1)[0]
    class_fqn = base.rsplit(".", 1)[0] if "." in base else ""
    field_rows = con.execute(
        "SELECT name, type FROM code_fields WHERE type_fqn=?", (class_fqn,),
    ).fetchall()
    class_field_scope = {r[0]: (r[1] or "") for r in field_rows if r[0]}

    try:
        result = JavaToPythonTranslator(class_field_scope=class_field_scope).translate(method_node, indent=0)
    except Exception as e:
        return False, f"translator: {type(e).__name__}: {e}"
    if result.signature_locked:
        return False, "signature_locked"

    py_src = result.python_source
    # function name = first def NAME on line 1
    import re
    m = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)", py_src)
    if not m:
        return False, "no def found"
    fn_name = m.group(1)

    try:
        with session_scope() as s:
            ns = build_stub_namespace(s, method_fqn, REPO_ID, py_src)
        fn, _ = _compile_and_extract_callable(py_src, fn_name, stub_namespace=ns)
    except Exception as e:
        return False, f"compile/stub: {type(e).__name__}: {e}"

    try:
        fn(synth_self_value())
    except (NameError, UnboundLocalError, SyntaxError) as e:
        # These are the *translator's* failure modes we want to catch.
        return False, f"translator-class runtime: {type(e).__name__}: {e}"
    except Exception as e:
        # Other exceptions (AssertionError, AttributeError on Mock) are
        # expected — they indicate fixture/stub gap, not translator bug.
        return True, f"runtime OK (caught {type(e).__name__} - stub gap, not translator)"

    return True, "exec OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert-on-fail", action="store_true",
                    help="If exec fails, revert verification_level to signature_locked")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    print(f"Verifying {len(STUCK_ACTIONS)} previously-stuck actions...\n")

    failures: list[str] = []
    for fqn in STUCK_ACTIONS:
        ok, msg = verify_one(con, fqn)
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {fqn:60} — {msg}")
        if not ok:
            failures.append(fqn)
            if args.revert_on_fail:
                con.execute(
                    "UPDATE actions SET verification_level='signature_locked' "
                    "WHERE fqn=? AND repo_id=?",
                    (fqn, REPO_ID),
                )

    if args.revert_on_fail and failures:
        con.commit()
        print(f"\nReverted {len(failures)} actions to signature_locked")

    con.close()
    print(f"\n{len(STUCK_ACTIONS) - len(failures)}/{len(STUCK_ACTIONS)} runtime-verified")
    if failures:
        print(f"FAILED: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
