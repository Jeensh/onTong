"""OD-11-B6-2 : Spring BeanUtilsAnalyzer.

Detect `BeanUtils.copyProperties` / `ModelMapper.map` call sites and attach
METHOD/CONSTRUCTOR attribute marker `beanutils_calls` for B6-4 `CrossFileEnricher`
to resolve field intersection into concrete `PROPAGATES_TO` edges.

라이브러리 판별 (import 기반):
  - Spring       `org.springframework.beans.BeanUtils.copyProperties(src, dst, ...)`
  - Apache       `org.apache.commons.beanutils.BeanUtils.copyProperties(dst, src)`  ← 인자 순서 반대!
  - ModelMapper  `org.modelmapper.ModelMapper.map(src, Dst.class)` / `.map(src, dst)`
  - Static import (`import static ...BeanUtils.copyProperties` / `...BeanUtils.*`) → bare `copyProperties(...)` 감지

출력:
  `method/ctor.attributes["beanutils_calls"] = [
      {"library": "spring"|"apache"|"modelmapper"|"unknown",
       "src_type": <fqn|simple>, "dst_type": <fqn|simple>,
       "ignore": [str, ...], "confidence": 0.7|0.5, "line": N},
      ...
  ]`

설계:
  - `analyze()` 는 Protocol 호환을 위해 `([], [])` 반환 (B5-6/B5-8 과 같은 post-processor 패턴).
  - `enrich(entities, relations, tree, pkg_name)` 에서 AST 스캔 →
    클래스/메서드/생성자 별 scope 맵 (params + locals + fields + `this`) 구축 →
    호출 분류 → 기존 METHOD/CONSTRUCTOR entity `.attributes` 에 merge.
  - 실제 `PROPAGATES_TO` 엣지 승격은 B6-4 에서 import 맵 + class/field index 로 확정.
"""

from __future__ import annotations

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
)

_SPRING_FQN = "org.springframework.beans.BeanUtils"
_APACHE_FQN = "org.apache.commons.beanutils.BeanUtils"
_MODELMAPPER_FQN = "org.modelmapper.ModelMapper"

_COPY_PROPS = "copyProperties"
_MAP = "map"

_UNRESOLVED = "<unresolved>"


