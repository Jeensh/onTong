"""OD-11-B5-1 : Spring DI analyzer — @Autowired / @Inject / 생성자 주입.

Round 1 rev.3 대응:
  - 6 stereotype (@Component/@Service/@Repository/@Controller/@RestController/@Configuration)
    → `spring_bean` entity. qualified_name = class FQN.
  - @Bean 메서드 → `spring_bean` entity. qualified_name = `<class FQN>.<method>#bean`.
  - @Autowired / @Inject on field / constructor / 단일 생성자 → `AUTOWIRES` 엣지.
  - @Qualifier → `attributes.qualifier`
  - @Profile (class-level) → `attributes.profile` on outgoing AUTOWIRES
  - @ConditionalOnProperty (class-level) → `attributes.condition`
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
from backend.modeling.code_analysis.spring import DIAnalyzer


_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _run(src: str, pkg_name: str | None = "com.x", file_path: str = "X.java"):
    tree = _parse(src)
    a = DIAnalyzer()
    return a.analyze(tree=tree, content=src.encode(), file_path=file_path, pkg_name=pkg_name)


# ---------------------------------------------------------------------------
# 6 stereotypes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("annotation, stereotype", [
    ("@Component", "Component"),
    ("@Service", "Service"),
    ("@Repository", "Repository"),
    ("@Controller", "Controller"),
    ("@RestController", "RestController"),
    ("@Configuration", "Configuration"),
])
def test_stereotype_produces_spring_bean(annotation: str, stereotype: str) -> None:
    src = f"""
{annotation}
public class Foo {{ }}
"""
    entities, relations = _run(src)
    beans = [e for e in entities if e.kind == EntityKinds.SPRING_BEAN]
    assert len(beans) == 1
    assert beans[0].qualified_name == "com.x.Foo"
    assert beans[0].name == "Foo"
    assert beans[0].attributes["stereotype"] == stereotype


def test_plain_class_does_not_produce_bean() -> None:
    entities, relations = _run("public class Plain {}")
    assert not any(e.kind == EntityKinds.SPRING_BEAN for e in entities)
    assert relations == []


# ---------------------------------------------------------------------------
# Field injection
# ---------------------------------------------------------------------------
def test_autowired_field_produces_autowires_edge() -> None:
    src = """
import com.y.OrderRepo;
@Service
public class OrderService {
    @Autowired
    private OrderRepo repo;
}
"""
    entities, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert len(aut) == 1
    assert aut[0].source == "com.x.OrderService"
    assert aut[0].target == "com.y.OrderRepo"


def test_inject_annotation_treated_same_as_autowired() -> None:
    src = """
