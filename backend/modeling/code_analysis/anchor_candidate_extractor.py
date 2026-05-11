"""Anchor candidate extractor — produces dropdown-friendly fragment locators.

Wave 1 of the AnchorBinding UX overhaul (replaces the free-text
`anchor_locator` input with a typed dropdown). For a given `CodeMethodRow`
this module returns a deterministic, sorted list of `AnchorCandidate`
objects covering the method body's bindable fragments.

Locator format (dropdown id, stable across calls):
    method-body
    param-name({param_name})
    if-stmt@line-{N}
    loop-body@line-{N}                 # for / while / do
    return-stmt@line-{N}
    try-block@line-{N}
    assignment@line-{N}                # variable = ...  (skip trivial init)
    call@line-{N}({callee_name})

Implementation notes
- Pure scan over `CodeMethodRow.body_text` + `params_json` — no tree-sitter
  dependency at request time, so this is safe to call from a FastAPI
  handler under an LRU cache.
- Skips lines that are inside `//` line comments or `/* ... */` block
  comments (block scan strips them out before fragment matching).
- `assignment` candidates exclude the bare local-declaration init form
  (`Type x = ...`) — those land in the dropdown via `call@...` if the RHS
  contains an invocation, otherwise they are intentionally left out
  because they correspond to a `local[name]` anchor (already in
  `code_methods.anchors_json`).
- All candidates carry a Korean/short `description` for UI tooltip use.
- Output ordering: `method-body` first → `param-name(...)` (params order)
  → fragment candidates sorted by `(line, kind, locator)`.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from backend.modeling.code_layer.orm import CodeMethodRow


__all__ = ("AnchorCandidate", "extract_candidates")


# ---------------------------------------------------------------------------
# Public DTO
# ---------------------------------------------------------------------------
class AnchorCandidate(BaseModel):
    """One dropdown item that can be picked as an `AnchorBinding.anchor_locator`."""

    locator: str = Field(..., description="Stable dropdown id; matches anchor_bindings.anchor_locator")
    kind: str = Field(..., description="method-body | param-name | if-stmt | loop-body | return-stmt | try-block | assignment | call")
    line: int | None = Field(None, description="1-based source line; None for whole-method anchors")
    snippet: str = Field("", description="Short visible label (≤120 chars after collapsing whitespace)")
    description: str = Field("", description="Korean one-liner for tooltip / help text")


# ---------------------------------------------------------------------------
# Comment stripper — keeps line numbers stable, replaces comment chars with spaces
# ---------------------------------------------------------------------------
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"//[^\n]*")


def _strip_comments_keep_lines(src: str) -> str:
    """Replace comment runs with spaces of equal length so line/column numbers are preserved."""

    def _blank(match: re.Match[str]) -> str:
        text = match.group(0)
        # Preserve newlines, blank everything else.
        return "".join("\n" if ch == "\n" else " " for ch in text)

    src = _BLOCK_COMMENT.sub(_blank, src)
    src = _LINE_COMMENT.sub(_blank, src)
    return src


def _collapse(text: str, cap: int = 120) -> str:
    flat = " ".join(text.split())
    if len(flat) > cap:
        flat = flat[: cap - 3] + "..."
    return flat


# ---------------------------------------------------------------------------
# Param parsing
# ---------------------------------------------------------------------------
def _load_params(method: CodeMethodRow) -> list[dict[str, Any]]:
    raw = method.params_json or "[]"
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict) and p.get("name")]
    except json.JSONDecodeError:
        pass
    return []


# ---------------------------------------------------------------------------
# Body scanners
# ---------------------------------------------------------------------------
# Pattern shapes (Java-like):
#   if (...)                              → `if-stmt`
#   for (...)                             → `loop-body`
#   while (...)                           → `loop-body`
#   do {                                  → `loop-body`
#   try {                                 → `try-block`
#   return ...;                           → `return-stmt`
#   x = expr;  (NOT preceded by Type)     → `assignment`
#   foo(...) / obj.bar(...)               → `call`
_RE_IF = re.compile(r"\bif\s*\(")
_RE_FOR = re.compile(r"\bfor\s*\(")
_RE_WHILE = re.compile(r"\bwhile\s*\(")
_RE_DO = re.compile(r"\bdo\s*\{")
_RE_TRY = re.compile(r"\btry\s*\{")
_RE_RETURN = re.compile(r"\breturn\b")
# assignment: identifier (or chained identifier) `=` (single, not `==` `!=` `<=` `>=` `+=` etc.)
# rough form: `name(.field|[idx])* = ...`
_RE_ASSIGN = re.compile(
    r"(?<![=!<>+\-*/%&|^])"             # not preceded by another op char
    r"\b([A-Za-z_$][\w$]*"
    r"(?:\s*\.\s*[A-Za-z_$][\w$]*)*"
    r"(?:\s*\[[^\]\n]*\])*)"
    r"\s*=\s*"
    r"(?!=)"                             # not `==`
)
# Detect the `Type ident =` local-declaration form (Java-ish) that we want to *skip*
# as an `assignment` candidate (it's the LOCAL anchor, not an assignment fragment).
_JAVA_PRIMITIVE_TYPES = frozenset({
    "boolean", "byte", "short", "int", "long", "float", "double", "char", "void",
    "var", "final",
})
_RE_LOCAL_DECL = re.compile(
    r"^\s*"
    r"(?:final\s+)?"
    r"(?P<typ>[A-Za-z_$][\w$.<>,?\s]*?)"  # type token (greedy-light; allows generics)
    r"\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
)
# call sites — best-effort: word identifier followed by `(`, NOT preceded by control kw or type.
_RE_CALL = re.compile(
    r"(?<![\w$.])"                       # not part of larger identifier
    r"(?P<callee>[A-Za-z_$][\w$]*)"
    r"\s*\("
)
# control-flow / declaration keywords we never want to treat as a callee
_NON_CALLEE_KEYWORDS = frozenset({
    "if", "for", "while", "switch", "catch", "do", "try", "synchronized",
    "return", "throw", "new", "super", "this", "assert", "instanceof",
    "case", "yield",
})


def _line_of(body_text: str, char_index: int, line_start: int) -> int:
    """Line number (1-based, source-absolute) for a char offset inside body_text."""
    return line_start + body_text.count("\n", 0, char_index)


def _line_text(body_text: str, char_index: int) -> str:
    """The single source line containing `char_index` (raw, no comment-strip)."""
    line_begin = body_text.rfind("\n", 0, char_index) + 1
    line_end = body_text.find("\n", char_index)
    if line_end < 0:
        line_end = len(body_text)
    return body_text[line_begin:line_end]


def _looks_like_local_decl(line_text: str) -> bool:
    """`Type ident = ...` heuristic — we treat that as a LOCAL anchor, not an assignment."""
    match = _RE_LOCAL_DECL.match(line_text)
    if match is None:
        return False
    typ = match.group("typ").strip()
    head = typ.split()[0] if typ else ""
    if head in _JAVA_PRIMITIVE_TYPES:
        return True
    # Capitalised first char → looks like a class name (List<...>, BigDecimal, ...).
    if head and head[0].isupper():
        return True
    return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def extract_candidates(method_row: CodeMethodRow) -> list[AnchorCandidate]:
    """Pure function: `CodeMethodRow` → deterministic list of `AnchorCandidate`.

    Empty body or missing line_start → returns only `method-body` + params.
    """
    out: list[AnchorCandidate] = []

    # 1) method-body — always exactly one, always first
    out.append(AnchorCandidate(
        locator="method-body",
        kind="method-body",
        line=method_row.line_start,
        snippet="method-body",
        description="메서드 본문 전체에 결합 (가장 일반적인 anchor)",
    ))

    # 2) param-name(...) — one per declared parameter, in declaration order
    for param in _load_params(method_row):
        name = str(param.get("name", "")).strip()
        if not name:
            continue
        decl_type = str(param.get("type", "")).strip()
        out.append(AnchorCandidate(
            locator=f"param-name({name})",
            kind="param-name",
            line=method_row.line_start,
            snippet=f"{decl_type} {name}".strip(),
            description=f"파라미터 `{name}` 에 결합",
        ))

    # 3) Body fragments — only if we have body_text + line_start
    body_text = method_row.body_text or ""
    line_start = method_row.line_start or 1
    if body_text.strip():
        fragments = _scan_body_fragments(body_text, line_start)
        # Sort fragments deterministically (line, then kind, then locator).
        fragments.sort(key=lambda c: (c.line if c.line is not None else 0, c.kind, c.locator))
        out.extend(fragments)

    return out


def _scan_body_fragments(body_text: str, line_start: int) -> list[AnchorCandidate]:
    """Run all regex scanners over a comment-stripped copy of the body."""
    clean = _strip_comments_keep_lines(body_text)
    seen: set[str] = set()
    candidates: list[AnchorCandidate] = []

    def add(c: AnchorCandidate) -> None:
        if c.locator in seen:
            return
        seen.add(c.locator)
        candidates.append(c)

    # if-stmt
    for match in _RE_IF.finditer(clean):
        line = _line_of(clean, match.start(), line_start)
        snippet = _extract_paren_snippet(clean, match.end() - 1)
        add(AnchorCandidate(
            locator=f"if-stmt@line-{line}",
            kind="if-stmt",
            line=line,
            snippet=_collapse(f"if ({snippet})"),
            description=f"line {line} 의 if 분기 조건",
        ))

    # for / while / do  → loop-body
    for regex, label in ((_RE_FOR, "for"), (_RE_WHILE, "while"), (_RE_DO, "do-while")):
        for match in regex.finditer(clean):
            line = _line_of(clean, match.start(), line_start)
            if regex is _RE_DO:
                snippet = "do { ... }"
            else:
                snippet = _extract_paren_snippet(clean, match.end() - 1)
                snippet = _collapse(f"{label} ({snippet})")
            add(AnchorCandidate(
                locator=f"loop-body@line-{line}",
                kind="loop-body",
                line=line,
                snippet=snippet,
                description=f"line {line} 의 {label} 반복 블록",
            ))

    # try-block
    for match in _RE_TRY.finditer(clean):
        line = _line_of(clean, match.start(), line_start)
        add(AnchorCandidate(
            locator=f"try-block@line-{line}",
            kind="try-block",
            line=line,
            snippet="try { ... }",
            description=f"line {line} 의 try 블록",
        ))

    # return-stmt
    for match in _RE_RETURN.finditer(clean):
        line = _line_of(clean, match.start(), line_start)
        # capture text up to the next ';' on the same logical statement (cap 120 chars)
        tail_end = clean.find(";", match.end())
        if tail_end < 0:
            tail_end = min(len(clean), match.end() + 120)
        body_snippet = clean[match.start():tail_end].strip()
        add(AnchorCandidate(
            locator=f"return-stmt@line-{line}",
            kind="return-stmt",
            line=line,
            snippet=_collapse(body_snippet),
            description=f"line {line} 의 return 문",
        ))

    # assignment — skip local declarations and trivial inits
    for match in _RE_ASSIGN.finditer(clean):
        line = _line_of(clean, match.start(), line_start)
        line_text = _line_text(clean, match.start())
        if _looks_like_local_decl(line_text):
            continue
        # Skip when the LHS lives inside a control-flow header (e.g., `for (int i = 0; ...)`),
        # because those don't represent a standalone assignment anchor.
        if _inside_for_header(clean, match.start()):
            continue
        lhs = match.group(1).strip()
        # Capture statement RHS up to next ';' (cap 120 chars).
        stmt_end = clean.find(";", match.end())
        if stmt_end < 0:
            stmt_end = min(len(clean), match.end() + 120)
        rhs_snippet = clean[match.start():stmt_end].strip()
        add(AnchorCandidate(
            locator=f"assignment@line-{line}",
            kind="assignment",
            line=line,
            snippet=_collapse(rhs_snippet),
            description=f"line {line} 의 대입식 ({lhs} = ...)",
        ))

    # call sites
    for match in _RE_CALL.finditer(clean):
        callee = match.group("callee")
        if callee in _NON_CALLEE_KEYWORDS:
            continue
        line = _line_of(clean, match.start(), line_start)
        # Capture invocation snippet (callee + matched paren chunk, capped).
        paren_open = match.end() - 1
        snippet = _extract_paren_snippet(clean, paren_open)
        add(AnchorCandidate(
            locator=f"call@line-{line}({callee})",
            kind="call",
            line=line,
            snippet=_collapse(f"{callee}({snippet})"),
            description=f"line {line} 의 `{callee}(...)` 호출",
        ))

    return candidates


# ---------------------------------------------------------------------------
# Helpers — paren matching + control-header detection
# ---------------------------------------------------------------------------
def _extract_paren_snippet(text: str, open_paren_idx: int, max_len: int = 100) -> str:
    """Return the characters between matching `()` starting at `open_paren_idx`."""
    if open_paren_idx >= len(text) or text[open_paren_idx] != "(":
        return ""
    depth = 0
    end = open_paren_idx
    for i in range(open_paren_idx, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
        if i - open_paren_idx > max_len:
            end = i
            break
    return text[open_paren_idx + 1:end]


def _inside_for_header(text: str, idx: int) -> bool:
    """Return True if `idx` is between `for (` and the matching `)`."""
    # Walk backwards looking for `for(` while tracking paren depth.
    depth = 0
    for i in range(idx - 1, max(idx - 400, -1), -1):
        ch = text[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                # Found an unmatched open paren — is it preceded by `for`?
                preceding = text[max(0, i - 6):i].rstrip()
                return preceding.endswith("for")
            depth -= 1
        elif ch == "\n" and depth == 0:
            # for-headers don't usually span far past a newline boundary at depth 0.
            continue
    return False
