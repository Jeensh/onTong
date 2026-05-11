"""Sanity check for `extract_candidates` against existing AnchorBindingRow data.

Run from repo root:
    .venv/bin/python scripts/test_anchor_candidates.py

Logic:
1. Pull every distinct (code_method_fqn, repo_id, anchor_locator, line) from
   `anchor_bindings` (free-text values typed by users so far).
2. Group them by (repo_id, code_method_fqn).
3. For 3 sample methods (and the full 9 rows for the summary), look up
   `code_methods.body_text` + `params_json` + `line_start/end` and run
   `extract_candidates`.
4. For each existing user-typed locator, check whether the extractor emits
   either an exact-locator match or a candidate whose snippet contains the
   user's text (substring, normalised whitespace).

The substring fallback exists because legacy locators are free-form
descriptions like `"matches.isEmpty() → null"` while the v1 extractor emits
structured ids like `return-stmt@line-35`. A *useful* dropdown
needs to surface a row whose snippet matches the legacy text — that's
what the test measures.
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.modeling.code_analysis.anchor_candidate_extractor import (  # noqa: E402
    AnchorCandidate,
    extract_candidates,
)

DB_PATH = ROOT / "data" / "ontology.db"


def _normalise(text: str) -> str:
    """Collapse whitespace + lowercase for fuzzy substring matching."""
    return " ".join(text.split()).lower()


def _stub_method_row(body_text: str, line_start: int | None,
                     line_end: int | None, params_json: str):
    """Lightweight stand-in for CodeMethodRow — extractor only reads 4 fields."""
    return SimpleNamespace(
        body_text=body_text,
        line_start=line_start,
        line_end=line_end,
        params_json=params_json or "[]",
        fqn="",
        repo_id="",
    )


_TOKEN_RE = __import__("re").compile(r"[A-Za-z_$][\w$]*|\d+")
# Identifier-tokens length>=2; numeric-tokens kept always (including single-digit literals).
# Stopwords drop AnchorBindingRow kind-marker prefixes that aren't part of the actual
# code (e.g. user typed `literal 8` to mean "the literal 8 in the code").
_STOPWORDS = frozenset({
    "the", "and", "or", "is", "of", "to",
    "literal", "branch", "param", "return", "field", "local",
})


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for tok in _TOKEN_RE.findall(text):
        if tok.isdigit():
            out.add(tok)
        elif len(tok) >= 2 and tok.lower() not in _STOPWORDS:
            out.add(tok)
    return out


def _candidate_matches(locator: str, candidates: list[AnchorCandidate]) -> str | None:
    """Return the matching candidate locator (exact / substring / token-overlap), or None.

    Three tiers in order of strictness:
        1) exact-locator equality (legacy data already in v1 format)
        2) candidate snippet *contains* the user-typed locator after whitespace
           normalisation (substring)
        3) token-overlap ≥0.6 of the user locator's identifier-tokens — measures
           "the user could plausibly find this row in the dropdown"
    """
    norm_loc = _normalise(locator)
    # 1) exact-locator equality
    for c in candidates:
        if c.locator == locator:
            return c.locator
    # 2) substring on snippet (after normalising)
    for c in candidates:
        if norm_loc and norm_loc in _normalise(c.snippet):
            return c.locator
    # 3) token-overlap: at least 60 % of the user-text identifier tokens land in
    # *some* candidate snippet. This is the realistic "would the dropdown
    # surface this option" check.
    user_tokens = _tokens(locator)
    if user_tokens:
        for c in candidates:
            cand_tokens = _tokens(c.snippet)
            if not cand_tokens:
                continue
            overlap = len(user_tokens & cand_tokens) / len(user_tokens)
            if overlap >= 0.6:
                return f"{c.locator} (fuzzy overlap={overlap:.0%})"
    return None


def main() -> int:
    if not DB_PATH.exists():
        print(f"FAIL: ontology DB not found at {DB_PATH}")
        return 2

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    rows = cur.execute(
        "SELECT code_method_fqn, repo_id, anchor_locator, line "
        "FROM anchor_bindings"
    ).fetchall()
    if not rows:
        print("FAIL: anchor_bindings table is empty")
        return 2

    print(f"Found {len(rows)} existing AnchorBindingRow entries.\n")

    grouped: dict[tuple[str, str], list[tuple[str, int | None]]] = defaultdict(list)
    for fqn, repo_id, locator, line in rows:
        grouped[(repo_id, fqn)].append((locator, line))

    sample_keys = sorted(grouped.keys())[:3]

    overall_total = 0
    overall_match = 0
    unmatched_overall: list[tuple[str, str, str]] = []   # (repo_id, fqn, locator)

    for key in sorted(grouped.keys()):
        repo_id, fqn = key
        method = cur.execute(
            "SELECT body_text, params_json, line_start, line_end "
            "FROM code_methods WHERE fqn = ? AND repo_id = ?",
            (fqn, repo_id),
        ).fetchone()
        if method is None:
            print(f"  [skip] no code_methods row for repo_id={repo_id} fqn={fqn}")
            for loc, _ in grouped[key]:
                unmatched_overall.append((repo_id, fqn, loc))
                overall_total += 1
            continue

        body, params_json, line_start, line_end = method
        stub = _stub_method_row(body or "", line_start, line_end, params_json or "[]")
        candidates = extract_candidates(stub)

        if key in sample_keys:
            print("=" * 78)
            print(f"SAMPLE METHOD: {fqn}")
            print(f"  repo_id={repo_id}  lines={line_start}-{line_end}")
            print(f"  candidates (first 12):")
            for c in candidates[:12]:
                print(f"    - {c.locator:36s}  line={c.line}  snippet={c.snippet!r}")
            print()

        for loc, _line in grouped[key]:
            overall_total += 1
            match = _candidate_matches(loc, candidates)
            if match is not None:
                overall_match += 1
                if key in sample_keys:
                    print(f"  [MATCH] {loc!r} → {match}")
            else:
                unmatched_overall.append((repo_id, fqn, loc))
                if key in sample_keys:
                    print(f"  [MISS ] {loc!r} (no candidate snippet contained this text)")
        if key in sample_keys:
            print()

    print("=" * 78)
    print(f"Overall: {overall_match}/{overall_total} existing locators matched "
          f"({100 * overall_match / overall_total:.1f}%)")
    if unmatched_overall:
        print("\nUnmatched locators (gaps to address in v2):")
        for repo_id, fqn, loc in unmatched_overall:
            short = fqn.rsplit(".", 1)[-1]
            print(f"  - [{repo_id}] {short:48s}  locator={loc!r}")

    return 0 if overall_total > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
