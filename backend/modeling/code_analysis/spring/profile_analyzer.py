"""OD-11-B5-6 : Spring ProfileAnalyzer (method-level).

감지 대상 (method-level만; class-level 은 B5-1 DIAnalyzer 에서 이미 AUTOWIRES 엣지에 주입):
  - `@Profile("prod")` / `@Profile({"prod", "legacy"})`
  - `@ConditionalOnProperty("feature.x")` / `@ConditionalOnProperty(name=..., havingValue=...)`

적용 대상 (다른 analyzer 가 emit 한 entity/relation 속성에 merge):
  - `@Bean` 메서드 → `spring_bean` entity (qn = `<class>.<method>#bean`)
  - HTTP handler 메서드 → `http_endpoint` entity + `MAPS_URL` relation
  - `@Scheduled` 메서드 → `scheduled_task` entity
  - `@EventListener` / `@TransactionalEventListener` 메서드 → `HANDLES` relation
  - `publishEvent(...)` 호출을 포함하는 메서드 → `PUBLISHES` relation

구조:
  - `analyze()` 는 Protocol 호환을 위해 `([], [])` 반환 (독립적으로 entity/relation emit 하지 않음).
  - `enrich(entities, relations, tree, pkg_name)` post-pass 메서드에서 AST 스캔 →
    method FQN 별 profile/condition map 구축 → 매칭 entity/relation 에 속성 merge.
  - `JavaParser` 가 `analyze` 일괄 호출 후 `hasattr(analyzer, 'enrich')` 체크해서 2차 패스 위임.
"""

from __future__ import annotations

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    RelationKinds,
)

_BEAN_SUFFIX = "#bean"
_SCHEDULED_SUFFIX = "#scheduled"


class ProfileAnalyzer:
    """method-level `@Profile` / `@ConditionalOnProperty` → 다른 analyzer 산출물 속성 보강."""

    def analyze(
        self,
        tree: object | None,
        content: bytes,
        file_path: str,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        return [], []

    # -- post-processor -----------------------------------------------------

    def enrich(
        self,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        tree: object | None,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        if tree is None:
            return entities, relations

        root: Node = tree.root_node  # type: ignore[attr-defined]
        profile_map = self._build_profile_map(root, pkg_name)
        if not profile_map:
            return entities, relations

        for ent in entities:
            method_fqn = self._entity_method_fqn(ent)
            if method_fqn is None:
                continue
            data = profile_map.get(method_fqn)
            if data is None:
                continue
            self._merge_attrs(ent.attributes, data)

        for rel in relations:
            method_fqn = self._relation_method_fqn(rel)
            if method_fqn is None:
                continue
            data = profile_map.get(method_fqn)
            if data is None:
                continue
            self._merge_attrs(rel.attributes, data)

        return entities, relations

    # -- AST scan ----------------------------------------------------------

    def _build_profile_map(
        self, root: Node, pkg_name: str | None,
    ) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for child in root.children:
            if child.type == "class_declaration":
                self._scan_class(child, pkg_name, out)
        return out

    def _scan_class(
        self,
        class_node: Node,
        pkg_name: str | None,
        out: dict[str, dict[str, object]],
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
            method_fqn = f"{class_qname}.{method_name_node.text.decode()}"
            data = self._extract_profile_condition(child)
            if data:
                out[method_fqn] = data

    def _extract_profile_condition(
        self, method_node: Node,
    ) -> dict[str, object]:
        annotations = self._collect_annotations(method_node)
        data: dict[str, object] = {}
        for a in annotations:
            if a["name"] == "Profile":
                vals = _string_or_array_arg(a["node"])  # type: ignore[arg-type]
                if vals:
                    data["profile"] = vals
            elif a["name"] == "ConditionalOnProperty":
                cond = _extract_condition_from_node(a["node"])  # type: ignore[arg-type]
                if cond is not None:
                    data["condition"] = cond
        return data

    # -- entity / relation → method_fqn mapping ----------------------------

    def _entity_method_fqn(self, ent: CodeEntity) -> str | None:
        if ent.kind == EntityKinds.SPRING_BEAN:
            if ent.qualified_name.endswith(_BEAN_SUFFIX):
                return ent.qualified_name[: -len(_BEAN_SUFFIX)]
            return None
        if ent.kind == EntityKinds.SCHEDULED_TASK:
            mf = ent.attributes.get("method_fqn")
            if isinstance(mf, str):
                return mf
            if ent.qualified_name.endswith(_SCHEDULED_SUFFIX):
                return ent.qualified_name[: -len(_SCHEDULED_SUFFIX)]
            return None
        if ent.kind == EntityKinds.HTTP_ENDPOINT:
            controller = ent.attributes.get("controller_fqn")
            handler = ent.attributes.get("handler_method")
            if isinstance(controller, str) and isinstance(handler, str):
                return f"{controller}.{handler}"
            return None
        return None

    def _relation_method_fqn(self, rel: CodeRelation) -> str | None:
        if rel.kind == RelationKinds.MAPS_URL:
            handler = rel.attributes.get("handler_method")
            if isinstance(handler, str):
                return f"{rel.source}.{handler}"
            return None
        if rel.kind in (RelationKinds.HANDLES, RelationKinds.PUBLISHES):
            return rel.source
        return None

    @staticmethod
    def _merge_attrs(attrs: dict[str, object], data: dict[str, object]) -> None:
        for k, v in data.items():
            attrs[k] = v

    # -- annotation helpers (mirror DIAnalyzer conventions) ---------------

    def _collect_annotations(self, node: Node) -> list[dict[str, object]]:
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
        return out

    @staticmethod
    def _annotation_name(node: Node) -> str:
        for c in node.children:
            if c.type == "identifier":
                return c.text.decode()
        return ""


# ---------------------------------------------------------------------------
# Module-level helpers (same shape as DIAnalyzer._string_or_array_arg / _kv_string_args)
# ---------------------------------------------------------------------------
def _string_literal_text(node: Node) -> str:
    text = node.text.decode()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _get_arg_list(annotation_node: Node) -> Node | None:
    args = annotation_node.child_by_field_name("arguments")
    if args is not None:
        return args
    for c in annotation_node.children:
        if c.type == "annotation_argument_list":
            return c
    return None


def _string_or_array_arg(annotation_node: Node) -> list[str]:
    args = _get_arg_list(annotation_node)
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


def _kv_string_args(annotation_node: Node) -> dict[str, str]:
    out: dict[str, str] = {}
    args = _get_arg_list(annotation_node)
    if args is None:
        return out
    for c in args.children:
        if c.type != "element_value_pair":
            continue
        key: str | None = None
        value: str | None = None
        for pc in c.children:
            if pc.type == "=":
                continue
            if key is None and pc.type == "identifier":
                key = pc.text.decode()
            elif key is not None and pc.type == "string_literal":
                value = _string_literal_text(pc)
                break
        if key is not None and value is not None:
            out[key] = value
    return out


def _single_string_arg(annotation_node: Node) -> str | None:
    args = _get_arg_list(annotation_node)
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


def _extract_condition_from_node(annotation_node: Node) -> str | None:
    single = _single_string_arg(annotation_node)
    if single is not None:
        return single
    pairs = _kv_string_args(annotation_node)
    name = pairs.get("name") or pairs.get("value")
    having = pairs.get("havingValue")
    if name and having is not None:
        return f"{name}={having}"
    if name:
        return name
    return None


__all__ = ("ProfileAnalyzer",)
