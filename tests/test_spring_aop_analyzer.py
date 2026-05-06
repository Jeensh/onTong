"""OD-11-B5-2 : Spring AopAnalyzer — @Aspect + 5 advice + pointcut target 유추.

감지 대상:
  - @Aspect class → `aspect` entity (qualified_name = class FQN).
  - @Before / @After / @Around / @AfterReturning / @AfterThrowing on methods inside @Aspect
    → `INTERCEPTS` edge (source = aspect FQN, target = pointcut 이 가리키는 FQN or `<unresolved>`).
  - attributes.advice_type ∈ {before, after, around, after_returning, after_throwing}.
  - attributes.pointcut_expr = 원본 포인트컷 표현식.
  - attributes.pointcut_kind ∈ {execution, within, annotation, within_annotation, named, raw}.
  - attributes.order (class-level @Order 또는 method-level @Order; method 가 class 덮어씀).
  - @Pointcut 로 선언한 이름을 advice 가 참조할 경우 동일 클래스 내에서 lookup.
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
from backend.modeling.code_analysis.spring import AopAnalyzer, DIAnalyzer

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _run(src: str, pkg_name: str | None = "com.x", file_path: str = "X.java"):
    tree = _parse(src)
    a = AopAnalyzer()
    return a.analyze(tree=tree, content=src.encode(), file_path=file_path, pkg_name=pkg_name)


# ---------------------------------------------------------------------------
# @Aspect entity
# ---------------------------------------------------------------------------
def test_aspect_class_produces_aspect_entity() -> None:
    src = """
@Aspect
public class LoggingAspect { }
"""
    entities, _ = _run(src)
    aspects = [e for e in entities if e.kind == EntityKinds.ASPECT]
    assert len(aspects) == 1
    assert aspects[0].qualified_name == "com.x.LoggingAspect"
    assert aspects[0].name == "LoggingAspect"


def test_aspect_with_component_still_emits_aspect_entity() -> None:
    """@Aspect + @Component : AopAnalyzer emits aspect; spring_bean 은 DIAnalyzer 담당."""
    src = """
@Aspect
@Component
public class LoggingAspect { }
"""
    entities, _ = _run(src)
    aspects = [e for e in entities if e.kind == EntityKinds.ASPECT]
    assert len(aspects) == 1
    # AopAnalyzer 는 spring_bean 을 만들지 않는다 (DIAnalyzer 담당)
    assert not any(e.kind == EntityKinds.SPRING_BEAN for e in entities)


def test_plain_class_produces_nothing() -> None:
    src = """
public class Plain {
    @Before("execution(* com.x.Service.*(..))")
    public void log() {}
}
"""
    entities, relations = _run(src)
    assert entities == []
    assert relations == []


# ---------------------------------------------------------------------------
# 5 advice annotations
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("annotation, advice_type", [
    ("@Before", "before"),
    ("@After", "after"),
    ("@Around", "around"),
    ("@AfterReturning", "after_returning"),
    ("@AfterThrowing", "after_throwing"),
])
def test_advice_annotation_produces_intercepts_edge(annotation: str, advice_type: str) -> None:
    src = f"""
@Aspect
public class LoggingAspect {{
    {annotation}("execution(* com.y.OrderService.*(..))")
    public void log() {{}}
}}
"""
    _, relations = _run(src)
    inter = [r for r in relations if r.kind == RelationKinds.INTERCEPTS]
    assert len(inter) == 1
    assert inter[0].source == "com.x.LoggingAspect"
    assert inter[0].target == "com.y.OrderService"
    assert inter[0].attributes["advice_type"] == advice_type


def test_non_advice_method_in_aspect_ignored() -> None:
    src = """
@Aspect
public class LoggingAspect {
    public void helper() {}
}
"""
    _, relations = _run(src)
    assert not any(r.kind == RelationKinds.INTERCEPTS for r in relations)


# ---------------------------------------------------------------------------
# Pointcut target extraction
# ---------------------------------------------------------------------------
def test_execution_pointcut_extracts_class_fqn() -> None:
    src = """
