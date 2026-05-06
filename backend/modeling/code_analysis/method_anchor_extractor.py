"""P14 (2026-04-26) — tree-sitter visitor : method body → MethodAnchor[].

`extract_anchors_from_method(method_node, method_fqn, params_node) → list[MethodAnchor]`

추출 규칙 :
    PARAM        — formal_parameter 의 (type, name)
    LOCAL        — local_variable_declaration 의 variable_declarator
    BRANCH       — if_statement / switch_statement / switch_expression / for_statement /
                   enhanced_for_statement / while_statement / do_statement / try_statement
                   각각의 condition / value / control 부분
    LITERAL      — string_literal / decimal_integer_literal / floating point / boolean / null
                   단 magic 만 (0/1/-1/null 제외, 단순 boolean 제외, 길이 < 2 string 제외)
    RETURN       — return_statement 의 expression
    FIELD_ACCESS — field_access (this.X 또는 instance.X) read/write/invoke
                   simple_name (qualifier 없는 인스턴스 field 참조) 도 포함

field_access 의 access_kind heuristic :
    - parent 가 assignment_expression 의 left → write
    - parent 가 method_invocation 의 object → invoke
    - 그 외 → read
"""
from __future__ import annotations

from typing import Iterator

from tree_sitter import Node

from backend.modeling.code_analysis.method_anchor import AnchorKind, MethodAnchor


_BRANCH_TYPES = frozenset({
    "if_statement", "switch_statement", "switch_expression",
    "for_statement", "enhanced_for_statement",
    "while_statement", "do_statement",
    "try_statement", "ternary_expression",
})

_LITERAL_TYPES = frozenset({
    "string_literal", "character_literal",
    "decimal_integer_literal", "hex_integer_literal",
    "octal_integer_literal", "binary_integer_literal",
    "decimal_floating_point_literal", "hex_floating_point_literal",
    "true", "false",
})

# 노이즈 제거 — 의미 없는 literal 필터
_TRIVIAL_NUMS = frozenset({"0", "1", "-1", "0.0", "1.0", "0L", "1L"})
_TRIVIAL_STR_LEN = 2   # length < 2 string literal (예: "", "a") 제외


def _snippet(node: Node, cap: int = 120) -> str:
    text = node.text.decode(errors="ignore")
    if len(text) > cap:
        text = text[: cap - 3] + "..."
    # newline → space, multiple spaces collapse
    text = " ".join(text.split())
    return text


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        yield from _walk(child)