class BeanUtilsAnalyzer:
    """`BeanUtils.copyProperties` / `ModelMapper.map` call marker for METHOD/CONSTRUCTOR entities."""

    # -- Protocol entry : analyze() is a no-op (post-processor pattern) -----

    def analyze(
        self,
        tree: object | None,
        content: bytes,
        file_path: str,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        return [], []

    # -- Post-processor : attach markers to existing METHOD/CONSTRUCTOR -----

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
        import_map, static_lib = self._build_imports(root)

        call_map: dict[str, list[dict[str, object]]] = {}
        for child in root.children:
            if child.type in ("class_declaration", "interface_declaration", "enum_declaration"):
                self._scan_type(
                    type_node=child,
                    pkg_name=pkg_name,
                    import_map=import_map,
                    static_lib=static_lib,
                    parent_qname=None,
                    call_map=call_map,
                )
        if not call_map:
            return entities, relations
        for ent in entities:
            if ent.kind not in (EntityKinds.METHOD, EntityKinds.CONSTRUCTOR):
                continue
            calls = call_map.get(ent.qualified_name)
            if calls:
                ent.attributes["beanutils_calls"] = calls
        return entities, relations

    # -- AST scan ----------------------------------------------------------

    def _scan_type(
        self,
        type_node: Node,
        pkg_name: str | None,
        import_map: dict[str, str],
        static_lib: str | None,
        parent_qname: str | None,
        call_map: dict[str, list[dict[str, object]]],
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

        field_types = self._build_field_types(body, import_map, pkg_name)

        for member in body.children:
            if member.type == "method_declaration":
                mname = member.child_by_field_name("name")
                if mname is None:
                    continue
                method_fqn = f"{class_qname}.{mname.text.decode()}"
                scope = self._build_scope_map(
                    member, field_types, import_map, pkg_name, class_qname,
                )
                calls = self._scan_body(member, scope, import_map, static_lib)
                if calls:
                    call_map[method_fqn] = calls
            elif member.type == "constructor_declaration":
                cname = member.child_by_field_name("name")
                if cname is None:
                    continue
                ctor_fqn = f"{class_qname}.{cname.text.decode()}"
                scope = self._build_scope_map(
                    member, field_types, import_map, pkg_name, class_qname,
                )
                calls = self._scan_body(member, scope, import_map, static_lib)
                if calls:
                    call_map[ctor_fqn] = calls
            elif member.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                self._scan_type(
                    type_node=member,
                    pkg_name=pkg_name,
                    import_map=import_map,
                    static_lib=static_lib,
                    parent_qname=class_qname,
                    call_map=call_map,
                )

    def _build_field_types(
        self,
        class_body: Node,
        import_map: dict[str, str],
        pkg_name: str | None,
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in class_body.children:
            if c.type != "field_declaration":
                continue
            type_node = c.child_by_field_name("type")
            if type_node is None:
                continue
            resolved = _resolve_type(type_node.text.decode(), import_map, pkg_name)
            for cc in c.children:
                if cc.type == "variable_declarator":
                    vname = cc.child_by_field_name("name")
                    if vname is not None:
                        out[vname.text.decode()] = resolved
        return out

    def _build_scope_map(
        self,
        member_node: Node,
        field_types: dict[str, str],
        import_map: dict[str, str],
        pkg_name: str | None,
        class_qname: str,
    ) -> dict[str, str]:
        scope: dict[str, str] = dict(field_types)
        scope["this"] = class_qname
        params = member_node.child_by_field_name("parameters")
        if params is not None:
            for p in params.children:
                if p.type != "formal_parameter":
                    continue
                ptype = p.child_by_field_name("type")
                pname = p.child_by_field_name("name")
                if ptype is None or pname is None:
                    continue
                scope[pname.text.decode()] = _resolve_type(
                    ptype.text.decode(), import_map, pkg_name,
                )
        body = member_node.child_by_field_name("body")
        if body is not None:
            for n in _walk(body):
                if n.type == "local_variable_declaration":
                    ltype = n.child_by_field_name("type")
                    if ltype is None:
                        continue
                    resolved = _resolve_type(ltype.text.decode(), import_map, pkg_name)
                    for cc in n.children:
                        if cc.type == "variable_declarator":
                            vname = cc.child_by_field_name("name")
                            if vname is not None:
                                scope[vname.text.decode()] = resolved
        return scope

    def _scan_body(
        self,
        member_node: Node,
        scope: dict[str, str],
        import_map: dict[str, str],
        static_lib: str | None,
    ) -> list[dict[str, object]]:
        body = member_node.child_by_field_name("body")
        if body is None:
            return []
        out: list[dict[str, object]] = []
        for n in _walk(body):
            if n.type != "method_invocation":
                continue
            entry = self._classify(n, scope, import_map, static_lib)
            if entry is not None:
                out.append(entry)
        out.sort(key=lambda c: c["line"])  # type: ignore[arg-type, return-value]
        return out

    def _classify(
        self,
        invocation_node: Node,
        scope: dict[str, str],
        import_map: dict[str, str],
        static_lib: str | None,
    ) -> dict[str, object] | None:
        name_node = invocation_node.child_by_field_name("name")
        if name_node is None:
            return None
        method_name = name_node.text.decode()
        obj_node = invocation_node.child_by_field_name("object")

        library: str | None = None
        confidence = 0.7

        if method_name == _COPY_PROPS:
            if obj_node is None:
                # bare `copyProperties(...)` — must have matching static import
                if static_lib is None:
                    return None
                library = static_lib
            elif obj_node.type == "identifier":
                obj_text = obj_node.text.decode()
                if obj_text != "BeanUtils":
                    return None
                fqn = import_map.get("BeanUtils")
                if fqn == _SPRING_FQN:
                    library = "spring"
                elif fqn == _APACHE_FQN:
                    library = "apache"
                else:
                    library = "unknown"
                    confidence = 0.5
            else:
                return None
        elif method_name == _MAP:
            # Only accept if obj is an identifier / field_access resolving to ModelMapper type
            obj_type = _lookup_obj_type(obj_node, scope)
            if obj_type != _MODELMAPPER_FQN:
                return None
            library = "modelmapper"
        else:
            return None

        args_node = invocation_node.child_by_field_name("arguments")
        if args_node is None:
            return None
        arg_nodes = [c for c in args_node.children if c.type not in ("(", ",", ")")]
        if len(arg_nodes) < 2:
            return None

        if library == "apache":
            dst_arg, src_arg = arg_nodes[0], arg_nodes[1]
            rest = arg_nodes[2:]
        else:
            src_arg, dst_arg = arg_nodes[0], arg_nodes[1]
            rest = arg_nodes[2:]

        src_type = _resolve_arg_type(src_arg, scope)
        if library == "modelmapper":
            dst_type = _resolve_class_literal_or_arg(dst_arg, scope, import_map)
        else:
            dst_type = _resolve_arg_type(dst_arg, scope)

        ignore: list[str] = []
        if method_name == _COPY_PROPS:
            for a in rest:
                if a.type == "string_literal":
                    t = a.text.decode()
                    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
                        ignore.append(t[1:-1])
                    else:
                        ignore.append(t)

        return {
            "library": library,
            "src_type": src_type,
            "dst_type": dst_type,
            "ignore": ignore,
            "confidence": confidence,
            "line": invocation_node.start_point[0] + 1,
        }

    # -- Import map build (regular + static) -------------------------------

    @staticmethod
    def _build_imports(root: Node) -> tuple[dict[str, str], str | None]:
        """Return (simple→fqn regular imports, static_lib in {'spring','apache', None})."""
        import_map: dict[str, str] = {}
        static_lib: str | None = None
        for child in root.children:
            if child.type != "import_declaration":
                continue
            text = child.text.decode().strip()
            if not text.startswith("import"):
                continue
            body = text[len("import"):].strip()
            if body.endswith(";"):
                body = body[:-1].strip()
            is_static = body.startswith("static ")
            if is_static:
                body = body[len("static "):].strip()
            is_wildcard = body.endswith(".*")
            if is_wildcard:
                body = body[:-2].strip()
            if not body:
                continue
            if is_static:
                base = body
                if body.endswith(".copyProperties"):
                    base = body[: -len(".copyProperties")]
                if base == _SPRING_FQN:
                    static_lib = "spring"
                elif base == _APACHE_FQN:
                    static_lib = "apache"
            else:
                if is_wildcard:
                    continue  # wildcard regular import — can't map to single simple name
                simple = body.rsplit(".", 1)[-1]
                import_map[simple] = body
        return import_map, static_lib


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_type(simple: str, import_map: dict[str, str], pkg_name: str | None) -> str:
    """Simple type name → FQN via import map. Strip generics/array. Fallback: simple name."""
    if not simple:
        return _UNRESOLVED
    root = simple.split("<", 1)[0].rstrip("[]").strip()
    if not root:
        return _UNRESOLVED
    if root in import_map:
        return import_map[root]
    return root


def _resolve_arg_type(arg_node: Node, scope: dict[str, str]) -> str:
    """Identifier / this / field_access → scope type or <unresolved>."""
    if arg_node.type == "identifier":
        return scope.get(arg_node.text.decode(), _UNRESOLVED)
    if arg_node.type == "this":
        return scope.get("this", _UNRESOLVED)
    if arg_node.type == "field_access":
        field_node = arg_node.child_by_field_name("field")
        if field_node is not None:
            return scope.get(field_node.text.decode(), _UNRESOLVED)
        return _UNRESOLVED
    return _UNRESOLVED


def _resolve_class_literal_or_arg(
    arg_node: Node,
    scope: dict[str, str],
    import_map: dict[str, str],
) -> str:
    """`Dst.class` (class_literal or field_access with field='class') → FQN of Dst; else treat as instance."""
    if arg_node.type == "class_literal":
        for c in arg_node.children:
            if c.type in ("type_identifier", "scoped_type_identifier", "identifier"):
                return _resolve_type(c.text.decode(), import_map, None)
        # Fallback: strip trailing ".class" from raw text
        text = arg_node.text.decode().strip()
        if text.endswith(".class"):
            return _resolve_type(text[: -len(".class")], import_map, None)
        return _UNRESOLVED
    if arg_node.type == "field_access":
        field_node = arg_node.child_by_field_name("field")
        object_node = arg_node.child_by_field_name("object")
        if (
            field_node is not None
            and field_node.text.decode() == "class"
            and object_node is not None
        ):
            return _resolve_type(object_node.text.decode(), import_map, None)
    return _resolve_arg_type(arg_node, scope)


def _lookup_obj_type(obj_node: Node | None, scope: dict[str, str]) -> str | None:
    """Identifier / this / field_access → FQN from scope map."""
    if obj_node is None:
        return None
    if obj_node.type == "identifier":
        return scope.get(obj_node.text.decode())
    if obj_node.type == "this":
        return scope.get("this")
    if obj_node.type == "field_access":
        field_node = obj_node.child_by_field_name("field")
        if field_node is not None:
            return scope.get(field_node.text.decode())
    return None


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


__all__ = ("BeanUtilsAnalyzer",)
