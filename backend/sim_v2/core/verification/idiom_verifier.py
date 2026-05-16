"""W49 — Idiom-level verification (refined W50).

Beyond "does the code translate cleanly" (W41 → 100% on production), the
verifier checks "did it translate *idiomatically*". For each `IdiomRule`,
when the Java source uses the Java pattern, the emitted Python should use the
expected Python pattern.

Per-rule outcomes:
    MATCH           — Java pattern present + Python pattern present
    VIOLATION       — Java pattern present, Python pattern absent
    NOT_APPLICABLE  — Java pattern not present (rule didn't fire)

Built-in catalog (DEFAULT_RULES):
    try_with_resources    — `try (Resource r = ...)` → `with ... as r:`
    optional_empty        — `Optional.empty()`       → `None`
    optional_of           — `Optional.of(x)`          → `x`
    list_of               — `List.of(a, b)`           → `[a, b]`
    lambda_block_to_def   — `(args) -> { ... }`       → `def _lambda_N`
    bigdecimal_arith      — `.subtract/multiply/divide/remainder(y)` → `*` `/` etc.
    increment_to_augadd   — `i++` / `++i`             → `i += 1`

Each rule's `java_pattern` / `python_pattern` are pre-compiled regexes. The
verifier dispatches them; no semantic AST analysis is performed at this layer.

W50 refinements:
- Java source is comment-stripped before rules apply (eliminates `--` matches
  inside `// ----` ASCII-art comments).
- `bigdecimal_arith` no longer matches `.add()` — too many false positives
  on `List.add()` / `Set.add()`. The remaining 4 methods (subtract, multiply,
  divide, remainder) are unique to BigDecimal in real-world Java.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


IdiomStatus = Literal["MATCH", "VIOLATION", "NOT_APPLICABLE"]


class IdiomRule(BaseModel):
    """One Java-pattern ↔ expected-Python-pattern check.

    `java_pattern` and `python_pattern` are regex strings (not pre-compiled to
    keep the rule fully serializable). Caller compiles via `verify_idioms`.
    """
    model_config = ConfigDict(frozen=True)

    name:            str
    java_pattern:    str
    python_pattern:  str
    description:     str = ""


class IdiomCheck(BaseModel):
    """One rule's outcome on a (java_src, python_src) pair."""
    model_config = ConfigDict(frozen=True)

    rule_name:        str
    status:           IdiomStatus
    java_matches:     int = 0
    python_matches:   int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Default catalog — Java idiom ↔ Python expected emission
# ─────────────────────────────────────────────────────────────────────────────


DEFAULT_RULES: tuple[IdiomRule, ...] = (
    IdiomRule(
        name="try_with_resources",
        # \btry\s*\( — word boundary on `try` so `recordRetry(` / `retry(` /
        # `tryStep(` don't match. (W54 — production false positive on v2.)
        java_pattern=r"\btry\s*\(",
        python_pattern=r"^\s*with\s+",
        description="Java try-with-resources → Python `with` statement (W27)",
    ),
    IdiomRule(
        name="optional_empty",
        java_pattern=r"Optional\.empty\s*\(",
        python_pattern=r"\bNone\b",
        description="Java Optional.empty() → Python None",
    ),
    IdiomRule(
        name="optional_of",
        java_pattern=r"Optional\.of\s*\(",
        # Optional.of(x) → x  ⇒ the bare value should appear in Python; absence
        # of the literal `Optional` symbol counts as MATCH
        python_pattern=r"^(?!.*\bOptional\.of\b).*$",
        description="Java Optional.of(x) → bare value in Python",
    ),
    IdiomRule(
        name="list_of",
        java_pattern=r"\bList\.of\s*\(",
        python_pattern=r"\[",
        description="Java List.of(...) → Python list literal [...]",
    ),
    IdiomRule(
        name="lambda_block_to_def",
        # Java multi-statement lambda — `(args) -> { stmt; stmt; }`
        java_pattern=r"->\s*\{[^}]*;\s*[^}]*\}",
        python_pattern=r"\bdef\s+_lambda_\d+\b",
        description="Java multi-statement lambda → Python nested `def _lambda_N` (W41)",
    ),
    IdiomRule(
        name="bigdecimal_arith",
        # `.add()` removed in W50 — clashes with List.add / Set.add. The remaining
        # 4 methods are unique to BigDecimal in real-world Java.
        java_pattern=r"\.(subtract|multiply|divide|remainder)\s*\(",
        # Python uses native operator
        python_pattern=r"[+\-*/%]",
        description=(
            "Java BigDecimal x.subtract/multiply/divide/remainder(y) → -/*//%. "
            "(add omitted — too noisy with Collection.add.)"
        ),
    ),
    IdiomRule(
        name="increment_to_augadd",
        java_pattern=r"(\+\+|--)\s*\w+|\w+\s*(\+\+|--)",
        python_pattern=r"\s\+=\s1\b|\s-=\s1\b",
        description="Java i++ / ++i / i-- / --i → Python `i += 1` / `i -= 1` (W39)",
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────────────


# W50 — strip `// line` and `/* block */` Java comments before running patterns.
# ASCII-art comments (`// ----`) otherwise leak `--` matches into the
# increment_to_augadd regex.
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_java_comments(src: str) -> str:
    """Remove `// line` and `/* block */` comments from Java source."""
    src = _BLOCK_COMMENT_RE.sub("", src)
    src = _LINE_COMMENT_RE.sub("", src)
    return src


def verify_idioms(
    java_src: str,
    python_src: str,
    rules: tuple[IdiomRule, ...] = DEFAULT_RULES,
) -> list[IdiomCheck]:
    """Run every rule against the (java_src, python_src) pair.

    Order-preserving — returns one IdiomCheck per rule in the input order.
    `java_matches` / `python_matches` count regex hits (informational; useful
    for finding partial coverage where some occurrences translated and others
    didn't).

    Java source is comment-stripped before rules apply (W50).
    """
    java_src = strip_java_comments(java_src)
    results: list[IdiomCheck] = []
    for rule in rules:
        java_re = re.compile(rule.java_pattern, re.MULTILINE | re.DOTALL)
        py_re = re.compile(rule.python_pattern, re.MULTILINE | re.DOTALL)

        j_hits = len(java_re.findall(java_src))
        if j_hits == 0:
            results.append(IdiomCheck(
                rule_name=rule.name,
                status="NOT_APPLICABLE",
                java_matches=0,
                python_matches=0,
            ))
            continue

        p_hits = len(py_re.findall(python_src))
        status: IdiomStatus = "MATCH" if p_hits > 0 else "VIOLATION"
        results.append(IdiomCheck(
            rule_name=rule.name,
            status=status,
            java_matches=j_hits,
            python_matches=p_hits,
        ))
    return results


def summarize(checks: list[IdiomCheck]) -> dict[str, int]:
    """Aggregate counts by status — useful for survey reports."""
    out = {"MATCH": 0, "VIOLATION": 0, "NOT_APPLICABLE": 0}
    for c in checks:
        out[c.status] = out.get(c.status, 0) + 1
    return out


__all__ = [
    "DEFAULT_RULES",
    "IdiomCheck",
    "IdiomRule",
    "IdiomStatus",
    "strip_java_comments",
    "summarize",
    "verify_idioms",
]
