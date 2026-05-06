"""OD-11-B7-1 TDD — reflection_literal_resolver.

리터럴 arg 가 있는 reflection 호출 (B5-8/B7-0 `reflection_calls` marker)
을 `class_index` / `bean_index` 로 정적 해소해 `CALLS{source:static_literal}`
또는 `CALLS{source:static_unresolved}` 엣지를 emit.

Spec: `toClaude/modeling/OD-11-B7-SPEC.md` §5.
"""
from __future__ import annotations

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)
from backend.modeling.code_analysis.reflection_literal_resolver import (
    build_bean_index,
    resolve_reflection_literals,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _camel_case(n: str) -> str:
    if len(n) >= 2 and n[0].isupper() and n[1].isupper():
        return n
    return n[0].lower() + n[1:] if n else n


def _class(fqn, stereotype=None, bean_name=None):
    name = fqn.rsplit(".", 1)[-1]
    entities = [
        CodeEntity(
            kind=EntityKinds.CLASS,
            qualified_name=fqn,
            name=name,
            file_path=f"{name}.java",
            line_start=1,
            line_end=1,
        ),
    ]
    if stereotype is not None:
        attrs: dict[str, object] = {
            "stereotype": stereotype,
            "bean_name": bean_name if bean_name is not None else _camel_case(name),
        }
        entities.append(
            CodeEntity(
                kind=EntityKinds.SPRING_BEAN,
                qualified_name=fqn,
                name=name,
                file_path=f"{name}.java",
                line_start=1,
                line_end=1,
                attributes=attrs,
            )
        )
    return entities


def _bean_method(class_fqn, method_name, bean_name=None):
    # Configuration 안의 @Bean 메서드 → SPRING_BEAN qn = <class>.<method>#bean
    attrs: dict[str, object] = {"stereotype": "Bean"}
    if bean_name is not None:
        attrs["bean_name"] = bean_name
    else:
        attrs["bean_name"] = method_name
    return CodeEntity(
        kind=EntityKinds.SPRING_BEAN,
        qualified_name=f"{class_fqn}.{method_name}#bean",
        name=method_name,
        file_path=f"{class_fqn.rsplit('.', 1)[-1]}.java",
        line_start=1,
        line_end=1,
        parent=class_fqn,
        attributes=attrs,
    )


def _method_with_reflection(fqn, reflection_calls):
    return CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name=fqn,
        name=fqn.rsplit(".", 1)[-1],
        file_path="Caller.java",
        line_start=1,
        line_end=1,
        attributes={"reflection_calls": list(reflection_calls)},
    )


def _pr(file_path, entities, relations=()):
    return ParseResult(
        entities=list(entities),
        relations=list(relations),
        file_path=file_path,
        language="java",
    )


def _indices(parse_results):
    class_index: dict[str, CodeEntity] = {}
    for pr in parse_results:
        for e in pr.entities:
            if e.kind in (EntityKinds.CLASS, EntityKinds.INTERFACE, EntityKinds.ENUM):
                class_index[e.qualified_name] = e
    return class_index


# ---------------------------------------------------------------------------
# build_bean_index
# ---------------------------------------------------------------------------
def test_bean_index_component_with_explicit_name() -> None:
    prs = [
        _pr("Foo.java", _class("com.x.FooShipper", stereotype="Component", bean_name="fooShipper")),
    ]
    idx = build_bean_index(prs)
    assert idx["fooShipper"].qualified_name == "com.x.FooShipper"


def test_bean_index_service_camelcase_fallback() -> None:
    # stereotype 있음, bean_name 없음 → camelCase fallback
    prs = [
        _pr("OrderService.java", _class("com.x.OrderService", stereotype="Service")),
    ]
    idx = build_bean_index(prs)
    assert "orderService" in idx
    assert idx["orderService"].qualified_name == "com.x.OrderService"


