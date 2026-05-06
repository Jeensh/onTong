"""Path syntax — Action slot 경로.

문법 (C2=A 풍부):
- `params[0]`                          : 첫 번째 param 참조
- `params[0]<RushOrder>`               : subtype cast (Java instanceof 분기)
- `params[0].spec.diameter`            : composite term traversal (HAS_A)
- `params[0].chemical[-1]`             : 1:N collection 의 마지막
- `params[0].chemical[*]`              : 1:N 전체
- `params[0].chemical[2]`              : 인덱스
- `params[0].chemical[?(filter)]`      : 필터 (Phase 2 — parser 만 인식)
- `output.value`                       : output 참조
- `preconditions[0]`                   : Action 슬롯 직접
- `effects[1].target_term`             : Action 슬롯 직접
- `params[0].spec.diameter.range[1]`   : atomic 의 range 끝 값

Parse → 결정적 토큰 리스트 → validator 가 Domain Layer 그래프에 대해 traversal 가능 여부 검증.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from backend.modeling.domain_layer import (
    BusinessTerm,
    Composition,
    Inheritance,
)
from backend.modeling.domain_layer.resolver import effective_parts


class PathSegmentKind(StrEnum):
    ROOT_PARAM       = "root_param"        # params[i]
    ROOT_OUTPUT      = "root_output"
    ROOT_SLOT        = "root_slot"         # preconditions[i] / postconditions[i] / effects[i]
    SUBTYPE_CAST     = "subtype_cast"      # <SubtypeName>
    DOTTED           = "dotted"            # .name
    INDEX            = "index"             # [i] 정수
    LAST             = "last"              # [-1]
    ALL              = "all"               # [*]
    FILTER           = "filter"            # [?(...)] - 인식만, Phase 2


@dataclass(frozen=True)
class PathSegment:
    kind: PathSegmentKind
    value: str = ""               # 'spec' / '0' / 'RushOrder' / ...


@dataclass(frozen=True)
class ParsedPath:
    segments: tuple[PathSegment, ...]


class PathParseError(ValueError):
    pass


_ROOT_RE = re.compile(r"^(params|output|preconditions|postconditions|effects)(?:\[(\d+)\])?")
_SEG_RE = re.compile(
    r"\.(\w+)|"                      # group 1: dotted name
    r"<([\w.$]+)>|"                  # group 2: subtype cast
    r"\[(-1|\*)\]|"                  # group 3: last / all
    r"\[(\d+)\]|"                    # group 4: index
    r"\[\?\(([^)]+)\)\]"             # group 5: filter
)


def parse_path(path: str) -> ParsedPath:
    """Path string → ParsedPath. 문법 오류면 PathParseError."""
    if not path or not path.strip():
        raise PathParseError("empty path")
    p = path.strip()

    # 1. ROOT
    m = _ROOT_RE.match(p)
    if m is None:
        raise PathParseError(f"path must start with params/output/preconditions/postconditions/effects, got {p!r}")
    root_name, root_idx = m.group(1), m.group(2)
    if root_name == "params":
        if root_idx is None:
            raise PathParseError(f"'params' requires index: {p!r} — use params[i]")
        segs: list[PathSegment] = [PathSegment(PathSegmentKind.ROOT_PARAM, root_idx)]
    elif root_name == "output":
        segs = [PathSegment(PathSegmentKind.ROOT_OUTPUT)]
    else:
        # preconditions / postconditions / effects — index optional (없으면 ROOT_SLOT '*')
        segs = [PathSegment(PathSegmentKind.ROOT_SLOT, root_name + (f"[{root_idx}]" if root_idx else ""))]

    # 2. 나머지 segments
    pos = m.end()
    while pos < len(p):
        m2 = _SEG_RE.match(p, pos)
        if m2 is None:
            raise PathParseError(f"unexpected token at pos {pos}: ...{p[pos:pos+10]}")
        if m2.group(1) is not None:
            segs.append(PathSegment(PathSegmentKind.DOTTED, m2.group(1)))
        elif m2.group(2) is not None:
            segs.append(PathSegment(PathSegmentKind.SUBTYPE_CAST, m2.group(2)))
        elif m2.group(3) is not None:
            v = m2.group(3)
            segs.append(PathSegment(PathSegmentKind.LAST if v == "-1" else PathSegmentKind.ALL))
        elif m2.group(4) is not None:
            segs.append(PathSegment(PathSegmentKind.INDEX, m2.group(4)))
        elif m2.group(5) is not None:
            segs.append(PathSegment(PathSegmentKind.FILTER, m2.group(5)))
        pos = m2.end()

    return ParsedPath(segments=tuple(segs))


# ---------------------------------------------------------------------------
# Validate against Domain graph
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PathValidation:
    ok: bool
    last_term_fqn: str | None     # final 위치의 BusinessTerm fqn (atomic 이면 leaf)
    error: str = ""


def validate_path(
    path: ParsedPath,
    *,
    action_params: list[tuple[str, str | None]],   # [(param_name, object_ref_term_fqn or None), ...]
    terms: Iterable[BusinessTerm],
    inheritance: Iterable[Inheritance],
    composition: Iterable[Composition],
) -> PathValidation:
    """Path 가 Domain graph 에서 traversal 가능한지 검증.

    action_params: Action.params 의 (name, object_ref_term) tuple 리스트.
                   순서대로 params[i] 참조 시 사용.
    """
    term_by_fqn = {t.fqn: t for t in terms}

    if not path.segments:
        return PathValidation(False, None, "empty path")

    head = path.segments[0]

    # ROOT 종류별 시작 term 결정
    current_term: str | None = None
    if head.kind == PathSegmentKind.ROOT_PARAM:
        idx = int(head.value)
        if idx < 0 or idx >= len(action_params):
            return PathValidation(False, None, f"params[{idx}] out of range (have {len(action_params)})")
        current_term = action_params[idx][1]    # object_ref_term
        if current_term is None:
            # primitive param — 추가 traversal 불가
            if len(path.segments) > 1:
                return PathValidation(False, None, f"params[{idx}] is primitive, cannot traverse further")
            return PathValidation(True, None)
    elif head.kind == PathSegmentKind.ROOT_OUTPUT:
        # output 는 본 검증에서 단순 OK 처리 (output object_ref 정보 추가 인자로 받지 않음)
        return PathValidation(True, None)
    elif head.kind == PathSegmentKind.ROOT_SLOT:
        # preconditions[i] / effects[i] 등 — Action 슬롯 직접. graph traversal X.
        return PathValidation(True, None)
    else:
        return PathValidation(False, None, f"path must start with root, got {head.kind}")

    # 2. 나머지 segments traversal
    for seg in path.segments[1:]:
        # INDEX/LAST/ALL/FILTER 는 current_term 무관 (collection 또는 atomic.range 인덱싱)
        if seg.kind in (PathSegmentKind.INDEX, PathSegmentKind.LAST,
                        PathSegmentKind.ALL, PathSegmentKind.FILTER):
            continue

        if current_term is None:
            return PathValidation(False, None, f"cannot traverse beyond primitive at {seg}")
        cur = term_by_fqn.get(current_term)
        if cur is None:
            return PathValidation(False, None, f"unknown term '{current_term}'")

        if seg.kind == PathSegmentKind.SUBTYPE_CAST:
            # subtype cast — 그 subtype 이 current_term 의 자손인지 검사
            from backend.modeling.domain_layer.resolver import descendants as _desc
            target = seg.value
            # CamelCase 'RushOrder' → snake 'rush_order' 변환 (Java class name 호환)
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", target).lower()
            # 매칭 우선순위: exact fqn → exact label → fqn endswith .{target} → fqn endswith .{snake}
            possible = [t for t in terms if (
                t.fqn == target or
                t.label == target or
                t.fqn.endswith(f".{target}") or
                t.fqn.endswith(f".{snake}")
            )]
            if not possible:
                return PathValidation(False, None, f"subtype cast '<{target}>' — term not found")
            target_fqn = possible[0].fqn
            # current_term 의 descendants 에 포함?
            if target_fqn != current_term and target_fqn not in _desc(current_term, inheritance):
                return PathValidation(False, None,
                    f"subtype cast '<{target}>' is not a descendant of '{current_term}'")
            current_term = target_fqn

        elif seg.kind == PathSegmentKind.DOTTED:
            # role traversal — effective_parts 안에서 role_name 매칭
            eff = effective_parts(current_term, inheritance, composition)
            match = next((c for c in eff if c.role_name == seg.value), None)
            if match is None:
                # atomic 의 'range' 같은 reserved 경로?
                if seg.value in ("range", "value", "unit", "enum_values"):
                    cur_t = term_by_fqn.get(current_term)
                    if cur_t and cur_t.kind.value == "atomic":
                        # atomic 의 meta 접근 — leaf, 추가 traversal X
                        current_term = None
                        continue
                return PathValidation(False, None,
                    f"role '{seg.value}' not found on '{current_term}' (effective parts: "
                    f"{[c.role_name for c in eff]})")
            current_term = match.child_fqn

        else:
            return PathValidation(False, None, f"unexpected segment kind {seg.kind}")

    return PathValidation(True, current_term)


__all__ = (
    "PathSegment", "PathSegmentKind", "ParsedPath",
    "PathParseError", "PathValidation",
    "parse_path", "validate_path",
)
