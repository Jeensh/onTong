"""W30 — local class declaration + anonymous inner class translation.

Local Java classes (declared inside method bodies) translate to Python nested
classes. Anonymous inner classes signature-lock with an actionable note.
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator


JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _parse_body(java_parser, src: str):
    full = "class _T { void m() { " + src + " } }"
    tree = java_parser.parse(full.encode())
    for cls in tree.root_node.children:
        if cls.type == "class_declaration":
            for ch in cls.children:
                if ch.type == "class_body":
                    for member in ch.named_children:
                        if member.type == "method_declaration":
                            return member.child_by_field_name("body")
    raise RuntimeError("could not find method block")


def _translate(java_parser, src: str):
    body = _parse_body(java_parser, src)
    return JavaToPythonTranslator().translate(body, indent=0)


# ─────────────────────────────────────────────────────────────────────────────
# Local class declaration
# ─────────────────────────────────────────────────────────────────────────────


def test_local_class_with_single_method(java_parser):
    tr = _translate(java_parser, "class Helper { int x() { return 1; } }")
    assert not tr.signature_locked
    src = tr.python_source
    assert "class Helper:" in src
    assert "def x(self):" in src
    assert "return 1" in src


def test_local_class_empty(java_parser):
    tr = _translate(java_parser, "class Empty {}")
    assert not tr.signature_locked
    src = tr.python_source
    assert "class Empty:" in src
    assert "pass" in src


def test_local_class_multi_method(java_parser):
    tr = _translate(java_parser, """
        class Helper {
            int x() { return 1; }
            int y() { return 2; }
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "def x(self):" in src
    assert "def y(self):" in src


def test_local_class_method_with_params(java_parser):
    tr = _translate(java_parser, "class Helper { int z(int n) { return n + 1; } }")
    assert not tr.signature_locked
    src = tr.python_source
    assert "def z(self, n):" in src
    assert "return n + 1" in src


def test_local_class_followed_by_instantiation_compiles_and_runs(java_parser):
    """Realistic pattern: declare local class, then use it."""
    tr = _translate(java_parser, """
        class Helper {
            int x() { return 42; }
        }
        new Helper().x();
    """)
    assert not tr.signature_locked
    # Wrap into a function so the local class + call form valid Python
    src = tr.python_source
    wrapped = "def run():\n" + "\n".join("    " + line for line in src.split("\n"))
    g = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    # Run it — no error since the call's return is discarded
    g["run"]()


def test_local_class_with_field_declaration(java_parser):
    """Field declaration inside class body → class attribute."""
    tr = _translate(java_parser, """
        class Holder {
            int value = 10;
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "class Holder:" in src
    assert "value = 10" in src


def test_local_class_with_recursive_method(java_parser):
    """Recursive local class works in Python the same way."""
    tr = _translate(java_parser, """
        class Counter {
            int up(int n) { return n + 1; }
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    wrapped = "def run(n):\n" + "\n".join("    " + line for line in src.split("\n")) + "\n    return Counter().up(n)"
    g = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["run"](5) == 6


# ─────────────────────────────────────────────────────────────────────────────
# Anonymous inner class — signature_locked with note
# ─────────────────────────────────────────────────────────────────────────────


def test_anonymous_runnable_signature_locked(java_parser):
    tr = _translate(java_parser, """
        Runnable r = new Runnable() {
            public void run() { doIt(); }
        };
    """)
    assert tr.signature_locked
    assert any("anonymous inner class" in n for n in tr.notes)
    assert any("Runnable" in n for n in tr.notes)


def test_anonymous_callable_signature_locked(java_parser):
    tr = _translate(java_parser, """
        Callable<Integer> c = new Callable<Integer>() {
            public Integer call() { return 42; }
        };
    """)
    assert tr.signature_locked
    notes = " ".join(tr.notes)
    assert "anonymous inner class" in notes


def test_anonymous_inner_note_actionable(java_parser):
    """The signature-lock note should suggest a refactor."""
    tr = _translate(java_parser, """
        Runnable r = new Runnable() { public void run() {} };
    """)
    notes = " ".join(tr.notes)
    assert "lambda" in notes or "named class" in notes


# ─────────────────────────────────────────────────────────────────────────────
# Mix: local class is fine even when other constructs lock
# ─────────────────────────────────────────────────────────────────────────────


def test_local_class_does_not_lock_translator(java_parser):
    """Just because a method body has a local class shouldn't lock the whole translation."""
    tr = _translate(java_parser, """
        class Helper { int x() { return 1; } }
        int y = 5;
    """)
    assert not tr.signature_locked
