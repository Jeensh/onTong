"""OD-11-B5-3 : Spring HttpAnalyzer — @RestController / @RequestMapping / 5 HTTP shortcut.

감지 대상:
  - @RestController / @Controller class-level 애너테이션 → controller.
  - @RequestMapping (class 또는 method), @GetMapping, @PostMapping, @PutMapping, @DeleteMapping, @PatchMapping (method).
  - 각 (HTTP method, 최종 path) 조합당 `http_endpoint` entity emit. qn = `<METHOD>:<full_path>`.
  - `MAPS_URL` edge : source = controller 클래스 FQN, target = http_endpoint qn.

엔티티 속성:
  - http_method ∈ {GET, POST, PUT, DELETE, PATCH, ANY}
  - path (combined)
  - controller_fqn, handler_method
  - controller_type ∈ {rest, mvc}
  - produces, consumes (있을 때만)

엣지 속성:
  - handler_method
  - path_variables, request_params (있을 때만)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import (
    EntityKinds,
    RelationKinds,
)
from backend.modeling.code_analysis.spring import (
    AopAnalyzer,
    DIAnalyzer,
    HttpAnalyzer,
)

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _run(src: str, pkg_name: str | None = "com.x", file_path: str = "X.java"):
    tree = _parse(src)
    a = HttpAnalyzer()
    return a.analyze(tree=tree, content=src.encode(), file_path=file_path, pkg_name=pkg_name)


# ---------------------------------------------------------------------------
# Controller detection
# ---------------------------------------------------------------------------
def test_rest_controller_method_produces_endpoint() -> None:
    src = """
@RestController
public class OrderController {
    @GetMapping("/orders")
    public List<Order> list() { return null; }
}
"""
    entities, relations = _run(src)
    eps = [e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT]
    assert len(eps) == 1
    ep = eps[0]
    assert ep.qualified_name == "GET:/orders"
    assert ep.name == "list"
    assert ep.attributes["http_method"] == "GET"
    assert ep.attributes["path"] == "/orders"
    assert ep.attributes["controller_fqn"] == "com.x.OrderController"
    assert ep.attributes["handler_method"] == "list"
    assert ep.attributes["controller_type"] == "rest"

    maps = [r for r in relations if r.kind == RelationKinds.MAPS_URL]
    assert len(maps) == 1
    assert maps[0].source == "com.x.OrderController"
    assert maps[0].target == "GET:/orders"
    assert maps[0].attributes["handler_method"] == "list"


def test_mvc_controller_type_mvc() -> None:
    src = """
@Controller
public class PageController {
    @GetMapping("/home")
    public String home() { return "home"; }
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["controller_type"] == "mvc"


def test_plain_class_with_mapping_ignored() -> None:
    src = """
public class Utils {
    @GetMapping("/x")
    public void x() {}
}
"""
    entities, relations = _run(src)
    assert entities == []
    assert relations == []


# ---------------------------------------------------------------------------
# 5 HTTP method shortcuts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("annotation, http_method", [
    ("@GetMapping", "GET"),
    ("@PostMapping", "POST"),
    ("@PutMapping", "PUT"),
    ("@DeleteMapping", "DELETE"),
    ("@PatchMapping", "PATCH"),
])
def test_http_method_shortcut(annotation: str, http_method: str) -> None:
    src = f"""
@RestController
public class C {{
    {annotation}("/r")
    public void h() {{}}
}}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["http_method"] == http_method
    assert ep.qualified_name == f"{http_method}:/r"


# ---------------------------------------------------------------------------
# Path combining (class + method)
# ---------------------------------------------------------------------------
def test_class_request_mapping_prefix_combined_with_method_path() -> None:
    src = """
