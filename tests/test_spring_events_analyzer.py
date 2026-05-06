"""OD-11-B5-4 : Spring EventsAnalyzer — @EventListener / @TransactionalEventListener / publishEvent.

감지 대상:
  - `@EventListener` (on method) → `HANDLES` edge.
  - `@TransactionalEventListener` (on method) → `HANDLES` edge with `attributes.transactional=True`.
  - `ApplicationEventPublisher.publishEvent(new X(...))` 호출 → `PUBLISHES` edge + `event_type` entity.
  - `publishEvent(existingVar)` — 변수 타입 추적 불가 → target = `<unresolved>` + `attributes.publish_expr`.

엔티티:
  - `event_type` : qn = 이벤트 클래스 FQN (import_map 해석). `attributes.inferred_from` ∈ {handler, publish}.

엣지 속성:
  - HANDLES : `handler_method` (short name), `transactional` (True 일 때만).
  - PUBLISHES : `via` (publisher 필드/식별자 이름), `publish_expr` (unresolved 일 때만).
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
    EventsAnalyzer,
    HttpAnalyzer,
)

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _run(src: str, pkg_name: str | None = "com.x", file_path: str = "X.java"):
    tree = _parse(src)
    a = EventsAnalyzer()
    return a.analyze(tree=tree, content=src.encode(), file_path=file_path, pkg_name=pkg_name)


# ---------------------------------------------------------------------------
# @EventListener (handler)
# ---------------------------------------------------------------------------
def test_event_listener_single_param_produces_handles_edge() -> None:
    src = """
import com.y.OrderCreatedEvent;

public class OrderHandler {
    @EventListener
    public void onOrderCreated(OrderCreatedEvent event) {}
}
"""
    entities, relations = _run(src)
    handles = [r for r in relations if r.kind == RelationKinds.HANDLES]
    assert len(handles) == 1
    h = handles[0]
    assert h.source == "com.x.OrderHandler.onOrderCreated"
    assert h.target == "com.y.OrderCreatedEvent"
    assert h.attributes["handler_method"] == "onOrderCreated"
    assert "transactional" not in h.attributes


def test_event_listener_emits_event_type_entity() -> None:
    src = """
import com.y.OrderCreatedEvent;

public class OrderHandler {
    @EventListener
    public void onOrderCreated(OrderCreatedEvent event) {}
}
"""
    entities, _ = _run(src)
    evs = [e for e in entities if e.kind == EntityKinds.EVENT_TYPE]
    assert len(evs) == 1
    ev = evs[0]
    assert ev.qualified_name == "com.y.OrderCreatedEvent"
    assert ev.name == "OrderCreatedEvent"
    assert ev.attributes["inferred_from"] == "handler"


def test_event_listener_with_class_literal_value() -> None:
    """@EventListener(OrderCreatedEvent.class) — value-form 이벤트 타입 명시."""
    src = """
import com.y.OrderCreatedEvent;

public class OrderHandler {
    @EventListener(OrderCreatedEvent.class)
    public void onOrderCreated() {}
}
"""
    entities, relations = _run(src)
    h = next(r for r in relations if r.kind == RelationKinds.HANDLES)
    assert h.target == "com.y.OrderCreatedEvent"


def test_event_listener_class_literal_prefers_over_param() -> None:
    """value-form 이 명시되면 첫 파라미터 타입보다 우선."""
    src = """
import com.y.OrderCreatedEvent;
import com.y.OtherEvent;

public class H {
    @EventListener(OrderCreatedEvent.class)
    public void h(OtherEvent e) {}
}
"""
    _, relations = _run(src)
    h = next(r for r in relations if r.kind == RelationKinds.HANDLES)
    assert h.target == "com.y.OrderCreatedEvent"


def test_event_listener_without_import_uses_same_package() -> None:
    src = """
public class H {
    @EventListener
    public void h(LocalEvent e) {}
}
"""
    _, relations = _run(src)
    h = next(r for r in relations if r.kind == RelationKinds.HANDLES)
    assert h.target == "com.x.LocalEvent"


def test_event_listener_no_param_no_value_unresolved() -> None:
    src = """
public class H {
    @EventListener
    public void h() {}
}
"""
    _, relations = _run(src)
    h = next(r for r in relations if r.kind == RelationKinds.HANDLES)
    assert h.target == "<unresolved>"


# ---------------------------------------------------------------------------
# @TransactionalEventListener
# ---------------------------------------------------------------------------
def test_transactional_event_listener_marks_transactional_true() -> None:
    src = """
