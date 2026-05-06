"""OD-11-B8-1 TDD — `QueryEngine.impact` BFS + 3-mode filter.

12 테스트 케이스 (SPEC §6):
  1. SAFE : confidence>=0.9 만 통과 (static_unresolved skip)
  2. OBSERVED : {None, static_literal, runtime} 통과 (static_unresolved skip)
  3. POTENTIAL : 모든 엣지 통과
  4. max_hops 제한 : hop 3 에서 멈춤
  5. cycle : 자기 참조/사이클에서 무한 루프 없음
  6. 다중 경로 같은 엔티티 : 최단 경로만 결과
  7. edge_kinds 필터 : calls 만, publishes 제외
  8. entity_kinds 필터 : method 만, class 제외
  9. `<reflection-site>` skip + unresolved_sources 누적
 10. unknown target_fqn : affected 빈 리스트 + message
 11. path 역추적 : source → ... → target 순서 맞음
 12. confidence_min : 경로 상 병목 = 최소 confidence

Spec: `toClaude/modeling/OD-11-B8-SPEC.md` §3, §6.
"""
from __future__ import annotations

import pytest

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)
from backend.modeling.query.graph_view import InMemoryGraphView
from backend.modeling.query.query_engine import QueryEngine
from backend.modeling.query.query_models import (
    ImpactConfig,
    ImpactMode,
    ImpactQuery,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _m(fqn: str) -> CodeEntity:
    return CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name=fqn,
        name=fqn.rsplit(".", 1)[-1],
        file_path="X.java",
        line_start=1,
        line_end=2,
    )


def _c(fqn: str) -> CodeEntity:
    return CodeEntity(
        kind=EntityKinds.CLASS,
        qualified_name=fqn,
        name=fqn.rsplit(".", 1)[-1],
        file_path="X.java",
        line_start=1,
        line_end=2,
    )


def _rel(kind: str, src: str, tgt: str, *, source=None, confidence=None) -> CodeRelation:
    attrs: dict[str, object] = {}
    if source is not None:
        attrs["source"] = source
    if confidence is not None:
        attrs["confidence"] = confidence
    return CodeRelation(kind=kind, source=src, target=tgt, attributes=attrs)


def _pr(entities, relations) -> ParseResult:
    return ParseResult(
        entities=list(entities),
        relations=list(relations),
        file_path="pr.java",
        language="java",
    )


def _engine(entities, relations, config=None) -> QueryEngine:
    view = InMemoryGraphView([_pr(entities, relations)])
    return QueryEngine(view, config or ImpactConfig())


# ---------------------------------------------------------------------------
# 1. SAFE mode
# ---------------------------------------------------------------------------
def test_safe_filters_out_static_unresolved() -> None:
    entities = [_m("A"), _m("B"), _m("C"), _m("D")]
    rels = [
        _rel(RelationKinds.CALLS, "B", "A", source="static_literal", confidence=0.9),
        _rel(RelationKinds.CALLS, "C", "A", source="static_unresolved", confidence=0.4),
        _rel(RelationKinds.CALLS, "D", "A", source="runtime", confidence=0.95),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(ImpactQuery(target_fqn="A", mode=ImpactMode.SAFE, auto_hops=False))
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"B", "D"}  # static_unresolved 의 C 는 제외


# ---------------------------------------------------------------------------
# 2. OBSERVED mode
# ---------------------------------------------------------------------------
def test_observed_includes_none_source_and_excludes_unresolved() -> None:
    entities = [_m("Service.run"), _m("CtrlA.post"), _m("CtrlB.get"), _m("CtrlC.bad")]
    rels = [
        # source 없음 = JavaParser 기본, OBSERVED 에 포함
        _rel(RelationKinds.CALLS, "CtrlA.post", "Service.run"),
        # runtime = 포함
        _rel(RelationKinds.CALLS, "CtrlB.get", "Service.run", source="runtime", confidence=0.95),
        # static_unresolved = 제외
        _rel(RelationKinds.CALLS, "CtrlC.bad", "Service.run", source="static_unresolved", confidence=0.4),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(ImpactQuery(target_fqn="Service.run", mode=ImpactMode.OBSERVED, auto_hops=False))
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"CtrlA.post", "CtrlB.get"}


