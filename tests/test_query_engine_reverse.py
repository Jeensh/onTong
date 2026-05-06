"""OD-11-B8-3 TDD — `QueryEngine.reverse_lookup` + outgoing 방향 `<reflection-site>` 진단.

SPEC: `toClaude/modeling/OD-11-B8-SPEC.md` §2.2, §3.3, §5.2.

7 테스트:
  1. reverse_lookup(FQN) — outgoing 방향 BFS 재사용
  2. reverse_lookup 다중 hop — A→B→C 모두 반환
  3. reverse_lookup unknown term — affected=[] + "not found" message
  4. outgoing 중간 `<reflection-site>` → skip + `unresolved_sources` 수집
  5. `<reflection-site>` 직접 질의 + direction="outgoing" → 진단 분기 (sentinel sink)
  6. reverse_lookup 이 auto-shrink 도 그대로 적용 (outgoing 에서도 축소)
  7. reverse_lookup entity_kinds 기본값 적용 (class noise 제외)
"""
from __future__ import annotations

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
# 1. reverse_lookup (outgoing) 기본
# ---------------------------------------------------------------------------
def test_reverse_lookup_returns_outgoing_neighbors() -> None:
    entities = [_m("A.run"), _m("B.foo"), _m("C.bar")]
    rels = [
        _rel(RelationKinds.CALLS, "A.run", "B.foo"),
        _rel(RelationKinds.CALLS, "A.run", "C.bar"),
    ]
    engine = _engine(entities, rels)
    result = engine.reverse_lookup("A.run", auto_hops=False)
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"B.foo", "C.bar"}
    assert result.hops_used == 1


# ---------------------------------------------------------------------------
# 2. multi-hop outgoing
# ---------------------------------------------------------------------------
def test_reverse_lookup_multi_hop() -> None:
    entities = [_m("A"), _m("B"), _m("C"), _m("D")]
    rels = [
        _rel(RelationKinds.CALLS, "A", "B"),
        _rel(RelationKinds.CALLS, "B", "C"),
        _rel(RelationKinds.CALLS, "C", "D"),
    ]
    engine = _engine(entities, rels)
    result = engine.reverse_lookup("A", max_hops=5, auto_hops=False)
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"B", "C", "D"}
    # A → B(d=1) → C(d=2) → D(d=3)
    by_name = {a.qualified_name: a.distance for a in result.affected}
    assert by_name == {"B": 1, "C": 2, "D": 3}


# ---------------------------------------------------------------------------
# 3. unknown term
# ---------------------------------------------------------------------------
def test_reverse_lookup_unknown_term() -> None:
    entities = [_m("A.run")]
    engine = _engine(entities, [])
    result = engine.reverse_lookup("not.exist.term", auto_hops=False)
    assert result.affected == []
    assert "not found" in result.message.lower()


# ---------------------------------------------------------------------------
# 4. outgoing 중간 `<reflection-site>`
# ---------------------------------------------------------------------------
def test_outgoing_mid_traversal_reflection_site_collected() -> None:
    entities = [_m("A.run"), _m("B.foo")]
    rels = [
        _rel(RelationKinds.CALLS, "A.run", "B.foo"),
        # A.run 이 정적 해소 실패한 reflection 호출을 가진다고 가정 (B7-1 산출)
        _rel(
            RelationKinds.CALLS,
            "A.run",
            "<reflection-site>",
            source="static_unresolved",
            confidence=0.4,
        ),
    ]
    engine = _engine(entities, rels)
    result = engine.reverse_lookup("A.run", mode=ImpactMode.POTENTIAL, auto_hops=False)
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"B.foo"}  # reflection-site 는 엔티티 아님
    assert "A.run" in result.unresolved_sources


# ---------------------------------------------------------------------------
# 5. `<reflection-site>` 직접 질의 + outgoing → sentinel sink 진단
# ---------------------------------------------------------------------------
def test_reflection_site_direct_query_outgoing_returns_sentinel_note() -> None:
    entities = [_m("A.caller")]
    rels = [
        _rel(
            RelationKinds.CALLS,
            "A.caller",
            "<reflection-site>",
            source="static_unresolved",
            confidence=0.4,
        ),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(
            target_fqn="<reflection-site>",
            mode=ImpactMode.POTENTIAL,
            direction="outgoing",
            auto_hops=False,
        )
    )
    assert result.affected == []
    assert result.unresolved_sources == []
    assert "sentinel" in result.message.lower() or "no outgoing" in result.message.lower()


def test_reflection_site_direct_query_incoming_still_collects_callers() -> None:
    # B8-1 진단 모드 회귀 — direction="incoming" (기본) 은 변함 없음
    entities = [_m("X.a"), _m("Y.b")]
    rels = [
        _rel(
            RelationKinds.CALLS,
            "X.a",
            "<reflection-site>",
            source="static_unresolved",
            confidence=0.4,
        ),
        _rel(
            RelationKinds.CALLS,
            "Y.b",
            "<reflection-site>",
            source="static_unresolved",
            confidence=0.4,
        ),
    ]
    engine = _engine(entities, rels)
    result = engine.impact(
        ImpactQuery(target_fqn="<reflection-site>", mode=ImpactMode.POTENTIAL)
    )
    assert set(result.unresolved_sources) == {"X.a", "Y.b"}


# ---------------------------------------------------------------------------
# 6. reverse_lookup + auto-shrink
# ---------------------------------------------------------------------------
def test_reverse_lookup_honors_auto_shrink() -> None:
    # A → B1, B2, B3 (hop1 fan-out 3) → 각 Bi → Ci_j (hop2 per-each 3)
    entities = [_m("A")]
    rels = []
    for i in range(3):
        entities.append(_m(f"B_{i}"))
        rels.append(_rel(RelationKinds.CALLS, "A", f"B_{i}"))
        for j in range(3):
            entities.append(_m(f"C_{i}_{j}"))
            rels.append(_rel(RelationKinds.CALLS, f"B_{i}", f"C_{i}_{j}"))
    cfg = ImpactConfig(shrink_result_threshold=2)
    engine = _engine(entities, rels, cfg)
    result = engine.reverse_lookup("A", max_hops=5, auto_hops=True)
    assert result.hops_shrunk_reason == "result_too_large"
    assert result.hops_used == 1
    hits = {a.qualified_name for a in result.affected}
    assert hits == {"B_0", "B_1", "B_2"}


# ---------------------------------------------------------------------------
# 7. reverse_lookup entity_kinds 기본값
# ---------------------------------------------------------------------------
def test_reverse_lookup_default_entity_kinds_excludes_class() -> None:
    entities = [_m("A.run"), _c("pkg.B"), _m("pkg.B.foo")]
    rels = [
        _rel(RelationKinds.CONTAINS, "A.run", "pkg.B"),
        _rel(RelationKinds.CALLS, "pkg.B", "pkg.B.foo"),
    ]
    engine = _engine(entities, rels)
    result = engine.reverse_lookup("A.run", mode=ImpactMode.POTENTIAL, max_hops=3, auto_hops=False)
    # class 는 entity_kinds 기본값(method 등)에 없음 → affected 에서 제외
    # 하지만 경유는 가능 → pkg.B.foo 는 도달 가능
    hits = {a.qualified_name for a in result.affected}
    assert "pkg.B" not in hits
    assert "pkg.B.foo" in hits