import com.y.OrderCreatedEvent;

public class H {
    @TransactionalEventListener
    public void h(OrderCreatedEvent e) {}
}
"""
    _, relations = _run(src)
    h = next(r for r in relations if r.kind == RelationKinds.HANDLES)
    assert h.target == "com.y.OrderCreatedEvent"
    assert h.attributes["transactional"] is True


# ---------------------------------------------------------------------------
# publishEvent(new X(...))
# ---------------------------------------------------------------------------
def test_publish_event_with_new_object_extracts_type() -> None:
    src = """
import com.y.OrderCreatedEvent;
import org.springframework.context.ApplicationEventPublisher;

public class OrderService {
    private ApplicationEventPublisher publisher;

    public void place() {
        publisher.publishEvent(new OrderCreatedEvent(1L));
    }
}
"""
    entities, relations = _run(src)
    pubs = [r for r in relations if r.kind == RelationKinds.PUBLISHES]
    assert len(pubs) == 1
    p = pubs[0]
    assert p.source == "com.x.OrderService.place"
    assert p.target == "com.y.OrderCreatedEvent"
    assert p.attributes["via"] == "publisher"

    evs = [e for e in entities if e.kind == EntityKinds.EVENT_TYPE]
    assert len(evs) == 1
    assert evs[0].qualified_name == "com.y.OrderCreatedEvent"
    assert evs[0].attributes["inferred_from"] == "publish"


def test_publish_event_with_variable_argument_unresolved() -> None:
    src = """
import org.springframework.context.ApplicationEventPublisher;

public class S {
    private ApplicationEventPublisher publisher;

    public void fire(Object event) {
        publisher.publishEvent(event);
    }
}
"""
    entities, relations = _run(src)
    p = next(r for r in relations if r.kind == RelationKinds.PUBLISHES)
    assert p.target == "<unresolved>"
    assert "publish_expr" in p.attributes
    assert "event" in p.attributes["publish_expr"]
    # Unresolved → no event_type entity created
    assert not any(e.kind == EntityKinds.EVENT_TYPE for e in entities)


def test_publish_event_via_this_prefix_captured() -> None:
    src = """
import com.y.E;

public class S {
    private ApplicationEventPublisher pub;

    public void f() {
        this.pub.publishEvent(new E());
    }
}
"""
    _, relations = _run(src)
    p = next(r for r in relations if r.kind == RelationKinds.PUBLISHES)
    assert p.target == "com.y.E"
    assert p.attributes["via"] == "pub"


def test_publish_event_without_object_treated_as_self() -> None:
    """상속받은 ApplicationContextAware 등에서 publishEvent() 직접 호출하는 케이스.

    object 없는 publishEvent 는 'this' 기반 self-dispatch 로 간주 (via=this).
    """
    src = """
import com.y.E;

public class S {
    public void f() {
        publishEvent(new E());
    }
}
"""
    _, relations = _run(src)
    pubs = [r for r in relations if r.kind == RelationKinds.PUBLISHES]
    assert len(pubs) == 1
    assert pubs[0].target == "com.y.E"
    assert pubs[0].attributes["via"] == "this"


def test_multiple_publish_events_each_tracked() -> None:
    src = """
import com.y.A;
import com.y.B;

public class S {
    private ApplicationEventPublisher pub;

    public void f() {
        pub.publishEvent(new A());
        pub.publishEvent(new B());
    }
}
"""
    entities, relations = _run(src)
    pubs = [r for r in relations if r.kind == RelationKinds.PUBLISHES]
    assert len(pubs) == 2
    targets = {p.target for p in pubs}
    assert targets == {"com.y.A", "com.y.B"}

    evs = [e for e in entities if e.kind == EntityKinds.EVENT_TYPE]
    ev_qns = {e.qualified_name for e in evs}
    assert ev_qns == {"com.y.A", "com.y.B"}


def test_duplicate_event_type_references_dedupe_to_one_entity() -> None:
    src = """
import com.y.E;

public class S {
    private ApplicationEventPublisher pub;

    public void a() { pub.publishEvent(new E()); }
    public void b() { pub.publishEvent(new E()); }
}
"""
    entities, relations = _run(src)
    evs = [e for e in entities if e.kind == EntityKinds.EVENT_TYPE]
    assert len(evs) == 1
    pubs = [r for r in relations if r.kind == RelationKinds.PUBLISHES]
    assert len(pubs) == 2


def test_unrelated_method_call_with_same_name_not_matched() -> None:
    """publishEvent 이 아닌 다른 메서드 호출은 무시."""
    src = """
