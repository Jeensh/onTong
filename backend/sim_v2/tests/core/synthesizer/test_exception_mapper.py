"""Exception mapper unit tests — W10.3."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.exception_mapper import (
    is_java_std_exception,
    map_java_exception,
)


# ─────────────────────────────────────────────────────────────────────────────
# Java std lib → Python builtin
# ─────────────────────────────────────────────────────────────────────────────


def test_runtime_exception_to_runtime_error():
    assert map_java_exception("RuntimeException") == "RuntimeError"
    assert map_java_exception("java.lang.RuntimeException") == "RuntimeError"


def test_illegal_argument_to_value_error():
    assert map_java_exception("IllegalArgumentException") == "ValueError"
    assert map_java_exception("NumberFormatException") == "ValueError"


def test_illegal_state_to_runtime_error():
    assert map_java_exception("IllegalStateException") == "RuntimeError"


def test_unsupported_operation_to_not_implemented():
    assert map_java_exception("UnsupportedOperationException") == "NotImplementedError"


def test_null_pointer_to_attribute_error():
    assert map_java_exception("NullPointerException") == "AttributeError"


def test_class_cast_to_type_error():
    assert map_java_exception("ClassCastException") == "TypeError"


def test_arithmetic_to_arithmetic_error():
    assert map_java_exception("ArithmeticException") == "ArithmeticError"


def test_index_out_of_bounds():
    assert map_java_exception("IndexOutOfBoundsException") == "IndexError"
    assert map_java_exception("ArrayIndexOutOfBoundsException") == "IndexError"


def test_io_exception():
    assert map_java_exception("IOException") == "IOError"
    assert map_java_exception("FileNotFoundException") == "FileNotFoundError"


def test_throwable_to_base_exception():
    assert map_java_exception("Throwable") == "BaseException"


def test_generic_exception_passthrough():
    assert map_java_exception("Exception") == "Exception"


# ─────────────────────────────────────────────────────────────────────────────
# Plugin-specific exception passthrough
# ─────────────────────────────────────────────────────────────────────────────


def test_plugin_specific_passthrough():
    """Plugin exceptions (not in std lib map) are returned unchanged."""
    assert map_java_exception("AlgorithmException") == "AlgorithmException"
    assert map_java_exception("CatalogException") == "CatalogException"
    assert map_java_exception("BpmnDeploymentException") == "BpmnDeploymentException"


def test_empty_exception_defaults_to_exception():
    assert map_java_exception("") == "Exception"


# ─────────────────────────────────────────────────────────────────────────────
# is_java_std_exception
# ─────────────────────────────────────────────────────────────────────────────


def test_is_std_exception_known():
    assert is_java_std_exception("RuntimeException")
    assert is_java_std_exception("IllegalArgumentException")
    assert is_java_std_exception("java.lang.RuntimeException")


def test_is_std_exception_unknown():
    assert not is_java_std_exception("AlgorithmException")
    assert not is_java_std_exception("MyCustomException")
    assert not is_java_std_exception("")
