"""OD-11-B5-3 : Spring HttpAnalyzer.

감지 대상:
  - @RestController / @Controller class-level 애너테이션 → controller.
  - @RequestMapping (class 또는 method), @GetMapping, @PostMapping, @PutMapping,
    @DeleteMapping, @PatchMapping → HTTP endpoint mapping.
  - 각 (HTTP method, 최종 path) 조합당 `http_endpoint` entity.
    qualified_name = `<METHOD>:<full_path>` (e.g. `GET:/api/orders/{id}`).
  - `MAPS_URL` edge : source = controller 클래스 FQN, target = endpoint qn.

엔티티 속성:
  - http_method ∈ {GET, POST, PUT, DELETE, PATCH, ANY}
  - path (combined)
  - controller_fqn, handler_method
  - controller_type ∈ {rest, mvc}
  - produces, consumes (있을 때만)

엣지 속성:
  - handler_method, path_variables, request_params (있을 때만)
"""

from __future__ import annotations

from typing import Iterable

from tree_sitter import Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    RelationKinds,
)

_SHORTCUT_HTTP_METHOD: dict[str, str] = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

_MAPPING_ANNOTATIONS: frozenset[str] = frozenset(
    {"RequestMapping", *_SHORTCUT_HTTP_METHOD.keys()}
)


