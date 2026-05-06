"""OD-11-B5-4 : Spring EventsAnalyzer.

감지 대상:
  - `@EventListener` (on method) → `HANDLES` edge.
  - `@TransactionalEventListener` (on method) → `HANDLES` edge + `attributes.transactional=True`.
  - `ApplicationEventPublisher.publishEvent(new X(...))` 호출 → `PUBLISHES` edge + `event_type` entity.

엔티티:
  - `event_type` : qn = 이벤트 클래스 FQN (import_map 해석). 파일별 dedup.
    attributes.inferred_from ∈ {"handler", "publish"}.

엣지 속성:
  - HANDLES : `handler_method`, `transactional` (True 일 때만).
  - PUBLISHES : `via` (publisher 필드/식별자 이름; object 없으면 "this"),
                `publish_expr` (unresolved 일 때만; 인자 리스트 raw 텍스트).

Event 타입 추론 전략:
  - `@EventListener(X.class)` / `@EventListener(value=X.class)` → value-form 우선.
  - 그 외 `@EventListener` → 메서드 첫 파라미터 타입.
  - `publishEvent(new X(...))` → 첫 인자 `object_creation_expression` 의 type.
  - `publishEvent(existingVar)` 등 그 외 → `<unresolved>` + `publish_expr` 보존.
"""

from __future__ import annotations

from typing import Generator, Iterable

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    RelationKinds,
)

_UNRESOLVED = "<unresolved>"

_HANDLER_ANNOTATIONS: frozenset[str] = frozenset({
    "EventListener",
    "TransactionalEventListener",
})

_PUBLISH_METHOD_NAME = "publishEvent"


