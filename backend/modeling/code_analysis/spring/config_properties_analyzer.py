"""OD-11-E1-f : Spring `@ConfigurationProperties` analyzer (11번째).

`@ConfigurationProperties(prefix=..)` 가 붙은 클래스의 instance field 를 모두
`config_property` 엔티티 + `has_config` 엣지 (class FQN → config_property FQN)
로 emit 한다. CONFLICTS_WITH gap 감지에서 매뉴얼이 기술하는 "최대 두께" 같은
운영 파라미터 ↔ 코드 default 값 비교의 핵심 입력.

지원 어노테이션 형식 :
  @ConfigurationProperties(prefix = "slab.equipment")
  @ConfigurationProperties("slab.equipment")
  @ConfigurationProperties                              ← 마커 (prefix="")

Field 선택 :
  - 비-`static` instance field 만 (constants 는 config 가 아님).
  - `final` 은 허용 (Spring Boot 2.2+ 생성자 바인딩).

Entity attributes :
  prefix             "slab.equipment"
  key                "slab.equipment.maxThicknessMm"  (canonical, camelCase)
  key_kebab          "slab.equipment.max-thickness-mm" (relaxed binding alias)
  field_name         "maxThicknessMm"
  field_type         "double"
  default_value      "240.0"  (initializer literal text — 없으면 키 부재)
  bound_class_fqn    "com.ontong.slab.config.EquipmentProperties"
  bound_field_fqn    "com.ontong.slab.config.EquipmentProperties.maxThicknessMm"

Relation : `has_config` (parser_protocol L169 — `spring_bean/method → config_property`).
"""

from __future__ import annotations

import re

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    RelationKinds,
)

_ANNOTATION_NAME = "ConfigurationProperties"

# camelCase → kebab-case (Spring relaxed binding alias).
_CAMEL_TO_KEBAB_RE = re.compile(r"([a-z0-9])([A-Z])")


class ConfigPropertiesAnalyzer:
    """Spring `@ConfigurationProperties` → `config_property` 엔티티 + `has_config` 엣지."""

    def analyze(
        self,
        tree: object | None,
        content: bytes,
        file_path: str,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        if tree is None:
            return [], []

        root: Node = tree.root_node  # type: ignore[attr-defined]

        entities: list[CodeEntity] = []
        relations: list[CodeRelation] = []

        for child in root.children:
            if child.type == "class_declaration":
                self._analyze_class(child, pkg_name, file_path, entities, relations)
        return entities, relations

    # -- class --------------------------------------------------------------

    def _analyze_class(
        self,
        node: Node,
        pkg_name: str | None,
        file_path: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        anno = self._find_config_properties_annotation(node)
        if anno is None:
            return

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        class_qname = f"{pkg_name}.{class_name}" if pkg_name else class_name

        prefix = self._extract_prefix(anno)

        body = node.child_by_field_name("body")
        if body is None:
            return

        for member in body.children:
            if member.type != "field_declaration":
                continue
            self._analyze_field(
                member, class_qname, prefix, file_path, entities, relations,
            )

    # -- field --------------------------------------------------------------

    def _analyze_field(
        self,
        node: Node,
        class_qname: str,
        prefix: str,
        file_path: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        modifiers = _collect_modifiers(node)
        if "static" in modifiers:
            return  # constants 는 config 가 아님

        type_node = node.child_by_field_name("type")
        field_type = type_node.text.decode() if type_node is not None else None

        # field_declaration 안의 첫 variable_declarator 만 — JavaParser._extract_field
        # 와 동일하게 "한 declaration = 한 variable" 단순화.
        decl_node: Node | None = None
        for child in node.children:
            if child.type == "variable_declarator":
                decl_node = child
                break
        if decl_node is None:
            return

        name_node = decl_node.child_by_field_name("name")
        if name_node is None:
            return
        field_name = name_node.text.decode()

        canonical_key = f"{prefix}.{field_name}" if prefix else field_name
        kebab_key = _to_kebab_key(prefix, field_name)
        bound_field_fqn = f"{class_qname}.{field_name}"

        attrs: dict[str, object] = {
            "prefix": prefix,
            "key": canonical_key,
            "key_kebab": kebab_key,
            "field_name": field_name,
            "bound_class_fqn": class_qname,
            "bound_field_fqn": bound_field_fqn,
        }
        if field_type is not None:
            attrs["field_type"] = field_type

        value_node = decl_node.child_by_field_name("value")
        if value_node is not None:
            attrs["default_value"] = value_node.text.decode()

        entities.append(
            CodeEntity(
                kind=EntityKinds.CONFIG_PROPERTY,
                qualified_name=canonical_key,
                name=field_name,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                modifiers=modifiers,
                parent=class_qname,
                attributes=attrs,
            )
        )
        relations.append(
            CodeRelation(
                kind=RelationKinds.HAS_CONFIG,
                source=class_qname,
                target=canonical_key,
                file_path=file_path,
                line=node.start_point[0] + 1,
            )
        )

    # -- annotation parsing -------------------------------------------------

    def _find_config_properties_annotation(self, class_node: Node) -> Node | None:
        for child in class_node.children:
            if child.type == "modifiers":
                for m in child.children:
                    if (
                        m.type in ("marker_annotation", "annotation")
                        and _annotation_name(m) == _ANNOTATION_NAME
                    ):
                        return m
            if (
                child.type in ("marker_annotation", "annotation")
                and _annotation_name(child) == _ANNOTATION_NAME
            ):
                return child
        return None

    def _extract_prefix(self, anno_node: Node) -> str:
        """`@ConfigurationProperties(...)` 에서 prefix 추출. 마커/부재 시 빈 문자열."""
        if anno_node.type == "marker_annotation":
            return ""

        args = anno_node.child_by_field_name("arguments")
        if args is None:
            for c in anno_node.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return ""

        for c in args.children:
            if c.type == "element_value_pair":
                key, value_node = _split_pair(c)
                if key == "prefix" or key == "value":
                    return _string_literal_value(value_node) if value_node else ""
            elif c.type == "string_literal":
                # 단일 값 형 — @ConfigurationProperties("slab.equipment")
                return _string_literal_value(c)
        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _annotation_name(node: Node) -> str:
    for c in node.children:
        if c.type == "identifier":
            return c.text.decode()
    return ""


def _collect_modifiers(field_decl: Node) -> list[str]:
    out: list[str] = []
    for c in field_decl.children:
        if c.type == "modifiers":
            for m in c.children:
                if m.type in ("(", ")", ","):
                    continue
                # annotation 들은 modifier 가 아님
                if m.type in ("marker_annotation", "annotation"):
                    continue
                out.append(m.text.decode())
            break
    return out


def _split_pair(pair_node: Node) -> tuple[str | None, Node | None]:
    key: str | None = None
    value: Node | None = None
    for c in pair_node.children:
        if c.type == "=":
            continue
        if key is None and c.type == "identifier":
            key = c.text.decode()
        elif key is not None:
            value = c
            break
    return key, value


def _string_literal_value(node: Node | None) -> str:
    if node is None:
        return ""
    text = node.text.decode()
    if node.type == "string_literal" and len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _to_kebab_key(prefix: str, field_name: str) -> str:
    kebab = _CAMEL_TO_KEBAB_RE.sub(r"\1-\2", field_name).lower()
    return f"{prefix}.{kebab}" if prefix else kebab


__all__ = ("ConfigPropertiesAnalyzer",)
