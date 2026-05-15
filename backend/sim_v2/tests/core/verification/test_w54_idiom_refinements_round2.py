"""W54 — Second round of idiom verifier refinements.

W53's framework health report surfaced 3 new v2-specific findings:
  - 2 `try_with_resources` violations on methods named `recordRetry` / `tryStep`
    — the regex was matching `try(` as a substring inside `<word>retry(`.
  - 1 `list_of` violation — a real translator gap.

W54 fixes both: regex word boundary on `try`, and `List.of(...)` translation.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.idiom_verifier import (
    DEFAULT_RULES,
    verify_idioms,
)


def _rule_named(name: str):
    return tuple(r for r in DEFAULT_RULES if r.name == name)


# ─────────────────────────────────────────────────────────────────────────────
# try_with_resources regex — false positive elimination
# ─────────────────────────────────────────────────────────────────────────────


def test_recordretry_does_not_trigger_try_with_resources():
    """`trace.recordRetry(...)` — regex must not match `try(` inside `retry(`."""
    java = 'trace.recordRetry(1, "step", "phase", 1, null, "reason");'
    py = "self.recordRetry(...)"
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_method_named_recordretry_signature_does_not_trigger():
    """`public void recordRetry(int step, ...)` — declaration shouldn't fire."""
    java = (
        "public void recordRetry(int step, String stepName) {\n"
        "    // body\n"
        "}"
    )
    py = "def recordRetry(self, step, stepName):\n    pass"
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_method_named_trystep_does_not_trigger():
    """`tryStep(` — `try` is part of a longer identifier, regex word boundary
    keeps it from matching."""
    java = "public boolean tryStep(int n) { return true; }"
    py = "def tryStep(self, n):\n    return True"
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_method_named_retry_does_not_trigger():
    java = "public void retry() {}"
    py = "def retry(self):\n    pass"
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "NOT_APPLICABLE"


def test_real_try_with_resources_still_matches():
    java = 'try (Reader r = new FileReader("x")) { read(); }'
    py = 'with FileReader("x") as r:\n    read()'
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "MATCH"


def test_real_try_with_resources_violation_still_fires():
    """Java has try-with-resources but Python emits plain assignment."""
    java = 'try (Reader r = new FileReader("x")) { read(); }'
    py = 'r = FileReader("x")\nread()'
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "VIOLATION"


def test_try_with_space_before_paren_still_matches():
    """`try   (Reader r = ...)` — the `\\s*` allows arbitrary whitespace."""
    java = 'try   (Reader r = new FileReader("x")) { read(); }'
    py = 'with FileReader("x") as r:\n    read()'
    checks = verify_idioms(java, py, _rule_named("try_with_resources"))
    assert checks[0].status == "MATCH"


# ─────────────────────────────────────────────────────────────────────────────
# List.of translator — also exercised end-to-end via idiom verifier
# ─────────────────────────────────────────────────────────────────────────────


def test_list_of_idiom_matches_translated_output():
    java = 'List<String> a = List.of("x");'
    py = 'a = ["x"]'  # what the translator now emits
    checks = verify_idioms(java, py, _rule_named("list_of"))
    assert checks[0].status == "MATCH"


def test_list_of_idiom_now_violates_when_translator_leaves_it_intact():
    """A still-broken translation (legacy output) should be flagged."""
    java = 'List<String> a = List.of("x");'
    py = 'a = List.of("x")'  # legacy output
    checks = verify_idioms(java, py, _rule_named("list_of"))
    assert checks[0].status == "VIOLATION"