class EventsAnalyzer:
    """@EventListener / @TransactionalEventListener / publishEvent → event_type + HANDLES/PUBLISHES."""

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
        seen_event_types: set[str] = set()

        for child in root.children:
            if child.type == "class_declaration":
                self._analyze_class(
                    child, pkg_name, file_path, import_map,
                    entities, relations, seen_event_types,
                )

        return entities, relations

    # -- class / method ----------------------------------------------------

    def _analyze_class(
        self,
        node: Node,
        pkg_name: str | None,
        file_path: str,
        import_map: dict[str, str],
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        seen_event_types: set[str],
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
            self._analyze_method(
                child, class_qname, pkg_name, file_path, import_map,
                entities, relations, seen_event_types,
            )

    def _analyze_method(
        self,
        node: Node,
        class_qname: str,
        pkg_name: str | None,
        file_path: str,
        import_map: dict[str, str],
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        seen_event_types: set[str],
    ) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        method_name = name_node.text.decode()
        method_qname = f"{class_qname}.{method_name}"

        annotations = self._collect_annotations(node)
        handler_anno: dict[str, object] | None = None
        transactional = False
        for a in annotations:
            if a["name"] == "EventListener":
                handler_anno = a
                break
            if a["name"] == "TransactionalEventListener":
                handler_anno = a
                transactional = True
                break

        if handler_anno is not None:
            self._emit_handler_edge(
                node, handler_anno, method_qname, method_name, transactional,
                pkg_name, file_path, import_map,
                entities, relations, seen_event_types,
            )

        body = node.child_by_field_name("body")
        if body is None:
            return
        for inv in self._find_publish_invocations(body):
            self._emit_publisher_edge(
                inv, method_qname, pkg_name, file_path, import_map,
                entities, relations, seen_event_types,
            )

    # -- handler emission --------------------------------------------------

    def _emit_handler_edge(
        self,
        method_node: Node,
        anno: dict[str, object],
        method_qname: str,
        method_name: str,
        transactional: bool,
        pkg_name: str | None,
        file_path: str,
        import_map: dict[str, str],
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        seen_event_types: set[str],
    ) -> None:
        event_simple = self._extract_class_literal_type(anno["node"])  # type: ignore[arg-type]
        if event_simple is None:
            params = method_node.child_by_field_name("parameters")
            event_simple = self._first_param_type(params)

        if event_simple is None:
            event_fqn = _UNRESOLVED
        else:
            event_fqn = _resolve_type(event_simple, import_map, pkg_name)

        attrs: dict[str, object] = {"handler_method": method_name}
        if transactional:
            attrs["transactional"] = True

        relations.append(CodeRelation(
            kind=RelationKinds.HANDLES,
            source=method_qname,
            target=event_fqn,
            file_path=file_path,
            line=method_node.start_point[0] + 1,
            attributes=attrs,
        ))

        if event_fqn != _UNRESOLVED:
            self._maybe_emit_event_type(
                event_fqn, "handler", file_path,
                method_node.start_point[0] + 1,
                entities, seen_event_types,
            )

    # -- publisher emission ------------------------------------------------

    def _emit_publisher_edge(
        self,
        invocation: Node,
        method_qname: str,
        pkg_name: str | None,
        file_path: str,
        import_map: dict[str, str],
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        seen_event_types: set[str],
    ) -> None:
        args = invocation.child_by_field_name("arguments")
        if args is None:
            return

        first_arg = _first_real_arg(args)
        event_fqn: str | None = None
        if first_arg is not None and first_arg.type == "object_creation_expression":
            type_node = first_arg.child_by_field_name("type")
            if type_node is not None:
                event_simple = type_node.text.decode()
                event_fqn = _resolve_type(event_simple, import_map, pkg_name)

        attrs: dict[str, object] = {"via": self._extract_via(invocation)}
        if event_fqn is None:
            target = _UNRESOLVED
            attrs["publish_expr"] = args.text.decode()
        else:
            target = event_fqn

        relations.append(CodeRelation(
            kind=RelationKinds.PUBLISHES,
            source=method_qname,
            target=target,
            file_path=file_path,
            line=invocation.start_point[0] + 1,
            attributes=attrs,
        ))

        if event_fqn is not None:
            self._maybe_emit_event_type(
                event_fqn, "publish", file_path,
                invocation.start_point[0] + 1,
                entities, seen_event_types,
            )

    def _maybe_emit_event_type(
        self,
        event_fqn: str,
        inferred_from: str,
        file_path: str,
        line: int,
        entities: list[CodeEntity],
        seen_event_types: set[str],
    ) -> None:
        if event_fqn in seen_event_types:
            return
        seen_event_types.add(event_fqn)
        simple = event_fqn.rsplit(".", 1)[-1]
        entities.append(CodeEntity(
            kind=EntityKinds.EVENT_TYPE,
            qualified_name=event_fqn,
            name=simple,
            file_path=file_path,
            line_start=line,
            line_end=line,
            attributes={"inferred_from": inferred_from},
        ))

    # -- invocation walking ------------------------------------------------

    def _find_publish_invocations(self, body: Node) -> Generator[Node, None, None]:
        for n in _walk(body):
            if n.type != "method_invocation":
                continue
            name_node = n.child_by_field_name("name")
            if name_node is None:
                continue
            if name_node.text.decode() == _PUBLISH_METHOD_NAME:
                yield n

    @staticmethod
    def _extract_via(invocation: Node) -> str:
        obj = invocation.child_by_field_name("object")
        if obj is None:
            return "this"
        return obj.text.decode().rsplit(".", 1)[-1]

    # -- annotation / value parsing ---------------------------------------

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

    def _extract_class_literal_type(self, annotation_node: Node) -> str | None:
        args = annotation_node.child_by_field_name("arguments")
        if args is None:
            for c in annotation_node.children:
                if c.type == "annotation_argument_list":
                    args = c
                    break
        if args is None:
            return None
        # Positional class literal: @Anno(X.class)
        for c in args.children:
            if c.type == "class_literal":
                return _class_literal_type_name(c)
            if c.type == "element_value_array_initializer":
                for x in c.children:
                    if x.type == "class_literal":
                        return _class_literal_type_name(x)
        # Keyword class literal: @Anno(value=X.class) or @Anno(classes={X.class})
        for c in args.children:
            if c.type != "element_value_pair":
                continue
            key = None
            val_node: Node | None = None
            for pc in c.children:
                if pc.type == "identifier" and key is None:
                    key = pc.text.decode()
                elif pc.type == "class_literal":
                    val_node = pc
                elif pc.type == "element_value_array_initializer":
                    for x in pc.children:
                        if x.type == "class_literal":
                            val_node = x
                            break
            if key in ("value", "classes") and val_node is not None:
                return _class_literal_type_name(val_node)
        return None

    @staticmethod
    def _first_param_type(params_node: Node | None) -> str | None:
        if params_node is None:
            return None
        for p in params_node.children:
            if p.type != "formal_parameter":
                continue
            t = p.child_by_field_name("type")
            if t is not None:
                return t.text.decode()
        return None

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


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
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


def _class_literal_type_name(node: Node) -> str | None:
    for c in node.children:
        if c.type in (
            "type_identifier",
            "scoped_type_identifier",
            "scoped_identifier",
        ):
            return c.text.decode()
    return None


def _first_real_arg(args_node: Node) -> Node | None:
    for c in args_node.children:
        if c.type in ("(", ")", ","):
            continue
        return c
    return None


def _walk(node: Node) -> Iterable[Node]:
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


__all__ = ("EventsAnalyzer",)
