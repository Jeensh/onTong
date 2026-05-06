"""OD-11-B6-1 : Spring MapStructAnalyzer.

`@Mapper` 가 붙은 interface / abstract class 에서 `@Mapping(source, target)` /
`@Mapping(expression)` 를 해석하여 데이터 계보 엣지 (`PROPAGATES_TO` /
`DERIVES_FROM`) 를 emit 한다.

설계 개요:
  - `analyze()` 가 직접 `(entities, relations)` 를 반환 (standalone 패턴).
  - `enrich()` 는 명시 @Mapping 이 없는 매퍼 메서드의 METHOD 엔티티에
    `mapstruct_implicit_fields` marker 만 주입 — 실제 implicit 엣지는 B6-4 에서 확정.
  - `default` / `@Named` 메서드는 MapStruct 의 helper 이므로 skip.
  - @Mapping.ignore = true 는 엣지 미생성.
  - @Mapping.qualifiedByName = "..." 는 `via_methods` 리스트 끝에 qualifier 이름을 append.
  - 파라미터 prefix 감지: `@Mapping.source = "paramName.field.path"` 처럼
    첫 토큰이 파라미터 이름이면 타입 FQN 으로 replace.
  - import 맵에서 해소 실패한 타입은 simple name 그대로 남긴다 (B6-4 에서 재해소).
"""

from __future__ import annotations

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    RelationKinds,
)

_EXPRESSION_SENTINEL = "<expression>"


