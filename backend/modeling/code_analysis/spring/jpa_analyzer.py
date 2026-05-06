"""OD-11-B5-7 — Spring `JpaAnalyzer` (12번째 Spring analyzer).

Spring Data JPA Repository interface 의 메서드 → `READS_TABLE` / `WRITES_TABLE`
엣지 + edge attribute marker (`jpa_operation`, `jpa_property_path`).

탐지 대상 :
  - `@Repository` 어노테이션 붙은 interface, 또는
  - 4 base interface 중 하나를 extends 하는 interface :
      Repository / CrudRepository / PagingAndSortingRepository / JpaRepository
    (Spring Data 의 표준 base. **첫 generic 파라미터** = entity simple name.)

메서드 이름 컨벤션 (Spring Data Query Methods 명명 규칙) :
  find* / get* / query* / read* / search*  By*  → READS  (`jpa_operation="find"`)
  exists* By*                                   → READS  (`"exists"`)
  count*  By*                                   → READS  (`"count"`)
  delete* / remove* By*                         → WRITES (`"delete"`)
  save / saveAll / saveAndFlush  (정확 매치)     → WRITES (`"save"`)
  그 외                                         → marker only, edge 없음

Target table = entity simple name. 추후 CrossFileEnricher 가 `@Table(name="...")`
으로 rewrite — 본 analyzer 는 simple name 만 emit (cross-file resolution out of scope).

`@Query` / `@Modifying` 은 `NativeSqlAnalyzer` (B6-3) 가 이미 처리. 본 analyzer 는
Spring Data 의 **메서드 이름 magic** 만.
"""

from __future__ import annotations

import re

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    RelationKinds,
)

# Spring Data 의 4 base repository interface (simple names — import 무관 매칭).
_REPO_BASE_INTERFACES = frozenset({
    "Repository",
    "CrudRepository",
    "PagingAndSortingRepository",
    "JpaRepository",
    # ReactiveCrudRepository / R2dbcRepository 등 추가 시 여기에.
})

_REPOSITORY_ANNOTATION = "Repository"

# 메서드 이름 prefix → operation. find/get/query/read/search 모두 "find" 로 통합.
_PREFIX_TO_OP: tuple[tuple[str, str], ...] = (
    ("find",   "find"),
    ("get",    "find"),
    ("query",  "find"),
    ("read",   "find"),
    ("search", "find"),
    ("exists", "exists"),
    ("count",  "count"),
    ("delete", "delete"),
    ("remove", "delete"),
)
_READ_OPS = frozenset({"find", "exists", "count"})
_WRITE_OPS = frozenset({"delete", "save"})

# 정확 매치 save 패밀리.
_SAVE_NAMES = frozenset({"save", "saveAll", "saveAndFlush"})

# By 토큰 split — `findByEmailAndStatus` → "By" 로 자르고 다시 "And"/"Or" 로 split.
_BY_SPLIT_RE = re.compile(r"(?<=[a-z])By(?=[A-Z])")
_PROP_SPLIT_RE = re.compile(r"And|Or")


