"""OD-11-B8-2 TDD — `QueryEngine.impact` hops 자율 축소 + timeout + frontier 경고.

SPEC: `toClaude/modeling/OD-11-B8-SPEC.md` §4.

7 테스트:
  1. result_too_large : len(affected) > shrink_result_threshold → 다음 hop 중단
  2. timeout : elapsed > timeout_seconds → 현재 hop 완료 후 중단
  3. auto_hops=False 는 shrink 비활성화 (max_hops 까지 완주)
  4. auto_hops=False 는 timeout 비활성화
  5. frontier_warn_threshold 초과 시 경고 로깅만, 탐색은 max_hops 까지 계속
  6. hops_shrunk_reason 은 message 에도 노출
  7. 정상 범위에서는 hops_shrunk_reason is None
"""
from __future__ import annotations

import logging

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
# Fixtures (동일 패턴 as test_query_engine_impact.py)
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


def _rel(kind: str, src: str, tgt: str) -> CodeRelation:
    return CodeRelation(kind=kind, source=src, target=tgt, attributes={})


def _pr(entities, relations) -> ParseResult:
    return ParseResult(
        entities=list(entities),
        relations=list(relations),
        file_path="pr.java",
        language="java",
    )


def _engine(entities, relations, config) -> QueryEngine:
    view = InMemoryGraphView([_pr(entities, relations)])
    return QueryEngine(view, config)


def _chain_fanout(target: str, hop1_width: int, hop2_per_hop1: int):
    """hop0=target, hop1=H1_i (callers), hop2=H2_i_j (callers-of-callers) 체인."""
    entities = [_m(target)]
    rels = []
    for i in range(hop1_width):
        h1 = f"H1_{i}"
        entities.append(_m(h1))
        rels.append(_rel(RelationKinds.CALLS, h1, target))
        for j in range(hop2_per_hop1):
            h2 = f"H2_{i}_{j}"
            entities.append(_m(h2))
            rels.append(_rel(RelationKinds.CALLS, h2, h1))
    return entities, rels


# ---------------------------------------------------------------------------
# 1. result_too_large
# ---------------------------------------------------------------------------
def test_shrink_stops_when_results_exceed_threshold() -> None:
    entities, rels = _chain_fanout("T", hop1_width=3, hop2_per_hop1=3)
    cfg = ImpactConfig(shrink_result_threshold=2)
    engine = _engine(entities, rels, cfg)
    result = engine.impact(
        ImpactQuery(target_fqn="T", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=True)
    )
    # hop 1 후 affected=3 > 2 → 중단. hop 2 의 H2_* 는 미도달.
    assert result.hops_shrunk_reason == "result_too_large"
    assert result.hops_used == 1
    names = {a.qualified_name for a in result.affected}
    assert names == {"H1_0", "H1_1", "H1_2"}


# ---------------------------------------------------------------------------
# 2. timeout
# ---------------------------------------------------------------------------
def test_shrink_stops_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    entities, rels = _chain_fanout("T", hop1_width=2, hop2_per_hop1=2)
    cfg = ImpactConfig(timeout_seconds=1.0, shrink_result_threshold=9999)

    ticks = iter([0.0, 5.0, 999.0])  # start, after hop1, (not reached)
    monkeypatch.setattr(
        "backend.modeling.query.query_engine.time.monotonic",
        lambda: next(ticks, 999.0),
    )

    engine = _engine(entities, rels, cfg)
    result = engine.impact(
        ImpactQuery(target_fqn="T", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=True)
    )
    assert result.hops_shrunk_reason == "timeout"
    assert result.hops_used == 1
    names = {a.qualified_name for a in result.affected}
    assert names == {"H1_0", "H1_1"}


# ---------------------------------------------------------------------------
# 3. auto_hops=False disables shrink
# ---------------------------------------------------------------------------
def test_auto_hops_false_ignores_shrink_threshold() -> None:
    entities, rels = _chain_fanout("T", hop1_width=3, hop2_per_hop1=3)
    cfg = ImpactConfig(shrink_result_threshold=2)
    engine = _engine(entities, rels, cfg)
    result = engine.impact(
        ImpactQuery(target_fqn="T", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=False)
    )
    assert result.hops_shrunk_reason is None
    assert result.hops_used == 2  # hop1=3 + hop2=9 = 12 entities
    assert len(result.affected) == 12


# ---------------------------------------------------------------------------
# 4. auto_hops=False disables timeout
# ---------------------------------------------------------------------------
def test_auto_hops_false_ignores_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    entities, rels = _chain_fanout("T", hop1_width=2, hop2_per_hop1=2)
    cfg = ImpactConfig(timeout_seconds=1.0)

    ticks = iter([0.0, 999.0, 9999.0])
    monkeypatch.setattr(
        "backend.modeling.query.query_engine.time.monotonic",
        lambda: next(ticks, 99999.0),
    )

    engine = _engine(entities, rels, cfg)
    result = engine.impact(
        ImpactQuery(target_fqn="T", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=False)
    )
    assert result.hops_shrunk_reason is None
    assert result.hops_used == 2
    assert len(result.affected) == 6  # hop1=2 + hop2=4


# ---------------------------------------------------------------------------
# 5. frontier warning
# ---------------------------------------------------------------------------
def test_frontier_warn_threshold_logs_without_shrinking(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # hop1 에 caller 5개 → next_frontier=5, threshold=3
    entities, rels = _chain_fanout("T", hop1_width=5, hop2_per_hop1=1)
    cfg = ImpactConfig(frontier_warn_threshold=3, shrink_result_threshold=9999)
    engine = _engine(entities, rels, cfg)

    with caplog.at_level(logging.WARNING, logger="backend.modeling.query.query_engine"):
        result = engine.impact(
            ImpactQuery(target_fqn="T", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=True)
        )

    # 경고만 — 탐색은 끝까지 (hop1=5 + hop2=5 = 10)
    assert result.hops_shrunk_reason is None
    assert result.hops_used == 2
    assert len(result.affected) == 10
    warn_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("frontier" in m.lower() for m in warn_msgs)


# ---------------------------------------------------------------------------
# 6. message includes shrunk reason
# ---------------------------------------------------------------------------
def test_shrunk_message_mentions_reason() -> None:
    entities, rels = _chain_fanout("T", hop1_width=5, hop2_per_hop1=1)
    cfg = ImpactConfig(shrink_result_threshold=2)
    engine = _engine(entities, rels, cfg)
    result = engine.impact(
        ImpactQuery(target_fqn="T", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=True)
    )
    assert "result_too_large" in result.message


# ---------------------------------------------------------------------------
# 7. 정상 범위 no-shrink
# ---------------------------------------------------------------------------
def test_no_shrink_when_under_threshold() -> None:
    entities, rels = _chain_fanout("T", hop1_width=2, hop2_per_hop1=2)
    cfg = ImpactConfig(shrink_result_threshold=100, timeout_seconds=60.0)
    engine = _engine(entities, rels, cfg)
    result = engine.impact(
        ImpactQuery(target_fqn="T", mode=ImpactMode.POTENTIAL, max_hops=5, auto_hops=True)
    )
    assert result.hops_shrunk_reason is None
    assert result.hops_used == 2
    assert len(result.affected) == 6
