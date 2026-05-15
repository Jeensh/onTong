"""Translator instrument mode (with_trace=True) tests — W16.2."""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.verification.trace import TraceCollector

JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _parse_method_body(java_parser, body_src: str):
    full = f"class _T {{ void m() {{ {body_src} }} }}\n"
    tree = java_parser.parse(full.encode())
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            method = next(x for x in body.named_children if x.type == "method_declaration")
            return method.child_by_field_name("body")
    raise RuntimeError("no body")


# ─────────────────────────────────────────────────────────────────────────────
# Trace emission in source
# ─────────────────────────────────────────────────────────────────────────────


def test_no_trace_when_disabled(java_parser):
    body = _parse_method_body(java_parser, "int x = 1;")
    src = JavaToPythonTranslator().translate(body, indent=0, with_trace=False).python_source
    assert "_trace" not in src


def test_local_var_decl_emits_trace_step(java_parser):
    body = _parse_method_body(java_parser, "int x = 1;")
    src = JavaToPythonTranslator().translate(body, indent=0, with_trace=True).python_source
    assert "_trace.step" in src
    assert "'x': x" in src


def test_multiple_var_decls_emit_multiple_steps(java_parser):
    body = _parse_method_body(java_parser, """
        int x = 1;
        int y = 2;
        int z = 3;
    """)
    src = JavaToPythonTranslator().translate(body, indent=0, with_trace=True).python_source
    assert src.count("_trace.step") == 3
    assert "anchor_1" in src
    assert "anchor_2" in src
    assert "anchor_3" in src


def test_throw_emits_trace_exception(java_parser):
    body = _parse_method_body(java_parser, 'throw new RuntimeException("oops");')
    src = JavaToPythonTranslator().translate(body, indent=0, with_trace=True).python_source
    assert "_trace.exception" in src
    assert "'RuntimeError'" in src


def test_if_emits_trace_branch(java_parser):
    body = _parse_method_body(java_parser, """
        if (x > 0) { y = 1; }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0, with_trace=True).python_source
    assert "_trace.branch" in src


def test_traced_source_runs_against_collector(java_parser):
    """Emitted traced Python source actually runs and populates the collector."""
    body = _parse_method_body(java_parser, """
        int x = 5;
        int y = x + 1;
    """)
    src = JavaToPythonTranslator().translate(body, indent=0, with_trace=True).python_source

    # Wrap in a function and exec
    collector = TraceCollector()
    wrapped = "def f():\n" + "\n".join("    " + line for line in src.split("\n"))
    g = {"_trace": collector}
    exec(wrapped, g)
    g["f"]()

    assert len(collector.events) == 2
    assert collector.events[0].anchor_id == "anchor_1"
    assert dict(collector.events[0].vars) == {"x": 5}
    assert dict(collector.events[1].vars) == {"y": 6}


def test_traced_if_branch_records_cond(java_parser):
    body = _parse_method_body(java_parser, """
        int x = 5;
        if (x > 0) {
            x = 10;
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0, with_trace=True).python_source

    collector = TraceCollector()
    wrapped = "def f():\n" + "\n".join("    " + line for line in src.split("\n"))
    g = {"_trace": collector}
    exec(wrapped, g)
    g["f"]()

    # Expect: step (x=5), branch (cond=True), step (x=10)
    kinds = [e.kind for e in collector.events]
    assert "branch" in kinds
    branch_events = [e for e in collector.events if e.kind == "branch"]
    assert dict(branch_events[0].vars) == {"cond": True}
