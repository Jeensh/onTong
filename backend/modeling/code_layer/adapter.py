"""Adapter — 기존 java_parser ParseResult → 새 Code Layer schema.

기존 출력 (parser_protocol.CodeEntity / CodeRelation) 의 정보를 새 모델에 매핑.
graph_writer 의 출력은 사용 X (Two-Layer 정합).

매핑:
- CodeEntity(kind="package")           → 무시 (CodeType 후보 X)
- CodeEntity(kind="class"|"interface"|"enum") → CodeType
  - is_abstract: modifiers 안 'abstract' 있으면 True
  - kind: class+abstract → ABSTRACT_CLASS, interface → INTERFACE, enum → ENUM
- CodeEntity(kind="method")            → CodeMethod
  - parent_type_fqn: parent 또는 fqn split
  - role: 기본 UNKNOWN (다음 step C2-4 role_classifier 가 채움)
  - anchors: attributes["anchors"] 그대로 변환
  - params: attributes["parameters"]
  - return_type: attributes["return_type"]
  - body_text: attributes["source"]
  - extra: mutations / value_flow / extracted_rules 등 보존
- CodeEntity(kind="field")             → CodeField (parent 의 fields 에 append)
- CodeEntity(kind="constructor")       → CodeMethod (is_constructor=True)

CodeRelation 매핑:
- extends                              → CodeType.extends (단일) 또는 extends_interfaces (interface)
- implements                           → CodeType.implements
- contains, calls, depends_on, reads, writes 등 → CodeType 단계에서는 무시
  (calls 는 C2-5 CallSiteAnalyzer 에서 별도 처리)

Spring entity (spring_bean / http_endpoint / aspect 등) → 각 클래스의 annotations 로 흡수.
"""
from __future__ import annotations

import logging
from typing import Iterable

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)
from backend.modeling.code_layer.schema import (
    CodeField,
    CodeMethod,
    CodeMethodAnchor,
    CodeMethodParam,
    CodeType,
    CodeTypeKind,
    MethodRole,
)

logger = logging.getLogger(__name__)


_TYPE_ENTITY_KINDS = {EntityKinds.CLASS, EntityKinds.INTERFACE, EntityKinds.ENUM}


def _resolve_type_kind(entity: CodeEntity) -> CodeTypeKind:
    if entity.kind == EntityKinds.INTERFACE:
        return CodeTypeKind.INTERFACE
    if entity.kind == EntityKinds.ENUM:
        return CodeTypeKind.ENUM
    if entity.kind == EntityKinds.CLASS:
        if "abstract" in entity.modifiers:
            return CodeTypeKind.ABSTRACT_CLASS
        return CodeTypeKind.CLASS
    raise ValueError(f"Unsupported type entity kind: {entity.kind}")


def _entity_annotations(entity: CodeEntity) -> list[str]:
    """annotations 정규화 → ["@Override", "@Service(\"x\")"] 류 string list.

    java_parser 출력은 [{'name': 'Override', 'arguments': {...}}] dict list.
    """
    raw = entity.attributes.get("annotations", [])
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for a in raw:
        if isinstance(a, dict):
            name = a.get("name", "")
            args = a.get("arguments")
            if args and isinstance(args, dict) and args:
                # @Profile(value="prod") 등 — 단순 stringify
                arg_str = ",".join(f"{k}={v}" for k, v in args.items())
                out.append(f"@{name}({arg_str})")
            else:
                out.append(f"@{name}")
        else:
            out.append(str(a))
    return out


def _signature_suffix(params_raw: list) -> str:
    """`(int,String)` 형식 — Java 오버로드 구분 위해 fqn 에 append."""
    if not params_raw:
        return "()"
    types = [
        str(p.get("type", "?")).replace(" ", "") if isinstance(p, dict) else "?"
        for p in params_raw
    ]
    return "(" + ",".join(types) + ")"


