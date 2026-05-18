"""Java source code parser using tree-sitter."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)
from backend.modeling.code_analysis.spring import SpringAnalyzer

JAVA_LANGUAGE = Language(tsjava.language())


class JavaParser:
    """Parses Java source files into CodeEntity / CodeRelation graphs.

    `spring_analyzers` : 선택적 Spring-specific analyzer 리스트 (DIAnalyzer 등).
    전달된 analyzer 각각의 `analyze` 결과가 ParseResult 에 병합된다.
    """

    def __init__(self, spring_analyzers: list[SpringAnalyzer] | None = None) -> None:
        self._parser = Parser(JAVA_LANGUAGE)
        self._spring_analyzers: list[SpringAnalyzer] = list(spring_analyzers or [])

    # -- CodeParser protocol ------------------------------------------------

    def supported_extensions(self) -> list[str]:
        return [".java"]

    def language_name(self) -> str:
        return "Java"

    def parse_file(self, file_path: Path, content: str) -> ParseResult:
        tree = self._parser.parse(content.encode())
        root = tree.root_node

        entities: list[CodeEntity] = []
        relations: list[CodeRelation] = []
        errors: list[str] = []
        fp = str(file_path)

        # Collect errors from tree-sitter
        for node in self._walk(root):
            if node.type == "ERROR":
                errors.append(
                    f"Syntax error at line {node.start_point[0] + 1}"
                )

        # 1. Package
        pkg_name: str | None = None
        for node in root.children:
            if node.type == "package_declaration":
                pkg_name = self._identifier_text(node)
                entities.append(
                    CodeEntity(
                        kind=EntityKinds.PACKAGE,
                        qualified_name=pkg_name,
                        name=pkg_name.split(".")[-1],
                        file_path=fp,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                    )
                )
                break

        # 2. Imports -> build a simple-name -> qualified-name map
        import_map: dict[str, str] = {}
        for node in root.children:
            if node.type == "import_declaration":
                fqn = self._identifier_text(node)
                simple = fqn.rsplit(".", 1)[-1]
                import_map[simple] = fqn

        # 3. Top-level type declarations
        for node in root.children:
            if node.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                self._extract_type(
                    node, pkg_name, fp, entities, relations, import_map
                )

        # 4. DEPENDS_ON from imports
        for fqn in import_map.values():
            source = self._first_type_qname(entities, pkg_name)
            if source:
                relations.append(
                    CodeRelation(
                        kind=RelationKinds.DEPENDS_ON,
                        source=source,
                        target=fqn,
                        file_path=fp,
                    )
                )

        # 5. Spring analyzers (optional, B5+)
        for analyzer in self._spring_analyzers:
            extra_entities, extra_relations = analyzer.analyze(
                tree=tree,
                content=content.encode(),
                file_path=fp,
                pkg_name=pkg_name,
            )
            entities.extend(extra_entities)
            relations.extend(extra_relations)

        # 6. Post-pass : enrich-capable analyzers (B5-6 ProfileAnalyzer)
        for analyzer in self._spring_analyzers:
            enrich = getattr(analyzer, "enrich", None)
            if callable(enrich):
                entities, relations = enrich(
                    entities, relations, tree, pkg_name,
                )

        return ParseResult(
            entities=entities,
            relations=relations,
            file_path=fp,
            language="Java",
            errors=errors,
        )

    # -- Internal helpers ---------------------------------------------------

    def _extract_type(
        self,
        node: Node,
        pkg_name: str | None,
        fp: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        import_map: dict[str, str],
        parent_qname: str | None = None,
    ) -> None:
        """Extract a class / interface / enum declaration and its members."""
        kind_map = {
            "class_declaration": EntityKinds.CLASS,
            "interface_declaration": EntityKinds.INTERFACE,
            "enum_declaration": EntityKinds.ENUM,
        }
        kind = kind_map[node.type]

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = name_node.text.decode()

        # Build qualified name
        if parent_qname:
            qname = f"{parent_qname}.{name}"
        elif pkg_name:
            qname = f"{pkg_name}.{name}"
        else:
            qname = name

        modifiers = self._extract_modifiers(node)
        annotations = self._extract_annotations(node)

        type_attrs: dict[str, object] = {}
        if annotations:
            type_attrs["annotations"] = annotations

        entities.append(
            CodeEntity(
                kind=kind,
                qualified_name=qname,
                name=name,
                file_path=fp,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                modifiers=modifiers,
                parent=parent_qname or pkg_name,
                attributes=type_attrs,
            )
        )

        # CONTAINS: package/parent -> this type
        container = parent_qname or pkg_name
        if container:
            relations.append(
                CodeRelation(
                    kind=RelationKinds.CONTAINS,
                    source=container,
                    target=qname,
                    file_path=fp,
                    line=node.start_point[0] + 1,
                )
            )

        # EXTENDS (class superclass)
        superclass = node.child_by_field_name("superclass")
        if superclass:
            for child in superclass.children:
                if child.type == "type_identifier":
                    target = self._resolve_type(child.text.decode(), import_map, pkg_name)
                    relations.append(
                        CodeRelation(
                            kind=RelationKinds.EXTENDS,
                            source=qname,
                            target=target,
                            file_path=fp,
                            line=child.start_point[0] + 1,
                        )
                    )

        # EXTENDS (interface extends_interfaces)
        for child in node.children:
            if child.type == "extends_interfaces":
                for desc in self._walk(child):
                    if desc.type == "type_identifier":
                        target = self._resolve_type(desc.text.decode(), import_map, pkg_name)
                        relations.append(
                            CodeRelation(
                                kind=RelationKinds.EXTENDS,
                                source=qname,
                                target=target,
                                file_path=fp,
                                line=desc.start_point[0] + 1,
                            )
                        )

        # IMPLEMENTS
        interfaces = node.child_by_field_name("interfaces")
        if interfaces:
            for desc in self._walk(interfaces):
                if desc.type == "type_identifier":
                    target = self._resolve_type(desc.text.decode(), import_map, pkg_name)
                    relations.append(
                        CodeRelation(
                            kind=RelationKinds.IMPLEMENTS,
                            source=qname,
                            target=target,
                            file_path=fp,
                            line=desc.start_point[0] + 1,
                        )
                    )

        # Walk the body for members
        body_node = node.child_by_field_name("body")
        if body_node is None:
            return

        # Pre-pass: build field name → declared type, so method bodies can
        # resolve `this.X` and bare-name field references at call extraction.
        from backend.modeling.code_analysis.method_symbol_table import (
            build_class_field_scope,
        )
        class_field_scope = build_class_field_scope(body_node)

        for child in body_node.children:
            if child.type == "method_declaration":
                self._extract_method(
                    child, qname, fp, entities, relations,
                    import_map, pkg_name, class_field_scope,
                )
            elif child.type == "constructor_declaration":
                self._extract_constructor(
                    child, qname, fp, entities, relations,
                    import_map, pkg_name, class_field_scope,
                )
            elif child.type == "field_declaration":
                self._extract_field(child, qname, fp, entities, relations)
            elif child.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                # Nested type
                self._extract_type(
                    child, pkg_name, fp, entities, relations, import_map, parent_qname=qname
                )

    def _extract_method(
        self,
        node: Node,
        class_qname: str,
        fp: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        import_map: dict[str, str],
        pkg_name: str | None,
        class_field_scope: dict[str, str] | None = None,
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = name_node.text.decode()
        qname = f"{class_qname}.{name}"
        modifiers = self._extract_modifiers(node)
        annotations = self._extract_annotations(node)
        method_attrs: dict[str, object] = {}
        if annotations:
            method_attrs["annotations"] = annotations

        # P23 (2026-04-27) — method source body 캡처 (PythonGenerator + simulation 입력)
        try:
            method_attrs["source"] = node.text.decode("utf-8", errors="replace")
        except Exception:
            pass

        # P14 (2026-04-26) — body anchor 추출 (param/local/branch/literal/return/field_access)
        from backend.modeling.code_analysis.method_anchor_extractor import (
            extract_anchors_from_method,
        )
        anchors = extract_anchors_from_method(node, qname)
        if anchors:
            method_attrs["anchors"] = [
                {
                    "method_fqn": a.method_fqn,
                    "kind": a.kind.value,
                    "locator": a.locator,
                    "line": a.line,
                    "snippet": a.snippet,
                    "extra": dict(a.extra),
                }
                for a in anchors
            ]

        # P15 (2026-04-26) — round1 §6-B-1 : method-internal value_flow
        from backend.modeling.code_analysis.value_flow_extractor import (
            extract_value_flow,
        )
        vf = extract_value_flow(node)
        if vf:
            method_attrs["value_flow"] = vf

        # M1a (2026-04-27) — param/field mutation 추적 (포인터처럼 전달된 객체 변경)
        from backend.modeling.code_analysis.method_mutation_extractor import (
            extract_mutations,
        )
        # param 이름 추출
        params_node = node.child_by_field_name("parameters")
        param_names: set[str] = set()
        if params_node is not None:
            for p in params_node.children:
                if p.type == "formal_parameter":
                    pname = p.child_by_field_name("name")
                    if pname is not None:
                        param_names.add(pname.text.decode("utf-8", errors="replace"))
        mutations = extract_mutations(node, param_names)
        if mutations:
            method_attrs["mutations"] = [
                {
                    "target": m.target,
                    "kind": m.kind.value,
                    "accessor": m.accessor,
                    "source_var": m.source_var,
                    "line": m.line,
                }
                for m in mutations
            ]
        # param 이름 + 타입 (signature builder 가 사용)
        if params_node is not None:
            param_specs: list[dict] = []
            for p in params_node.children:
                if p.type != "formal_parameter":
                    continue
                pname = p.child_by_field_name("name")
                ptype = p.child_by_field_name("type")
                param_specs.append({
                    "name": pname.text.decode() if pname else "",
                    "type": ptype.text.decode() if ptype else "",
                })
            if param_specs:
                method_attrs["parameters"] = param_specs
        # return type
        rtype = node.child_by_field_name("type")
        if rtype is not None:
            method_attrs["return_type"] = rtype.text.decode()

        # P16 (2026-04-27) — body-driven BusinessRule 추출 (7 종 visitor)
        from backend.modeling.code_analysis.body_rule_extractor import (
            extract_rules_from_method,
        )
        extracted = extract_rules_from_method(node, qname)
        if extracted:
            method_attrs["extracted_rules"] = [
                {
                    "method_fqn": r.method_fqn,
                    "kind": r.kind.value,
                    "statement": r.statement,
                    "line": r.line,
                    "snippet": r.snippet,
                    "anchor_locator": r.anchor_locator,
                    "auto_confirmed": r.auto_confirmed,
                    "extra": dict(r.extra),
                }
                for r in extracted
            ]

        entities.append(
            CodeEntity(
                kind=EntityKinds.METHOD,
                qualified_name=qname,
                name=name,
                file_path=fp,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                modifiers=modifiers,
                parent=class_qname,
                attributes=method_attrs,
            )
        )

        relations.append(
            CodeRelation(
                kind=RelationKinds.CONTAINS,
                source=class_qname,
                target=qname,
                file_path=fp,
                line=node.start_point[0] + 1,
            )
        )

        # Extract CALLS from method body
        body = node.child_by_field_name("body")
        if body:
            from backend.modeling.code_analysis.method_symbol_table import (
                build_method_scope,
            )
            method_scope = build_method_scope(node)
            self._extract_calls(
                body, qname, class_qname, fp, relations,
                import_map, pkg_name, method_scope, class_field_scope or {},
            )

    def _extract_constructor(
        self,
        node: Node,
        class_qname: str,
        fp: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        import_map: dict[str, str],
        pkg_name: str | None,
        class_field_scope: dict[str, str] | None = None,
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = name_node.text.decode()
        qname = f"{class_qname}.{name}"
        modifiers = self._extract_modifiers(node)

        entities.append(
            CodeEntity(
                kind=EntityKinds.CONSTRUCTOR,
                qualified_name=qname,
                name=name,
                file_path=fp,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                modifiers=modifiers,
                parent=class_qname,
            )
        )

        relations.append(
            CodeRelation(
                kind=RelationKinds.CONTAINS,
                source=class_qname,
                target=qname,
                file_path=fp,
                line=node.start_point[0] + 1,
            )
        )

        # Extract CALLS from constructor body
        body = node.child_by_field_name("body")
        if body:
            from backend.modeling.code_analysis.method_symbol_table import (
                build_method_scope,
            )
            method_scope = build_method_scope(node)
            self._extract_calls(
                body, qname, class_qname, fp, relations,
                import_map, pkg_name, method_scope, class_field_scope or {},
            )

    def _extract_field(
        self,
        node: Node,
        class_qname: str,
        fp: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        modifiers = self._extract_modifiers(node)
        annotations = self._extract_annotations(node)

        # field_type : declared type text (primitive / reference / generic)
        type_node = node.child_by_field_name("type")
        field_type: str | None = (
            type_node.text.decode() if type_node is not None else None
        )

        # Field name is in variable_declarator -> identifier
        for child in self._walk(node):
            if child.type == "variable_declarator":
                id_node = child.child_by_field_name("name")
                if id_node is None:
                    # fallback: first identifier child
                    for gc in child.children:
                        if gc.type == "identifier":
                            id_node = gc
                            break
                if id_node:
                    name = id_node.text.decode()
                    qname = f"{class_qname}.{name}"

                    attributes: dict[str, object] = {}
                    if field_type:
                        attributes["field_type"] = field_type
                    if annotations:
                        attributes["annotations"] = annotations

                    value_node = child.child_by_field_name("value")
                    if value_node is not None:
                        attributes["initializer"] = value_node.text.decode()
                        attributes["initializer_kind"] = (
                            self._classify_initializer(value_node)
                        )

                    entities.append(
                        CodeEntity(
                            kind=EntityKinds.FIELD,
                            qualified_name=qname,
                            name=name,
                            file_path=fp,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            modifiers=modifiers,
                            parent=class_qname,
                            attributes=attributes,
                        )
                    )
                    relations.append(
                        CodeRelation(
                            kind=RelationKinds.CONTAINS,
                            source=class_qname,
                            target=qname,
                            file_path=fp,
                            line=node.start_point[0] + 1,
                        )
                    )
                break  # one field_declaration = one variable (simplified)

    _NUMERIC_LITERAL_TYPES = frozenset(
        {
            "decimal_integer_literal",
            "hex_integer_literal",
            "octal_integer_literal",
            "binary_integer_literal",
            "decimal_floating_point_literal",
            "hex_floating_point_literal",
        }
    )

    def _classify_initializer(self, node: Node) -> str:
        """Classify a variable_declarator value node into a literal kind.

        Returns one of: literal_number, literal_string, literal_char,
        literal_boolean, literal_null, expression.
        """
        t = node.type
        if t in self._NUMERIC_LITERAL_TYPES:
            return "literal_number"
        if t == "string_literal":
            return "literal_string"
        if t == "character_literal":
            return "literal_char"
        if t in ("true", "false"):
            return "literal_boolean"
        if t == "null_literal":
            return "literal_null"
        if t == "unary_expression":
            # +N / -N wrapping a numeric literal
            operand = node.child_by_field_name("operand")
            if operand is None:
                # tree-sitter may not always set field name; fall back to scan
                for ch in node.children:
                    if ch.type in self._NUMERIC_LITERAL_TYPES:
                        return "literal_number"
            elif operand.type in self._NUMERIC_LITERAL_TYPES:
                return "literal_number"
        return "expression"

    def _extract_calls(
        self,
        body: Node,
        method_qname: str,
        class_qname: str,
        fp: str,
        relations: list[CodeRelation],
        import_map: dict[str, str],
        pkg_name: str | None,
        method_scope: dict[str, str] | None = None,
        class_field_scope: dict[str, str] | None = None,
    ) -> None:
        """Find method_invocation nodes inside a method/constructor body.

        Annotates each emitted `calls` relation with `attributes["receiver_type"]`
        (FQN or simple name of the receiver's static type) and
        `attributes["receiver_kind"]` (classification — see method_symbol_table
        for the kind enum). Downstream `callsite_analyzer` consumes these to
        dispatch between SINGLE_IMPL / ANNOTATION / EXTERNAL_LIBRARY routes
        instead of falling through to STATIC_UNRESOLVED.
        """
        from backend.modeling.code_analysis.method_symbol_table import (
            resolve_receiver,
        )
        method_scope = method_scope or {}
        class_field_scope = class_field_scope or {}

        for node in self._walk(body):
            if node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                obj_node = node.child_by_field_name("object")
                if name_node is None:
                    continue
                call_name = name_node.text.decode()

                # Target shape preserved for backward compat with call_resolver
                # (which splits target on `.` to extract varname for field lookup).
                if obj_node is None:
                    target = f"{class_qname}.{call_name}"
                else:
                    obj_text = obj_node.text.decode()
                    resolved = self._resolve_type(obj_text, import_map, pkg_name)
                    target = f"{resolved}.{call_name}"

                # Additive enrichment: receiver_type for the analyzer.
                receiver_text, receiver_kind = resolve_receiver(
                    obj_node, method_scope, class_field_scope, class_qname,
                )
                attributes: dict[str, object] = {"receiver_kind": receiver_kind}
                if receiver_text:
                    attributes["receiver_text"] = receiver_text
                    attributes["receiver_type"] = self._resolve_type(
                        self._strip_generics(receiver_text), import_map, pkg_name,
                    )

                relations.append(
                    CodeRelation(
                        kind=RelationKinds.CALLS,
                        source=method_qname,
                        target=target,
                        file_path=fp,
                        line=node.start_point[0] + 1,
                        attributes=attributes,
                    )
                )

    @staticmethod
    def _strip_generics(type_text: str) -> str:
        """Strip Java generic args — `List<Order>` → `List`, `Map<K,V>` → `Map`."""
        if not type_text:
            return type_text
        lt = type_text.find("<")
        if lt == -1:
            return type_text
        return type_text[:lt].strip()

    # -- Utility ------------------------------------------------------------

    def _extract_modifiers(self, node: Node) -> list[str]:
        """Extract modifier keywords (public, private, static, etc.)."""
        modifiers: list[str] = []
        for child in node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if mod.type not in ("(", ")", ","):
                        modifiers.append(mod.text.decode())
                break
        return modifiers

    # -- annotation capture -----------------------------------------------
    def _extract_annotations(self, node: Node) -> list[dict]:
        """Walk node's `modifiers` and return list of annotations.

        Each entry: ``{"name": "Column", "arguments": {"name": "X", "length": 4}}``.
        Marker form (`@Entity`) → arguments={}. Single-value form (`@Table("X")`)
        → arguments={"value": "X"}. Class literal (`@IdClass(K.class)`) →
        arguments={"value": "K.class"}.
        """
        out: list[dict] = []
        for child in node.children:
            if child.type != "modifiers":
                continue
            for m in child.children:
                if m.type == "marker_annotation":
                    name = self._annotation_name(m)
                    if name:
                        out.append({"name": name, "arguments": {}})
                elif m.type == "annotation":
                    name = self._annotation_name(m)
                    if not name:
                        continue
                    out.append(
                        {"name": name, "arguments": self._annotation_arguments(m)}
                    )
            break
        return out

    @staticmethod
    def _annotation_name(node: Node) -> str:
        """First identifier / scoped_identifier child = annotation simple name."""
        for c in node.children:
            if c.type == "identifier":
                return c.text.decode()
            if c.type == "scoped_identifier":
                # `jakarta.persistence.Column` → "Column"
                return c.text.decode().rsplit(".", 1)[-1]
        return ""

    def _annotation_arguments(self, anno_node: Node) -> dict:
        """Parse `(name="X", length=4)` or `("X")` or `(K.class)` into dict."""
        # find the argument list child
        args_node: Node | None = None
        for c in anno_node.children:
            if c.type == "annotation_argument_list":
                args_node = c
                break
        if args_node is None:
            return {}

        result: dict = {}
        for c in args_node.children:
            if c.type == "element_value_pair":
                key, value = self._parse_element_value_pair(c)
                if key is not None:
                    result[key] = value
            elif c.type in ("(", ")", ","):
                continue
            elif self._is_value_node(c):
                # 단일 값 (`@Table("X")`, `@IdClass(K.class)`) → "value" 키.
                result.setdefault("value", self._parse_annotation_value(c))
        return result

    def _parse_element_value_pair(self, pair: Node) -> tuple[str | None, object]:
        key: str | None = None
        value: object = None
        for c in pair.children:
            if c.type == "=":
                continue
            if key is None and c.type == "identifier":
                key = c.text.decode()
            elif key is not None and value is None and self._is_value_node(c):
                value = self._parse_annotation_value(c)
        return key, value

    @staticmethod
    def _is_value_node(node: Node) -> bool:
        return node.type in {
            "string_literal", "character_literal",
            "decimal_integer_literal", "hex_integer_literal",
            "octal_integer_literal", "binary_integer_literal",
            "decimal_floating_point_literal", "hex_floating_point_literal",
            "true", "false", "null_literal",
            "class_literal", "identifier", "scoped_identifier",
            "field_access", "array_initializer", "unary_expression",
        }

    @staticmethod
    def _parse_annotation_value(node: Node) -> object:
        """Convert annotation literal node to Python value."""
        text = node.text.decode()
        t = node.type
        if t == "string_literal" and len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            return text[1:-1]
        if t in ("decimal_integer_literal", "hex_integer_literal",
                 "octal_integer_literal", "binary_integer_literal"):
            try:
                return int(text.rstrip("Ll"), 0) if text.startswith(("0x", "0X", "0b", "0B")) else int(text.rstrip("Ll"))
            except ValueError:
                return text
        if t in ("decimal_floating_point_literal", "hex_floating_point_literal"):
            try:
                return float(text.rstrip("FfDd"))
            except ValueError:
                return text
        if t == "true":
            return True
        if t == "false":
            return False
        if t == "null_literal":
            return None
        # class_literal, identifier, scoped_identifier, field_access, etc. → raw text
        return text

    def _identifier_text(self, node: Node) -> str:
        """Extract the fully-qualified identifier from a declaration node.

        Works for package_declaration and import_declaration by finding
        the scoped_identifier or identifier child.
        """
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                return child.text.decode()
        return ""

    def _resolve_type(
        self,
        simple_name: str,
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> str:
        """Resolve a simple type name to a qualified name using imports."""
        if simple_name in import_map:
            return import_map[simple_name]
        # If it looks already qualified (contains dots), return as-is
        if "." in simple_name:
            return simple_name
        # Same package assumption
        if pkg_name:
            return f"{pkg_name}.{simple_name}"
        return simple_name

    def _first_type_qname(
        self,
        entities: list[CodeEntity],
        pkg_name: str | None,
    ) -> str | None:
        """Return the qualified name of the first class/interface/enum."""
        for e in entities:
            if e.kind in (EntityKinds.CLASS, EntityKinds.INTERFACE, EntityKinds.ENUM):
                return e.qualified_name
        return pkg_name

    @staticmethod
    def _walk(node: Node) -> Generator[Node, None, None]:
        """Depth-first traversal of all descendant nodes."""
        cursor = node.walk()
        visited = False

        while True:
            if not visited:
                yield cursor.node
                if cursor.goto_first_child():
                    continue
            if cursor.goto_next_sibling():
                visited = False
                continue
            if not cursor.goto_parent():
                break
            visited = True
