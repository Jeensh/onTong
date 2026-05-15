"""W49 — Idiom-level verification tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.idiom_verifier import (
    DEFAULT_RULES,
    IdiomCheck,
    IdiomRule,
    summarize,
    verify_idioms,
)


# ─────────────────────────────────────────────────────────────────────────────
# Per-rule outcomes — single rule at a time
# ─────────────────────────────────────────────────────────────────────────────


def _rule_named(name: str) -> tuple[IdiomRule, ...]:
    return tuple(r for r in DEFAULT_RULES if r.name == name)


def test_try_with_resources_match():
    java = 'try (Reader r = new FileReader("x")) { read(); }'
    py = 'with FileReader("x") as r:\n    read()'
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "MATCH"


def test_try_with_resources_violation():
    """Java has try-with-resources but Python emits plain assignment."""
    java = 'try (Reader r = new FileReader("x")) { read(); }'
    py = 'r = FileReader("x")\nread()'
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "VIOLATION"


def test_try_with_resources_not_applicable():
    java = "int x = 5;"
    py = "x = 5"
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_optional_empty_match():
    java = "Optional<String> r = Optional.empty();"
    py = "r = None"
    checks = verify_idioms(java, py, _rule_named("optional_empty"))
    assert checks[0].status == "MATCH"


def test_optional_empty_violation():
    java = "Optional<String> r = Optional.empty();"
    py = 'r = "EMPTY"'  # Python missing None — rule should violate
    checks = verify_idioms(java, py, _rule_named("optional_empty"))
    assert checks[0].status == "VIOLATION"


def test_list_of_match():
    java = 'List<String> items = List.of("a", "b");'
    py = 'items = ["a", "b"]'
    checks = verify_idioms(java, py, _rule_named("list_of"))
    assert checks[0].status == "MATCH"


def test_list_of_not_applicable_when_no_list_of():
    java = "int x = 5;"
    py = "x = 5"
    checks = verify_idioms(java, py, _rule_named("list_of"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_lambda_block_to_def_match():
    java = 'Runnable r = () -> { step.run(); return snapshotMap(); };'
    py = ("def _lambda_1():\n"
          "    step.run()\n"
          "    return snapshotMap()\n"
          "r = _lambda_1")
    checks = verify_idioms(java, py, _rule_named("lambda_block_to_def"))
    assert checks[0].status == "MATCH"


def test_lambda_block_to_def_not_applicable_for_expression_lambda():
    """`(x) -> x + 1` is a single-expression lambda — different rule path."""
    java = "Function<Integer,Integer> f = x -> x + 1;"
    py = "f = lambda x: x + 1"
    checks = verify_idioms(java, py, _rule_named("lambda_block_to_def"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_bigdecimal_arith_match():
    java = "BigDecimal s = x.multiply(y);"
    py = "s = (x * y)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "MATCH"


def test_bigdecimal_arith_no_longer_matches_collection_add():
    """W50 — bare `.add()` (Collection.add) no longer matches the rule."""
    java = "result.add(entity);"
    py = "result.append(entity)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_bigdecimal_arith_still_matches_subtract_divide_remainder():
    java = "BigDecimal d = x.subtract(y).divide(z).remainder(w);"
    py = "d = (((x - y) / z) % w)"
    checks = verify_idioms(java, py, _rule_named("bigdecimal_arith"))
    assert checks[0].status == "MATCH"


def test_increment_to_augadd_match():
    java = "int i = 0; i++;"
    py = "i = 0\ni += 1"
    checks = verify_idioms(java, py, _rule_named("increment_to_augadd"))
    assert checks[0].status == "MATCH"


def test_increment_to_augadd_violation():
    java = "int i = 0; i++;"
    py = "i = 0\nincrement(i)"  # No augmented assignment in Python
    checks = verify_idioms(java, py, _rule_named("increment_to_augadd"))
    assert checks[0].status == "VIOLATION"


# ─────────────────────────────────────────────────────────────────────────────
# Combined verify_idioms across the whole catalog
# ─────────────────────────────────────────────────────────────────────────────


def test_verify_idioms_returns_aligned_list_per_rule():
    java = "int x = 5;"
    py = "x = 5"
    checks = verify_idioms(java, py)
    assert len(checks) == len(DEFAULT_RULES)
    for check, rule in zip(checks, DEFAULT_RULES, strict=True):
        assert check.rule_name == rule.name


def test_verify_idioms_combined_example():
    java = """
        try (Reader r = new FileReader("x")) {
            Optional<String> e = Optional.empty();
            List<String> items = List.of("a", "b");
            int i = 0; i++;
        }
    """
    py = """
        with FileReader("x") as r:
            e = None
            items = ["a", "b"]
            i = 0
            i += 1
    """
    checks = verify_idioms(java, py)
    by_name = {c.rule_name: c for c in checks}
    assert by_name["try_with_resources"].status == "MATCH"
    assert by_name["optional_empty"].status == "MATCH"
    assert by_name["list_of"].status == "MATCH"
    assert by_name["increment_to_augadd"].status == "MATCH"
    # Rules whose Java patterns are absent → NOT_APPLICABLE
    assert by_name["lambda_block_to_def"].status == "NOT_APPLICABLE"


# ─────────────────────────────────────────────────────────────────────────────
# summarize
# ─────────────────────────────────────────────────────────────────────────────


def test_summarize_counts_each_status():
    checks = [
        IdiomCheck(rule_name="a", status="MATCH"),
        IdiomCheck(rule_name="b", status="MATCH"),
        IdiomCheck(rule_name="c", status="VIOLATION"),
        IdiomCheck(rule_name="d", status="NOT_APPLICABLE"),
    ]
    s = summarize(checks)
    assert s == {"MATCH": 2, "VIOLATION": 1, "NOT_APPLICABLE": 1}


def test_summarize_on_empty_list_returns_zero_counts():
    s = summarize([])
    assert s == {"MATCH": 0, "VIOLATION": 0, "NOT_APPLICABLE": 0}


# ─────────────────────────────────────────────────────────────────────────────
# IdiomRule + IdiomCheck shape
# ─────────────────────────────────────────────────────────────────────────────


def test_idiom_rule_is_frozen():
    r = IdiomRule(name="x", java_pattern="a", python_pattern="b")
    with pytest.raises(Exception):
        r.name = "y"  # type: ignore[misc]


def test_idiom_check_carries_match_counts():
    c = IdiomCheck(
        rule_name="r", status="MATCH", java_matches=3, python_matches=3,
    )
    assert c.java_matches == 3
    assert c.python_matches == 3


def test_default_rules_have_distinct_names():
    """A rule's name is its identity — duplicates would mask outcomes in summarize."""
    names = [r.name for r in DEFAULT_RULES]
    assert len(names) == len(set(names))