class HttpAnalyzer:
    """@RestController/@Controller + mapping annotations → http_endpoint + MAPS_URL."""

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
        controller_type: str | None = None
        for a in annotations:
            if a["name"] == "RestController":
                controller_type = "rest"
                break
            if a["name"] == "Controller":
                controller_type = "mvc"
                break
        if controller_type is None:
            return

        class_path = ""
        for a in annotations:
            if a["name"] == "RequestMapping":
                class_path = self._extract_path(a["node"]) or ""  # type: ignore[arg-type]
                break

        body = node.child_by_field_name("body")
        if body is None:
            return

        for child in body.children:
            if child.type != "method_declaration":
                continue
            self._analyze_handler_method(
                child, class_qname, class_path, controller_type,
                file_path, entities, relations,
            )

    # -- method-level -------------------------------------------------------

    def _analyze_handler_method(
        self,
        node: Node,
        class_qname: str,
        class_path: str,
        controller_type: str,
        file_path: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        annotations = self._collect_annotations(node)

        mapping_anno: dict[str, object] | None = None
        for a in annotations:
            if a["name"] in _MAPPING_ANNOTATIONS:
                mapping_anno = a
                break
        if mapping_anno is None:
            return

        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        handler_method = name_node.text.decode()

        anno_name = mapping_anno["name"]
        anno_node: Node = mapping_anno["node"]  # type: ignore[assignment]

        method_path = self._extract_path(anno_node) or ""
        full_path = self._combine_paths(class_path, method_path)

        if anno_name in _SHORTCUT_HTTP_METHOD:
            http_methods: list[str] = [_SHORTCUT_HTTP_METHOD[anno_name]]  # type: ignore[index]
        else:
            methods_from_anno = self._extract_request_methods(anno_node)
            http_methods = methods_from_anno if methods_from_anno else ["ANY"]

        produces = self._extract_string_attr(anno_node, "produces")
        consumes = self._extract_string_attr(anno_node, "consumes")

        params = node.child_by_field_name("parameters")
        path_vars, req_params = self._collect_parameter_roles(params)

        for hm in http_methods:
            qn = f"{hm}:{full_path}"

            ent_attrs: dict[str, object] = {
                "http_method": hm,
                "path": full_path,
                "controller_fqn": class_qname,
                "handler_method": handler_method,
                "controller_type": controller_type,
            }
            if produces is not None:
                ent_attrs["produces"] = produces
            if consumes is not None:
                ent_attrs["consumes"] = consumes

            entities.append(CodeEntity(
                kind=EntityKinds.HTTP_ENDPOINT,
                qualified_name=qn,
                name=handler_method,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                parent=class_qname,
                attributes=ent_attrs,
            ))

            edge_attrs: dict[str, object] = {"handler_method": handler_method}
            if path_vars:
                edge_attrs["path_variables"] = path_vars
            if req_params:
                edge_attrs["request_params"] = req_params

            relations.append(CodeRelation(
                kind=RelationKinds.MAPS_URL,
                source=class_qname,
                target=qn,
                file_path=file_path,
                line=node.start_point[0] + 1,
                attributes=edge_attrs,
            ))

    # -- path helpers -------------------------------------------------------

    @staticmethod
    def _combine_paths(class_path: str, method_path: str) -> str:
        cp = class_path.strip()
        mp = method_path.strip()
        if cp and not cp.startswith("/"):
            cp = "/" + cp
        if cp.endswith("/") and len(cp) > 1:
            cp = cp[:-1]
        if mp and not mp.startswith("/"):
            mp = "/" + mp
        if mp.endswith("/") and len(mp) > 1:
            mp = mp[:-1]
        combined = cp + mp
        if not combined:
            return "/"
        return combined

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

    def _extract_path(self, annotation_node: Node) -> str | None:
        """Extract path from positional, value=, or path= attribute."""
        args = self._args_node(annotation_node)
        if args is None:
            return None
        for c in args.children:
            if c.type == "string_literal":
                return _string_literal_text(c)
            if c.type == "element_value_array_initializer":
                for x in c.children:
                    if x.type == "string_literal":
                        return _string_literal_text(x)
        for c in args.children:
            if c.type != "element_value_pair":
                continue
            key, val = self._kv_pair(c)
            if key in ("value", "path") and isinstance(val, str):
                return val
            if key in ("value", "path") and isinstance(val, list) and val:
                return val[0]
        return None

    def _extract_string_attr(self, annotation_node: Node, key: str) -> str | None:
        args = self._args_node(annotation_node)
        if args is None:
            return None
        for c in args.children:
            if c.type != "element_value_pair":
                continue
            k, val = self._kv_pair(c)
            if k == key and isinstance(val, str):
                return val
        return None

    def _extract_request_methods(self, annotation_node: Node) -> list[str]:
        """@RequestMapping(method=RequestMethod.GET) or method={RequestMethod.GET, POST}."""
        args = self._args_node(annotation_node)
        if args is None:
            return []
        for c in args.children:
            if c.type != "element_value_pair":
                continue
            key = None
            value_node: Node | None = None
            for pc in c.children:
                if pc.type == "identifier" and key is None:
                    key = pc.text.decode()
                elif pc.type not in ("=",):
                    value_node = pc
            if key != "method" or value_node is None:
                continue
            if value_node.type == "element_value_array_initializer":
                out: list[str] = []
                for x in value_node.children:
                    if x.type not in ("identifier", "scoped_identifier", "field_access"):
                        continue
                    short = _enum_short_name(x)
                    if short:
                        out.append(short)
                return out
            short = _enum_short_name(value_node)
            return [short] if short else []
        return []

    @staticmethod
    def _args_node(annotation_node: Node) -> Node | None:
        args = annotation_node.child_by_field_name("arguments")
        if args is not None:
            return args
        for c in annotation_node.children:
            if c.type == "annotation_argument_list":
                return c
        return None

    @staticmethod
    def _kv_pair(pair_node: Node) -> tuple[str | None, object | None]:
        key: str | None = None
        value: object | None = None
        for pc in pair_node.children:
            if pc.type == "identifier" and key is None:
                key = pc.text.decode()
            elif pc.type == "string_literal":
                value = _string_literal_text(pc)
            elif pc.type == "element_value_array_initializer":
                arr: list[str] = []
                for x in pc.children:
                    if x.type == "string_literal":
                        arr.append(_string_literal_text(x))
                value = arr
        return key, value

    # -- parameter helpers -------------------------------------------------

    def _collect_parameter_roles(
        self, params_node: Node | None,
    ) -> tuple[list[str], list[str]]:
        path_vars: list[str] = []
        req_params: list[str] = []
        if params_node is None:
            return path_vars, req_params
        for p in params_node.children:
            if p.type != "formal_parameter":
                continue
            p_anns = self._collect_annotations(p)
            name = self._param_name(p)
            if not name:
                continue
            if any(a["name"] == "PathVariable" for a in p_anns):
                path_vars.append(name)
            elif any(a["name"] == "RequestParam" for a in p_anns):
                req_params.append(name)
        return path_vars, req_params

    @staticmethod
    def _param_name(formal: Node) -> str | None:
        for c in formal.children:
            if c.type == "identifier":
                return c.text.decode()
        return None


def _enum_short_name(node: Node) -> str:
    """RequestMethod.GET → 'GET', GET → 'GET', scoped_identifier → last segment."""
    if node.type == "identifier":
        return node.text.decode()
    if node.type == "scoped_identifier" or node.type == "field_access":
        text = node.text.decode()
        return text.rsplit(".", 1)[-1]
    # Fallback: text after last dot
    text = node.text.decode().strip()
    return text.rsplit(".", 1)[-1] if text else ""


def _string_literal_text(node: Node) -> str:
    for c in node.children:
        if c.type == "string_fragment":
            return c.text.decode()
    text = node.text.decode()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


__all__ = ("HttpAnalyzer",)
