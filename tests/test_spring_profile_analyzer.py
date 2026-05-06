"""OD-11-B5-6 : Spring ProfileAnalyzer — method-level `@Profile` / `@ConditionalOnProperty`.

감지 대상 (method-level만):
  - `@Profile("prod")` / `@Profile({"prod", "legacy"})`
  - `@ConditionalOnProperty("feature.x")`
  - `@ConditionalOnProperty(name="k", havingValue="v")`

적용 대상 (다른 analyzer 가 emit 한 entity/relation 속성에 merge):
  - `@Bean` 메서드 → `spring_bean` entity (qn = `<class>.<method>#bean`)
  - HTTP handler 메서드 → `http_endpoint` entity + `MAPS_URL` relation
  - `@Scheduled` 메서드 → `scheduled_task` entity
  - `@EventListener` / `@TransactionalEventListener` 메서드 → `HANDLES` relation

설계:
  - ProfileAnalyzer 는 standalone `analyze()` 호출 시 `([], [])` 반환 (Protocol 호환).
  - 대신 `enrich(entities, relations, tree, pkg_name)` 후처리 메서드 제공.
  - `JavaParser` 가 `analyze` 전체 호출 후 `enrich` 가 있는 analyzer 에게 2차 패스 위임.
  - class-level `@Profile` 은 B5-1 DIAnalyzer 에서 AUTOWIRES 엣지 속성으로 이미 주입 — 여기서는 영향 없음.
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKinds, RelationKinds
from backend.modeling.code_analysis.spring import (
    DIAnalyzer,
    EventsAnalyzer,
    HttpAnalyzer,
    ProfileAnalyzer,
    ScheduledAnalyzer,
)

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


# ---------------------------------------------------------------------------
# Standalone analyze() — no effect (Protocol compat)
# ---------------------------------------------------------------------------
def test_profile_analyzer_analyze_returns_empty() -> None:
    src = """
@Configuration
public class Cfg {
    @Bean
    @Profile("prod")
    public Clock clock() { return Clock.systemUTC(); }
}
"""
    tree = _parse(src)
    a = ProfileAnalyzer()
    entities, relations = a.analyze(
        tree=tree, content=src.encode(), file_path="Cfg.java", pkg_name="com.x",
    )
    assert entities == []
    assert relations == []


# ---------------------------------------------------------------------------
# @Bean + method-level @Profile → spring_bean entity enriched
# ---------------------------------------------------------------------------
def test_bean_method_with_profile_enriches_spring_bean() -> None:
    src = """