public class S {
    public void f() {
        someService.doSomething(new X());
    }
}
"""
    _, relations = _run(src)
    assert not any(r.kind == RelationKinds.PUBLISHES for r in relations)


# ---------------------------------------------------------------------------
# Combined publish + handle in same file
# ---------------------------------------------------------------------------
def test_same_class_publish_and_handle_both_recorded() -> None:
    src = """
import com.y.OrderCreatedEvent;

public class OrderService {
    private ApplicationEventPublisher pub;

    public void place() {
        pub.publishEvent(new OrderCreatedEvent());
    }

    @EventListener
    public void onCreated(OrderCreatedEvent e) {}
}
"""
    entities, relations = _run(src)
    pubs = [r for r in relations if r.kind == RelationKinds.PUBLISHES]
    handles = [r for r in relations if r.kind == RelationKinds.HANDLES]
    assert len(pubs) == 1
    assert len(handles) == 1
    assert pubs[0].target == "com.y.OrderCreatedEvent"
    assert handles[0].target == "com.y.OrderCreatedEvent"
    # Dedup: only one event_type entity even though referenced twice.
    evs = [e for e in entities if e.kind == EntityKinds.EVENT_TYPE]
    assert len(evs) == 1


# ---------------------------------------------------------------------------
# Non-listener / non-publisher methods ignored
# ---------------------------------------------------------------------------
def test_plain_method_no_edges() -> None:
    src = """
public class S {
    public void plain() {
        int x = 1;
    }
}
"""
    entities, relations = _run(src)
    assert not any(r.kind == RelationKinds.HANDLES for r in relations)
    assert not any(r.kind == RelationKinds.PUBLISHES for r in relations)
    assert not any(e.kind == EntityKinds.EVENT_TYPE for e in entities)


# ---------------------------------------------------------------------------
# Integration with JavaParser
# ---------------------------------------------------------------------------
def test_java_parser_accepts_events_analyzer() -> None:
    src = """
package com.x;
import com.y.OrderCreatedEvent;

public class OrderHandler {
    @EventListener
    public void on(OrderCreatedEvent e) {}
}
"""
    parser = JavaParser(spring_analyzers=[EventsAnalyzer()])
    result = parser.parse_file(Path("OrderHandler.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.EVENT_TYPE in kinds
    rel_kinds = {r.kind for r in result.relations}
    assert RelationKinds.HANDLES in rel_kinds


def test_java_parser_with_di_aop_http_events_quadruple() -> None:
    """DIAnalyzer + AopAnalyzer + HttpAnalyzer + EventsAnalyzer 동시 주입 동작."""
    src = """
package com.x;
import com.y.OrderCreatedEvent;

@RestController
@RequestMapping("/api")
public class OrderController {
    @Autowired
    private ApplicationEventPublisher pub;

    @PostMapping("/orders")
    public void create() {
        pub.publishEvent(new OrderCreatedEvent());
    }

    @EventListener
    public void onCreated(OrderCreatedEvent e) {}
}
"""
    parser = JavaParser(spring_analyzers=[
        DIAnalyzer(), AopAnalyzer(), HttpAnalyzer(), EventsAnalyzer(),
    ])
    result = parser.parse_file(Path("OrderController.java"), src)
    kinds = {e.kind for e in result.entities}
    assert EntityKinds.SPRING_BEAN in kinds       # DIAnalyzer
    assert EntityKinds.HTTP_ENDPOINT in kinds     # HttpAnalyzer
    assert EntityKinds.EVENT_TYPE in kinds        # EventsAnalyzer

    rel_kinds = {r.kind for r in result.relations}
    assert RelationKinds.AUTOWIRES in rel_kinds   # DIAnalyzer
    assert RelationKinds.MAPS_URL in rel_kinds    # HttpAnalyzer
    assert RelationKinds.PUBLISHES in rel_kinds   # EventsAnalyzer
    assert RelationKinds.HANDLES in rel_kinds     # EventsAnalyzer


def test_java_parser_without_events_analyzer_no_events_artifacts() -> None:
    src = """
package com.x;
public class H {
    @EventListener
    public void on(Evt e) {}
}
"""
    result = JavaParser().parse_file(Path("H.java"), src)
    assert not any(e.kind == EntityKinds.EVENT_TYPE for e in result.entities)
    assert not any(r.kind == RelationKinds.HANDLES for r in result.relations)
