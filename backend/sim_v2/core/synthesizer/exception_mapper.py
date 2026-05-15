"""Java exception class → Python builtin mapping — W10.3.

Java std lib 의 가장 흔한 unchecked exception 만 cover. Plugin-specific
exception (e.g., `AlgorithmException`, `CatalogException`) 은 passthrough —
plugin contract 의 `exception_base()` 가 emit time 에 해결.

Public API:
  - map_java_exception(class_fqn_or_simple_name) -> str
"""
from __future__ import annotations


# Java std lib unchecked exception → Python builtin
_BUILTIN_MAP: dict[str, str] = {
    # java.lang
    "RuntimeException":            "RuntimeError",
    "Exception":                   "Exception",
    "Error":                       "Exception",  # broad
    "Throwable":                   "BaseException",

    "IllegalArgumentException":    "ValueError",
    "NumberFormatException":       "ValueError",
    "IllegalStateException":       "RuntimeError",
    "UnsupportedOperationException": "NotImplementedError",
    "NullPointerException":        "AttributeError",
    "ClassCastException":          "TypeError",
    "ArithmeticException":         "ArithmeticError",
    "IndexOutOfBoundsException":   "IndexError",
    "ArrayIndexOutOfBoundsException": "IndexError",
    "StringIndexOutOfBoundsException": "IndexError",
    "NoSuchElementException":      "StopIteration",
    "ConcurrentModificationException": "RuntimeError",
    "InterruptedException":        "KeyboardInterrupt",

    # java.io
    "IOException":                 "IOError",
    "FileNotFoundException":       "FileNotFoundError",

    # java.util
    "NoSuchMethodException":       "AttributeError",

    # fully qualified variants
    "java.lang.RuntimeException":  "RuntimeError",
    "java.lang.IllegalArgumentException": "ValueError",
    "java.lang.IllegalStateException": "RuntimeError",
    "java.lang.UnsupportedOperationException": "NotImplementedError",
    "java.lang.NullPointerException": "AttributeError",
    "java.lang.ClassCastException": "TypeError",
    "java.lang.ArithmeticException": "ArithmeticError",
    "java.lang.IndexOutOfBoundsException": "IndexError",
    "java.lang.Exception":         "Exception",
    "java.io.IOException":         "IOError",
}


def map_java_exception(class_name: str) -> str:
    """Java exception class name → Python equivalent.

    Falls back to passthrough (returns the input unchanged) when class is
    plugin-specific or not in std-library map. Caller's emitted Python expects
    that class to be imported via plugin contract.
    """
    if not class_name:
        return "Exception"
    return _BUILTIN_MAP.get(class_name, class_name)


def is_java_std_exception(class_name: str) -> bool:
    """True if class_name is in the Java std lib mapping (vs. plugin-specific)."""
    return class_name in _BUILTIN_MAP


__all__ = ["is_java_std_exception", "map_java_exception"]
