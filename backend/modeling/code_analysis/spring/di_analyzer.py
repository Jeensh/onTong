"""OD-11-B5-1 : Spring DI analyzer.

감지 대상:
  - 6 stereotype : @Component / @Service / @Repository / @Controller / @RestController / @Configuration
    → `spring_bean` 엔티티 (qualified_name = class FQN).
  - @Bean 메서드 (in @Configuration) → `spring_bean` 엔티티
    (qualified_name = `<class FQN>.<method>#bean`).
  - @Autowired / @Inject on:
      (a) 필드
      (b) 명시 @Autowired 생성자
      (c) 단일 생성자 (Spring 4.3+ implicit injection)
    → `AUTOWIRES` 엣지.
  - @Qualifier("name") → `attributes.qualifier`.
  - 클래스 레벨 @Profile(...) → 해당 빈에서 나가는 AUTOWIRES 엣지에 `attributes.profile=[...]`.
  - 클래스 레벨 @ConditionalOnProperty(...) → `attributes.condition`.
"""

from __future__ import annotations

from typing import Iterable

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    RelationKinds,
)


_STEREOTYPES: frozenset[str] = frozenset({
    "Component", "Service", "Repository", "Controller",
    "RestController", "Configuration",
})

_INJECT_ANNOTATIONS: frozenset[str] = frozenset({"Autowired", "Inject"})


