"""OD-11-B5-8 : Spring ReflectionAnalyzer (static call-site marker).

감지 대상 (method/constructor body 내 호출):
  - `Class.forName("com.x.MyClass")` — static class lookup
  - `Proxy.newProxyInstance(loader, ifaces, handler)` — JDK dynamic proxy
  - `ctx.getBean("name")` — Spring ApplicationContext bean lookup by name
  - `clazz.getMethod("x")` / `clazz.getDeclaredMethod("x")` — method lookup
  - `clazz.getField("x")` / `clazz.getDeclaredField("x")` — field lookup

출력 포맷 (METHOD / CONSTRUCTOR entity 속성에 merge):
  - `reflection_calls = [{"api": "...", "arg": "...", "arg_kind": "...", "line": N}, ...]`
  - `api` 규약: static 호출 `Class.forName` / `Proxy.newProxyInstance` 는 prefix 포함,
    나머지는 bare method name (getBean/getMethod/getDeclaredMethod/getField/getDeclaredField).
  - `arg` 는 항상 소스 텍스트 (B7 downstream resolver 가 literal/variable/concat/type 별도 처리):
      * string_literal  → quote 제거한 텍스트
      * identifier      → 변수/필드 이름
      * class_literal   → `Foo.class` 에서 `Foo`
      * binary (`+`)    → 원본 표현식 텍스트 그대로
      * 그 외           → 원본 텍스트
  - `arg_kind` ∈ {"literal","variable","concat","type","other"} — B7-1 literal resolver,
    B7-2 runtime collector 가 이 필드 기준으로 3-tier routing.

설계:
  - `analyze()` 는 Protocol 호환을 위해 `([], [])` 반환.
  - `enrich(entities, relations, tree, pkg_name)` post-pass 에서 AST 스캔 →
    method FQN 별 reflection call 리스트 구축 → METHOD/CONSTRUCTOR entity 속성 보강.
  - PoC 범위: `Method.invoke` / `Constructor.newInstance` 는 noise 가 커서 제외
    (B7 런타임 collector 에서 정밀 감지).
"""

from __future__ import annotations

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
)

# Reflection API names we track.
# 키 = tree-sitter method_invocation name, 값 = api 문자열 (prefix 여부 결정)
_BARE_METHOD_NAMES: frozenset[str] = frozenset({
    "getBean",
    "getMethod",
    "getDeclaredMethod",
    "getField",
    "getDeclaredField",
})

# static API : method name → required object identifier → api prefix
_STATIC_METHODS: dict[str, tuple[str, str]] = {
    "forName": ("Class", "Class.forName"),
    "newProxyInstance": ("Proxy", "Proxy.newProxyInstance"),
}

_DYNAMIC = "<dynamic>"

# Sentinel for missing/malformed arg list — callers still see a non-empty arg.
_MISSING = "<missing>"


