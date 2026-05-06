"""M1a (2026-04-27) — Method body 에서 mutation 추적.

자바에서 객체가 "포인터처럼" 전달되어 method 안에서 변경되는 경우 추출 :

1. **param.setXxx(...)**           — JavaBeans setter (가장 흔한 패턴)
2. **param.field = value**         — public field 직접 할당
3. **param.put(k, v)** / map.add() — collection 변경
4. **this.field = value**          — 같은 클래스 field 변경 (instance state)

결과 : `MethodMutation` list — {target (param 이름 또는 this), kind, accessor (setXxx 또는 field), source_var (할당된 값의 출처)}

이 정보로 method signature 의 in/out 역할 분류, 부수 효과 표시, 시뮬레이션 mock 정확도 향상.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

from tree_sitter import Node

logger = logging.getLogger(__name__)


class MutationKind(StrEnum):
    SETTER = "setter"               # param.setXxx(value)
    FIELD_WRITE = "field_write"     # param.field = value
    COLLECTION_ADD = "collection_add"  # list.add / map.put
    THIS_FIELD = "this_field"       # this.field = value


@dataclass(frozen=True)
class MethodMutation:
    target: str              # param 이름 또는 "this"
    kind: MutationKind
    accessor: str            # setXxx 메서드명 또는 field 이름
    source_var: str = ""     # 할당된 값의 출처 변수 (가능하면)
    line: int = 0


def _decode(node: Node | None) -> str:
    if node is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def extract_mutations(method_node: Node, param_names: set[str]) -> list[MethodMutation]:
    """method body 를 walk 하면서 mutation 패턴 검출.

    Args:
        method_node: tree-sitter `method_declaration` 노드
        param_names: 메서드의 파라미터 이름 set (포인터 추적 대상)
    """
    body = method_node.child_by_field_name("body")
    if body is None:
        return []
    out: list[MethodMutation] = []

    def visit(n: Node) -> None:
        # 1. method_invocation : foo.setBar(x) — receiver 가 param 또는 this
        if n.type == "method_invocation":
            obj = n.child_by_field_name("object")
            name = n.child_by_field_name("name")
            args = n.child_by_field_name("arguments")
            if name is not None:
                method_name = _decode(name)
                receiver = _decode(obj) if obj is not None else "this"
                # setter pattern : setXxx (and obj is param 또는 this)
                if method_name.startswith("set") and len(method_name) > 3 and method_name[3].isupper():
                    if receiver in param_names or receiver == "this":
                        first_arg_text = ""
                        if args is not None and len(args.children) >= 2:
                            for ch in args.children:
                                if ch.type not in ("(", ")", ","):
                                    first_arg_text = _decode(ch)
                                    break
                        out.append(MethodMutation(
                            target=receiver,
                            kind=MutationKind.SETTER,
                            accessor=method_name,
                            source_var=first_arg_text[:40],
                            line=n.start_point[0] + 1,
                        ))
                # collection add/put
                elif method_name in ("add", "put", "addAll", "putAll", "remove", "clear"):
                    if receiver in param_names or receiver == "this":
                        out.append(MethodMutation(
                            target=receiver,
                            kind=MutationKind.COLLECTION_ADD,
                            accessor=method_name,
                            line=n.start_point[0] + 1,
                        ))

        # 2. assignment_expression : foo.field = value, this.field = value
        elif n.type == "assignment_expression":
            left = n.child_by_field_name("left")
            right = n.child_by_field_name("right")
            if left is not None and left.type == "field_access":
                obj = left.child_by_field_name("object")
                fld = left.child_by_field_name("field")
                if obj is not None and fld is not None:
                    receiver = _decode(obj)
                    field_name = _decode(fld)
                    if receiver == "this":
                        out.append(MethodMutation(
                            target="this",
                            kind=MutationKind.THIS_FIELD,
                            accessor=field_name,
                            source_var=_decode(right)[:40] if right else "",
                            line=n.start_point[0] + 1,
                        ))
                    elif receiver in param_names:
                        out.append(MethodMutation(
                            target=receiver,
                            kind=MutationKind.FIELD_WRITE,
                            accessor=field_name,
                            source_var=_decode(right)[:40] if right else "",
                            line=n.start_point[0] + 1,
                        ))

        for child in n.children:
            visit(child)

    visit(body)
    return out


__all__ = ("MethodMutation", "MutationKind", "extract_mutations")