package com.x;
@Configuration
public class Cfg {
    @Bean
    @Profile("prod")
    public Clock clock() { return Clock.systemUTC(); }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Cfg.java"), src)
    beans = [
        e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN
        and e.qualified_name.endswith("#bean")
    ]
    assert len(beans) == 1
    assert beans[0].attributes["profile"] == ["prod"]


def test_bean_method_with_profile_array() -> None:
    src = """
package com.x;
@Configuration
public class Cfg {
    @Bean
    @Profile({"prod", "legacy"})
    public Clock clock() { return Clock.systemUTC(); }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Cfg.java"), src)
    bean = next(
        e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN and e.qualified_name.endswith("#bean")
    )
    assert bean.attributes["profile"] == ["prod", "legacy"]


def test_bean_method_with_conditional_on_property_single() -> None:
    src = """
package com.x;
@Configuration
public class Cfg {
    @Bean
    @ConditionalOnProperty("feature.x")
    public Clock clock() { return Clock.systemUTC(); }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Cfg.java"), src)
    bean = next(
        e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN and e.qualified_name.endswith("#bean")
    )
    assert bean.attributes["condition"] == "feature.x"


def test_bean_method_with_conditional_on_property_kv() -> None:
    src = """
package com.x;
@Configuration
public class Cfg {
    @Bean
    @ConditionalOnProperty(name = "feature.flag", havingValue = "on")
    public Clock clock() { return Clock.systemUTC(); }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Cfg.java"), src)
    bean = next(
        e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN and e.qualified_name.endswith("#bean")
    )
    assert bean.attributes["condition"] == "feature.flag=on"


def test_bean_without_profile_has_no_profile_attr() -> None:
    src = """
package com.x;
@Configuration
public class Cfg {
    @Bean
    public Clock clock() { return Clock.systemUTC(); }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Cfg.java"), src)
    bean = next(
        e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN and e.qualified_name.endswith("#bean")
    )
    assert "profile" not in bean.attributes
    assert "condition" not in bean.attributes


# ---------------------------------------------------------------------------
# @Scheduled + method-level @Profile → scheduled_task enriched
# ---------------------------------------------------------------------------
def test_scheduled_method_with_profile_enriches_scheduled_task() -> None:
    src = """
package com.x;
public class JobRunner {
    @Scheduled(fixedRate = 1000)
    @Profile("prod")
    public void tick() {}
}
"""
    parser = JavaParser(spring_analyzers=[ScheduledAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("JobRunner.java"), src)
    task = next(e for e in result.entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert task.attributes["profile"] == ["prod"]
    assert task.attributes["fixed_rate"] == "1000"


def test_scheduled_method_with_conditional() -> None:
    src = """
package com.x;
public class JobRunner {
    @Scheduled(cron = "0 0 * * * *")
    @ConditionalOnProperty(name = "batch.enabled", havingValue = "true")
    public void hourly() {}
}
"""
    parser = JavaParser(spring_analyzers=[ScheduledAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("JobRunner.java"), src)
    task = next(e for e in result.entities if e.kind == EntityKinds.SCHEDULED_TASK)
    assert task.attributes["condition"] == "batch.enabled=true"


# ---------------------------------------------------------------------------
# HTTP handler + method-level @Profile → http_endpoint entity + MAPS_URL relation
# ---------------------------------------------------------------------------
def test_http_handler_with_profile_enriches_endpoint_and_edge() -> None:
    src = """
package com.x;
@RestController
@RequestMapping("/api")
public class OrderApi {
    @GetMapping("/orders")
    @Profile("prod")
    public String list() { return "[]"; }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), HttpAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("OrderApi.java"), src)
    endpoint = next(e for e in result.entities if e.kind == EntityKinds.HTTP_ENDPOINT)
    assert endpoint.attributes["profile"] == ["prod"]

    maps_url = next(r for r in result.relations if r.kind == RelationKinds.MAPS_URL)
    assert maps_url.attributes["profile"] == ["prod"]


# ---------------------------------------------------------------------------
# @EventListener + method-level @Profile → HANDLES relation enriched
# ---------------------------------------------------------------------------
def test_event_listener_with_profile_enriches_handles_edge() -> None:
    src = """
package com.x;
public class OrderHandler {
    @EventListener
    @Profile("prod")
    public void onEvent(OrderPlaced e) {}
}
"""
    parser = JavaParser(spring_analyzers=[EventsAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("OrderHandler.java"), src)
    handles = next(r for r in result.relations if r.kind == RelationKinds.HANDLES)
    assert handles.attributes["profile"] == ["prod"]


def test_transactional_event_listener_preserves_transactional_plus_profile() -> None:
    src = """
package com.x;
public class OrderHandler {
    @TransactionalEventListener
    @Profile("prod")
    public void onCommit(OrderPlaced e) {}
}
"""
    parser = JavaParser(spring_analyzers=[EventsAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("OrderHandler.java"), src)
    handles = next(r for r in result.relations if r.kind == RelationKinds.HANDLES)
    assert handles.attributes["profile"] == ["prod"]
    assert handles.attributes["transactional"] is True


# ---------------------------------------------------------------------------
# Combined @Profile + @ConditionalOnProperty on same method
# ---------------------------------------------------------------------------
def test_both_profile_and_condition_on_same_method() -> None:
    src = """
package com.x;
@Configuration
public class Cfg {
    @Bean
    @Profile("prod")
    @ConditionalOnProperty(name = "feature.x", havingValue = "on")
    public Clock clock() { return Clock.systemUTC(); }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Cfg.java"), src)
    bean = next(
        e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN and e.qualified_name.endswith("#bean")
    )
    assert bean.attributes["profile"] == ["prod"]
    assert bean.attributes["condition"] == "feature.x=on"


# ---------------------------------------------------------------------------
# Method-level doesn't pollute other methods
# ---------------------------------------------------------------------------
def test_profile_scoped_to_annotated_method_only() -> None:
    src = """
package com.x;
@Configuration
public class Cfg {
    @Bean
    @Profile("prod")
    public Clock prodClock() { return Clock.systemUTC(); }

    @Bean
    public Clock devClock() { return Clock.systemUTC(); }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Cfg.java"), src)
    beans = {
        e.qualified_name: e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN and e.qualified_name.endswith("#bean")
    }
    assert beans["com.x.Cfg.prodClock#bean"].attributes["profile"] == ["prod"]
    assert "profile" not in beans["com.x.Cfg.devClock#bean"].attributes


# ---------------------------------------------------------------------------
# Class-level @Profile unaffected by ProfileAnalyzer (still handled by DI)
# ---------------------------------------------------------------------------
def test_class_level_profile_still_on_autowires_not_entity() -> None:
    """class-level `@Profile` is DIAnalyzer's job — ProfileAnalyzer shouldn't touch it."""
    src = """
package com.x;
@Component
@Profile("prod")
public class OrderService {
    @Autowired
    private OrderRepo repo;
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("OrderService.java"), src)
    # stereotype entity does NOT get profile (entity has stereotype only)
    stereotype = next(
        e for e in result.entities
        if e.kind == EntityKinds.SPRING_BEAN and not e.qualified_name.endswith("#bean")
    )
    assert "profile" not in stereotype.attributes
    # AUTOWIRES edge DOES have profile (from DIAnalyzer)
    autowires = next(r for r in result.relations if r.kind == RelationKinds.AUTOWIRES)
    assert autowires.attributes["profile"] == ["prod"]


# ---------------------------------------------------------------------------
# ProfileAnalyzer without other analyzers — no-op (nothing to enrich)
# ---------------------------------------------------------------------------
def test_profile_analyzer_alone_is_noop() -> None:
    src = """
package com.x;
public class J {
    @Profile("prod")
    public void t() {}
}
"""
    parser = JavaParser(spring_analyzers=[ProfileAnalyzer()])
    result = parser.parse_file(Path("J.java"), src)
    # Only the base METHOD entity from java_parser, no Spring extras.
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.SPRING_BEAN not in kinds
    assert EntityKinds.SCHEDULED_TASK not in kinds
    assert EntityKinds.HTTP_ENDPOINT not in kinds


# ---------------------------------------------------------------------------
# JavaParser wire — analyzer with enrich() attribute gets second-pass call
# ---------------------------------------------------------------------------
def test_java_parser_calls_enrich_after_analyze() -> None:
    """`JavaParser` post-pass 로 `enrich()` 호출 — ProfileAnalyzer 에만 정의."""
    assert hasattr(ProfileAnalyzer(), "enrich")


# ---------------------------------------------------------------------------
# Multiple annotations mixed — scheduled + publishes same method, @Profile applies to both
# ---------------------------------------------------------------------------
def test_publish_edge_also_enriched_by_method_level_profile() -> None:
    src = """
package com.x;
public class Publisher {
    @Autowired
    private ApplicationEventPublisher pub;

    @Profile("prod")
    public void fire() {
        pub.publishEvent(new OrderPlaced());
    }
}
"""
    parser = JavaParser(spring_analyzers=[DIAnalyzer(), EventsAnalyzer(), ProfileAnalyzer()])
    result = parser.parse_file(Path("Publisher.java"), src)
    publishes = next(r for r in result.relations if r.kind == RelationKinds.PUBLISHES)
    assert publishes.attributes.get("profile") == ["prod"]
