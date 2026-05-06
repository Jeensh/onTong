"""effective_parts resolver — Inheritance + Composition transitive closure.

핵심 함수:
- effective_parts(fqn, ...) → list[Composition] : term 의 own + inherited parts (extends + implements 따라)
- ancestors(fqn, ...)       → list[str]         : 모든 조상 fqn (transitive closure)
- descendants(fqn, ...)     → list[str]         : 모든 자손 fqn

Resolver 는 read-only — store 에서 가져온 데이터를 input 으로 받는다.
사이클 보호: visited set + max_depth (default 32, 안전망).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.modeling.domain_layer.schema import (
    Composition,
    Inheritance,
)


_DEFAULT_MAX_DEPTH = 32


@dataclass(frozen=True)
class _Indexed:
    """resolver 가 빠르게 traverse 할 수 있도록 인덱스."""
    inh_parents: dict[str, list[Inheritance]]    # child → list[Inheritance]
    inh_children: dict[str, list[Inheritance]]   # parent → list[Inheritance]
    comp_by_parent: dict[str, list[Composition]] # parent → list[Composition]


def _build_index(
    inheritance: Iterable[Inheritance],
    composition: Iterable[Composition],
) -> _Indexed:
    inh_p: dict[str, list[Inheritance]] = {}
    inh_c: dict[str, list[Inheritance]] = {}
    for i in inheritance:
        inh_p.setdefault(i.child_fqn, []).append(i)
        inh_c.setdefault(i.parent_fqn, []).append(i)
    comp_p: dict[str, list[Composition]] = {}
    for c in composition:
        comp_p.setdefault(c.parent_fqn, []).append(c)
    return _Indexed(inh_parents=inh_p, inh_children=inh_c, comp_by_parent=comp_p)


def ancestors(
    fqn: str,
    inheritance: Iterable[Inheritance],
    *,
    max_depth: int = _DEFAULT_MAX_DEPTH,
) -> list[str]:
    """fqn 의 모든 조상 (extends + implements 모두).

    BFS, 사이클 보호 (visited).
    """
    idx = _build_index(inheritance, [])
    visited: set[str] = set()
    out: list[str] = []
    stack: list[tuple[str, int]] = [(fqn, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth >= max_depth:
            continue
        for parent_edge in idx.inh_parents.get(cur, []):
            p = parent_edge.parent_fqn
            if p in visited:
                continue
            visited.add(p)
            out.append(p)
            stack.append((p, depth + 1))
    return out


def descendants(
    fqn: str,
    inheritance: Iterable[Inheritance],
    *,
    max_depth: int = _DEFAULT_MAX_DEPTH,
) -> list[str]:
    """fqn 의 모든 자손."""
    idx = _build_index(inheritance, [])
    visited: set[str] = set()
    out: list[str] = []
    stack: list[tuple[str, int]] = [(fqn, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth >= max_depth:
            continue
        for child_edge in idx.inh_children.get(cur, []):
            c = child_edge.child_fqn
            if c in visited:
                continue
            visited.add(c)
            out.append(c)
            stack.append((c, depth + 1))
    return out


def effective_parts(
    fqn: str,
    inheritance: Iterable[Inheritance],
    composition: Iterable[Composition],
    *,
    max_depth: int = _DEFAULT_MAX_DEPTH,
) -> list[Composition]:
    """fqn 의 effective composition parts.

    own parts + 모든 조상의 parts (extends + implements 통한 inherited).
    같은 role_name 이 충돌하면 own (가장 가까운 자손) 이 우선.

    반환 순서: own first, then inherited (BFS 순서).
    """
    idx = _build_index(inheritance, composition)

    # 1. 자신의 parts
    seen_roles: set[str] = set()
    out: list[Composition] = []
    for c in idx.comp_by_parent.get(fqn, []):
        if c.role_name in seen_roles:
            continue
        seen_roles.add(c.role_name)
        out.append(c)

    # 2. 조상의 parts (BFS)
    visited_anc: set[str] = set()
    queue: list[tuple[str, int]] = [(fqn, 0)]
    while queue:
        cur, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for inh in idx.inh_parents.get(cur, []):
            p = inh.parent_fqn
            if p in visited_anc:
                continue
            visited_anc.add(p)
            for c in idx.comp_by_parent.get(p, []):
                if c.role_name in seen_roles:
                    # 자손이 override (실제로는 same role 다른 child) — skip
                    continue
                seen_roles.add(c.role_name)
                out.append(c)
            queue.append((p, depth + 1))

    return out


__all__ = ("ancestors", "descendants", "effective_parts")
