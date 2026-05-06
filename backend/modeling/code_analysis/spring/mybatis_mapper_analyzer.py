"""P29-2 (2026-04-27) — MyBatisMapperAnalyzer.

@Mapper interface 의 메서드들을 mapper_method entity 로 emit. XML mapper 와는 별도로
어노테이션 기반 SQL (`@Select`, `@Insert`, `@Update`, `@Delete`) 도 처리.

emit :
  - `<method_fqn>` (이미 method entity 가 있음) — 추가로 attributes 에 mapper=True 표기
  - 어노테이션 SQL 이 있으면 sqlglot 으로 table edge (NativeSqlAnalyzer 와 유사)
"""
from __future__ import annotations

import re
from typing import Iterable

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    RelationKinds,
)

_MAPPER = "Mapper"
_SQL_ANNOTATIONS = {
    "Select": ("read", "READS_TABLE"),
    "Insert": ("write", "WRITES_TABLE"),
    "Update": ("write", "WRITES_TABLE"),
    "Delete": ("write", "WRITES_TABLE"),
    "SelectKey": ("read", "READS_TABLE"),
}

# 매우 단순 SQL → table 추출 (sqlglot 없이도 동작하는 fallback)
_TABLE_RX = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z_][A-Za-z0-9_\.]*)",
    re.IGNORECASE,
)


class MyBatisMapperAnalyzer:
    """@Mapper interface + 어노테이션 SQL → table edges."""

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
            if child.type == "interface_declaration":
                self._analyze_interface(child, pkg_name, file_path, entities, relations)
            elif child.type == "class_declaration":
                self._analyze_class(child, pkg_name, file_path, entities, relations)
        return entities, relations

    def _analyze_interface(
        self,
        node: Node,
        pkg_name: str | None,
        file_path: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        if not self._has_annotation(node, _MAPPER):
            # not a mapper interface
            return

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        interface_name = name_node.text.decode()
        interface_qname = f"{pkg_name}.{interface_name}" if pkg_name else interface_name

        body = node.child_by_field_name("body")
        if body is None:
            return

        for child in body.children:
            if child.type != "method_declaration":
                continue
            self._analyze_method(child, interface_qname, file_path, entities, relations, owner_kind="mapper_interface")

    def _analyze_class(
        self, node: Node, pkg_name: str | None, file_path: str,
        entities: list[CodeEntity], relations: list[CodeRelation],
    ) -> None:
        if not self._has_annotation(node, _MAPPER):
            return
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        class_qname = f"{pkg_name}.{class_name}" if pkg_name else class_name

        body = node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type != "method_declaration":
                continue
            self._analyze_method(child, class_qname, file_path, entities, relations, owner_kind="mapper_class")

    def _analyze_method(
        self, method_node: Node, owner_qname: str, file_path: str,
        entities: list[CodeEntity], relations: list[CodeRelation],
        *, owner_kind: str,
    ) -> None:
        name_node = method_node.child_by_field_name("name")
        if name_node is None:
            return
        method_name = name_node.text.decode()
        method_fqn = f"{owner_qname}.{method_name}"

        # mapper_method entity (info marker)
        attrs: dict[str, object] = {
            "method_fqn": method_fqn,
            "owner_kind": owner_kind,
        }

        # @Select / @Insert / @Update / @Delete 어노테이션 SQL
        sql_anno = None
        sql_kind = None
        sql_force_kind = None
        for sql_name, (force_kind, edge_kind) in _SQL_ANNOTATIONS.items():
            anno = self._find_annotation(method_node, sql_name)
            if anno is not None:
                sql_anno = anno
                sql_kind = sql_name
                sql_force_kind = force_kind
                break

        if sql_anno is not None:
            sql_text = self._extract_sql_text(sql_anno)
            attrs["sql_annotation"] = sql_kind
            attrs["sql_text"] = sql_text[:300]
            tables = self._extract_tables_simple(sql_text)
            edge_kind = RelationKinds.READS_TABLE if sql_force_kind == "read" else RelationKinds.WRITES_TABLE
            for tbl in tables:
                relations.append(CodeRelation(
                    kind=edge_kind,
                    source=method_fqn,
                    target=tbl.lower(),
                    attributes={
                        "confidence": 0.85,
                        "dialect": "mybatis_annotation",
                        "annotation": sql_kind,
                    },
                ))
        else:
            # XML 의 SQL 이 있을 가능성 — XML parser 가 별도로 처리 (mybatis_xml_parser)
            attrs["xml_external"] = True

        entities.append(CodeEntity(
            kind=EntityKinds.MAPPER_METHOD,
            qualified_name=f"{method_fqn}#mapper",
            name=method_name,
            file_path=file_path,
            line_start=method_node.start_point[0] + 1,
            line_end=method_node.end_point[0] + 1,
            attributes=attrs,
        ))

    @staticmethod
    def _has_annotation(node: Node, name: str) -> bool:
        for child in node.children:
            if child.type == "modifiers":
                for m in child.children:
                    if m.type in ("marker_annotation", "annotation"):
                        if _annotation_name(m) == name:
                            return True
            if child.type in ("marker_annotation", "annotation"):
                if _annotation_name(child) == name:
                    return True
        return False

    @staticmethod
    def _find_annotation(node: Node, name: str) -> Node | None:
        for child in node.children:
            if child.type == "modifiers":
                for m in child.children:
                    if m.type in ("marker_annotation", "annotation"):
                        if _annotation_name(m) == name:
                            return m
            if child.type in ("marker_annotation", "annotation"):
                if _annotation_name(child) == name:
                    return child
        return None

    @staticmethod
    def _extract_sql_text(anno_node: Node) -> str:
        """@Select("SELECT ...") 또는 @Select({"SELECT ", " FROM ..."}) 의 string 추출."""
        if anno_node.type == "marker_annotation":
            return ""
        parts: list[str] = []
        for c in anno_node.children:
            if c.type != "annotation_argument_list":
                continue
            for child in c.children:
                _collect_strings(child, parts)
        return " ".join(parts)

    @staticmethod
    def _extract_tables_simple(sql: str) -> list[str]:
        """단순 regex 기반 table 추출 (sqlglot 없이도 동작)."""
        seen = set()
        out = []
        for m in _TABLE_RX.finditer(sql or ""):
            tbl = m.group(1).strip().rstrip(",")
            if tbl and tbl.lower() not in seen and not tbl.upper() in ("DUAL",):
                seen.add(tbl.lower())
                out.append(tbl)
        return out


def _collect_strings(node: Node, out: list[str]) -> None:
    if node.type == "string_literal":
        text = node.text.decode()
        if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            out.append(text[1:-1])
        return
    for child in node.children:
        _collect_strings(child, out)


def _annotation_name(node: Node) -> str:
    for c in node.children:
        if c.type == "identifier":
            return c.text.decode()
        if c.type == "scoped_identifier":
            return c.text.decode().rsplit(".", 1)[-1]
    return ""


__all__ = ("MyBatisMapperAnalyzer",)
