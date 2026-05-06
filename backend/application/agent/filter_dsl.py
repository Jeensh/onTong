"""Filter DSL parser — Boolean expression → Chroma where clause.

Grammar:
    expr   := or_expr
    or_expr  := and_expr (OR and_expr)*
    and_expr := term ((AND|<implicit>) term)*
    term   := NOT? atom | "(" expr ")"
    atom   := field ":" value

Fields: path | folder | tag | author | type | mtime | status | acl
Value: unquoted non-space token OR "..." / '...' (for values with spaces)
mtime value may be prefixed with >=, <=, >, < for range.

Examples:
    folder:ERP
    folder:ERP AND author:@동해
    (tag:재고 OR tag:주문) AND !author:@민수
    mtime:>=2026-01-01 AND tag:"재고 관리"
"""

from __future__ import annotations

import re
from typing import Any


class DSLError(ValueError):
    pass


# ── Public entry point ─────────────────────────────────────────────

def parse_dsl(text: str) -> dict:
    """Parse DSL string into a Chroma-compatible where clause. Empty → {}."""
    text = (text or "").strip()
    if not text:
        return {}
    tokens = _tokenize(text)
    if not tokens:
        return {}
    parser = _Parser(tokens)
    result = parser.parse_expr()
    if parser.pos < len(parser.tokens):
        rest = parser.tokens[parser.pos]
        raise DSLError(f"Unexpected token after expression: {rest}")
    return result


# ── Tokenizer ───────────────────────────────────────────────────────

_ATOM_RE = re.compile(
    r"([\w가-힣-]+)\s*:\s*("
    r'"[^"]*"'
    r"|'[^']*'"
    r"|[^\s()]+"
    r")"
)

_KEYWORDS = {"AND", "OR", "NOT"}


def _tokenize(text: str) -> list[tuple[str, Any]]:
    tokens: list[tuple[str, Any]] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            tokens.append(("LPAREN", "("))
            i += 1
            continue
        if ch == ")":
            tokens.append(("RPAREN", ")"))
            i += 1
            continue
        if ch == "!":
            tokens.append(("NOT", "!"))
            i += 1
            continue

        # Keyword (AND / OR / NOT)
        matched_keyword = False
        for kw in _KEYWORDS:
            kw_len = len(kw)
            if (
                text[i:i + kw_len].upper() == kw
                and (i + kw_len == n or not (text[i + kw_len].isalnum() or text[i + kw_len] == "_"))
            ):
                tokens.append((kw, kw))
                i += kw_len
                matched_keyword = True
                break
        if matched_keyword:
            continue

        # Atom field:value
        m = _ATOM_RE.match(text, i)
        if m:
            field = m.group(1)
            value = m.group(2)
            if value and value[0] in ('"', "'"):
                value = value[1:-1]
            tokens.append(("ATOM", (field, value)))
            i = m.end()
            continue

        raise DSLError(f"Unexpected character at {i}: {text[i:i+20]!r}")

    return tokens


# ── Recursive descent parser ───────────────────────────────────────

class _Parser:
    def __init__(self, tokens: list[tuple[str, Any]]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> tuple[str, Any]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return ("EOF", None)

    def _consume(self) -> tuple[str, Any]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse_expr(self) -> dict:
        return self.parse_or()

    def parse_or(self) -> dict:
        left = self.parse_and()
        clauses = [left]
        while self._peek()[0] == "OR":
            self._consume()
            clauses.append(self.parse_and())
        if len(clauses) == 1:
            return left
        return {"$or": clauses}

    def parse_and(self) -> dict:
        left = self.parse_term()
        clauses = [left]
        while True:
            kind = self._peek()[0]
            if kind == "AND":
                self._consume()
                clauses.append(self.parse_term())
            elif kind in ("ATOM", "LPAREN", "NOT"):
                # Implicit AND
                clauses.append(self.parse_term())
            else:
                break
        if len(clauses) == 1:
            return left
        return {"$and": clauses}

    def parse_term(self) -> dict:
        kind, _ = self._peek()
        if kind == "LPAREN":
            self._consume()
            expr = self.parse_expr()
            if self._peek()[0] != "RPAREN":
                raise DSLError("Missing closing parenthesis")
            self._consume()
            return expr
        if kind == "NOT":
            self._consume()
            atom = self._parse_negatable()
            return _negate(atom)
        if kind == "ATOM":
            return self._parse_atom()
        raise DSLError(f"Expected atom / '(' / NOT, got {kind}")

    def _parse_negatable(self) -> dict:
        """After NOT/!: allow atom or parenthesized expr."""
        kind, _ = self._peek()
        if kind == "LPAREN":
            self._consume()
            expr = self.parse_expr()
            if self._peek()[0] != "RPAREN":
                raise DSLError("Missing closing parenthesis")
            self._consume()
            return expr
        if kind == "ATOM":
            return self._parse_atom()
        raise DSLError(f"Expected atom or '(' after NOT, got {kind}")

    def _parse_atom(self) -> dict:
        kind, val = self._consume()
        if kind != "ATOM":
            raise DSLError(f"Expected atom, got {kind}")
        field, value = val
        return _atom_to_where(field.lower(), value)


# ── Atom → where clause ─────────────────────────────────────────────

def _atom_to_where(field: str, value: str) -> dict:
    if field == "path":
        from backend.application.agent.filter_compiler import _compile_path_glob
        c = _compile_path_glob(value)
        if not c:
            raise DSLError(f"Invalid path: {value}")
        return c

    if field == "folder":
        from backend.application.agent.filter_compiler import _compile_folders
        c = _compile_folders([value])
        if not c:
            raise DSLError(f"Invalid folder: {value}")
        return c

    if field == "tag":
        return {"tags": {"$in": [value]}}

    if field == "author":
        return {"authors": {"$in": [value]}}

    if field == "type":
        return {"doc_type": value}

    if field == "status":
        return {"status": value}

    if field == "acl":
        return {"acl_read": {"$in": [value]}}

    if field == "mtime":
        return _parse_mtime(value)

    raise DSLError(f"Unknown field: {field}")


def _parse_mtime(value: str) -> dict:
    from backend.application.agent.filter_compiler import _iso_to_epoch

    for prefix, op in (("<=", "$lte"), (">=", "$gte"), ("<", "$lt"), (">", "$gt")):
        if value.startswith(prefix):
            ts = _iso_to_epoch(value[len(prefix):])
            return {"mtime_epoch": {op: ts}}

    # Exact date → [start, start+86400)
    ts_start = _iso_to_epoch(value)
    return {"mtime_epoch": {"$gte": ts_start, "$lt": ts_start + 86400}}


# ── Negation ────────────────────────────────────────────────────────

_FLIP = {
    "$eq": "$ne",
    "$ne": "$eq",
    "$in": "$nin",
    "$nin": "$in",
    "$gt": "$lte",
    "$lt": "$gte",
    "$gte": "$lt",
    "$lte": "$gt",
}


def _negate(clause: dict) -> dict:
    """Logical NOT via De Morgan's laws + operator flipping."""
    if "$and" in clause:
        return {"$or": [_negate(sub) for sub in clause["$and"]]}
    if "$or" in clause:
        return {"$and": [_negate(sub) for sub in clause["$or"]]}

    result: dict = {}
    for field, cond in clause.items():
        if isinstance(cond, dict):
            new_cond = {}
            for op, val in cond.items():
                flipped = _FLIP.get(op)
                if not flipped:
                    raise DSLError(f"Cannot negate operator: {op}")
                new_cond[flipped] = val
            result[field] = new_cond
        else:
            result[field] = {"$ne": cond}
    return result
