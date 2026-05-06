"""OD-11-B5-5 : Spring ScheduledAnalyzer.

감지 대상:
  - 메서드 레벨 `@Scheduled` 애너테이션 → `scheduled_task` 엔티티.
  - `qn = <method FQN>#scheduled` (메서드 엔티티와 충돌 회피; `@Bean` 의 `#bean` 패턴과 동일).

속성 (있을 때만 기록):
  - `method_fqn` : 메서드 FQN (항상 기록).
  - `fixed_rate` / `fixed_delay` / `initial_delay` : ms 리터럴 또는 placeholder 문자열.
  - `cron` : cron 표현식.
  - `zone` : 타임존 문자열.

`fixedRateString` / `fixedDelayString` / `initialDelayString` 은 String variant 로,
동일 키 (`fixed_rate` / `fixed_delay` / `initial_delay`) 에 placeholder 값 그대로 저장.

엣지: 없음. 이 analyzer 는 entity-only.
"""

from __future__ import annotations

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
)

_SCHEDULED = "Scheduled"

_INT_KEY_MAP: dict[str, str] = {
    "fixedRate": "fixed_rate",
    "fixedDelay": "fixed_delay",
    "initialDelay": "initial_delay",
    "fixedRateString": "fixed_rate",
    "fixedDelayString": "fixed_delay",
    "initialDelayString": "initial_delay",
}

_STRING_KEY_MAP: dict[str, str] = {
    "cron": "cron",
    "zone": "zone",
}


class ScheduledAnalyzer:
    """@Scheduled → `scheduled_task` 엔티티 (entity-only)."""

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

    # -- class / method ----------------------------------------------------

    def _analyze_class(
        self,
        node: Node,
        pkg_name: str | None,
        file_path: str,
        entities: list[CodeEntity],
    ) -> None:
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
            self._analyze_method(child, class_qname, file_path, entities)

    def _analyze_method(
        self,
        node: Node,
        class_qname: str,
        file_path: str,
        entities: list[CodeEntity],
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        method_name = name_node.text.decode()
        method_fqn = f"{class_qname}.{method_name}"

        scheduled_anno = self._find_scheduled_annotation(node)
        if scheduled_anno is None:
            return

        attrs: dict[str, object] = {"method_fqn": method_fqn}
        self._extract_attributes(scheduled_anno, attrs)

        entities.append(CodeEntity(
            kind=EntityKinds.SCHEDULED_TASK,
            qualified_name=f"{method_fqn}#scheduled",
            name=method_name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            attributes=attrs,
        ))

    # -- annotation parsing -----------------------------------------------

    def _find_scheduled_annotation(self, method_node: Node) -> Node | None:
        for child in method_node.children:
            if child.type == "modifiers":
                for m in child.children:
                    if m.type in ("marker_annotation", "annotation"):
                        if self._annotation_name(m) == _SCHEDULED:
                            return m
            if child.type in ("marker_annotation", "annotation"):
                if self._annotation_name(child) == _SCHEDULED:
                    return child
        return None

    @staticmethod
    def _annotation_name(node: Node) -> str:
        for c in node.children:
            if c.type == "identifier":
                return c.text.decode()
        return ""

    def _extract_attributes(self, anno_node: Node, attrs: dict[str, object]) -> None:
        if anno_node.type == "marker_annotation":
            return

        args = anno_node.child_by_field_name("arguments")
        if args is None:
            for c in anno_node.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return

        for c in args.children:
            if c.type != "element_value_pair":
                continue
            key, value_node = self._split_pair(c)
            if key is None or value_node is None:
                continue

            if key in _INT_KEY_MAP:
                attrs[_INT_KEY_MAP[key]] = self._literal_value(value_node)
            elif key in _STRING_KEY_MAP:
                attrs[_STRING_KEY_MAP[key]] = self._literal_value(value_node)

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


__all__ = ("ScheduledAnalyzer",)
