"""Cross-file method call resolution — 12-analyzer post-pass.

기본 JavaParser 는 `service.method()` 같은 호출에서 target 을
`<package>.service.method` 로 적음 (변수명 그대로). 이 모듈은 :

1. 클래스/인터페이스 entity 들의 simple-name → FQN 인덱스 빌드
2. 각 클래스의 field 의 (name, field_type) 인덱스 빌드
3. 미해소 call edge 의 target 을 분석 :
   - `<containing-class>.<varname>.<method>` 패턴
   - varname 이 enclosing class 의 field 면 → field.field_type → 클래스 FQN 룩업
   - 새 resolved call edge 추가 (기존 edge 는 보존)

결과 : Impact Analysis incoming 이 의미 있는 결과를 줌.

설계 결정 :
  - 기존 edge 보존 — debugging 시 두 버전 모두 볼 수 있게
  - 새 edge 의 attributes 에 `resolution: "field_type_lookup"` 표시
  - 추가 edge_kind 는 "calls" 그대로 (단순 추가)
  - 1-패스, in-memory — 큰 repo 도 sub-second
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.modeling.code_analysis.parser_protocol import (
    CodeRelation, EntityKinds, ParseResult, RelationKinds,
)


@dataclass(frozen=True)
class CallResolutionStats:
    total_calls: int
    already_resolved: int    # target 이 이미 method/constructor FQN
    newly_resolved: int      # 추가된 새 edge
    still_unresolved: int    # 해소 못 함 (varname 이 field 가 아니거나, type 매핑 실패)


def resolve_calls(parse_results: Sequence[ParseResult]) -> tuple[list[CodeRelation], CallResolutionStats]:
    """Parse_results → 추가 call edges (이미 있는 edges 와 합쳐서 사용).

    반환 :
        new_edges : 추가할 CodeRelation 리스트
        stats     : 해소 통계
    """
    # 1. simple-name → FQN 인덱스 (class / interface / enum)
    class_fqn_by_simple: dict[str, list[str]] = {}
    method_fqns: set[str] = set()
    fields_by_class: dict[str, dict[str, str]] = {}  # class_fqn → {field_name: field_type_simple}

    # P29-3 — bean_name → class FQN, (class, field) → qualifier
    bean_name_index: dict[str, str] = {}
    field_qualifier: dict[tuple[str, str], str] = {}  # (source_class_fqn, field_name) → qualifier

    for pr in parse_results:
        for e in pr.entities:
            if e.kind in (EntityKinds.CLASS, EntityKinds.INTERFACE, EntityKinds.ENUM):
                class_fqn_by_simple.setdefault(e.name, []).append(e.qualified_name)
            elif e.kind in (EntityKinds.METHOD, EntityKinds.CONSTRUCTOR):
                method_fqns.add(e.qualified_name)
            elif e.kind == EntityKinds.FIELD:
                ft = (e.attributes or {}).get("field_type")
                if ft and e.parent:
                    fields_by_class.setdefault(e.parent, {})[e.name] = str(ft)
            elif e.kind == EntityKinds.SPRING_BEAN:
                attrs = e.attributes or {}
                bn = attrs.get("bean_name")
                if bn:
                    bean_name_index[str(bn)] = e.qualified_name
        for rel in pr.relations:
            if rel.kind == RelationKinds.AUTOWIRES:
                attrs = rel.attributes or {}
                qual = attrs.get("qualifier")
                fname = attrs.get("field_name")
                if qual and fname:
                    field_qualifier[(rel.source, str(fname))] = str(qual)

    # 2. 각 call edge 분석
    new_edges: list[CodeRelation] = []
    seen_new: set[tuple[str, str]] = set()  # dedup
    already_resolved = 0
    newly_resolved = 0
    still_unresolved = 0
    total = 0

    for pr in parse_results:
        for rel in pr.relations:
            if rel.kind != "calls":
                continue
            total += 1
            if rel.target in method_fqns:
                already_resolved += 1
                continue

            # rel.target = "<...>.<varname>.<method>" 패턴
            parts = rel.target.rsplit(".", 2)
            if len(parts) < 3:
                still_unresolved += 1
                continue
            _, varname, method_name = parts

            # rel.source 의 enclosing class 추출 — source = "<class_fqn>.<method>"
            source_class_fqn = rel.source.rsplit(".", 1)[0]
            class_fields = fields_by_class.get(source_class_fqn)
            if not class_fields or varname not in class_fields:
                still_unresolved += 1
                continue

            type_simple = class_fields[varname]
            type_candidates = class_fqn_by_simple.get(type_simple, [])
            if not type_candidates:
                still_unresolved += 1
                continue

            # P29-3 — qualifier-aware resolution.
            # Qualifier 가 명시돼 있고 bean_name_index 에 hit 하면 type_candidates 와 무관하게
            # qualifier 가 가리키는 impl 을 사용 (interface 필드 + impl @Component("name") 패턴).
            ambiguity_attrs: dict[str, object] = {}
            qual = field_qualifier.get((source_class_fqn, varname))
            if qual and qual in bean_name_index:
                target_class_fqn = bean_name_index[qual]
                ambiguity_attrs["resolved_by_qualifier"] = qual
            elif len(type_candidates) > 1:
                target_class_fqn = type_candidates[0]
                ambiguity_attrs["ambiguous_resolution"] = True
                ambiguity_attrs["ambiguity_candidates"] = list(type_candidates)
            else:
                target_class_fqn = type_candidates[0]
            resolved_fqn = f"{target_class_fqn}.{method_name}"
            if resolved_fqn not in method_fqns:
                # method 도 안 잡히면 skip
                still_unresolved += 1
                continue

            key = (rel.source, resolved_fqn)
            if key in seen_new:
                continue
            seen_new.add(key)
            new_edges.append(CodeRelation(
                kind="calls",
                source=rel.source,
                target=resolved_fqn,
                file_path=rel.file_path,
                line=rel.line,
                attributes={
                    **(rel.attributes or {}),
                    "resolution": "field_type_lookup",
                    "original_target": rel.target,
                    **ambiguity_attrs,
                },
            ))
            newly_resolved += 1

    return new_edges, CallResolutionStats(
        total_calls=total,
        already_resolved=already_resolved,
        newly_resolved=newly_resolved,
        still_unresolved=still_unresolved,
    )


__all__ = ("CallResolutionStats", "resolve_calls")