class ReflectionAnalyzer:
    """static reflection call-site marker — METHOD/CONSTRUCTOR 속성에 `reflection_calls` 주입."""

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
        call_map = self._build_call_map(root, pkg_name)
        if not call_map:
            return entities, relations

        for ent in entities:
            if ent.kind not in (EntityKinds.METHOD, EntityKinds.CONSTRUCTOR):
                continue
            calls = call_map.get(ent.qualified_name)
            if not calls:
                continue
            ent.attributes["reflection_calls"] = calls

        return entities, relations

    # -- AST scan ----------------------------------------------------------

    def _build_call_map(
        self, root: Node, pkg_name: str | None,
    ) -> dict[str, list[dict[str, object]]]:
        """Walk every top-level class_declaration and collect per-method reflection calls."""
        out: dict[str, list[dict[str, object]]] = {}
        for child in root.children:
            if child.type == "class_declaration":
                self._scan_type(child, pkg_name, out, parent_qname=None)
            elif child.type in ("interface_declaration", "enum_declaration"):
                self._scan_type(child, pkg_name, out, parent_qname=None)
        return out

    def _scan_type(
        self,
        type_node: Node,
        pkg_name: str | None,
        out: dict[str, list[dict[str, object]]],
        parent_qname: str | None,
    ) -> None:
        name_node = type_node.child_by_field_name("name")
        if name_node is None:
            return
        class_name = name_node.text.decode()
        if parent_qname:
            class_qname = f"{parent_qname}.{class_name}"
        elif pkg_name:
            class_qname = f"{pkg_name}.{class_name}"
        else:
            class_qname = class_name

        body = type_node.child_by_field_name("body")
        if body is None:
            return

        for member in body.children:
            if member.type == "method_declaration":
                method_name_node = member.child_by_field_name("name")
                if method_name_node is None:
                    continue
                method_fqn = f"{class_qname}.{method_name_node.text.decode()}"
                calls = self._scan_body(member)
                if calls:
                    out[method_fqn] = calls
            elif member.type == "constructor_declaration":
                ctor_name_node = member.child_by_field_name("name")
                if ctor_name_node is None:
                    continue
                method_fqn = f"{class_qname}.{ctor_name_node.text.decode()}"
                calls = self._scan_body(member)
                if calls:
                    out[method_fqn] = calls
            elif member.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                self._scan_type(member, pkg_name, out, parent_qname=class_qname)

    def _scan_body(self, member_node: Node) -> list[dict[str, object]]:
        """Walk every descendant method_invocation and collect matching reflection calls."""
        body = member_node.child_by_field_name("body")
        if body is None:
            return []
        calls: list[dict[str, object]] = []
        for node in _walk(body):
            if node.type != "method_invocation":
                continue
            entry = self._classify_invocation(node)
            if entry is not None:
                calls.append(entry)
        calls.sort(key=lambda c: c["line"])  # type: ignore[arg-type, return-value]
        return calls

    @staticmethod
    def _classify_invocation(node: Node) -> dict[str, object] | None:
        """Return `{api, arg, line}` if invocation matches a tracked reflection API."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        method_name = name_node.text.decode()

        api: str | None = None
        if method_name in _STATIC_METHODS:
            required_obj, prefixed_api = _STATIC_METHODS[method_name]
            obj_node = node.child_by_field_name("object")
            if (
                obj_node is not None
                and obj_node.type == "identifier"
                and obj_node.text.decode() == required_obj
            ):
                api = prefixed_api
        elif method_name in _BARE_METHOD_NAMES:
            api = method_name

        if api is None:
            return None

        arg, arg_kind = _first_arg_value(node)
        return {
            "api": api,
            "arg": arg,
            "arg_kind": arg_kind,
            "line": node.start_point[0] + 1,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _first_arg_value(invocation_node: Node) -> tuple[str, str]:
    """Classify the first argument.

    Returns (arg_text, arg_kind) where arg_kind ∈
    {"literal","variable","concat","type","other"}.

    Semantics:
      - string_literal            → ("unquoted", "literal")
      - identifier                → (ident,       "variable")
      - class_literal `Foo.class` → ("Foo",       "type")
      - binary_expression with `+`→ (source text, "concat")
      - everything else           → (source text, "other")
    """
    args = invocation_node.child_by_field_name("arguments")
    if args is None:
        return _MISSING, "other"
    for c in args.children:
        if c.type in ("(", ",", ")"):
            continue
        return _classify_arg_node(c)
    return _MISSING, "other"


def _classify_arg_node(node: Node) -> tuple[str, str]:
    """Map a tree-sitter argument node to (arg_text, arg_kind)."""
    ntype = node.type

    if ntype == "string_literal":
        text = node.text.decode()
        if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            return text[1:-1], "literal"
        return text, "literal"

    if ntype == "identifier":
        return node.text.decode(), "variable"

    if ntype == "class_literal":
        # tree-sitter-java: class_literal wraps a type_identifier / scoped_type_identifier.
        # Fall back to text-strip of ".class" suffix.
        raw = node.text.decode().strip()
        if raw.endswith(".class"):
            return raw[: -len(".class")], "type"
        return raw, "type"

    if ntype == "binary_expression":
        op_node = node.child_by_field_name("operator")
        op = op_node.text.decode() if op_node is not None else ""
        text = node.text.decode()
        if op == "+":
            return text, "concat"
        return text, "other"

    return node.text.decode(), "other"


def _walk(node: Node):
    """Depth-first traversal of every descendant node."""
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


__all__ = ("ReflectionAnalyzer",)
