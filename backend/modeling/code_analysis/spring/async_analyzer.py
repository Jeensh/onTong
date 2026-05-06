"""P29-1 (2026-04-27) — AsyncAnalyzer.

@Async / @TransactionalEventListener.phase 추출 :

  - **@Async** : 메서드가 별도 스레드에서 실행됨 — 메인 트랜잭션과 분리
  - **@TransactionalEventListener(phase=AFTER_COMMIT)** : commit 후에만 실행, rollback 시 skip
  - **@TransactionalEventListener(phase=BEFORE_COMMIT/AFTER_ROLLBACK 등)**

emit : `<method_fqn>#async` entity (ScheduledAnalyzer 와 동일 패턴).
"""
from __future__ import annotations

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
)

_ASYNC = "Async"
_TX_EVENT_LISTENER = "TransactionalEventListener"
_EVENT_LISTENER = "EventListener"


class AsyncAnalyzer:
    """@Async + @TransactionalEventListener.phase → async_marker entity."""

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

            attrs: dict[str, object] = {}

            async_anno = self._find_annotation(child, _ASYNC)
            if async_anno is not None:
                attrs["async"] = True
                executor = self._extract_executor_name(async_anno)
                if executor:
                    attrs["executor"] = executor

            tx_event_anno = self._find_annotation(child, _TX_EVENT_LISTENER)
            if tx_event_anno is not None:
                attrs["tx_event_listener"] = True
                phase = self._extract_phase(tx_event_anno)
                attrs["tx_phase"] = phase or "AFTER_COMMIT"   # default per Spring

            event_anno = self._find_annotation(child, _EVENT_LISTENER)
            if event_anno is not None and tx_event_anno is None:
                attrs["event_listener"] = True

            if not attrs:
                continue

            entities.append(CodeEntity(
                kind=EntityKinds.ASYNC_MARKER,
                qualified_name=f"{method_fqn}#async",
                name=method_name,
                file_path=file_path,
                line_start=child.start_point[0] + 1,
                line_end=child.end_point[0] + 1,
                attributes={
                    "method_fqn": method_fqn,
                    "class_fqn": class_qname,
                    **attrs,
                },
            ))

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
    def _extract_executor_name(anno_node: Node) -> str | None:
        """@Async("myExecutor") 또는 @Async(value = "x") 의 string."""
        if anno_node.type == "marker_annotation":
            return None
        for c in anno_node.children:
            if c.type == "annotation_argument_list":
                for arg in c.children:
                    if arg.type == "string_literal":
                        text = arg.text.decode()
                        if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
                            return text[1:-1]
                    if arg.type == "element_value_pair":
                        for cc in arg.children:
                            if cc.type == "string_literal":
                                text = cc.text.decode()
                                if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
                                    return text[1:-1]
        return None

    @staticmethod
    def _extract_phase(anno_node: Node) -> str | None:
        """@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT) → 'AFTER_COMMIT'."""
        if anno_node.type == "marker_annotation":
            return None
        for c in anno_node.children:
            if c.type != "annotation_argument_list":
                continue
            for arg in c.children:
                if arg.type != "element_value_pair":
                    continue
                key_node, value_node = None, None
                for cc in arg.children:
                    if cc.type == "=":
                        continue
                    if key_node is None and cc.type == "identifier":
                        key_node = cc
                    elif key_node is not None:
                        value_node = cc
                        break
                if key_node is None or value_node is None:
                    continue
                if key_node.text.decode() == "phase":
                    text = value_node.text.decode()
                    return text.rsplit(".", 1)[-1]
        return None


def _annotation_name(node: Node) -> str:
    for c in node.children:
        if c.type == "identifier":
            return c.text.decode()
        if c.type == "scoped_identifier":
            return c.text.decode().rsplit(".", 1)[-1]
    return ""


__all__ = ("AsyncAnalyzer",)
