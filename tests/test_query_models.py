"""OD-11-B8-0 TDD — query DTOs.

DTO 레이어만 검증 : `ImpactQuery` / `ImpactMode` / `AffectedEntity`
/ `ImpactResult` / `EdgeRow` / `EntityRow` / `ImpactConfig`.

BFS 로직은 B8-1 (`test_query_engine_impact.py`) 에서 다룬다.

Spec: `toClaude/modeling/OD-11-B8-SPEC.md` §2.1, §5.1.
"""
from __future__ import annotations

import pytest

from backend.modeling.query.query_models import (
    AffectedEntity,
    EdgeRow,
    EntityRow,
    ImpactConfig,
    ImpactMode,
    ImpactQuery,
    ImpactResult,
)


# ---------------------------------------------------------------------------
# ImpactMode
# ---------------------------------------------------------------------------
def test_impact_mode_values() -> None:
    assert ImpactMode.SAFE.value == "safe"
    assert ImpactMode.OBSERVED.value == "observed"
    assert ImpactMode.POTENTIAL.value == "potential"
    # StrEnum equality
    assert ImpactMode("safe") is ImpactMode.SAFE


# ---------------------------------------------------------------------------
# ImpactQuery
# ---------------------------------------------------------------------------
def test_impact_query_defaults() -> None:
    q = ImpactQuery(target_fqn="com.acme.Service.doIt")
    assert q.mode == ImpactMode.OBSERVED
    assert q.max_hops == 5
    assert q.auto_hops is True
    assert q.direction == "incoming"
    assert q.edge_kinds is None
    assert q.entity_kinds is None


def test_impact_query_hops_bounds() -> None:
    with pytest.raises(ValueError):
        ImpactQuery(target_fqn="x", max_hops=0)
    with pytest.raises(ValueError):
        ImpactQuery(target_fqn="x", max_hops=21)
    ImpactQuery(target_fqn="x", max_hops=1)
    ImpactQuery(target_fqn="x", max_hops=20)


def test_impact_query_direction_enum() -> None:
    ImpactQuery(target_fqn="x", direction="incoming")
    ImpactQuery(target_fqn="x", direction="outgoing")
    with pytest.raises(ValueError):
        ImpactQuery(target_fqn="x", direction="sideways")


def test_impact_query_edge_kinds_as_set() -> None:
    q = ImpactQuery(target_fqn="x", edge_kinds={"calls", "publishes"})
    assert q.edge_kinds == {"calls", "publishes"}


# ---------------------------------------------------------------------------
# AffectedEntity
# ---------------------------------------------------------------------------
def test_affected_entity_shape() -> None:
    a = AffectedEntity(
        qualified_name="com.acme.Ctrl.handle",
        kind="method",
        distance=2,
        confidence_min=0.85,
        edge_source_chain=["runtime", "static_literal"],
        path=["com.acme.Service.doIt", "com.acme.Router.dispatch", "com.acme.Ctrl.handle"],
        reasons=["calls (runtime)", "calls (static_literal)"],
    )
    assert a.distance == 2
    assert a.confidence_min == pytest.approx(0.85)
    assert len(a.path) == 3


# ---------------------------------------------------------------------------
# ImpactResult
# ---------------------------------------------------------------------------
def test_impact_result_defaults() -> None:
    r = ImpactResult(
        source="com.acme.Service.doIt",
        mode=ImpactMode.OBSERVED,
        hops_used=3,
        hops_shrunk_reason=None,
        affected=[],
        unresolved_sources=[],
        message="ok",
    )
    assert r.hops_shrunk_reason is None
    assert r.affected == []


def test_impact_result_hops_shrunk_reason_literal() -> None:
    r = ImpactResult(
        source="x",
        mode=ImpactMode.SAFE,
        hops_used=2,
        hops_shrunk_reason="result_too_large",
        affected=[],
        unresolved_sources=[],
        message="",
    )
    assert r.hops_shrunk_reason == "result_too_large"


# ---------------------------------------------------------------------------
# EdgeRow / EntityRow
# ---------------------------------------------------------------------------
def test_edge_row_frozen() -> None:
    e = EdgeRow(
        source="A",
        target="B",
        kind="calls",
        confidence=0.9,
        edge_source="static_literal",
        attributes={"api": "getBean"},
    )
    assert e.source == "A"
    with pytest.raises(Exception):
        e.source = "C"  # type: ignore[misc]


def test_edge_row_edge_source_none_allowed() -> None:
    e = EdgeRow(source="A", target="B", kind="extends", confidence=1.0, edge_source=None, attributes={})
    assert e.edge_source is None


def test_entity_row_shape() -> None:
    e = EntityRow(qualified_name="com.acme.X", kind="class", attributes={})
    assert e.qualified_name == "com.acme.X"
    assert e.kind == "class"


# ---------------------------------------------------------------------------
# ImpactConfig
# ---------------------------------------------------------------------------
def test_impact_config_defaults() -> None:
    c = ImpactConfig()
    assert c.shrink_result_threshold == 200
    assert c.timeout_seconds == pytest.approx(2.0)
    assert c.frontier_warn_threshold == 500
    assert c.safe_min_confidence == pytest.approx(0.9)
    assert None in c.observed_sources
    assert "static_literal" in c.observed_sources
    assert "runtime" in c.observed_sources
    assert "static_unresolved" not in c.observed_sources
    assert "method" in c.default_entity_kinds
    assert "http_endpoint" in c.default_entity_kinds
    assert "class" not in c.default_entity_kinds


def test_impact_config_override() -> None:
    c = ImpactConfig(shrink_result_threshold=500, timeout_seconds=5.0)
    assert c.shrink_result_threshold == 500
    assert c.timeout_seconds == pytest.approx(5.0)


def test_impact_config_frozen() -> None:
    c = ImpactConfig()
    with pytest.raises(Exception):
        c.shrink_result_threshold = 99  # type: ignore[misc]