def _convert_method(entity: CodeEntity, type_fqn: str) -> CodeMethod:
    attrs = entity.attributes
    params_raw = attrs.get("parameters", [])
    params = [
        CodeMethodParam(name=p.get("name", ""), type=p.get("type", ""))
        for p in params_raw
        if isinstance(p, dict)
    ]
    sig = _signature_suffix(params_raw)
    method_fqn = entity.qualified_name + sig

    anchors_raw = attrs.get("anchors", [])
    anchors = [
        CodeMethodAnchor(
            # anchor 의 method_fqn 도 시그니처 포함으로 통일
            method_fqn=method_fqn,
            kind=str(a.get("kind", "")),
            locator=str(a.get("locator", "")),
            line=a.get("line"),
            snippet=a.get("snippet", ""),
            extra=a.get("extra", {}) or {},
        )
        for a in anchors_raw
        if isinstance(a, dict)
    ]
    extra: dict = {}
    for k in ("value_flow", "mutations", "extracted_rules"):
        if k in attrs:
            extra[k] = attrs[k]

    return CodeMethod(
        fqn=method_fqn,
        name=entity.name,
        parent_type_fqn=type_fqn,
        return_type=str(attrs.get("return_type", "")),
        params=params,
        modifiers=list(entity.modifiers),
        annotations=_entity_annotations(entity),
        role=MethodRole.UNKNOWN,
        is_abstract=("abstract" in entity.modifiers),
        is_override=False,  # @Override annotation 검사로 다음 단계에서 갱신
        is_constructor=False,
        body_text=attrs.get("source"),
        line_start=entity.line_start,
        line_end=entity.line_end,
        anchors=anchors,
        extra=extra,
    )


def _convert_constructor(entity: CodeEntity, type_fqn: str) -> CodeMethod:
    m = _convert_method(entity, type_fqn)
    return m.model_copy(update={"is_constructor": True})


def _dedup_fqn(m: CodeMethod, seen: set[str]) -> CodeMethod:
    """동일 fqn 중복 시 `@line` suffix 추가 (java_parser overloading mis-extract 방어)."""
    if m.fqn not in seen:
        return m
    new_fqn = f"{m.fqn}@line{m.line_start or 0}"
    # anchor 들의 method_fqn 도 동기화
    new_anchors = [a.model_copy(update={"method_fqn": new_fqn}) for a in m.anchors]
    return m.model_copy(update={"fqn": new_fqn, "anchors": new_anchors})


def _convert_field(entity: CodeEntity) -> CodeField:
    attrs = entity.attributes
    type_str = str(attrs.get("type", attrs.get("field_type", "")))
    is_collection = bool(attrs.get("is_collection", False))
    return CodeField(
        name=entity.name,
        type=type_str or "Object",
        modifiers=list(entity.modifiers),
        annotations=_entity_annotations(entity),
        is_collection=is_collection,
        element_type=attrs.get("element_type"),
        line=entity.line_start,
    )


