"""throw / try / catch / finally translation tests — W10.1, W10.2."""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

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
    raise RuntimeError("method body not found")


# ─────────────────────────────────────────────────────────────────────────────
# throw_statement → raise
# ─────────────────────────────────────────────────────────────────────────────


def test_throw_runtime_exception(java_parser):
    body = _parse_method_body(java_parser, 'throw new RuntimeException("oops");')
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert 'raise RuntimeError("oops")' in src
    assert not tr.signature_locked


def test_throw_illegal_argument(java_parser):
    body = _parse_method_body(
        java_parser, 'throw new IllegalArgumentException("bad arg");'
    )
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert 'raise ValueError("bad arg")' in src


def test_throw_null_pointer(java_parser):
    body = _parse_method_body(java_parser, 'throw new NullPointerException("null");')
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert 'raise AttributeError("null")' in src


def test_throw_no_args(java_parser):
    body = _parse_method_body(java_parser, "throw new IllegalStateException();")
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "raise RuntimeError()" in src


def test_throw_plugin_specific_passthrough(java_parser):
    body = _parse_method_body(
        java_parser, 'throw new AlgorithmException("ALG_001", "iter failed");'
    )
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    # Plugin-specific exception class — passthrough
    assert 'raise AlgorithmException("ALG_001", "iter failed")' in src


def test_throw_bare_variable(java_parser):
    body = _parse_method_body(java_parser, "throw caughtException;")
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "raise caughtException" in src


def test_throw_compiles_to_valid_python(java_parser):
    body = _parse_method_body(java_parser, 'throw new RuntimeException("oops");')
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    wrapped = "def f():\n" + "\n".join("    " + l for l in src.split("\n"))
    compile(wrapped, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# try / catch
# ─────────────────────────────────────────────────────────────────────────────


def test_try_catch_basic(java_parser):
    body = _parse_method_body(java_parser, """
        try {
            x = 1;
        } catch (RuntimeException e) {
            x = -1;
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "try:" in src
    assert "except RuntimeError as e:" in src
    assert "x = 1" in src
    assert "x = -1" in src
    assert not tr.signature_locked
    wrapped = "def f(x):\n" + "\n".join("    " + l for l in src.split("\n"))
    compile(wrapped, "<test>", "exec")


def test_try_catch_plugin_exception(java_parser):
    body = _parse_method_body(java_parser, """
        try {
            run();
        } catch (AlgorithmException e) {
            handleError();
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    # AlgorithmException is plugin-specific → passthrough (assumes plugin imports it)
    assert "except AlgorithmException as e:" in src


def test_try_catch_finally(java_parser):
    body = _parse_method_body(java_parser, """
        try {
            doWork();
        } catch (IOException e) {
            log(e);
        } finally {
            cleanup();
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "try:" in src
    assert "except IOError as e:" in src
    assert "finally:" in src
    assert "cleanup()" in src


def test_try_only_finally(java_parser):
    body = _parse_method_body(java_parser, """
        try {
            doWork();
        } finally {
            cleanup();
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "try:" in src
    assert "finally:" in src
    # No except — valid try/finally only
    assert "except" not in src


def test_multi_catch(java_parser):
    """`catch (A | B e)` → `except (A, B) as e:`"""
    body = _parse_method_body(java_parser, """
        try {
            doWork();
        } catch (IllegalStateException | IllegalArgumentException e) {
            handle(e);
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    # Multi-catch in tuple form
    assert "except (RuntimeError, ValueError) as e:" in src or \
           "except (ValueError, RuntimeError) as e:" in src


def test_try_with_multiple_catches(java_parser):
    body = _parse_method_body(java_parser, """
        try {
            doWork();
        } catch (IllegalArgumentException e) {
            handleBad();
        } catch (RuntimeException e) {
            handleRuntime();
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "except ValueError as e:" in src
    assert "except RuntimeError as e:" in src


def test_try_with_resources_translates_to_with_statement(java_parser):
    """W27 — try-with-resources is now supported via Python `with` statement."""
    body = _parse_method_body(java_parser, """
        try (Connection conn = getConn()) {
            conn.exec();
        } catch (Exception e) {
            log(e);
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    assert not tr.signature_locked
    src = tr.python_source
    assert "with getConn() as conn:" in src
    assert "except Exception as e:" in src


# ─────────────────────────────────────────────────────────────────────────────
# Combined: try / throw inside / catch
# ─────────────────────────────────────────────────────────────────────────────


def test_throw_inside_try(java_parser):
    body = _parse_method_body(java_parser, """
        try {
            throw new IllegalStateException("bad");
        } catch (RuntimeException e) {
            return;
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert 'raise RuntimeError("bad")' in src
    assert "except RuntimeError as e:" in src


def test_compile_full_try_catch(java_parser):
    """End-to-end: try/catch compiles to valid Python."""
    body = _parse_method_body(java_parser, """
        try {
            x = 1;
            throw new IllegalArgumentException("bad");
        } catch (IllegalArgumentException e) {
            x = -1;
        } finally {
            x = 0;
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    wrapped = "def f(x):\n" + "\n".join("    " + l for l in src.split("\n"))
    compile(wrapped, "<test>", "exec")
