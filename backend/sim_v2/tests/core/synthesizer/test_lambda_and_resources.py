"""W27 — lambda + try-with-resources translator coverage tests.

Adds coverage for two previously unsupported Java constructs:
  - lambda_expression (with all 4 parameter forms + block bodies)
  - try_with_resources_statement (single + multi-resource, optional catch/finally)
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
    """Parse a Java method body — returns the block node."""
    full = "class _T { void m() throws Exception { " + src + " } }"
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
# Lambda expression
# ─────────────────────────────────────────────────────────────────────────────


def test_lambda_single_bare_arg(java_parser):
    tr = _translate(java_parser, "Function<Integer,Integer> f = x -> x + 1;")
    assert not tr.signature_locked
    assert "f = lambda x: x + 1" in tr.python_source


def test_lambda_zero_args(java_parser):
    tr = _translate(java_parser, "Runnable r = () -> doIt();")
    assert not tr.signature_locked
    assert "r = lambda: doIt()" in tr.python_source


def test_lambda_multi_args(java_parser):
    tr = _translate(java_parser, "BiFunction<Integer,Integer,Integer> f = (a, b) -> a * b;")
    assert not tr.signature_locked
    assert "f = lambda a, b: a * b" in tr.python_source


def test_lambda_single_arg_in_parens(java_parser):
    tr = _translate(java_parser, "Function<Integer,Integer> f = (x) -> x * 2;")
    assert not tr.signature_locked
    assert "f = lambda x: x * 2" in tr.python_source


def test_lambda_block_body_with_single_return(java_parser):
    """Block body with one return inlines cleanly to a Python lambda."""
    tr = _translate(java_parser, "Function<Integer,Integer> f = (x) -> { return x + 1; };")
    assert not tr.signature_locked
    assert "f = lambda x: x + 1" in tr.python_source


def test_lambda_multi_stmt_block_hoisted_to_def(java_parser):
    """W41: multi-statement lambda bodies are hoisted to a nested `def` whose name
    replaces the lambda expression. (Previously locked; now translates cleanly.)"""
    tr = _translate(java_parser, """
        Function<Integer,Integer> f = (x) -> {
            int y = x;
            return y + 1;
        };
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "def _lambda_" in src
    assert "f = _lambda_" in src
    # The def precedes its use
    def_idx = src.find("def _lambda_")
    use_idx = src.find("f = _lambda_")
    assert def_idx < use_idx


def test_lambda_arithmetic_body_compiles(java_parser):
    """Emitted Python must actually compile."""
    tr = _translate(java_parser, "Function<Integer,Integer> f = x -> x * x + 2;")
    g = {}
    exec(compile(tr.python_source, "<test>", "exec"), g)
    assert g["f"](3) == 11


def test_lambda_method_invocation_body_compiles(java_parser):
    """Lambda body that calls a function name compiles + invokes it."""
    tr = _translate(java_parser, "Runnable r = () -> hello();")
    g = {"hello": lambda: "ok"}
    exec(compile(tr.python_source, "<test>", "exec"), g)
    assert g["r"]() == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Try-with-resources
# ─────────────────────────────────────────────────────────────────────────────


def test_try_with_resources_single(java_parser):
    tr = _translate(java_parser, """
        try (Reader r = new FileReader("x")) {
            use(r);
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert 'with FileReader("x") as r:' in src
    assert "use(r)" in src


def test_try_with_resources_multi(java_parser):
    tr = _translate(java_parser, """
        try (A a = new A(); B b = new B()) {
            use(a);
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "with A() as a, B() as b:" in src


def test_try_with_resources_plus_catch(java_parser):
    tr = _translate(java_parser, """
        try (Connection conn = getConn()) {
            conn.exec();
        } catch (Exception e) {
            log(e);
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "try:" in src
    assert "with getConn() as conn:" in src
    assert "conn.exec()" in src
    assert "except Exception as e:" in src
    assert "log(e)" in src


def test_try_with_resources_plus_finally(java_parser):
    tr = _translate(java_parser, """
        try (Conn c = open()) {
            use(c);
        } finally {
            cleanup();
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "try:" in src
    assert "with open() as c:" in src
    assert "finally:" in src
    assert "cleanup()" in src


def test_try_with_resources_catch_and_finally(java_parser):
    tr = _translate(java_parser, """
        try (A a = new A()) {
            use(a);
        } catch (Exception e) {
            handle(e);
        } finally {
            cleanup();
        }
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "try:" in src
    assert "with A() as a:" in src
    assert "except Exception as e:" in src
    assert "finally:" in src


def test_try_with_resources_compiles(java_parser):
    """Emitted Python (no resource calls) must syntactically compile."""
    tr = _translate(java_parser, """
        try (A a = new A()) {
            doIt(a);
        }
    """)
    # Wrap in a function so the with-statement is a complete Python construct
    wrapped = "def f():\n" + "\n".join("    " + line for line in tr.python_source.split("\n"))
    compile(wrapped, "<test>", "exec")


def test_try_with_resources_executes(java_parser):
    """Run the emitted Python against a context-manager class — verifies real semantics."""
    tr = _translate(java_parser, """
        try (Resource r = open()) {
            consume(r);
        }
    """)
    wrapped = "def run():\n" + "\n".join("    " + line for line in tr.python_source.split("\n"))

    enter_log = []
    exit_log = []

    class CM:
        def __enter__(self):
            enter_log.append("entered")
            return "the-resource"
        def __exit__(self, *args):
            exit_log.append("exited")
            return False

    g = {"open": lambda: CM(), "consume": lambda x: enter_log.append(f"consumed:{x}")}
    exec(compile(wrapped, "<test>", "exec"), g)
    g["run"]()

    assert enter_log == ["entered", "consumed:the-resource"]
    assert exit_log == ["exited"]