def extract_anchors_from_method(
    method_node: Node,
    method_fqn: str,
) -> list[MethodAnchor]:
    """method_declaration / constructor_declaration node → anchor list."""
    out: list[MethodAnchor] = []

    # 1) PARAMS
    params_node = method_node.child_by_field_name("parameters")
    if params_node is not None:
        for i, param in enumerate(_iter_formal_params(params_node)):
            type_node = param.child_by_field_name("type")
            name_node = param.child_by_field_name("name")
            if name_node is None:
                continue
            name = name_node.text.decode(errors="ignore")
            decl_type = type_node.text.decode(errors="ignore") if type_node is not None else ""
            out.append(MethodAnchor(
                method_fqn=method_fqn,
                kind=AnchorKind.PARAM,
                locator=f"param[{name}]",
                line=name_node.start_point[0] + 1,
                snippet=_snippet(param),
                extra={"declared_type": decl_type, "position": i},
            ))

    # 2) Body 안 walk
    body = method_node.child_by_field_name("body")
    if body is None:
        return out

    seen_branches: set[tuple[int, str]] = set()
    for n in _walk(body):
        # LOCAL
        if n.type == "local_variable_declaration":
            type_node = n.child_by_field_name("type")
            decl_type = type_node.text.decode(errors="ignore") if type_node else ""
            for child in n.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node is None:
                        continue
                    name = name_node.text.decode(errors="ignore")
                    value_node = child.child_by_field_name("value")
                    rhs_text = value_node.text.decode(errors="ignore") if value_node else ""
                    rhs_text = rhs_text[:120]
                    out.append(MethodAnchor(
                        method_fqn=method_fqn,
                        kind=AnchorKind.LOCAL,
                        locator=f"local[{name}]",
                        line=name_node.start_point[0] + 1,
                        snippet=_snippet(n),
                        extra={"declared_type": decl_type, "rhs_text": rhs_text},
                    ))
            continue

        # BRANCH
        if n.type in _BRANCH_TYPES:
            line = n.start_point[0] + 1
            key = (line, n.type)
            if key in seen_branches:
                continue
            seen_branches.add(key)
            stmt_text = ""
            cond = n.child_by_field_name("condition")
            if cond is not None:
                stmt_text = cond.text.decode(errors="ignore")[:120]
            else:
                # enhanced_for / try 등은 condition 필드 없음 — node text 일부
                stmt_text = _snippet(n)[:80]
            branch_kind = n.type.replace("_statement", "").replace("_expression", "")
            out.append(MethodAnchor(
                method_fqn=method_fqn,
                kind=AnchorKind.BRANCH,
                locator=f"branch[{branch_kind}@line:{line}]",
                line=line,
                snippet=_snippet(n),
                extra={"statement_text": stmt_text, "branch_kind": branch_kind},
            ))
            continue

        # RETURN
        if n.type == "return_statement":
            line = n.start_point[0] + 1
            return_text = ""
            for child in n.children:
                if child.type not in ("return", ";"):
                    return_text = child.text.decode(errors="ignore")[:120]
                    break
            out.append(MethodAnchor(
                method_fqn=method_fqn,
                kind=AnchorKind.RETURN,
                locator=f"return[@line:{line}]",
                line=line,
                snippet=_snippet(n),
                extra={"return_text": return_text},
            ))
            continue

        # LITERAL
        if n.type in _LITERAL_TYPES:
            raw = n.text.decode(errors="ignore")
            line = n.start_point[0] + 1
            literal_kind = _classify_literal(n.type)

            # noise filter
            if literal_kind == "boolean":
                continue   # true/false 그 자체는 anchor 가치 낮음
            if literal_kind in ("integer", "float") and raw in _TRIVIAL_NUMS:
                continue
            if literal_kind == "string":
                # quote 안 내용 길이
                inner = raw.strip('"\'')
                if len(inner) < _TRIVIAL_STR_LEN:
                    continue

            out.append(MethodAnchor(
                method_fqn=method_fqn,
                kind=AnchorKind.LITERAL,
                locator=f"literal[{raw[:30]}@line:{line}]",
                line=line,
                snippet=_snippet(n),
                extra={"raw": raw, "literal_kind": literal_kind, "is_magic": True},
            ))
            continue

        # FIELD_ACCESS — this.X 또는 explicit field reference
        if n.type == "field_access":
            obj = n.child_by_field_name("object")
            field = n.child_by_field_name("field")
            if obj is None or field is None:
                continue
            obj_text = obj.text.decode(errors="ignore")
            field_name = field.text.decode(errors="ignore")
            line = n.start_point[0] + 1
            access_kind = _infer_access_kind(n)
            # `this.castSpec.smCd` 같은 chained 는 가장 안쪽 field_access 가 이 visitor 에 잡힘
            # locator 는 root path
            full_path = n.text.decode(errors="ignore")[:80]
            out.append(MethodAnchor(
                method_fqn=method_fqn,
                kind=AnchorKind.FIELD_ACCESS,
                locator=f"field_access[{full_path}@{access_kind}@line:{line}]",
                line=line,
                snippet=_snippet(n),
                extra={
                    "target_path": full_path,
                    "object": obj_text[:60],
                    "field_name": field_name,
                    "access_kind": access_kind,
                },
            ))
            continue

    return out


def _iter_formal_params(params_node: Node) -> Iterator[Node]:
    for child in params_node.children:
        if child.type == "formal_parameter":
            yield child


def _classify_literal(node_type: str) -> str:
    if "string" in node_type or "character" in node_type:
        return "string"
    if "floating" in node_type:
        return "float"
    if "integer" in node_type:
        return "integer"
    if node_type in ("true", "false"):
        return "boolean"
    return "other"


def _infer_access_kind(field_access_node: Node) -> str:
    """parent 컨텍스트로 read/write/invoke 결정."""
    parent = field_access_node.parent
    if parent is None:
        return "read"
    if parent.type == "assignment_expression":
        # 우리가 left 인지?
        left = parent.child_by_field_name("left")
        if left is field_access_node:
            return "write"
    if parent.type == "method_invocation":
        # 우리가 object 인지?
        obj = parent.child_by_field_name("object")
        if obj is field_access_node:
            return "invoke"
    return "read"


__all__ = ("extract_anchors_from_method",)