@Aspect
public class A {
    @Before("execution(* com.y.OrderService.placeOrder(..))")
    public void log() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert r.target == "com.y.OrderService"
    assert r.attributes["pointcut_kind"] == "execution"
    assert r.attributes["pointcut_expr"] == "execution(* com.y.OrderService.placeOrder(..))"


def test_execution_pointcut_wildcard_method() -> None:
    src = """
@Aspect
public class A {
    @Before("execution(* com.y.Service.*(..))")
    public void log() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert r.target == "com.y.Service"


def test_within_pointcut_extracts_fqn() -> None:
    src = """
@Aspect
public class A {
    @Before("within(com.y.Util)")
    public void log() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert r.target == "com.y.Util"
    assert r.attributes["pointcut_kind"] == "within"


def test_annotation_pointcut_extracts_fqn() -> None:
    src = """
@Aspect
public class A {
    @Around("@annotation(com.y.MyAnno)")
    public void log() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert r.target == "com.y.MyAnno"
    assert r.attributes["pointcut_kind"] == "annotation"


def test_within_annotation_pointcut_extracts_fqn() -> None:
    src = """
@Aspect
public class A {
    @Before("@within(com.y.MyAnno)")
    public void log() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert r.target == "com.y.MyAnno"
    assert r.attributes["pointcut_kind"] == "within_annotation"


def test_unresolved_pointcut_marked_raw() -> None:
    src = """
@Aspect
public class A {
    @Before("this(some.weird.Thing) && args(x)")
    public void log() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert r.target == "<unresolved>"
    assert r.attributes["pointcut_kind"] == "raw"
    assert r.attributes["pointcut_expr"] == "this(some.weird.Thing) && args(x)"


# ---------------------------------------------------------------------------
# @Pointcut named reference
# ---------------------------------------------------------------------------
def test_named_pointcut_resolved_via_same_class_lookup() -> None:
    """@Pointcut 으로 이름 지은 표현식을 @Before 가 참조하면 표현식을 lookup 하여 target 해석."""
    src = """
@Aspect
public class A {
    @Pointcut("execution(* com.y.Service.*(..))")
    public void serviceOps() {}

    @Before("serviceOps()")
    public void log() {}
}
"""
    _, relations = _run(src)
    intercepts = [r for r in relations if r.kind == RelationKinds.INTERCEPTS]
    assert len(intercepts) == 1
    r = intercepts[0]
    assert r.target == "com.y.Service"
    assert r.attributes["pointcut_kind"] == "named"
    assert r.attributes["pointcut_expr"] == "serviceOps()"
    assert r.attributes["resolved_expr"] == "execution(* com.y.Service.*(..))"


def test_named_pointcut_unknown_name_falls_back_to_raw() -> None:
    src = """
@Aspect
public class A {
    @Before("unknownPointcut()")
    public void log() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert r.target == "<unresolved>"
    assert r.attributes["pointcut_kind"] == "raw"


# ---------------------------------------------------------------------------
# @Order
# ---------------------------------------------------------------------------
def test_class_level_order_applied_to_all_intercepts() -> None:
    src = """
@Aspect
@Order(5)
public class A {
    @Before("execution(* com.y.S.*(..))")
    public void one() {}

    @After("execution(* com.y.T.*(..))")
    public void two() {}
}
"""
    _, relations = _run(src)
    inter = [r for r in relations if r.kind == RelationKinds.INTERCEPTS]
    assert len(inter) == 2
    assert all(r.attributes["order"] == 5 for r in inter)


def test_method_level_order_overrides_class_level() -> None:
    src = """
@Aspect
@Order(5)
public class A {
    @Before("execution(* com.y.S.*(..))")
    public void one() {}

    @Order(10)
    @After("execution(* com.y.T.*(..))")
    public void two() {}
}
"""
    _, relations = _run(src)
    inter = [r for r in relations if r.kind == RelationKinds.INTERCEPTS]
    one = next(r for r in inter if r.attributes["advice_type"] == "before")
    two = next(r for r in inter if r.attributes["advice_type"] == "after")
    assert one.attributes["order"] == 5
    assert two.attributes["order"] == 10


def test_no_order_annotation_omits_order_attr() -> None:
    src = """
@Aspect
public class A {
    @Before("execution(* com.y.S.*(..))")
    public void one() {}
}
"""
    _, relations = _run(src)
    r = next(r for r in relations if r.kind == RelationKinds.INTERCEPTS)
    assert "order" not in r.attributes


# ---------------------------------------------------------------------------
# Integration with JavaParser
# ---------------------------------------------------------------------------
def test_java_parser_accepts_aop_analyzer() -> None:
    src = """
package com.x;
@Aspect
public class LoggingAspect {
    @Before("execution(* com.y.Service.*(..))")
    public void log() {}
}
"""
    parser = JavaParser(spring_analyzers=[AopAnalyzer()])
    result = parser.parse_file(Path("LoggingAspect.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.CLASS in kinds
    assert EntityKinds.ASPECT in kinds
    rel_kinds = {r.kind for r in result.relations}
    assert RelationKinds.INTERCEPTS in rel_kinds


def test_java_parser_with_both_di_and_aop_analyzers() -> None:
    """DIAnalyzer + AopAnalyzer 동시 주입 — @Aspect + @Component 클래스에서 둘 다 산출."""
    src = """
package com.x;
@Aspect
@Component
public class TxAspect {
    @Around("execution(* com.y.Svc.*(..))")
    public Object around() { return null; }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), AopAnalyzer()])
    result = parser.parse_file(Path("TxAspect.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.SPRING_BEAN in kinds  # from DIAnalyzer
    assert EntityKinds.ASPECT in kinds       # from AopAnalyzer
    assert any(r.kind == RelationKinds.INTERCEPTS for r in result.relations)


def test_java_parser_without_aop_analyzer_no_aspect_entities() -> None:
    src = "package com.x; @Aspect public class A {}"
    result = JavaParser().parse_file(Path("A.java"), src)
    assert not any(e.kind == EntityKinds.ASPECT for e in result.entities)
