"""P15 (2026-04-26) — round1-code-schema §6-B 구현 : method body value_flow.

Method body 안의 변수/필드 lineage 를 dict 로 압축 :
    `{src_path: [target_path, ...]}`

예 (`SdFinalLengthRangeAction.execute`) :
    {
        "slab.weightTon":              ["slabWgt"],
        "slab.thicknessMm":            ["thickness"],
        "spec.density":                ["density"],
        "slabWgt":                     ["numerator"],
        "numerator":                   ["lengthFromWidthHigh", "lengthFromWidthLow"],
        "lengthFromWidthHigh":         ["return"],
    }

추출 규칙 :
    1. local_variable_declaration : `Type lhs = rhs` → rhs 안 var refs → lhs
    2. assignment_expression       : `lhs = rhs`      → rhs 안 var refs → lhs
    3. return_statement            : `return expr`    → expr 안 var refs → "return"

var ref 추출 :
    - identifier (간단 var)
    - field_access (this.x / inst.x.y / outer.inner)
    - method_invocation 의 args (재귀)
    - 빈 결과 OK (literal 만 있는 RHS)

결과는 `method.attributes["value_flow"]` (dict[str, list[str]]).
LLM Python generator 가 이 정보로 변수 의존도 그래프 파악.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterator

from tree_sitter import Node


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for c in node.children:
        yield from _walk(c)


def _path_text(node: Node) -> str | None:
    """field_access / identifier 노드의 source path text. 그 외엔 None."""
    if node.type == "identifier":
        return node.text.decode(errors="ignore")
    if node.type in ("field_access", "this"):
        text = node.text.decode(errors="ignore")
        if len(text) > 80:
            return None
        return text
    return None


def _collect_refs(expr_node: Node) -> list[str]:
    """expression node 안에서 사용된 var/field reference 들의 path 수집.

    중복 제거. method_invocation 안의 args 재귀.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(p: str) -> None:
        if p and p not in seen:
            seen.add(p)
            out.append(p)

    # field_access 와 identifier 를 BFS — 단 method_invocation 의 callee 는 제외
    # callee = method 이름이라 var ref 가 아님
    for n in _walk(expr_node):
        if n.type == "field_access":
            # field_access 가 chained 면 가장 외곽만 잡음 (this.a.b → "this.a.b")
            # 근데 walker 가 inner field_access 도 visit 함. parent 도 field_access 면 skip
            if n.parent is not None and n.parent.type == "field_access":
                continue
            p = _path_text(n)
            if p:
                add(p)
        elif n.type == "identifier":
            # parent context 에서 method_invocation 의 name 인지 확인 — name 이면 skip
            parent = n.parent
            if parent is None:
                add(n.text.decode(errors="ignore"))
                continue
            if parent.type == "method_invocation":
                name_node = parent.child_by_field_name("name")
                if name_node is n:
                    continue   # method 이름이라 skip
            if parent.type == "field_access":
                continue   # field_access 하위 identifier 는 위에서 잡힘
            if parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node is n:
                    continue   # 선언 자체의 lhs name 은 skip
            if parent.type in ("class_declaration", "method_declaration", "type_identifier", "scoped_type_identifier"):
                continue
            if parent.type == "formal_parameter":
                continue
            add(n.text.decode(errors="ignore"))
    return out


def extract_value_flow(method_node: Node) -> dict[str, list[str]]:
    """method body → value_flow dict. src_var → list of target_var."""
    body = method_node.child_by_field_name("body")
    if body is None:
        return {}

    flow: dict[str, set[str]] = defaultdict(set)

    for n in _walk(body):
        # local_variable_declaration : `Type lhs = rhs;`
        if n.type == "local_variable_declaration":
            for child in n.children:
                if child.type != "variable_declarator":
                    continue
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node is None or value_node is None:
                    continue
                lhs = name_node.text.decode(errors="ignore")
                refs = _collect_refs(value_node)
                for r in refs:
                    flow[r].add(lhs)
            continue

        # assignment_expression : `lhs = rhs`
        if n.type == "assignment_expression":
            left = n.child_by_field_name("left")
            right = n.child_by_field_name("right")
            if left is None or right is None:
                continue
            lhs = _path_text(left)
            if lhs is None:
                continue
            refs = _collect_refs(right)
            for r in refs:
                flow[r].add(lhs)
            continue

        # return_statement : `return expr;`
        if n.type == "return_statement":
            for child in n.children:
                if child.type in ("return", ";"):
                    continue
                refs = _collect_refs(child)
                for r in refs:
                    flow[r].add("return")
                break

    # set → list (deterministic order)
    return {k: sorted(v) for k, v in flow.items() if v}


__all__ = ("extract_value_flow",)