def test_bean_index_bean_method() -> None:
    # @Bean method without explicit name → method name
    class_entities = _class("com.x.Cfg", stereotype="Configuration", bean_name="cfg")
    class_entities.append(_bean_method("com.x.Cfg", "dataSource"))
    prs = [_pr("Cfg.java", class_entities)]
    idx = build_bean_index(prs)
    assert "dataSource" in idx
    assert idx["dataSource"].qualified_name == "com.x.Cfg.dataSource#bean"


def test_bean_index_bean_method_with_explicit_name() -> None:
    class_entities = _class("com.x.Cfg", stereotype="Configuration", bean_name="cfg")
    class_entities.append(_bean_method("com.x.Cfg", "dsBean", bean_name="customDs"))
    prs = [_pr("Cfg.java", class_entities)]
    idx = build_bean_index(prs)
    assert "customDs" in idx
    assert "dsBean" not in idx  # only custom name registered


# ---------------------------------------------------------------------------
# resolve_reflection_literals — getBean
# ---------------------------------------------------------------------------
def test_resolve_get_bean_literal_match() -> None:
    bean_entities = _class("com.x.FooShipper", stereotype="Component", bean_name="fooShipper")
    caller = _method_with_reflection(
        "com.x.Orders.dispatch",
        [{"api": "getBean", "arg": "fooShipper", "arg_kind": "literal", "line": 15}],
    )
    prs = [
        _pr("FooShipper.java", bean_entities),
        _pr("Orders.java", [caller]),
    ]
    class_index = _indices(prs)
    bean_index = build_bean_index(prs)
    resolve_reflection_literals(prs, class_index, bean_index)

    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    e = edges[0]
    assert e.source == "com.x.Orders.dispatch"
    assert e.target == "com.x.FooShipper"
    assert e.attributes["source"] == "static_literal"
    assert e.attributes["confidence"] == 0.9
    assert e.attributes["api"] == "getBean"
    assert e.attributes["arg"] == "fooShipper"
    assert e.attributes["line"] == 15


def test_resolve_get_bean_literal_camelcase_match() -> None:
    bean_entities = _class("com.x.OrderService", stereotype="Service")
    caller = _method_with_reflection(
        "com.x.Web.boot",
        [{"api": "getBean", "arg": "orderService", "arg_kind": "literal", "line": 3}],
    )
    prs = [
        _pr("OrderService.java", bean_entities),
        _pr("Web.java", [caller]),
    ]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    assert edges[0].target == "com.x.OrderService"
    assert edges[0].attributes["source"] == "static_literal"


def test_resolve_get_bean_literal_miss() -> None:
    caller = _method_with_reflection(
        "com.x.Orders.dispatch",
        [{"api": "getBean", "arg": "nonExistent", "arg_kind": "literal", "line": 22}],
    )
    prs = [_pr("Orders.java", [caller])]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))

    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    e = edges[0]
    assert e.target == "<reflection-site>"
    assert e.attributes["source"] == "static_unresolved"
    assert e.attributes["confidence"] == 0.4
    assert e.attributes["reason"] == "bean_not_found"
    assert e.attributes["arg"] == "nonExistent"


# ---------------------------------------------------------------------------
# resolve_reflection_literals — Class.forName
# ---------------------------------------------------------------------------
def test_resolve_class_forname_fqn_match() -> None:
    target_entities = _class("com.acme.FooShipper")  # no stereotype
    caller = _method_with_reflection(
        "com.x.Loader.load",
        [{"api": "Class.forName", "arg": "com.acme.FooShipper", "arg_kind": "literal", "line": 8}],
    )
    prs = [
        _pr("FooShipper.java", target_entities),
        _pr("Loader.java", [caller]),
    ]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    e = edges[0]
    assert e.target == "com.acme.FooShipper"
    assert e.attributes["source"] == "static_literal"
    assert e.attributes["confidence"] == 0.9
    assert e.attributes["api"] == "Class.forName"


