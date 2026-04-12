"""Java source code parser using tree-sitter."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKind,
    ParseResult,
    RelationKind,
)

JAVA_LANGUAGE = Language(tsjava.language())


class JavaParser:
    """Parses Java source files into CodeEntity / CodeRelation graphs."""

    def __init__(self) -> None:
        self._parser = Parser(JAVA_LANGUAGE)

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
                        kind=EntityKind.PACKAGE,
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
                        kind=RelationKind.DEPENDS_ON,
                        source=source,
                        target=fqn,
                        file_path=fp,
                    )
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
            "class_declaration": EntityKind.CLASS,
            "interface_declaration": EntityKind.INTERFACE,
            "enum_declaration": EntityKind.ENUM,
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
            )
        )

        # CONTAINS: package/parent -> this type
        container = parent_qname or pkg_name
        if container:
            relations.append(
                CodeRelation(
                    kind=RelationKind.CONTAINS,
                    source=container,
                    target=qname,
                    file_path=fp,
                    line=node.start_point[0] + 1,
                )
            )

        # EXTENDS
        superclass = node.child_by_field_name("superclass")
        if superclass:
            for child in superclass.children:
                if child.type == "type_identifier":
                    target = self._resolve_type(child.text.decode(), import_map, pkg_name)
                    relations.append(
                        CodeRelation(
                            kind=RelationKind.EXTENDS,
                            source=qname,
                            target=target,
                            file_path=fp,
                            line=child.start_point[0] + 1,
                        )
                    )

        # IMPLEMENTS
        interfaces = node.child_by_field_name("interfaces")
        if interfaces:
            for child in interfaces.children:
                if child.type == "type_identifier":
                    target = self._resolve_type(child.text.decode(), import_map, pkg_name)
                    relations.append(
                        CodeRelation(
                            kind=RelationKind.IMPLEMENTS,
                            source=qname,
                            target=target,
                            file_path=fp,
                            line=child.start_point[0] + 1,
                        )
                    )

        # Walk the body for members
        body_node = node.child_by_field_name("body")
        if body_node is None:
            return

        for child in body_node.children:
            if child.type == "method_declaration":
                self._extract_method(
                    child, qname, fp, entities, relations, import_map, pkg_name
                )
            elif child.type == "constructor_declaration":
                self._extract_constructor(
                    child, qname, fp, entities, relations, import_map, pkg_name
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
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = name_node.text.decode()
        qname = f"{class_qname}.{name}"
        modifiers = self._extract_modifiers(node)

        entities.append(
            CodeEntity(
                kind=EntityKind.METHOD,
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
                kind=RelationKind.CONTAINS,
                source=class_qname,
                target=qname,
                file_path=fp,
                line=node.start_point[0] + 1,
            )
        )

        # Extract CALLS from method body
        body = node.child_by_field_name("body")
        if body:
            self._extract_calls(body, qname, class_qname, fp, relations, import_map, pkg_name)

    def _extract_constructor(
        self,
        node: Node,
        class_qname: str,
        fp: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = name_node.text.decode()
        qname = f"{class_qname}.{name}"
        modifiers = self._extract_modifiers(node)

        entities.append(
            CodeEntity(
                kind=EntityKind.CONSTRUCTOR,
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
                kind=RelationKind.CONTAINS,
                source=class_qname,
                target=qname,
                file_path=fp,
                line=node.start_point[0] + 1,
            )
        )

        # Extract CALLS from constructor body
        body = node.child_by_field_name("body")
        if body:
            self._extract_calls(body, qname, class_qname, fp, relations, import_map, pkg_name)

    def _extract_field(
        self,
        node: Node,
        class_qname: str,
        fp: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        modifiers = self._extract_modifiers(node)

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
                    entities.append(
                        CodeEntity(
                            kind=EntityKind.FIELD,
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
                            kind=RelationKind.CONTAINS,
                            source=class_qname,
                            target=qname,
                            file_path=fp,
                            line=node.start_point[0] + 1,
                        )
                    )
                break  # one field_declaration = one variable (simplified)

    def _extract_calls(
        self,
        body: Node,
        method_qname: str,
        class_qname: str,
        fp: str,
        relations: list[CodeRelation],
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> None:
        """Find method_invocation nodes inside a method/constructor body."""
        for node in self._walk(body):
            if node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                obj_node = node.child_by_field_name("object")
                if name_node is None:
                    continue
                call_name = name_node.text.decode()

                if obj_node is None:
                    # Unqualified call -> assume same class
                    target = f"{class_qname}.{call_name}"
                else:
                    obj_text = obj_node.text.decode()
                    # Try to resolve object to a fully qualified type
                    resolved = self._resolve_type(obj_text, import_map, pkg_name)
                    target = f"{resolved}.{call_name}"

                relations.append(
                    CodeRelation(
                        kind=RelationKind.CALLS,
                        source=method_qname,
                        target=target,
                        file_path=fp,
                        line=node.start_point[0] + 1,
                    )
                )

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
            if e.kind in (EntityKind.CLASS, EntityKind.INTERFACE, EntityKind.ENUM):
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
