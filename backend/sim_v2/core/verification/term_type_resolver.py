"""W57 — Term → Java type resolution.

Bridges the Domain layer (`business_terms`) to the Code layer (`code_classes`)
so that action-output `object_ref` references can be resolved to a concrete
Java type and compared against a method's actual return type.

The Section 2 authoring pipeline records the suggested Java class FQN inside
`business_terms.description` using the same 「자동 추천 — <FQN>」 stash format
that W45 uses for methods. The class form lacks the `(…)` suffix that methods
carry, so this resolver uses its own regex.

`aliases_json` (a `["SimpleName", …]` array) is consulted as a secondary
signal — useful when a term has multiple acceptable Java incarnations or when
the description is missing.

Public API:
    - TermJavaResolution            — Pydantic frozen view
    - extract_class_fqn_from_description(text)
    - resolve_term_to_java_type(session, term_fqn, repo_id)
    - simple_name_of(fqn)
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session


# ─────────────────────────────────────────────────────────────────────────────
# Regex — class FQN (no parens, distinct from W45's method regex)
# ─────────────────────────────────────────────────────────────────────────────


# Same prefix as W45 (자동 추천 — …) but the trailing token must be a *class*
# FQN, not a method signature. We grab the whole non-whitespace token first,
# then reject anything containing `(` (a method pattern) and anything that
# doesn't parse as a Java identifier path.
_DESC_TOKEN_RE = re.compile(r"자동\s*추천\s*[—–\-]\s*(?P<tok>\S+)")
_CLASS_FQN_RE  = re.compile(r"[A-Za-z_][\w\.$]*")


def extract_class_fqn_from_description(description: str) -> str | None:
    """Return a Java class FQN parsed out of a business_term description, or None.

    Rejects method-shaped tokens (`...(…)`) — those belong to W45.
    """
    if not description:
        return None
    m = _DESC_TOKEN_RE.search(description)
    if not m:
        return None
    token = m.group("tok")
    if "(" in token:
        return None
    if not _CLASS_FQN_RE.fullmatch(token):
        return None
    return token


def simple_name_of(fqn: str) -> str:
    """Strip package and outer-class prefixes — `a.b.Outer$Inner` → `Inner`."""
    if not fqn:
        return ""
    tail = fqn.rsplit(".", 1)[-1]
    return tail.rsplit("$", 1)[-1]


# ─────────────────────────────────────────────────────────────────────────────
# Resolution view
# ─────────────────────────────────────────────────────────────────────────────


class TermJavaResolution(BaseModel):
    model_config = ConfigDict(frozen=True)

    term_fqn:    str
    java_fqn:    str | None = None        # parsed from description, if present
    aliases:     tuple[str, ...] = ()     # simple-name candidates from aliases_json

    @property
    def is_resolved(self) -> bool:
        return self.java_fqn is not None or len(self.aliases) > 0

    @property
    def candidates(self) -> tuple[str, ...]:
        """All simple-name candidates a method's return_type could match.

        Includes:
          - the simple name of `java_fqn` (e.g. `ValidationResult`)
          - the full FQN itself (e.g. `com.x.ValidationResult`)
          - every alias verbatim
        Deduped, original order preserved.
        """
        seen: set[str] = set()
        out: list[str] = []
        if self.java_fqn:
            for candidate in (simple_name_of(self.java_fqn), self.java_fqn):
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    out.append(candidate)
        for alias in self.aliases:
            if alias and alias not in seen:
                seen.add(alias)
                out.append(alias)
        return tuple(out)


def _parse_aliases(aliases_json: str | None) -> tuple[str, ...]:
    if not aliases_json:
        return ()
    try:
        parsed = json.loads(aliases_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(s for s in parsed if isinstance(s, str) and s)


def resolve_term_to_java_type(
    session: Session, term_fqn: str, repo_id: str,
) -> TermJavaResolution:
    """Look up a business term and return its Java type resolution.

    Returns a resolution with `is_resolved=False` if the term row is missing
    or carries neither a parseable description nor any aliases.
    """
    row = session.execute(
        text(
            "SELECT description, aliases_json "
            "FROM business_terms WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": term_fqn, "rid": repo_id},
    ).fetchone()
    if row is None:
        return TermJavaResolution(term_fqn=term_fqn)

    description, aliases_json = row
    java_fqn = extract_class_fqn_from_description(description or "")
    aliases = _parse_aliases(aliases_json)
    return TermJavaResolution(
        term_fqn=term_fqn,
        java_fqn=java_fqn,
        aliases=aliases,
    )


__all__ = [
    "TermJavaResolution",
    "extract_class_fqn_from_description",
    "resolve_term_to_java_type",
    "simple_name_of",
]