# ---------------------------------------------------------------------------
# 3. POTENTIAL mode
# ---------------------------------------------------------------------------
def test_potential_includes_all_edges() -> None:
    entities = [_m("A"), _m("B"), _m("C")]
    rels = [
        _rel(RelationKinds.CALLS, "B", "A", source="static_unresolved", confidence=0.4),
        _rel(RelationKinds.CALLS, "C", "A", source="static_literal", confidence=0.9),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(ImpactQuery(target_fqn="A", mode=ImpactMode.POTENTIAL, auto_hops=False))
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"B", "C"}


# ---------------------------------------------------------------------------
# 4. max_hops
# ---------------------------------------------------------------------------
def test_max_hops_stops_bfs() -> None:
    # 체인 : H4 → H3 → H2 → H1 → A (모두 incoming 역방향)
    entities = [_m("A"), _m("H1"), _m("H2"), _m("H3"), _m("H4")]
    rels = [
        _rel(RelationKinds.CALLS, "H1", "A", source="runtime", confidence=1.0),
        _rel(RelationKinds.CALLS, "H2", "H1", source="runtime", confidence=1.0),
        _rel(RelationKinds.CALLS, "H3", "H2", source="runtime", confidence=1.0),
        _rel(RelationKinds.CALLS, "H4", "H3", source="runtime", confidence=1.0),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(
            target_fqn="A",
            mode=ImpactMode.POTENTIAL,
            max_hops=2,
            auto_hops=False,
        )
    )
    distances = {a.qualified_name: a.distance for a in result.affected}
    assert distances == {"H1": 1, "H2": 2}  # H3/H4 는 3/4 hop 이라 제외
    assert result.hops_used == 2


# ---------------------------------------------------------------------------
# 5. cycle
# ---------------------------------------------------------------------------
def test_cycle_does_not_loop_forever() -> None:
    # A ← B ← A (사이클). BFS 는 visited 로 차단.
    entities = [_m("A"), _m("B")]
    rels = [
        _rel(RelationKinds.CALLS, "B", "A"),
        _rel(RelationKinds.CALLS, "A", "B"),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(target_fqn="A", mode=ImpactMode.POTENTIAL, max_hops=10, auto_hops=False)
    )
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"B"}  # A 는 target 자기 자신 → affected 제외


# ---------------------------------------------------------------------------
# 6. multi-path 같은 노드
# ---------------------------------------------------------------------------
def test_multi_path_keeps_shortest() -> None:
    # A ← B ← C, A ← C (C 는 두 경로로 도달 가능. 직접이 최단)
    entities = [_m("A"), _m("B"), _m("C")]
    rels = [
        _rel(RelationKinds.CALLS, "B", "A"),
        _rel(RelationKinds.CALLS, "C", "A"),
        _rel(RelationKinds.CALLS, "C", "B"),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(target_fqn="A", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=False)
    )
    by_name = {a.qualified_name: a for a in result.affected}
    assert by_name["C"].distance == 1
    assert by_name["B"].distance == 1


# ---------------------------------------------------------------------------
# 7. edge_kinds filter
# ---------------------------------------------------------------------------
def test_edge_kinds_filters_relation_types() -> None:
    entities = [_m("A"), _m("B"), _m("C"), _c("Event")]
    rels = [
        _rel(RelationKinds.CALLS, "B", "A"),
        _rel(RelationKinds.PUBLISHES, "C", "Event"),
    ]
    # Event 에 대한 incoming = PUBLISHES. edge_kinds={calls} 면 보이지 않음.
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(
            target_fqn="Event",
            mode=ImpactMode.POTENTIAL,
            edge_kinds={"calls"},
            auto_hops=False,
        )
    )
    assert result.affected == []


def test_edge_kinds_allows_matching_kinds() -> None:
    entities = [_m("C"), _c("Event")]
    rels = [_rel(RelationKinds.PUBLISHES, "C", "Event")]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(
            target_fqn="Event",
            mode=ImpactMode.POTENTIAL,
            edge_kinds={"publishes"},
            auto_hops=False,
        )
    )
    assert {a.qualified_name for a in result.affected} == {"C"}