import com.y.BarService;
@Service
public class Foo {
    @Inject
    private BarService bar;
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert len(aut) == 1
    assert aut[0].target == "com.y.BarService"


def test_non_autowired_field_ignored() -> None:
    """Spring bean이어도 @Autowired가 없는 필드는 AUTOWIRES 엣지 생성 안 함."""
    src = """
import com.y.Util;
@Service
public class Foo {
    private Util u;  // no @Autowired
}
"""
    _, relations = _run(src)
    assert not any(r.kind == RelationKinds.AUTOWIRES for r in relations)


# ---------------------------------------------------------------------------
# Constructor injection
# ---------------------------------------------------------------------------
def test_explicit_autowired_constructor_emits_edge_per_param() -> None:
    src = """
import com.y.A;
import com.z.B;
@Service
public class Foo {
    @Autowired
    public Foo(A a, B b) { }
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    targets = {r.target for r in aut}
    assert targets == {"com.y.A", "com.z.B"}
    assert all(r.source == "com.x.Foo" for r in aut)


def test_single_constructor_implicit_injection() -> None:
    """Spring 4.3+ : Bean에 생성자가 하나이고 파라미터가 있으면 @Autowired 없이도 주입."""
    src = """
import com.y.Dep;
@Service
public class Foo {
    public Foo(Dep d) { }
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert len(aut) == 1
    assert aut[0].target == "com.y.Dep"


def test_multiple_constructors_require_explicit_autowired() -> None:
    """생성자 2개 이상 + 명시 @Autowired 없음 → AUTOWIRES 엣지 생성 안 함."""
    src = """
import com.y.Dep;
@Service
public class Foo {
    public Foo() {}
    public Foo(Dep d) {}
}
"""
    _, relations = _run(src)
    assert not any(r.kind == RelationKinds.AUTOWIRES for r in relations)


def test_zero_arg_single_constructor_emits_nothing() -> None:
    """파라미터가 없는 생성자는 주입 대상이 없음."""
    src = """
@Service
public class Foo {
    public Foo() {}
}
"""
    _, relations = _run(src)
    assert not any(r.kind == RelationKinds.AUTOWIRES for r in relations)


# ---------------------------------------------------------------------------
# Qualifier
# ---------------------------------------------------------------------------
def test_qualifier_attribute_on_autowires() -> None:
    src = """
import com.y.OrderRepo;
@Service
public class Foo {
    @Autowired
    @Qualifier("primary")
    private OrderRepo repo;
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert aut[0].attributes["qualifier"] == "primary"


# ---------------------------------------------------------------------------
# Profile (class-level)
# ---------------------------------------------------------------------------
def test_profile_single_value_on_bean_class() -> None:
    src = """
import com.y.A;
@Profile("prod")
@Service
public class Foo {
    @Autowired
    private A a;
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert aut[0].attributes["profile"] == ["prod"]


def test_profile_array_form_on_bean_class() -> None:
    src = """
import com.y.A;
@Profile({"prod", "legacy"})
@Service
public class Foo {
    @Autowired
    private A a;
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert aut[0].attributes["profile"] == ["prod", "legacy"]


# ---------------------------------------------------------------------------
# ConditionalOnProperty (class-level)
# ---------------------------------------------------------------------------
def test_conditional_on_property_string_form() -> None:
    src = """
import com.y.A;
@ConditionalOnProperty("feature.x.enabled")
@Service
public class Foo {
    @Autowired
    private A a;
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert aut[0].attributes["condition"] == "feature.x.enabled"


def test_conditional_on_property_kv_form() -> None:
    src = """
import com.y.A;
@ConditionalOnProperty(name="order.legacy.enabled", havingValue="true")
@Service
public class Foo {
    @Autowired
    private A a;
}
"""
    _, relations = _run(src)
    aut = [r for r in relations if r.kind == RelationKinds.AUTOWIRES]
    assert aut[0].attributes["condition"] == "order.legacy.enabled=true"


# ---------------------------------------------------------------------------
# @Bean methods in @Configuration
# ---------------------------------------------------------------------------
def test_bean_method_produces_spring_bean_entity() -> None:
    src = """
@Configuration
public class AppConfig {
    @Bean
    public DataSource dataSource() {
        return new HikariDataSource();
    }
}
"""
    entities, _ = _run(src)
    beans = [e for e in entities if e.kind == EntityKinds.SPRING_BEAN]
    # AppConfig (@Configuration) + dataSource (@Bean) = 2 beans
    qnames = {e.qualified_name for e in beans}
    assert "com.x.AppConfig" in qnames
    assert "com.x.AppConfig.dataSource#bean" in qnames
    ds_bean = next(e for e in beans if e.qualified_name == "com.x.AppConfig.dataSource#bean")
    assert ds_bean.name == "dataSource"
    assert ds_bean.attributes["stereotype"] == "Bean"


def test_bean_method_outside_configuration_ignored() -> None:
    """@Configuration 없는 클래스의 @Bean 메서드는 B5-1 에선 무시 (Spring 실제 동작도 보수적으로 처리)."""
    src = """
public class Plain {
    @Bean
    public DataSource dataSource() { return null; }
}
"""
    entities, _ = _run(src)
    beans = [e for e in entities if e.kind == EntityKinds.SPRING_BEAN]
    assert beans == []


# ---------------------------------------------------------------------------
# Integration with JavaParser
# ---------------------------------------------------------------------------
def test_java_parser_accepts_spring_analyzers_list() -> None:
    """JavaParser 가 옵션으로 받은 Spring analyzer 의 산출물을 ParseResult 에 병합."""
    src = """
package com.x;
import com.y.OrderRepo;
@Service
public class OrderService {
    @Autowired
    private OrderRepo repo;
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer()])
    result = parser.parse_file(Path("OrderService.java"), src)
    # Entity: should contain both CLASS (from core parser) and SPRING_BEAN (from DI)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.CLASS in kinds
    assert EntityKinds.SPRING_BEAN in kinds
    # Relation: core parser's CONTAINS + DIAnalyzer's AUTOWIRES
    rel_kinds = {r.kind for r in result.relations}
    assert RelationKinds.CONTAINS in rel_kinds
    assert RelationKinds.AUTOWIRES in rel_kinds


def test_java_parser_without_spring_analyzers_is_backward_compatible() -> None:
    """analyzers 인자 생략 시 이전 동작과 동일해야 한다."""
    src = "package com.x; @Service public class A {}"
    result = JavaParser().parse_file(Path("A.java"), src)
    assert not any(e.kind == EntityKinds.SPRING_BEAN for e in result.entities)