class JpaAnalyzer:
    """Spring Data JPA Repository → READS_TABLE/WRITES_TABLE 엣지."""

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

        relations: list[CodeRelation] = []
        for child in root.children:
            if child.type != "interface_declaration":
                continue
            self._analyze_interface(child, pkg_name, file_path, relations)
        return [], relations

    # -- interface ----------------------------------------------------------

    def _analyze_interface(
        self,
        node: Node,
        pkg_name: str | None,
        file_path: str,
        relations: list[CodeRelation],
    ) -> None:
        # entity_type : extends Spring Data base 의 첫 generic 파라미터.
        entity_type = self._extract_entity_type(node)
        has_repo_anno = self._has_repository_annotation(node)
        if entity_type is None and not has_repo_anno:
            return  # JPA repository 가 아님.
        # entity_type 미식별 시 edge 못 emit (spec : annotation 만 있으면 빈 결과).
        if entity_type is None:
            return

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        interface_name = name_node.text.decode()
        interface_qname = f"{pkg_name}.{interface_name}" if pkg_name else interface_name

        body = node.child_by_field_name("body")
        if body is None:
            return

        for member in body.children:
            if member.type != "method_declaration":
                continue
            self._analyze_method(
                member, interface_qname, entity_type, file_path, relations,
            )

    def _has_repository_annotation(self, node: Node) -> bool:
        for child in node.children:
            if child.type == "modifiers":
                for m in child.children:
                    if m.type in ("marker_annotation", "annotation"):
                        if _annotation_name(m) == _REPOSITORY_ANNOTATION:
                            return True
            if child.type in ("marker_annotation", "annotation"):
                if _annotation_name(child) == _REPOSITORY_ANNOTATION:
                    return True
        return False

    def _extract_entity_type(self, node: Node) -> str | None:
        """`extends JpaRepository<User, Long>` → "User"."""
        for child in node.children:
            if child.type != "extends_interfaces":
                continue
            # extends_interfaces > type_list > generic_type > scoped/type_identifier + type_arguments
            for desc in _walk(child):
                if desc.type != "generic_type":
                    continue
                base_name = self._generic_base_name(desc)
                if base_name not in _REPO_BASE_INTERFACES:
                    continue
                first_arg = self._first_type_argument_name(desc)
                if first_arg is not None:
                    return first_arg
        return None

    @staticmethod
    def _generic_base_name(generic_node: Node) -> str:
        # `JpaRepository<...>` → 첫 type_identifier 자식.
        for c in generic_node.children:
            if c.type == "type_identifier":
                return c.text.decode()
            if c.type == "scoped_type_identifier":
                # e.g. org.springframework.data.jpa.repository.JpaRepository
                txt = c.text.decode()
                return txt.rsplit(".", 1)[-1]
        return ""

    @staticmethod
    def _first_type_argument_name(generic_node: Node) -> str | None:
        for c in generic_node.children:
            if c.type != "type_arguments":
                continue
            for t in c.children:
                if t.type == "type_identifier":
                    return t.text.decode()
                if t.type == "scoped_type_identifier":
                    return t.text.decode().rsplit(".", 1)[-1]
        return None

    # -- method -------------------------------------------------------------

    def _analyze_method(
        self,
        node: Node,
        interface_qname: str,
        entity_type: str,
        file_path: str,
        relations: list[CodeRelation],
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        method_name = name_node.text.decode()

        op, property_path = _classify_method(method_name)
        if op is None:
            return  # 컨벤션 외 — edge 없음.

        edge_kind = (
            RelationKinds.WRITES_TABLE
            if op in _WRITE_OPS
            else RelationKinds.READS_TABLE
        )
        method_fqn = f"{interface_qname}.{method_name}"

        relations.append(
            CodeRelation(
                kind=edge_kind,
                source=method_fqn,
                target=entity_type,
                file_path=file_path,
                line=node.start_point[0] + 1,
                attributes={
                    "jpa_operation": op,
                    "jpa_property_path": property_path,
                    "target_kind": "jpa_entity_simple_name",
                },
            )
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _annotation_name(node: Node) -> str:
    for c in node.children:
        if c.type == "identifier":
            return c.text.decode()
    return ""


def _walk(node: Node):
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


def _classify_method(name: str) -> tuple[str | None, list[str]]:
    """메서드 이름 → (operation, property_path).

    Returns (None, []) if not a recognized convention.
    """
    if name in _SAVE_NAMES:
        return "save", []

    for prefix, op in _PREFIX_TO_OP:
        if not name.startswith(prefix):
            continue
        # prefix 다음 글자가 대문자거나 끝이어야 함 — `find` / `findX` OK,
        # `findxxx` (소문자) 는 매칭 X.
        rest = name[len(prefix):]
        if rest and not rest[0].isupper():
            continue
        # property path : `By` 뒤의 식별자 → "And"/"Or" 로 split → camelCase 첫 글자 소문자화
        property_path = _extract_property_path(name)
        return op, property_path
    return None, []


def _extract_property_path(method_name: str) -> list[str]:
    parts = _BY_SPLIT_RE.split(method_name, maxsplit=1)
    if len(parts) < 2:
        return []
    after_by = parts[1]
    if not after_by:
        return []
    # And/Or 로 분리 (Spring Data 명명 규칙)
    raw_props = _PROP_SPLIT_RE.split(after_by)
    out: list[str] = []
    for p in raw_props:
        if not p:
            continue
        # 첫 글자 소문자화 (camelCase property)
        out.append(p[0].lower() + p[1:])
    return out


__all__ = ("JpaAnalyzer",)