def adapt_parse_results(
    parse_results: Iterable[ParseResult],
    *,
    repo_id: str = "",
) -> list[CodeType]:
    """여러 파일의 ParseResult 를 합쳐서 CodeType 리스트 반환.

    같은 type fqn 이 여러 파일에 등장하면 (partial class 류) 첫 번째만 채택.
    nested type 도 자체 fqn 으로 등록 (parent 와 부모-자식 관계는 fqn 으로 유지).
    """
    type_entities: dict[str, CodeEntity] = {}      # fqn → CodeEntity (kind=class/interface/enum)
    method_entities_by_parent: dict[str, list[CodeEntity]] = {}
    field_entities_by_parent: dict[str, list[CodeEntity]] = {}
    constructor_entities_by_parent: dict[str, list[CodeEntity]] = {}

    extends_by_type: dict[str, str] = {}            # 단일 부모 (class)
    extends_interfaces_by_type: dict[str, list[str]] = {}
    implements_by_type: dict[str, list[str]] = {}

    # 1. entities 수집
    for pr in parse_results:
        for e in pr.entities:
            if e.kind in _TYPE_ENTITY_KINDS:
                if e.qualified_name not in type_entities:
                    type_entities[e.qualified_name] = e
            elif e.kind == EntityKinds.METHOD:
                parent = e.parent or ""
                method_entities_by_parent.setdefault(parent, []).append(e)
            elif e.kind == EntityKinds.FIELD:
                parent = e.parent or ""
                field_entities_by_parent.setdefault(parent, []).append(e)
            elif e.kind == EntityKinds.CONSTRUCTOR:
                parent = e.parent or ""
                constructor_entities_by_parent.setdefault(parent, []).append(e)
            # 기타 (package / spring entity / db 등) 은 CodeType 외로 무시

        # 2. relations 분류
        for r in pr.relations:
            if r.kind == RelationKinds.EXTENDS:
                src_kind = type_entities.get(r.source)
                if src_kind is not None and src_kind.kind == EntityKinds.INTERFACE:
                    # interface extends interface
                    extends_interfaces_by_type.setdefault(r.source, []).append(r.target)
                else:
                    # class/abstract_class extends class — 단일
                    extends_by_type[r.source] = r.target
            elif r.kind == RelationKinds.IMPLEMENTS:
                implements_by_type.setdefault(r.source, []).append(r.target)
            # contains/calls/depends_on 등 — Code Layer 단계에서는 무시 (CallSiteAnalyzer 가 별도)

    # 3. CodeType 빌드
    result: list[CodeType] = []
    for fqn, entity in type_entities.items():
        kind = _resolve_type_kind(entity)
        is_abstract = (kind in (CodeTypeKind.ABSTRACT_CLASS, CodeTypeKind.INTERFACE))

        # interface 의 단일 extends 는 schema 가 거부하므로 extends_interfaces 로 대체
        extends_val = extends_by_type.get(fqn)
        ext_ifaces = extends_interfaces_by_type.get(fqn, [])
        if kind == CodeTypeKind.INTERFACE:
            if extends_val:
                ext_ifaces = [extends_val] + ext_ifaces
                extends_val = None

        # methods + constructors
        methods: list[CodeMethod] = []
        seen_fqns: set[str] = set()  # 동일 fqn (오버로드 + java_parser 의 mis-extract) dedup
        for m_entity in method_entities_by_parent.get(fqn, []):
            try:
                m = _convert_method(m_entity, fqn)
                m = _dedup_fqn(m, seen_fqns)
                methods.append(m)
                seen_fqns.add(m.fqn)
            except Exception as e:
                logger.warning("method convert failed: %s — %s", m_entity.qualified_name, e)
        for c_entity in constructor_entities_by_parent.get(fqn, []):
            try:
                m = _convert_constructor(c_entity, fqn)
                m = _dedup_fqn(m, seen_fqns)
                methods.append(m)
                seen_fqns.add(m.fqn)
            except Exception as e:
                logger.warning("constructor convert failed: %s — %s", c_entity.qualified_name, e)

        # fields
        fields = [_convert_field(f) for f in field_entities_by_parent.get(fqn, [])]

        # @Override 메서드 표시 (annotations 안에 있으면)
        for i, m in enumerate(methods):
            if any(a.startswith("@Override") for a in m.annotations):
                methods[i] = m.model_copy(update={"is_override": True})

        try:
            ct = CodeType(
                fqn=fqn,
                simple_name=entity.name,
                package=entity.parent or "",
                kind=kind,
                is_abstract=is_abstract,
                extends=extends_val,
                implements=implements_by_type.get(fqn, []),
                extends_interfaces=ext_ifaces,
                fields=fields,
                methods=methods,
                modifiers=list(entity.modifiers),
                annotations=_entity_annotations(entity),
                source_file=entity.file_path,
                line_start=entity.line_start,
                line_end=entity.line_end,
                repo_id=repo_id,
            )
            result.append(ct)
        except Exception as e:
            logger.warning("CodeType convert failed: %s — %s", fqn, e)

    return result


__all__ = ("adapt_parse_results",)
