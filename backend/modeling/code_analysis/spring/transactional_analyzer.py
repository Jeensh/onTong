"""P29-1 (2026-04-27) — TransactionalAnalyzer.

@Transactional 애너테이션을 메서드/클래스 단위로 추출 :

  - **method-level**     : 그 메서드의 attributes 에 tx_propagation / read_only / rollback_for / no_rollback_for / isolation / timeout 추가
  - **class-level**      : 같은 클래스의 모든 public 메서드에 propagation 등을 inherit (Spring 의 실제 동작)
  - **edge 추가 X**       : 기존 method/class entity 의 attributes 만 enrich

다른 analyzer 가 emit 한 entity 를 enrich 못 하므로, 신규 `tx_marker` entity 를 emit 해서
cross_file_enricher 가 수합하도록 한다 (또는 java_parser 가 이걸 보고 method_attrs 에 합침).

설계 결정 :
  - **별도 entity** `<method_fqn>#tx` 로 emit (ScheduledAnalyzer 와 동일 패턴)
  - method 와 충돌 회피 위해 #tx suffix
  - cross_file_enricher 또는 query 시 join 해서 사용
"""
from __future__ import annotations

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
)

_TX = "Transactional"

_PROPAGATION_DEFAULT = "REQUIRED"
_ISOLATION_DEFAULT = "DEFAULT"


class TransactionalAnalyzer:
    """@Transactional → tx_marker entity (method/class 단위)."""

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
        for child in root.children:
            if child.type == "class_declaration":
                self._analyze_class(child, pkg_name, file_path, entities)
        return entities, []

    def _analyze_class(
        self,
        class_node: Node,
        pkg_name: str | None,
        file_path: str,
        entities: list[CodeEntity],
    ) -> None:
        name_node = class_node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        class_qname = f"{pkg_name}.{class_name}" if pkg_name else class_name

        # class-level @Transactional ?
        class_tx_attrs = self._extract_tx_from_node(class_node)

        if class_tx_attrs is not None:
            entities.append(self._make_entity(
                fqn=f"{class_qname}#tx",
                target_kind="class",
                target_fqn=class_qname,
                file_path=file_path,
                line=class_node.start_point[0] + 1,
                attrs=class_tx_attrs,
            ))

        # method-level
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type != "method_declaration":
                continue
            method_name_node = child.child_by_field_name("name")
            if method_name_node is None:
                continue
            method_name = method_name_node.text.decode()
            method_fqn = f"{class_qname}.{method_name}"
            method_tx = self._extract_tx_from_node(child)
            if method_tx is not None:
                entities.append(self._make_entity(
                    fqn=f"{method_fqn}#tx",
                    target_kind="method",
                    target_fqn=method_fqn,
                    file_path=file_path,
                    line=child.start_point[0] + 1,
                    attrs=method_tx,
                ))
            elif class_tx_attrs is not None and self._is_public(child):
                # class-level @Transactional inherited by public methods
                inherited = dict(class_tx_attrs)
                inherited["inherited_from_class"] = True
                entities.append(self._make_entity(
                    fqn=f"{method_fqn}#tx",
                    target_kind="method",
                    target_fqn=method_fqn,
                    file_path=file_path,
                    line=child.start_point[0] + 1,
                    attrs=inherited,
                ))

    @staticmethod
    def _make_entity(
        *, fqn: str, target_kind: str, target_fqn: str,
        file_path: str, line: int, attrs: dict[str, object],
    ) -> CodeEntity:
        merged = {
            "target_kind": target_kind,
            "target_fqn": target_fqn,
            **attrs,
        }
        return CodeEntity(
            kind=EntityKinds.TX_MARKER,
            qualified_name=fqn,
            name=fqn.rsplit(".", 1)[-1].replace("#tx", ""),
            file_path=file_path,
            line_start=line,
            line_end=line,
            attributes=merged,
        )

    @staticmethod
    def _is_public(method_node: Node) -> bool:
        for child in method_node.children:
            if child.type == "modifiers":
                for m in child.children:
                    if m.type == "modifier" and m.text.decode() == "public":
                        return True
                    if m.type == "public":
                        return True
        return False

    def _extract_tx_from_node(self, node: Node) -> dict[str, object] | None:
        """Find @Transactional on a class or method node and parse its attributes."""
        anno = self._find_annotation(node, _TX)
        if anno is None:
            return None
        attrs: dict[str, object] = {
            "propagation": _PROPAGATION_DEFAULT,
            "isolation": _ISOLATION_DEFAULT,
            "read_only": False,
        }
        if anno.type == "marker_annotation":
            return attrs

        args = anno.child_by_field_name("arguments")
        if args is None:
            for c in anno.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return attrs

        for c in args.children:
            if c.type != "element_value_pair":
                continue
            key, value_node = self._split_pair(c)
            if key is None or value_node is None:
                continue
            text = self._literal_value(value_node)
            if key == "propagation":
                # 예: Propagation.REQUIRES_NEW → 마지막 segment 만
                attrs["propagation"] = text.rsplit(".", 1)[-1]
            elif key == "isolation":
                attrs["isolation"] = text.rsplit(".", 1)[-1]
            elif key == "readOnly":
                attrs["read_only"] = text.strip().lower() == "true"
            elif key == "timeout":
                attrs["timeout"] = text
            elif key in ("rollbackFor", "rollbackForClassName"):
                attrs["rollback_for"] = self._parse_class_array(value_node)
            elif key in ("noRollbackFor", "noRollbackForClassName"):
                attrs["no_rollback_for"] = self._parse_class_array(value_node)
            elif key == "value" or key == "transactionManager":
                attrs["transaction_manager"] = text
        return attrs

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

    @staticmethod
    def _literal_value(node: Node) -> str:
        text = node.text.decode()
        if node.type == "string_literal":
            if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
                return text[1:-1]
        return text

    @staticmethod
    def _parse_class_array(node: Node) -> list[str]:
        """rollbackFor = {ExceptionA.class, ExceptionB.class} → ["ExceptionA", "ExceptionB"]."""
        text = node.text.decode()
        # 단순 텍스트 split (full AST walk 까지는 X)
        result = []
        for token in text.replace("{", "").replace("}", "").split(","):
            token = token.strip().rstrip(".class").rstrip(".class ")
            if token:
                result.append(token)
        return result


def _annotation_name(node: Node) -> str:
    for c in node.children:
        if c.type == "identifier":
            return c.text.decode()
        if c.type == "scoped_identifier":
            return c.text.decode().rsplit(".", 1)[-1]
    return ""


__all__ = ("TransactionalAnalyzer",)