class DIAnalyzer:
    """@Autowired / @Inject / 생성자 주입 → spring_bean + AUTOWIRES."""

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

        entities: list[CodeEntity] = []
        relations: list[CodeRelation] = []

        for child in root.children:
            if child.type == "class_declaration":
                self._analyze_class(
                    child, pkg_name, file_path, import_map, entities, relations
                )

        return entities, relations

    # -- class-level --------------------------------------------------------

    def _analyze_class(
        self,
        node: Node,
        pkg_name: str | None,
        file_path: str,
        import_map: dict[str, str],
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        class_qname = f"{pkg_name}.{class_name}" if pkg_name else class_name

        annotations = self._collect_annotations(node)
        stereotype = self._first_matching_stereotype(annotations)
        is_configuration = stereotype == "Configuration"

        edge_attrs: dict[str, object] = {}
        profile = self._extract_profile(annotations)
        if profile:
            edge_attrs["profile"] = profile
        condition = self._extract_condition(annotations)
        if condition is not None:
            edge_attrs["condition"] = condition

        if stereotype is not None:
            bean_name = self._extract_stereotype_bean_name(annotations, stereotype, class_name)
            entities.append(CodeEntity(
                kind=EntityKinds.SPRING_BEAN,
                qualified_name=class_qname,
                name=class_name,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent=pkg_name,
                attributes={"stereotype": stereotype, "bean_name": bean_name},
            ))

        body = node.child_by_field_name("body")
        if body is None:
            return

        # If not a stereotype, we don't emit field/ctor injections
        # (a plain class is not a bean target).
        if stereotype is None:
            return

        constructors: list[Node] = [
            c for c in body.children if c.type == "constructor_declaration"
        ]

        for child in body.children:
            if child.type == "field_declaration":
                self._analyze_field_injection(
                    child, class_qname, file_path, import_map, pkg_name,
                    edge_attrs, relations,
                )
            elif child.type == "constructor_declaration":
                self._analyze_constructor_injection(
                    child, class_qname, file_path, import_map, pkg_name,
                    edge_attrs, relations, total_ctors=len(constructors),
                )
            elif child.type == "method_declaration" and is_configuration:
                self._analyze_bean_method(
                    child, class_qname, file_path, pkg_name, entities,
                )

    # -- field injection ---------------------------------------------------

    def _analyze_field_injection(
        self,
        node: Node,
        bean_qname: str,
        file_path: str,
        import_map: dict[str, str],
        pkg_name: str | None,
        base_edge_attrs: dict[str, object],
        relations: list[CodeRelation],
    ) -> None:
        annotations = self._collect_annotations(node)
        if not any(a["name"] in _INJECT_ANNOTATIONS for a in annotations):
            return

        type_node = node.child_by_field_name("type")
        if type_node is None:
            return
        target = self._resolve_type(type_node.text.decode(), import_map, pkg_name)

        # P29-3 — field_name 추출 (qualifier resolution 시 필요)
        declarator = None
        for child in node.children:
            if child.type == "variable_declarator":
                declarator = child
                break
        field_name = ""
        if declarator is not None:
            name_node = declarator.child_by_field_name("name")
            if name_node is not None:
                field_name = name_node.text.decode()

        attrs: dict[str, object] = dict(base_edge_attrs)
        if field_name:
            attrs["field_name"] = field_name
        attrs["injection_kind"] = "field"
        qualifier = self._extract_qualifier(annotations)
        if qualifier is not None:
            attrs["qualifier"] = qualifier

        relations.append(CodeRelation(
            kind=RelationKinds.AUTOWIRES,
            source=bean_qname,
            target=target,
            file_path=file_path,
            line=node.start_point[0] + 1,
            attributes=attrs,
        ))

    # -- constructor injection ---------------------------------------------

    def _analyze_constructor_injection(
        self,
        node: Node,
        bean_qname: str,
        file_path: str,
        import_map: dict[str, str],
        pkg_name: str | None,
        base_edge_attrs: dict[str, object],
        relations: list[CodeRelation],
        total_ctors: int,
    ) -> None:
        annotations = self._collect_annotations(node)
        explicit = any(a["name"] in _INJECT_ANNOTATIONS for a in annotations)
        implicit = (not explicit) and total_ctors == 1

        if not (explicit or implicit):
            return

        params = node.child_by_field_name("parameters")
        if params is None:
            return

        for p in params.children:
            if p.type != "formal_parameter":
                continue
            type_node = p.child_by_field_name("type")
            if type_node is None:
                continue
            target = self._resolve_type(type_node.text.decode(), import_map, pkg_name)

            # P29-3 — param name 도 field_name 으로 (constructor 주입 → 보통 같은 이름의 field)
            param_name_node = p.child_by_field_name("name")
            param_name = param_name_node.text.decode() if param_name_node is not None else ""

            attrs: dict[str, object] = dict(base_edge_attrs)
            if param_name:
                attrs["field_name"] = param_name
            attrs["injection_kind"] = "constructor"
            p_annotations = self._collect_annotations(p)
            qualifier = self._extract_qualifier(p_annotations)
            if qualifier is not None:
                attrs["qualifier"] = qualifier

            relations.append(CodeRelation(
                kind=RelationKinds.AUTOWIRES,
                source=bean_qname,
                target=target,
                file_path=file_path,
                line=p.start_point[0] + 1,
                attributes=attrs,
            ))

    # -- @Bean method ------------------------------------------------------

    def _analyze_bean_method(
        self,
        node: Node,
        class_qname: str,
        file_path: str,
        pkg_name: str | None,
        entities: list[CodeEntity],
    ) -> None:
        annotations = self._collect_annotations(node)
        if not any(a["name"] == "Bean" for a in annotations):
            return
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        method_name = name_node.text.decode()
        bean_qname = f"{class_qname}.{method_name}#bean"
        bean_name = self._extract_bean_method_name(annotations, method_name)
        entities.append(CodeEntity(
            kind=EntityKinds.SPRING_BEAN,
            qualified_name=bean_qname,
            name=method_name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            parent=class_qname,
            attributes={"stereotype": "Bean", "bean_name": bean_name},
        ))

    # -- annotation helpers -------------------------------------------------

    def _collect_annotations(self, node: Node) -> list[dict[str, Node]]:
        """Return list of {'name': str, 'node': Node} for each annotation on node.

        Searches the node's `modifiers` child for annotation / marker_annotation entries.
        """
        out: list[dict[str, object]] = []
        for child in node.children:
            if child.type != "modifiers":
                continue
            for m in child.children:
                if m.type in ("marker_annotation", "annotation"):
                    name = self._annotation_name(m)
                    if name:
                        out.append({"name": name, "node": m})
        # For formal_parameter, the annotations can be direct children (no modifiers wrapper)
        for child in node.children:
            if child.type in ("marker_annotation", "annotation"):
                name = self._annotation_name(child)
                if name:
                    out.append({"name": name, "node": child})
        return out  # type: ignore[return-value]

    @staticmethod
    def _annotation_name(node: Node) -> str:
        """Extract the annotation's identifier (e.g. `@Foo` → 'Foo')."""
        for c in node.children:
            if c.type == "identifier":
                return c.text.decode()
        return ""

    def _first_matching_stereotype(
        self, annotations: Iterable[dict[str, object]],
    ) -> str | None:
        for a in annotations:
            if a["name"] in _STEREOTYPES:
                return a["name"]  # type: ignore[return-value]
        return None

    def _extract_stereotype_bean_name(
        self,
        annotations: Iterable[dict[str, object]],
        stereotype: str,
        class_name: str,
    ) -> str:
        """`@Component("name")` / `@Service(value="name")` → explicit name,
        else camelCase of class simple name (`OrderService` → `orderService`)."""
        for a in annotations:
            if a["name"] != stereotype:
                continue
            single = self._single_string_arg(a["node"])  # type: ignore[arg-type]
            if single:
                return single
            pairs = self._kv_string_args(a["node"])  # type: ignore[arg-type]
            name = pairs.get("value") or pairs.get("name")
            if name:
                return name
        return _camel_case(class_name)

    def _extract_bean_method_name(
        self,
        annotations: Iterable[dict[str, object]],
        method_name: str,
    ) -> str:
        """`@Bean(name="x")` / `@Bean("x")` → explicit name, else method name."""
        for a in annotations:
            if a["name"] != "Bean":
                continue
            single = self._single_string_arg(a["node"])  # type: ignore[arg-type]
            if single:
                return single
            pairs = self._kv_string_args(a["node"])  # type: ignore[arg-type]
            name = pairs.get("name") or pairs.get("value")
            if name:
                return name
        return method_name

    def _extract_qualifier(
        self, annotations: Iterable[dict[str, object]],
    ) -> str | None:
        for a in annotations:
            if a["name"] == "Qualifier":
                return self._single_string_arg(a["node"])  # type: ignore[arg-type]
        return None

    def _extract_profile(
        self, annotations: Iterable[dict[str, object]],
    ) -> list[str]:
        for a in annotations:
            if a["name"] == "Profile":
                return self._string_or_array_arg(a["node"])  # type: ignore[arg-type]
        return []

    def _extract_condition(
        self, annotations: Iterable[dict[str, object]],
    ) -> str | None:
        for a in annotations:
            if a["name"] != "ConditionalOnProperty":
                continue
            node = a["node"]
            single = self._single_string_arg(node)  # type: ignore[arg-type]
            if single is not None:
                return single
            pairs = self._kv_string_args(node)  # type: ignore[arg-type]
            name = pairs.get("name") or pairs.get("value")
            having = pairs.get("havingValue")
            if name and having is not None:
                return f"{name}={having}"
            if name:
                return name
        return None

    @staticmethod
    def _single_string_arg(annotation_node: Node) -> str | None:
        args = annotation_node.child_by_field_name("arguments")
        if args is None:
            for c in annotation_node.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return None
        # Only accept if a single string_literal child (no kv, no array)
        strings: list[str] = []
        for c in args.children:
            if c.type == "string_literal":
                strings.append(_string_literal_text(c))
            elif c.type in ("element_value_pair", "element_value_array_initializer"):
                return None
        if len(strings) == 1:
            return strings[0]
        return None

    @staticmethod
    def _string_or_array_arg(annotation_node: Node) -> list[str]:
        args = annotation_node.child_by_field_name("arguments")
        if args is None:
            for c in annotation_node.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return []
        for c in args.children:
            if c.type == "string_literal":
                return [_string_literal_text(c)]
            if c.type == "element_value_array_initializer":
                return [
                    _string_literal_text(x)
                    for x in c.children
                    if x.type == "string_literal"
                ]
        return []

    @staticmethod
    def _kv_string_args(annotation_node: Node) -> dict[str, str]:
        out: dict[str, str] = {}
        args = annotation_node.child_by_field_name("arguments")
        if args is None:
            for c in annotation_node.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return out
        for pair in args.children:
            if pair.type != "element_value_pair":
                continue
            key = None
            value = None
            for pc in pair.children:
                if pc.type == "identifier":
                    key = pc.text.decode()
                elif pc.type == "string_literal":
                    value = _string_literal_text(pc)
            if key is not None and value is not None:
                out[key] = value
        return out

    # -- import / type resolution ------------------------------------------

    @staticmethod
    def _build_import_map(root: Node) -> dict[str, str]:
        import_map: dict[str, str] = {}
        for node in root.children:
            if node.type != "import_declaration":
                continue
            for c in node.children:
                if c.type in ("scoped_identifier", "identifier"):
                    fqn = c.text.decode()
                    simple = fqn.rsplit(".", 1)[-1]
                    import_map[simple] = fqn
                    break
        return import_map

    @staticmethod
    def _resolve_type(
        simple_name: str, import_map: dict[str, str], pkg_name: str | None,
    ) -> str:
        if simple_name in import_map:
            return import_map[simple_name]
        if "." in simple_name:
            return simple_name
        if pkg_name:
            return f"{pkg_name}.{simple_name}"
        return simple_name


def _string_literal_text(node: Node) -> str:
    """Extract the raw text of a tree-sitter Java `string_literal` (strips quotes)."""
    for c in node.children:
        if c.type == "string_fragment":
            return c.text.decode()
    text = node.text.decode()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _camel_case(class_name: str) -> str:
    """Spring bean camelCase fallback (`OrderService` → `orderService`).

    Special rule: if the first two chars are both uppercase (e.g. `URLHandler`),
    Spring keeps the original (rare; defer to runtime for such cases).
    """
    if not class_name:
        return class_name
    if len(class_name) >= 2 and class_name[0].isupper() and class_name[1].isupper():
        return class_name
    return class_name[0].lower() + class_name[1:]


__all__ = ("DIAnalyzer",)
