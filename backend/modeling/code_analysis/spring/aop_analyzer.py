"""OD-11-B5-2 : Spring AopAnalyzer.

감지 대상:
  - @Aspect class → `aspect` entity (qualified_name = class FQN).
  - @Before / @After / @Around / @AfterReturning / @AfterThrowing advice methods
    → `INTERCEPTS` edge.
  - @Pointcut methods : expression 을 기억해 두고, advice 가 이름으로 참조하면 해석.
  - @Order : class-level → 모든 advice 에 적용, method-level → 해당 advice 에만 (class 덮어씀).

엣지 속성:
  - advice_type ∈ {before, after, around, after_returning, after_throwing}
  - pointcut_expr : advice 애너테이션 안에 적힌 원본 문자열
  - pointcut_kind ∈ {execution, within, annotation, within_annotation, named, raw}
  - resolved_expr : named pointcut 일 때만 (참조된 @Pointcut 의 실제 표현식)
  - order : 정수 (있을 때만)

target 해석 규칙 (PoC 범위):
  - execution(<ret> <FQN>.<method>(..))  → target = FQN,    pointcut_kind = execution
  - within(<FQN>)                        → target = FQN,    pointcut_kind = within
  - @annotation(<FQN>)                   → target = FQN,    pointcut_kind = annotation
  - @within(<FQN>)                       → target = FQN,    pointcut_kind = within_annotation
  - <name>()                             → named 로 lookup 성공 시 재귀 해석, 실패 시 raw
  - 그 외 복합식                           → target = "<unresolved>",  pointcut_kind = raw
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

_ADVICE_ANNOTATIONS: dict[str, str] = {
    "Before": "before",
    "After": "after",
    "Around": "around",
    "AfterReturning": "after_returning",
    "AfterThrowing": "after_throwing",
}

_UNRESOLVED = "<unresolved>"

# ---------------------------------------------------------------------------
# Pointcut expression parsing
# ---------------------------------------------------------------------------
_RX_EXECUTION = re.compile(
    r"^\s*execution\s*\(\s*[^()]*?\s+([A-Za-z_][\w.]*)\.[A-Za-z_*][\w*]*\s*\(.*\)\s*\)\s*$"
)
_RX_WITHIN = re.compile(r"^\s*within\s*\(\s*([A-Za-z_][\w.]*)\s*\)\s*$")
_RX_ANNOTATION = re.compile(r"^\s*@annotation\s*\(\s*([A-Za-z_][\w.]*)\s*\)\s*$")
_RX_WITHIN_ANNO = re.compile(r"^\s*@within\s*\(\s*([A-Za-z_][\w.]*)\s*\)\s*$")
_RX_NAMED_CALL = re.compile(r"^\s*([A-Za-z_][\w]*)\s*\(\s*\)\s*$")


class AopAnalyzer:
    """@Aspect + 5 advice → aspect entity + INTERCEPTS edges."""

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
                self._analyze_class(
                    child, pkg_name, file_path, entities, relations,
                )

        return entities, relations

    # -- class-level --------------------------------------------------------

    def _analyze_class(
        self,
        node: Node,
        pkg_name: str | None,
        file_path: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        class_qname = f"{pkg_name}.{class_name}" if pkg_name else class_name

        annotations = self._collect_annotations(node)
        if not any(a["name"] == "Aspect" for a in annotations):
            return

        entities.append(CodeEntity(
            kind=EntityKinds.ASPECT,
            qualified_name=class_qname,
            name=class_name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            parent=pkg_name,
            attributes={},
        ))

        class_order = self._extract_order(annotations)

        body = node.child_by_field_name("body")
        if body is None:
            return

        # First pass: collect named @Pointcut expressions in this class.
        named_pointcuts: dict[str, str] = {}
        for child in body.children:
            if child.type != "method_declaration":
                continue
            m_annotations = self._collect_annotations(child)
            pc_expr = self._extract_pointcut_expr(m_annotations)
            if pc_expr is None:
                continue
            m_name_node = child.child_by_field_name("name")
            if m_name_node is None:
                continue
            named_pointcuts[m_name_node.text.decode()] = pc_expr

        # Second pass: advice methods → INTERCEPTS edges.
        for child in body.children:
            if child.type != "method_declaration":
                continue
            self._analyze_advice_method(
                child, class_qname, file_path, class_order,
                named_pointcuts, relations,
            )

    # -- advice method ------------------------------------------------------

    def _analyze_advice_method(
        self,
        node: Node,
        aspect_qname: str,
        file_path: str,
        class_order: int | None,
        named_pointcuts: dict[str, str],
        relations: list[CodeRelation],
    ) -> None:
        annotations = self._collect_annotations(node)

        advice_type: str | None = None
        expr: str | None = None
        for a in annotations:
            if a["name"] in _ADVICE_ANNOTATIONS:
                advice_type = _ADVICE_ANNOTATIONS[a["name"]]
                expr = self._single_string_arg(a["node"])  # type: ignore[arg-type]
                break

        if advice_type is None or expr is None:
            return

        target, kind, resolved = _resolve_target(expr, named_pointcuts)

        attrs: dict[str, object] = {
            "advice_type": advice_type,
            "pointcut_expr": expr,
            "pointcut_kind": kind,
        }
        if resolved is not None:
            attrs["resolved_expr"] = resolved

        method_order = self._extract_order(annotations)
        effective_order = method_order if method_order is not None else class_order
        if effective_order is not None:
            attrs["order"] = effective_order

        relations.append(CodeRelation(
            kind=RelationKinds.INTERCEPTS,
            source=aspect_qname,
            target=target,
            file_path=file_path,
            line=node.start_point[0] + 1,
            attributes=attrs,
        ))

    # -- annotation helpers -------------------------------------------------

    def _collect_annotations(self, node: Node) -> list[dict[str, Node]]:
        out: list[dict[str, object]] = []
        for child in node.children:
            if child.type != "modifiers":
                continue
            for m in child.children:
                if m.type in ("marker_annotation", "annotation"):
                    name = self._annotation_name(m)
                    if name:
                        out.append({"name": name, "node": m})
        for child in node.children:
            if child.type in ("marker_annotation", "annotation"):
                name = self._annotation_name(child)
                if name:
                    out.append({"name": name, "node": child})
        return out  # type: ignore[return-value]

    @staticmethod
    def _annotation_name(node: Node) -> str:
        for c in node.children:
            if c.type == "identifier":
                return c.text.decode()
        return ""

    def _extract_order(
        self, annotations: Iterable[dict[str, object]],
    ) -> int | None:
        for a in annotations:
            if a["name"] != "Order":
                continue
            val = self._single_int_arg(a["node"])  # type: ignore[arg-type]
            if val is not None:
                return val
        return None

    def _extract_pointcut_expr(
        self, annotations: Iterable[dict[str, object]],
    ) -> str | None:
        for a in annotations:
            if a["name"] == "Pointcut":
                return self._single_string_arg(a["node"])  # type: ignore[arg-type]
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
    def _single_int_arg(annotation_node: Node) -> int | None:
        args = annotation_node.child_by_field_name("arguments")
        if args is None:
            for c in annotation_node.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return None
        for c in args.children:
            if c.type == "decimal_integer_literal":
                try:
                    return int(c.text.decode())
                except ValueError:
                    return None
        return None


def _resolve_target(
    expr: str, named_pointcuts: dict[str, str],
) -> tuple[str, str, str | None]:
    """Return (target_fqn, pointcut_kind, resolved_expr_or_none)."""
    m = _RX_EXECUTION.match(expr)
    if m:
        return m.group(1), "execution", None
    m = _RX_WITHIN.match(expr)
    if m:
        return m.group(1), "within", None
    m = _RX_ANNOTATION.match(expr)
    if m:
        return m.group(1), "annotation", None
    m = _RX_WITHIN_ANNO.match(expr)
    if m:
        return m.group(1), "within_annotation", None
    m = _RX_NAMED_CALL.match(expr)
    if m:
        name = m.group(1)
        pc_expr = named_pointcuts.get(name)
        if pc_expr is not None:
            inner_target, inner_kind, _ = _resolve_target(pc_expr, named_pointcuts)
            if inner_kind != "raw":
                return inner_target, "named", pc_expr
    return _UNRESOLVED, "raw", None


def _string_literal_text(node: Node) -> str:
    for c in node.children:
        if c.type == "string_fragment":
            return c.text.decode()
    text = node.text.decode()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


__all__ = ("AopAnalyzer",)