def test_resolve_class_forname_fqn_miss() -> None:
    caller = _method_with_reflection(
        "com.x.Loader.load",
        [{"api": "Class.forName", "arg": "invalid.ClassName", "arg_kind": "literal", "line": 9}],
    )
    prs = [_pr("Loader.java", [caller])]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    e = edges[0]
    assert e.target == "<reflection-site>"
    assert e.attributes["source"] == "static_unresolved"
    assert e.attributes["reason"] == "class_not_found"


# ---------------------------------------------------------------------------
# resolve_reflection_literals — non-literal arg_kind: skip in B7-1
# ---------------------------------------------------------------------------
def test_variable_arg_kind_skipped() -> None:
    caller = _method_with_reflection(
        "com.x.Orders.dispatch",
        [{"api": "getBean", "arg": "shipperName", "arg_kind": "variable", "line": 15}],
    )
    prs = [_pr("Orders.java", [caller])]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert edges == []


def test_type_arg_kind_skipped() -> None:
    caller = _method_with_reflection(
        "com.x.Orders.dispatch",
        [{"api": "getBean", "arg": "FooShipper", "arg_kind": "type", "line": 15}],
    )
    prs = [_pr("Orders.java", [caller])]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert edges == []


def test_concat_arg_kind_skipped() -> None:
    caller = _method_with_reflection(
        "com.x.Loader.load",
        [{"api": "Class.forName", "arg": '"com.acme." + suffix', "arg_kind": "concat", "line": 5}],
    )
    prs = [_pr("Loader.java", [caller])]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert edges == []


# ---------------------------------------------------------------------------
# resolve_reflection_literals — getMethod/getField: defer (no edge, no crash)
# ---------------------------------------------------------------------------
def test_get_method_literal_skipped_in_b7_1() -> None:
    # B7-1 defers getMethod resolution (requires receiver-type tracking).
    caller = _method_with_reflection(
        "com.x.Orders.dispatch",
        [{"api": "getMethod", "arg": "calculate", "arg_kind": "literal", "line": 15}],
    )
    prs = [_pr("Orders.java", [caller])]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = [r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS]
    assert edges == []


# ---------------------------------------------------------------------------
# Multi-site / multi-method
# ---------------------------------------------------------------------------
def test_two_methods_same_bean_emit_two_edges() -> None:
    bean_entities = _class("com.x.FooShipper", stereotype="Component", bean_name="fooShipper")
    caller_a = _method_with_reflection(
        "com.x.Orders.first",
        [{"api": "getBean", "arg": "fooShipper", "arg_kind": "literal", "line": 10}],
    )
    caller_b = _method_with_reflection(
        "com.x.Orders.second",
        [{"api": "getBean", "arg": "fooShipper", "arg_kind": "literal", "line": 25}],
    )
    prs = [
        _pr("FooShipper.java", bean_entities),
        _pr("Orders.java", [caller_a, caller_b]),
    ]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    edges = sorted(
        (r for pr in prs for r in pr.relations if r.kind == RelationKinds.CALLS),
        key=lambda r: r.source,
    )
    assert len(edges) == 2
    assert edges[0].source == "com.x.Orders.first"
    assert edges[1].source == "com.x.Orders.second"
    for e in edges:
        assert e.target == "com.x.FooShipper"
        assert e.attributes["source"] == "static_literal"


# ---------------------------------------------------------------------------
# Method with no reflection_calls marker: no change
# ---------------------------------------------------------------------------
def test_method_without_marker_is_noop() -> None:
    plain = CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name="com.x.Plain.run",
        name="run",
        file_path="Plain.java",
        line_start=1,
        line_end=1,
    )
    prs = [_pr("Plain.java", [plain])]
    resolve_reflection_literals(prs, _indices(prs), build_bean_index(prs))
    assert all(r.kind != RelationKinds.CALLS for pr in prs for r in pr.relations)