@RestController
@RequestMapping("/api")
public class OrderController {
    @GetMapping("/orders")
    public void list() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["path"] == "/api/orders"
    assert ep.qualified_name == "GET:/api/orders"


def test_class_prefix_trailing_slash_normalized() -> None:
    src = """
@RestController
@RequestMapping("/api/")
public class C {
    @GetMapping("/orders")
    public void list() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["path"] == "/api/orders"


def test_method_path_without_leading_slash_normalized() -> None:
    src = """
@RestController
@RequestMapping("/api")
public class C {
    @GetMapping("orders")
    public void list() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["path"] == "/api/orders"


def test_no_class_prefix_uses_method_path_only() -> None:
    src = """
@RestController
public class C {
    @GetMapping("/orders")
    public void list() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["path"] == "/orders"


def test_empty_method_path_uses_class_prefix() -> None:
    src = """
@RestController
@RequestMapping("/api/health")
public class C {
    @GetMapping
    public String check() { return "ok"; }
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["path"] == "/api/health"


# ---------------------------------------------------------------------------
# @RequestMapping method array
# ---------------------------------------------------------------------------
def test_request_mapping_with_method_enum() -> None:
    src = """
@RestController
public class C {
    @RequestMapping(value="/x", method=RequestMethod.POST)
    public void h() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["http_method"] == "POST"


def test_request_mapping_with_method_array_emits_multiple_endpoints() -> None:
    src = """
@RestController
public class C {
    @RequestMapping(value="/x", method={RequestMethod.GET, RequestMethod.POST})
    public void h() {}
}
"""
    entities, _ = _run(src)
    eps = [e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT]
    methods = {e.attributes["http_method"] for e in eps}
    assert methods == {"GET", "POST"}
    qns = {e.qualified_name for e in eps}
    assert qns == {"GET:/x", "POST:/x"}


def test_request_mapping_without_method_is_any() -> None:
    """method 지정 없이 @RequestMapping(path) 단독 → Spring 실제 동작은 모든 HTTP method 허용.
    PoC 에선 http_method='ANY' 로 단일 endpoint 기록."""
    src = """
@RestController
public class C {
    @RequestMapping("/x")
    public void h() {}
}
"""
    entities, _ = _run(src)
    eps = [e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT]
    assert len(eps) == 1
    assert eps[0].attributes["http_method"] == "ANY"


# ---------------------------------------------------------------------------
# Path attribute forms (value= / path= / positional)
# ---------------------------------------------------------------------------
def test_mapping_with_value_keyword() -> None:
    src = """
@RestController
public class C {
    @GetMapping(value="/x")
    public void h() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["path"] == "/x"


def test_mapping_with_path_keyword() -> None:
    src = """
@RestController
public class C {
    @GetMapping(path="/x")
    public void h() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["path"] == "/x"


# ---------------------------------------------------------------------------
# produces / consumes
# ---------------------------------------------------------------------------
def test_produces_attribute_captured() -> None:
    src = """
@RestController
public class C {
    @GetMapping(value="/x", produces="application/json")
    public void h() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["produces"] == "application/json"


def test_consumes_attribute_captured() -> None:
    src = """
@RestController
public class C {
    @PostMapping(value="/x", consumes="application/xml")
    public void h() {}
}
"""
    entities, _ = _run(src)
    ep = next(e for e in entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert ep.attributes["consumes"] == "application/xml"


# ---------------------------------------------------------------------------
# Path variables / request params
# ---------------------------------------------------------------------------
def test_path_variable_recorded_on_edge() -> None:
    src = """
@RestController
public class C {
    @GetMapping("/orders/{id}")
    public Order get(@PathVariable Long id) { return null; }
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.MAPS_URL)
    assert r.attributes["path_variables"] == ["id"]


def test_request_param_recorded_on_edge() -> None:
    src = """
@RestController
public class C {
    @GetMapping("/search")
    public List<Order> search(@RequestParam String q) { return null; }
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.MAPS_URL)
    assert r.attributes["request_params"] == ["q"]


def test_path_variable_and_request_param_combined() -> None:
    src = """
@RestController
public class C {
    @GetMapping("/orders/{id}/items")
    public List<Item> items(@PathVariable Long id, @RequestParam String filter) { return null; }
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.MAPS_URL)
    assert r.attributes["path_variables"] == ["id"]
    assert r.attributes["request_params"] == ["filter"]


# ---------------------------------------------------------------------------
# Integration with JavaParser
# ---------------------------------------------------------------------------
def test_java_parser_accepts_http_analyzer() -> None:
    src = """
package com.x;
@RestController
public class OrderController {
    @GetMapping("/orders")
    public void list() {}
}
"""
    parser = JavaParser(spring_analyzers=[HttpAnalyzer()])
    result = parser.parse_file(Path("OrderController.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.HTTP_ENDPOINT in kinds
    rel_kinds = {r.kind for r in result.relations}
    assert RelationKinds.MAPS_URL in rel_kinds


def test_java_parser_with_di_aop_http_triple() -> None:
    """DIAnalyzer + AopAnalyzer + HttpAnalyzer 동시 주입 동작."""
    src = """
package com.x;
@RestController
@RequestMapping("/api")
public class OrderController {
    @Autowired
    private OrderService svc;

    @GetMapping("/orders")
    public void list() {}
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), AopAnalyzer(), HttpAnalyzer()])
    result = parser.parse_file(Path("OrderController.java"), src)
    kinds = {e.kind for e in result.entities}
    # @RestController 는 DIAnalyzer 에선 stereotype 으로 인식하지 않지만 @RestController 는 포함됨
    assert EntityKinds.SPRING_BEAN in kinds  # from DIAnalyzer (RestController)
    assert EntityKinds.HTTP_ENDPOINT in kinds  # from HttpAnalyzer
    rel_kinds = {r.kind for r in result.relations}
    assert RelationKinds.AUTOWIRES in rel_kinds  # from DIAnalyzer
    assert RelationKinds.MAPS_URL in rel_kinds   # from HttpAnalyzer


def test_java_parser_without_http_analyzer_no_endpoints() -> None:
    src = "package com.x; @RestController public class C { @GetMapping(\"/x\") public void h() {} }"
    result = JavaParser().parse_file(Path("C.java"), src)
    assert not any(e.kind == EntityKinds.HTTP_ENDPOINT for e in result.entities)
