"""W50 — refinements to W49's idiom verifier.

Two production-grounded false positives surfaced in UC19 are eliminated:
  1. `--` inside `// ----` ASCII-art comments triggering `increment_to_augadd`
  2. `.add()` on Collections triggering `bigdecimal_arith`

This test file covers the refinements specifically; the broader W49 test
file already exercises the unchanged paths.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.idiom_verifier import (
    DEFAULT_RULES,
    strip_java_comments,
    verify_idioms,
)


def _rule_named(name: str):
    return tuple(r for r in DEFAULT_RULES if r.name == name)


# ─────────────────────────────────────────────────────────────────────────────
# strip_java_comments
# ─────────────────────────────────────────────────────────────────────────────


def test_strip_line_comments():
    src = "int x = 5; // inline comment\nint y = 6;"
    out = strip_java_comments(src)
    assert "inline comment" not in out
    assert "int x = 5;" in out
    assert "int y = 6;" in out


def test_strip_block_comments():
    src = "int x = 5; /* block\n   comment */ int y = 6;"
    out = strip_java_comments(src)
    assert "block" not in out
    assert "comment" not in out
    assert "int x = 5;" in out
    assert "int y = 6;" in out


def test_strip_javadoc_style_block_comments():
    src = "/** doc */ public void m() {}"
    out = strip_java_comments(src)
    assert "doc" not in out
    assert "public void m" in out


def test_strip_ascii_art_line_comments():
    """The specific case that triggered the UC19 false positive."""
    src = (
        "public void m() {\n"
        "    // ---------- 압연 MAX 단중 (필수, miss → DG107) ----------\n"
        "    int x = 1;\n"
        "}\n"
    )
    out = strip_java_comments(src)
    assert "압연 MAX" not in out
    assert "----------" not in out
    assert "int x = 1;" in out


def test_strip_preserves_non_comment_dashes():
    """A `--` inside string literals or genuine `i--` operators MUST be kept."""
    src = "i--; String s = \"a--b\";"
    out = strip_java_comments(src)
    assert "i--" in out
    assert '"a--b"' in out


# ─────────────────────────────────────────────────────────────────────────────
# Comment stripping eliminates false positive on increment_to_augadd
# ─────────────────────────────────────────────────────────────────────────────


def test_increment_rule_does_not_fire_on_ascii_art_comments():
    """The exact production case from UC19 that yielded the false positive."""
    java = (
        "public void m() {\n"
        "    // ---------- 압연 MAX 단중 ----------\n"
        "    // ---------- min 계산 ----------\n"
        "    int x = 1;\n"
        "}\n"
    )
    py = "def m(self):\n    x = 1"
    checks = verify_idioms(java, py, _rule_named("increment_to_augadd"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_increment_rule_still_fires_on_real_postfix():
    java = "int i = 0; i++;"
    py = "i = 0\ni += 1"
    checks = verify_idioms(java, py, _rule_named("increment_to_augadd"))
    assert checks[0].status == "MATCH"


def test_increment_rule_still_fires_on_real_prefix():
    java = "int i = 0; ++i;"
    py = "i = 0\ni += 1"
    checks = verify_idioms(java, py, _rule_named("increment_to_augadd"))
    assert checks[0].status == "MATCH"


# ─────────────────────────────────────────────────────────────────────────────
# bigdecimal_arith no longer matches Collection.add
# ─────────────────────────────────────────────────────────────────────────────


def test_bigdecimal_rule_skips_list_add():
    """The exact production case: result.add(entity) on an ArrayList."""
    java = (
        "ArrayList<X> result = new ArrayList<>();\n"
        "result.add(entity);\n"
    )
    py = "result = []\nresult.append(entity)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_bigdecimal_rule_skips_set_add():
    java = "set.add(item);"
    py = "set_.add(item)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_bigdecimal_rule_matches_subtract():
    java = "BigDecimal d = x.subtract(y);"
    py = "d = (x - y)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "MATCH"


def test_bigdecimal_rule_matches_multiply():
    java = "BigDecimal d = x.multiply(y);"
    py = "d = (x * y)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "MATCH"


def test_bigdecimal_rule_matches_divide():
    java = "BigDecimal d = x.divide(y);"
    py = "d = (x / y)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "MATCH"


def test_bigdecimal_rule_matches_remainder():
    java = "BigDecimal d = x.remainder(y);"
    py = "d = (x % y)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "MATCH"


# ─────────────────────────────────────────────────────────────────────────────
# Comment + add false positives don't bleed into each other
# ─────────────────────────────────────────────────────────────────────────────


def test_comment_with_add_inside_does_not_trigger_bigdecimal_rule():
    """A comment mentioning `.add(...)` shouldn't trigger anything."""
    java = "// result.add(entity);\nint x = 5;"
    py = "x = 5"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "NOT_APPLICABLE"