# ---------------------------------------------------------------------------
# 8. entity_kinds filter
# ---------------------------------------------------------------------------
def test_entity_kinds_default_excludes_class() -> None:
    entities = [_m("Target.run"), _m("Caller.m"), _c("Caller")]
    rels = [
        _rel(RelationKinds.CALLS, "Caller.m", "Target.run"),
        _rel(RelationKinds.CONTAINS, "Caller", "Target.run"),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(target_fqn="Target.run", mode=ImpactMode.POTENTIAL, auto_hops=False)
    )
    # 기본 entity_kinds 는 class 제외 → Caller (class) 는 필터됨
    hits = {a.qualified_name for a in result.affected}
    assert "Caller.m" in hits
    assert "Caller" not in hits


def test_entity_kinds_explicit_includes_class() -> None:
    entities = [_m("Target.run"), _c("Caller")]
    rels = [_rel(RelationKinds.CONTAINS, "Caller", "Target.run")]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(
            target_fqn="Target.run",
            mode=ImpactMode.POTENTIAL,
            entity_kinds={"class"},
            auto_hops=False,
        )
    )
    assert {a.qualified_name for a in result.affected} == {"Caller"}


# ---------------------------------------------------------------------------
# 9. <reflection-site>
# ---------------------------------------------------------------------------
def test_reflection_site_skipped_and_collected() -> None:
    # B7-1 에서 해소 실패 시 emit : source="X.caller" → target="<reflection-site>"
    entities = [_m("X.caller"), _m("RealTarget.run")]
    rels = [
        _rel(
            RelationKinds.CALLS,
            "X.caller",
            "<reflection-site>",
            source="static_unresolved",
            confidence=0.4,
        ),
        _rel(RelationKinds.CALLS, "Observer.m", "RealTarget.run", source="runtime", confidence=0.95),
    ]
    engine = _engine(entities + [_m("Observer.m")], rels)
    # 타깃은 RealTarget, <reflection-site> 는 BFS 경로 어디에도 포함 안 됨 → unresolved_sources
    # 에만 수집. 이 시나리오는 caller 가 target 에 도달 못 해도 리포트에는 남아야 한다.
    # 직접 테스트 : target="<reflection-site>" 질의
    result = engine.impact(
        ImpactQuery(
            target_fqn="<reflection-site>",
            mode=ImpactMode.POTENTIAL,
            auto_hops=False,
        )
    )
    # <reflection-site> 자체를 target 으로 삼으면 affected 는 빈 리스트. unresolved_sources
    # 에 caller X.caller 가 들어와야 함.
    assert result.affected == []
    assert "X.caller" in result.unresolved_sources


# ---------------------------------------------------------------------------
# 10. unknown target
# ---------------------------------------------------------------------------
def test_unknown_target_returns_empty_with_message() -> None:
    engine = _engine([_m("A")], [])
    result = engine.impact(
        ImpactQuery(target_fqn="does.not.exist", mode=ImpactMode.OBSERVED, auto_hops=False)
    )
    assert result.affected == []
    assert "not found" in result.message.lower()
    assert result.source == "does.not.exist"


# ---------------------------------------------------------------------------
# 11. path order
# ---------------------------------------------------------------------------
def test_path_order_source_first() -> None:
    # 체인 : C → B → A (incoming)
    entities = [_m("A"), _m("B"), _m("C")]
    rels = [
        _rel(RelationKinds.CALLS, "B", "A"),
        _rel(RelationKinds.CALLS, "C", "B"),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(target_fqn="A", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=False)
    )
    by_name = {a.qualified_name: a for a in result.affected}
    # B 의 path : [A, B]
    assert by_name["B"].path == ["A", "B"]
    # C 의 path : [A, B, C]
    assert by_name["C"].path == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# 12. confidence_min 병목
# ---------------------------------------------------------------------------
def test_confidence_min_tracks_bottleneck() -> None:
    # C → B(0.95) → A, B → A(0.5 병목)
    entities = [_m("A"), _m("B"), _m("C")]
    rels = [
        _rel(RelationKinds.CALLS, "B", "A", source="runtime", confidence=0.5),
        _rel(RelationKinds.CALLS, "C", "B", source="runtime", confidence=0.95),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(target_fqn="A", mode=ImpactMode.POTENTIAL, max_hops=3, auto_hops=False)
    )
    by_name = {a.qualified_name: a for a in result.affected}
    assert by_name["B"].confidence_min == pytest.approx(0.5)
    assert by_name["C"].confidence_min == pytest.approx(0.5)  # 병목 유지