class MapStructAnalyzer:
    """`@Mapper` + `@Mapping` → PROPAGATES_TO / DERIVES_FROM lineage edges."""

    # -- main entry ---------------------------------------------------------

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
        import_map = self._build_import_map(root)

        relations: list[CodeRelation] = []
        for child in root.children:
            if child.type in ("class_declaration", "interface_declaration"):
                self._scan_type(
                    child,
                    pkg_name=pkg_name,
                    import_map=import_map,
                    file_path=file_path,
                    parent_qname=None,
                    relations=relations,
                    marker_map=None,
                )
        return [], relations

    # -- post-processor : attach implicit markers to METHOD entities --------

    def enrich(
        self,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        tree: object | None,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        if tree is None:
            return entities, relations
        root: Node = tree.root_node  # type: ignore[attr-defined]
        import_map = self._build_import_map(root)

        marker_map: dict[str, dict[str, object]] = {}
        for child in root.children:
            if child.type in ("class_declaration", "interface_declaration"):
                self._scan_type(
                    child,
                    pkg_name=pkg_name,
                    import_map=import_map,
                    file_path=None,
                    parent_qname=None,
                    relations=None,
                    marker_map=marker_map,
                )

        if not marker_map:
            return entities, relations

        for ent in entities:
            if ent.kind != EntityKinds.METHOD:
                continue
            marker = marker_map.get(ent.qualified_name)
            if marker is None:
                continue
            existing = ent.attributes.get("mapstruct_implicit_fields")
            if isinstance(existing, list):
                existing.append(marker)
            else:
                ent.attributes["mapstruct_implicit_fields"] = [marker]

        return entities, relations

    # -- type walker --------------------------------------------------------

    def _scan_type(
        self,
        type_node: Node,
        pkg_name: str | None,
        import_map: dict[str, str],
        file_path: str | None,
        parent_qname: str | None,
        relations: list[CodeRelation] | None,
        marker_map: dict[str, dict[str, object]] | None,
    ) -> None:
        name_node = type_node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        if parent_qname:
            class_fqn = f"{parent_qname}.{class_name}"
        elif pkg_name:
            class_fqn = f"{pkg_name}.{class_name}"
        else:
            class_fqn = class_name

        body = type_node.child_by_field_name("body")
        if body is None:
            return

        # recurse into nested types first (may contain @Mapper even if parent isn't)
        for member in body.children:
            if member.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                self._scan_type(
                    member,
                    pkg_name=pkg_name,
                    import_map=import_map,
                    file_path=file_path,
                    parent_qname=class_fqn,
                    relations=relations,
                    marker_map=marker_map,
                )

        if not self._has_mapper_annotation(type_node):
            return

        for member in body.children:
            if member.type != "method_declaration":
                continue
            if self._has_default_modifier(member):
                continue
            if self._has_annotation_named(member, "Named"):
                continue

            method_name_node = member.child_by_field_name("name")
            if method_name_node is None:
                continue
            method_name = method_name_node.text.decode()
            method_fqn = f"{class_fqn}.{method_name}"

            params = self._get_parameters(member, import_map, pkg_name)
            return_fqn = self._get_return_type_fqn(member, import_map, pkg_name)

            if return_fqn is None:
                continue  # void / unparseable return — not a mapping method

            mappings = self._collect_mapping_annotations(member)

            if mappings:
                if relations is not None:
                    for m_node in mappings:
                        self._emit_mapping(
                            m_node,
                            params=params,
                            return_fqn=return_fqn,
                            class_fqn=class_fqn,
                            method_fqn=method_fqn,
                            file_path=file_path,
                            relations=relations,
                        )
            else:
                if marker_map is not None and params:
                    src_type = params[0][1]
                    marker_map[method_fqn] = {
                        "mapper_fqn": class_fqn,
                        "method": method_name,
                        "src_type": src_type,
                        "dst_type": return_fqn,
                        "line": member.start_point[0] + 1,
                    }

    # -- @Mapping emission --------------------------------------------------

    def _emit_mapping(
        self,
        mapping_node: Node,
        params: list[tuple[str, str | None]],
        return_fqn: str,
        class_fqn: str,
        method_fqn: str,
        file_path: str | None,
        relations: list[CodeRelation],
    ) -> None:
        kv = self._mapping_kv(mapping_node)
        if kv.get("ignore") == "true":
            return

        target_path = kv.get("target")
        if not target_path:
            return
        target = f"{return_fqn}.{target_path}"

        line = mapping_node.start_point[0] + 1

        if "expression" in kv:
            expression = kv["expression"]
            rel = CodeRelation(
                kind=RelationKinds.DERIVES_FROM,
                source=_EXPRESSION_SENTINEL,
                target=target,
                file_path=file_path,
                line=line,
                attributes={
                    "expression": expression,
                    "confidence": 1.0,
                    "via_methods": [method_fqn],
                    "mapper_fqn": class_fqn,
                },
            )
            relations.append(rel)
            return

        source_path = kv.get("source")
        if not source_path:
            return

        src_fqn = self._resolve_source_fqn(source_path, params)
        via: list[str] = [method_fqn]
        qname = kv.get("qualifiedByName")
        if qname:
            via.append(qname)

        attrs: dict[str, object] = {
            "confidence": 1.0,
            "via_methods": via,
            "mapper_fqn": class_fqn,
        }
        if "qualifiedByName" in kv:
            attrs["qualified_by_name"] = kv["qualifiedByName"]

        rel = CodeRelation(
            kind=RelationKinds.PROPAGATES_TO,
            source=src_fqn,
            target=target,
            file_path=file_path,
            line=line,
            attributes=attrs,
        )
        relations.append(rel)

    @staticmethod
    def _resolve_source_fqn(
        source_path: str, params: list[tuple[str, str | None]],
    ) -> str:
        """`paramName.a.b` → `<ParamType>.a.b`, otherwise fall back to first param type."""
        if not params:
            return source_path

        first_token, _, rest = source_path.partition(".")
        for p_name, p_type in params:
            if p_name == first_token and p_type:
                if rest:
                    return f"{p_type}.{rest}"
                return p_type

        # no prefix match → treat full path as field path on first parameter
        first_type = params[0][1]
        if first_type:
            return f"{first_type}.{source_path}"
        return source_path

    # -- annotation extractors ---------------------------------------------

    @staticmethod
    def _has_mapper_annotation(type_node: Node) -> bool:
        for a in _iter_annotations(type_node):
            if _annotation_name(a) == "Mapper":
                return True
        return False

    @staticmethod
    def _has_default_modifier(method_node: Node) -> bool:
        for c in method_node.children:
            if c.type == "modifiers":
                for m in c.children:
                    if m.type == "default":
                        return True
                    if m.type == "identifier" and m.text.decode() == "default":
                        return True
        return False

    @staticmethod
    def _has_annotation_named(node: Node, name: str) -> bool:
        for a in _iter_annotations(node):
            if _annotation_name(a) == name:
                return True
        return False

    def _collect_mapping_annotations(self, method_node: Node) -> list[Node]:
        """Return list of @Mapping nodes, flattening @Mappings container."""
        result: list[Node] = []
        for a in _iter_annotations(method_node):
            name = _annotation_name(a)
            if name == "Mapping":
                result.append(a)
            elif name == "Mappings":
                # @Mappings({@Mapping(...), @Mapping(...)})
                for inner in _iter_inner_mappings(a):
                    result.append(inner)
        return result

    def _mapping_kv(self, mapping_node: Node) -> dict[str, str]:
        """Parse @Mapping(...) arguments into dict of key → value (string-stripped)."""
        out: dict[str, str] = {}
        args = mapping_node.child_by_field_name("arguments")
        if args is None:
            return out
        for c in args.children:
            if c.type != "element_value_pair":
                continue
            key: str | None = None
            value: str | None = None
            for pc in c.children:
                if pc.type == "=":
                    continue
                if key is None and pc.type == "identifier":
                    key = pc.text.decode()
                elif key is not None and value is None:
                    if pc.type == "string_literal":
                        value = _strip_quotes(pc.text.decode())
                    elif pc.type == "true":
                        value = "true"
                    elif pc.type == "false":
                        value = "false"
                    else:
                        value = pc.text.decode()
            if key is not None and value is not None:
                out[key] = value
        return out

    # -- parameter / return type resolution --------------------------------

    def _get_parameters(
        self,
        method_node: Node,
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> list[tuple[str, str | None]]:
        params_node = method_node.child_by_field_name("parameters")
        if params_node is None:
            return []
        out: list[tuple[str, str | None]] = []
        for c in params_node.children:
            if c.type != "formal_parameter":
                continue
            p_type_node = c.child_by_field_name("type")
            p_name_node = c.child_by_field_name("name")
            if p_type_node is None or p_name_node is None:
                continue
            p_type_simple = p_type_node.text.decode()
            p_name = p_name_node.text.decode()
            resolved = self._resolve_type_fqn(p_type_simple, import_map, pkg_name)
            out.append((p_name, resolved))
        return out

    def _get_return_type_fqn(
        self,
        method_node: Node,
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> str | None:
        type_node = method_node.child_by_field_name("type")
        if type_node is None:
            return None
        text = type_node.text.decode()
        if text == "void":
            return None
        return self._resolve_type_fqn(text, import_map, pkg_name)

    @staticmethod
    def _resolve_type_fqn(
        simple: str,
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> str | None:
        if not simple:
            return None
        # strip generics, array suffix
        root = simple.split("<", 1)[0].rstrip("[]").strip()
        if not root:
            return None
        if root in import_map:
            return import_map[root]
        # no import — return simple name as-is (B6-4 will try repo-level resolution)
        return root

    # -- import map --------------------------------------------------------

    @staticmethod
    def _build_import_map(root: Node) -> dict[str, str]:
        """Map simple class name → fully qualified name via `import_declaration`."""
        out: dict[str, str] = {}
        for child in root.children:
            if child.type != "import_declaration":
                continue
            # import (static)? scoped_identifier (. * | asterisk)? ;
            is_wildcard = any(
                c.type == "asterisk" or (c.type == "*")
                for c in child.children
            )
            if is_wildcard:
                continue
            for c in child.children:
                if c.type == "scoped_identifier":
                    fqn = c.text.decode()
                    simple = fqn.rsplit(".", 1)[-1]
                    out[simple] = fqn
                    break
                if c.type == "identifier":
                    fqn = c.text.decode()
                    out[fqn] = fqn
                    break
        return out


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _iter_annotations(node: Node):
    """Yield `marker_annotation` / `annotation` children (also inside `modifiers`)."""
    for child in node.children:
        if child.type == "modifiers":
            for m in child.children:
                if m.type in ("marker_annotation", "annotation"):
                    yield m
        if child.type in ("marker_annotation", "annotation"):
            yield child


def _annotation_name(annotation_node: Node) -> str:
    for c in annotation_node.children:
        if c.type == "identifier":
            return c.text.decode()
        if c.type == "scoped_identifier":
            return c.text.decode().rsplit(".", 1)[-1]
    return ""


def _iter_inner_mappings(mappings_node: Node):
    """Yield each @Mapping(...) node inside `@Mappings({...})`."""
    args = mappings_node.child_by_field_name("arguments")
    if args is None:
        return
    for c in args.children:
        if c.type == "element_value_array_initializer":
            for inner in c.children:
                if inner.type in ("marker_annotation", "annotation"):
                    if _annotation_name(inner) == "Mapping":
                        yield inner
        elif c.type in ("marker_annotation", "annotation"):
            if _annotation_name(c) == "Mapping":
                yield c


def _strip_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


__all__ = ("MapStructAnalyzer",)
