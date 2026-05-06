"""P16 (2026-04-27) — body-driven BusinessRule 추출.

Javadoc 의존 제거 (사용자 합의 #2). 메서드 body AST visitor 7 종 :
    guard   — 파라미터 null/empty 검증 (if + throw)
    bound   — 비교 + literal (x < 200, x.compareTo(LOW) < 0)
    formula — 대입식 RHS 가 binary expression (length = wgt / (w * t * d))
    enum    — switch / equals 시리즈 ("HR1"|"HR2")
    regex   — Pattern.compile / matches 의 정규식 literal
    throw   — throw new XException("DG107") 의 에러코드
    lookup  — JPA Repository finder 메서드 호출 (findByXxx, ...)

Q-C=C3 결정 — formula/literal/throw/regex 는 자동 confirmed (패턴 명확),
branch (guard/bound/enum/lookup) 는 큐 (사람 검토).

각 추출 결과는 `ExtractedRule` dataclass — anchor locator 와 link.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterator

from tree_sitter import Node


class RuleKind(StrEnum):
    GUARD = "guard"
    BOUND = "bound"
    FORMULA = "formula"
    ENUM = "enum"
    REGEX = "regex"
    THROW = "throw"
    LOOKUP = "lookup"


# Q-C=C3 — 자동 confirmed 되는 kind set (명확한 패턴)
AUTO_CONFIRMED_KINDS = frozenset({
    RuleKind.FORMULA,
    RuleKind.THROW,
    RuleKind.REGEX,
})


@dataclass(frozen=True)
class ExtractedRule:
    """body 에서 추출된 rule 1 건."""
    method_fqn: str
    kind: RuleKind
    statement: str          # 사람-readable (예: "x < 200", "throw DG107", "wgt / (w * t * d)")
    line: int
    snippet: str            # source AST text (≤200자)
    anchor_locator: str     # 연결된 MethodAnchor (있으면) — branch[if@line:50] / literal[...] 등
    auto_confirmed: bool    # Q-C=C3 — true 면 자동 적용
    extra: dict = field(default_factory=dict)
    # extra 예시 :
    #   guard   : {"param": "name", "check": "null|empty"}
    #   bound   : {"variable": "x", "comparator": "<", "literal": "200"}
    #   formula : {"lhs": "length", "rhs_summary": "wgt/(w*t*d)"}
    #   enum    : {"variable": "plantCd", "values": ["HR1", "HR2"]}
    #   regex   : {"pattern": "^[A-Z0-9]{4}$"}
    #   throw   : {"exception": "ValidationException", "message": "DG107"}
    #   lookup  : {"repo_method": "findByThicknessLessThanEqual"}


def _walk(n: Node) -> Iterator[Node]:
    yield n
    for c in n.children:
        yield from _walk(c)


def _snippet(node: Node, cap: int = 200) -> str:
    text = node.text.decode(errors="ignore")
    if len(text) > cap:
        text = text[: cap - 3] + "..."
    return " ".join(text.split())


def _line(node: Node) -> int:
    return node.start_point[0] + 1


# ---------------------------------------------------------------------------
# 핵심 visitor — 모든 rule 한 번에
# ---------------------------------------------------------------------------
def extract_rules_from_method(method_node: Node, method_fqn: str) -> list[ExtractedRule]:
    body = method_node.child_by_field_name("body")
    if body is None:
        return []

    rules: list[ExtractedRule] = []
    seen: set[tuple] = set()  # (kind, line, statement) 중복 제거

    def add(rule: ExtractedRule) -> None:
        key = (rule.kind, rule.line, rule.statement)
        if key in seen:
            return
        seen.add(key)
        rules.append(rule)

    for n in _walk(body):
        # ── 1) GUARD : if (param == null) throw 또는 if (param.isEmpty()) throw
        if n.type == "if_statement":
            cond = n.child_by_field_name("condition")
            then_branch = n.child_by_field_name("consequence")
            if cond is not None and then_branch is not None and _has_throw(then_branch):
                guard = _detect_guard(cond)
                if guard:
                    add(ExtractedRule(
                        method_fqn=method_fqn,
                        kind=RuleKind.GUARD,
                        statement=f"if ({_snippet(cond, 60)}) throw",
                        line=_line(n),
                        snippet=_snippet(n, 200),
                        anchor_locator=f"branch[if@line:{_line(n)}]",
                        auto_confirmed=False,
                        extra=guard,
                    ))
                    continue   # GUARD 로 잡혔으면 BOUND 도 동시에 잡지 않음
            # ── 2) BOUND : if 조건이 비교 연산 + literal
            if cond is not None:
                bound = _detect_bound(cond)
                if bound:
                    add(ExtractedRule(
                        method_fqn=method_fqn,
                        kind=RuleKind.BOUND,
                        statement=_snippet(cond, 80),
                        line=_line(n),
                        snippet=_snippet(n, 200),
                        anchor_locator=f"branch[if@line:{_line(n)}]",
                        auto_confirmed=False,
                        extra=bound,
                    ))
                # ── 3) ENUM : equals 시리즈
                enum_info = _detect_enum(cond)
                if enum_info:
                    add(ExtractedRule(
                        method_fqn=method_fqn,
                        kind=RuleKind.ENUM,
                        statement=_snippet(cond, 100),
                        line=_line(n),
                        snippet=_snippet(n, 200),
                        anchor_locator=f"branch[if@line:{_line(n)}]",
                        auto_confirmed=False,
                        extra=enum_info,
                    ))
            continue

        # ── 4) FORMULA : assignment / local variable RHS 가 binary expression
        if n.type in ("local_variable_declaration", "assignment_expression"):
            formula = _detect_formula(n)
            if formula:
                add(ExtractedRule(
                    method_fqn=method_fqn,
                    kind=RuleKind.FORMULA,
                    statement=formula["rhs_summary"],
                    line=_line(n),
                    snippet=_snippet(n, 200),
                    anchor_locator=f"local[{formula['lhs']}]" if n.type == "local_variable_declaration" else "",
                    auto_confirmed=True,
                    extra=formula,
                ))
            continue

        # ── 5) THROW : throw new XException("DG107")
        if n.type == "throw_statement":
            throw = _detect_throw(n)
            if throw:
                add(ExtractedRule(
                    method_fqn=method_fqn,
                    kind=RuleKind.THROW,
                    statement=f"throw {throw['exception']}({throw.get('message', '')})",
                    line=_line(n),
                    snippet=_snippet(n, 150),
                    anchor_locator=f"literal[\"{throw.get('message','')}\"@line:{_line(n)}]" if throw.get("message") else "",
                    auto_confirmed=True,
                    extra=throw,
                ))
            continue

        # ── 6) REGEX : Pattern.compile("...") / matches("...")
        if n.type == "method_invocation":
            regex = _detect_regex(n)
            if regex:
                add(ExtractedRule(
                    method_fqn=method_fqn,
                    kind=RuleKind.REGEX,
                    statement=f"matches /{regex['pattern']}/",
                    line=_line(n),
                    snippet=_snippet(n, 150),
                    anchor_locator=f"literal[\"{regex['pattern'][:20]}\"@line:{_line(n)}]",
                    auto_confirmed=True,
                    extra=regex,
                ))
                # regex 잡혔으면 lookup 은 같은 노드에서 안 잡음
                continue
            # ── 7) LOOKUP : JPA repo 메서드 호출
            lookup = _detect_lookup(n)
            if lookup:
                add(ExtractedRule(
                    method_fqn=method_fqn,
                    kind=RuleKind.LOOKUP,
                    statement=f"{lookup['receiver']}.{lookup['repo_method']}(...)",
                    line=_line(n),
                    snippet=_snippet(n, 150),
                    anchor_locator="",
                    auto_confirmed=False,
                    extra=lookup,
                ))
            continue

    return rules


# ---------------------------------------------------------------------------
# 패턴 디텍터들
# ---------------------------------------------------------------------------
def _has_throw(node: Node) -> bool:
    """node 의 직계 또는 한 단계 안에 throw_statement 가 있나."""
    for n in _walk(node):
        if n.type == "throw_statement":
            return True
    return False


def _detect_guard(cond: Node) -> dict | None:
    """if (x == null) / if (x.isEmpty()) / if (x.length() == 0) 같은 검증 패턴."""
    text = cond.text.decode(errors="ignore")
    # null check
    m = re.search(r"\b(\w+(?:\.\w+)*)\s*==\s*null\b", text)
    if m:
        return {"param": m.group(1), "check": "null"}
    m = re.search(r"\bnull\s*==\s*(\w+(?:\.\w+)*)", text)
    if m:
        return {"param": m.group(1), "check": "null"}
    # isEmpty / isBlank
    m = re.search(r"(\w+(?:\.\w+)*)\.(isEmpty|isBlank)\(\)", text)
    if m:
        return {"param": m.group(1), "check": m.group(2)}
    # length() == 0 / .size() == 0
    m = re.search(r"(\w+(?:\.\w+)*)\.(length|size)\(\)\s*==\s*0", text)
    if m:
        return {"param": m.group(1), "check": "empty"}
    return None


def _detect_bound(cond: Node) -> dict | None:
    """비교 연산 + literal 형태. Java < > <= >= 또는 BigDecimal.compareTo."""
    text = cond.text.decode(errors="ignore")
    # 1) primitive: x < 200
    m = re.search(r"(\w+(?:\.\w+)*)\s*([<>]=?)\s*(-?\d+(?:\.\d+)?)", text)
    if m:
        return {"variable": m.group(1), "comparator": m.group(2), "literal": m.group(3)}
    # 2) reverse: 200 > x
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*([<>]=?)\s*(\w+(?:\.\w+)*)", text)
    if m:
        # 변수와 literal 교환 — comparator 도 반전
        rev = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
        return {"variable": m.group(3), "comparator": rev.get(m.group(2), m.group(2)), "literal": m.group(1)}
    # 3) BigDecimal.compareTo
    m = re.search(r"(\w+(?:\.\w+)*)\.compareTo\(([^)]+)\)\s*([<>]=?|==)\s*0", text)
    if m:
        return {"variable": m.group(1), "comparator": m.group(3), "literal": m.group(2).strip()}
    return None


def _detect_enum(cond: Node) -> dict | None:
    """x.equals("A") || x.equals("B") || ... 패턴."""
    text = cond.text.decode(errors="ignore")
    matches = re.findall(r"(\w+(?:\.\w+)*)\.equals\(\"([^\"]+)\"\)", text)
    if len(matches) < 2:
        return None
    # 모두 같은 변수에 대한 비교?
    var = matches[0][0]
    if not all(m[0] == var for m in matches):
        return None
    return {"variable": var, "values": [m[1] for m in matches]}


def _detect_formula(n: Node) -> dict | None:
    """대입식의 RHS 가 binary 또는 method_invocation chain 이면 formula."""
    if n.type == "local_variable_declaration":
        for child in n.children:
            if child.type != "variable_declarator":
                continue
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            if not _is_compute_rhs(value_node):
                return None
            lhs = name_node.text.decode(errors="ignore")
            return {"lhs": lhs, "rhs_summary": _snippet(value_node, 80)}
        return None
    if n.type == "assignment_expression":
        left = n.child_by_field_name("left")
        right = n.child_by_field_name("right")
        if left is None or right is None:
            return None
        if not _is_compute_rhs(right):
            return None
        return {"lhs": left.text.decode(errors="ignore"), "rhs_summary": _snippet(right, 80)}
    return None


def _is_compute_rhs(node: Node) -> bool:
    """RHS 가 단순 literal / 단순 var 가 아니라 계산식인지."""
    if node.type in ("decimal_integer_literal", "decimal_floating_point_literal", "string_literal", "true", "false", "null_literal"):
        return False
    if node.type == "identifier":
        return False
    if node.type in ("binary_expression", "ternary_expression"):
        return True
    if node.type == "method_invocation":
        # method chain (예: a.divide(b).multiply(c)) 또는 산술 함수
        text = node.text.decode(errors="ignore")
        if any(op in text for op in (".divide(", ".multiply(", ".add(", ".subtract(", ".max(", ".min(", "Math.")):
            return True
        return False
    return False


def _detect_throw(n: Node) -> dict | None:
    """throw new XException("DG107") 형태."""
    text = n.text.decode(errors="ignore")
    m = re.search(r"new\s+(\w+)\s*\(\s*\"([^\"]*)\"", text)
    if m:
        return {"exception": m.group(1), "message": m.group(2)}
    m = re.search(r"new\s+(\w+)", text)
    if m:
        return {"exception": m.group(1)}
    return None


def _detect_regex(n: Node) -> dict | None:
    """Pattern.compile("...") 또는 .matches("...") 호출."""
    text = n.text.decode(errors="ignore")
    m = re.search(r"(?:Pattern\.compile|\.matches)\s*\(\s*\"((?:[^\"\\]|\\.)+)\"\s*\)", text)
    if m:
        return {"pattern": m.group(1)}
    return None


# JPA Repository finder 메서드 prefix
_JPA_PREFIX_RE = re.compile(r"^(findBy|getBy|queryBy|searchBy|readBy|countBy|existsBy|deleteBy|removeBy)[A-Z]")


def _detect_lookup(n: Node) -> dict | None:
    """JPA Repository finder 메서드 호출 — receiver.findByXxx(args)."""
    name_node = n.child_by_field_name("name")
    if name_node is None:
        return None
    method_name = name_node.text.decode(errors="ignore")
    if not _JPA_PREFIX_RE.match(method_name):
        return None
    obj_node = n.child_by_field_name("object")
    receiver = obj_node.text.decode(errors="ignore") if obj_node else "?"
    return {"receiver": receiver[:60], "repo_method": method_name}


__all__ = (
    "AUTO_CONFIRMED_KINDS",
    "ExtractedRule",
    "RuleKind",
    "extract_rules_from_method",
)
