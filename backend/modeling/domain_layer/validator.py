"""Domain Layer 그래프-수준 검증.

Schema-level 은 단일 노드 invariant 만 검사 (atomic+struct_like 금지 등).
이 모듈은 graph-level — 사이클 / atomic-parts / dangling reference 등.

설계: 모든 검사는 store 의 현재 상태를 입력으로 받아 (BusinessTerm[] +
Inheritance[] + Composition[]) → list[ValidationError] 반환. raise 안 함.
사용자가 큐 형태로 처리할 수 있게.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from backend.modeling.domain_layer.schema import (
    BusinessTerm,
    Composition,
    Inheritance,
    TermKind,
)


Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class ValidationError:
    code: str           # "INHERITANCE_CYCLE" / "ATOMIC_HAS_PARTS" / ...
    severity: Severity
    fqn: str
    message: str
    related_fqns: tuple[str, ...] = ()


_WHITE, _GRAY, _BLACK = 0, 1, 2


def _detect_cycle(
    nodes: set[str], children_of: dict[str, list[str]],
) -> list[tuple[str, ...]]:
    """three-color DFS. 사이클 발견 시 cycle path 들 반환.

    중복 cycle 은 여러 진입점에서 detect 될 수 있음 — 단순 list 로 반환.
    """
    color: dict[str, int] = dict.fromkeys(nodes, _WHITE)
    cycles: list[tuple[str, ...]] = []
    path: list[str] = []

    def dfs(u: str) -> None:
        color[u] = _GRAY
        path.append(u)
        for v in children_of.get(u, []):
            if color.get(v, _WHITE) == _GRAY:
                # back edge → cycle
                idx = path.index(v) if v in path else 0
                cycles.append(tuple(path[idx:] + [v]))
            elif color.get(v, _WHITE) == _WHITE:
                dfs(v)
        path.pop()
        color[u] = _BLACK

    for n in nodes:
        if color.get(n, _WHITE) == _WHITE:
            dfs(n)
    return cycles


def validate_graph(
    terms: Iterable[BusinessTerm],
    inheritance: Iterable[Inheritance],
    composition: Iterable[Composition],
) -> list[ValidationError]:
    """전체 그래프 검사. 모든 검사 통과면 빈 리스트."""
    errors: list[ValidationError] = []
    term_by_fqn = {t.fqn: t for t in terms}

    # 1. atomic 의 parts 금지
    comp_list = list(composition)
    for c in comp_list:
        parent = term_by_fqn.get(c.parent_fqn)
        if parent is not None and parent.kind == TermKind.ATOMIC:
            errors.append(ValidationError(
                code="ATOMIC_HAS_PARTS",
                severity="error",
                fqn=parent.fqn,
                message=(
                    f"atomic term '{parent.fqn}' cannot have parts; "
                    f"found composition role='{c.role_name}' → {c.child_fqn}"
                ),
                related_fqns=(c.child_fqn,),
            ))

    # 2. dangling reference (composition / inheritance 가 없는 term 가리킴)
    inh_list = list(inheritance)
    for c in comp_list:
        if c.parent_fqn not in term_by_fqn:
            errors.append(ValidationError(
                code="COMPOSITION_DANGLING_PARENT",
                severity="error",
                fqn=c.parent_fqn,
                message=f"composition references unknown parent '{c.parent_fqn}'",
                related_fqns=(c.child_fqn,),
            ))
        if c.child_fqn not in term_by_fqn:
            errors.append(ValidationError(
                code="COMPOSITION_DANGLING_CHILD",
                severity="error",
                fqn=c.child_fqn,
                message=f"composition references unknown child '{c.child_fqn}' under '{c.parent_fqn}'",
                related_fqns=(c.parent_fqn,),
            ))
    for i in inh_list:
        if i.child_fqn not in term_by_fqn:
            errors.append(ValidationError(
                code="INHERITANCE_DANGLING_CHILD",
                severity="error",
                fqn=i.child_fqn,
                message=f"inheritance references unknown child '{i.child_fqn}'",
                related_fqns=(i.parent_fqn,),
            ))
        if i.parent_fqn not in term_by_fqn:
            errors.append(ValidationError(
                code="INHERITANCE_DANGLING_PARENT",
                severity="error",
                fqn=i.parent_fqn,
                message=f"inheritance references unknown parent '{i.parent_fqn}'",
                related_fqns=(i.child_fqn,),
            ))

    # 3. inheritance 사이클 (extends + implements 모두 DAG)
    inh_nodes: set[str] = set()
    inh_children: dict[str, list[str]] = {}
    for i in inh_list:
        inh_nodes.add(i.child_fqn)
        inh_nodes.add(i.parent_fqn)
        # child → parent 방향
        inh_children.setdefault(i.child_fqn, []).append(i.parent_fqn)
    for cycle in _detect_cycle(inh_nodes, inh_children):
        errors.append(ValidationError(
            code="INHERITANCE_CYCLE",
            severity="error",
            fqn=cycle[0],
            message=f"inheritance cycle detected: {' → '.join(cycle)}",
            related_fqns=cycle,
        ))

    # 4. composition 사이클 (parent → child 방향이 DAG)
    comp_nodes: set[str] = set()
    comp_children: dict[str, list[str]] = {}
    for c in comp_list:
        comp_nodes.add(c.parent_fqn)
        comp_nodes.add(c.child_fqn)
        comp_children.setdefault(c.parent_fqn, []).append(c.child_fqn)
    for cycle in _detect_cycle(comp_nodes, comp_children):
        errors.append(ValidationError(
            code="COMPOSITION_CYCLE",
            severity="error",
            fqn=cycle[0],
            message=f"composition cycle detected: {' → '.join(cycle)}",
            related_fqns=cycle,
        ))

    # 5. 같은 (parent, role_name) 중복
    seen_roles: dict[tuple[str, str], str] = {}
    for c in comp_list:
        key = (c.parent_fqn, c.role_name)
        if key in seen_roles and seen_roles[key] != c.child_fqn:
            errors.append(ValidationError(
                code="COMPOSITION_DUPLICATE_ROLE",
                severity="warning",
                fqn=c.parent_fqn,
                message=(
                    f"duplicate composition role '{c.role_name}' on '{c.parent_fqn}': "
                    f"'{seen_roles[key]}' vs '{c.child_fqn}'"
                ),
                related_fqns=(seen_roles[key], c.child_fqn),
            ))
        else:
            seen_roles[key] = c.child_fqn

    # 6. interface 가 implements 외에 다른 inheritance kind 로 사용되는 경우
    #    (현재는 schema 가 single-edge 이므로 자동 OK; 향후 mixin 도입 시 검사 위치)

    return errors


__all__ = ("ValidationError", "validate_graph")
