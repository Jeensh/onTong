"""OD-11-B8-0 TDD — InMemoryGraphView adapter.

`ParseResult` 리스트를 인덱싱해 `GraphView` Protocol (`outgoing`/`incoming`/
`entity`) 을 제공하는 인메모리 어댑터. Neo4j 읽기 어댑터는 B9 이후.

Spec: `toClaude/modeling/OD-11-B8-SPEC.md` §2.3.
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
from backend.modeling.query.graph_view import GraphView, InMemoryGraphView
from backend.modeling.query.query_models import EdgeRow, EntityRow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _class(fqn: str) -> CodeEntity:
    name = fqn.rsplit(".", 1)[-1]
    return CodeEntity(
        kind=EntityKinds.CLASS,
        qualified_name=fqn,
        name=name,
        file_path=f"{name}.java",
        line_start=1,
        line_end=1,
    )


def _method(fqn: str) -> CodeEntity:
    parts = fqn.rsplit(".", 2)
    owner = parts[-2] if len(parts) >= 2 else "Anon"
    return CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name=fqn,
        name=fqn.rsplit(".", 1)[-1],
        file_path=f"{owner}.java",
        line_start=1,
        line_end=20,
    )


def _rel(kind: str, src: str, tgt: str, *, source=None, confidence=None) -> CodeRelation:
    attrs: dict[str, object] = {}
    if source is not None:
        attrs["source"] = source
    if confidence is not None:
        attrs["confidence"] = confidence
    return CodeRelation(kind=kind, source=src, target=tgt, attributes=attrs)


def _pr(file_path: str, entities, relations) -> ParseResult:
    return ParseResult(
        entities=list(entities),
        relations=list(relations),
        file_path=file_path,
        language="java",
    )


# ---------------------------------------------------------------------------
# Protocol satisfaction
# ---------------------------------------------------------------------------
def test_in_memory_graph_view_satisfies_protocol() -> None:
    view = InMemoryGraphView([])
    assert isinstance(view, GraphView)


# ---------------------------------------------------------------------------
# entity() lookup
# ---------------------------------------------------------------------------
def test_entity_lookup_returns_entity_row() -> None:
    pr = _pr("Foo.java", [_method("com.acme.Foo.bar")], [])
    view = InMemoryGraphView([pr])
    row = view.entity("com.acme.Foo.bar")
    assert row is not None
    assert row.qualified_name == "com.acme.Foo.bar"
    assert row.kind == "method"


def test_entity_lookup_missing_returns_none() -> None:
    view = InMemoryGraphView([])
    assert view.entity("does.not.exist") is None


def test_entity_lookup_preserves_attributes() -> None:
    m = CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name="com.acme.X.y",
        name="y",
        file_path="X.java",
        line_start=1,
        line_end=2,
        attributes={"http_method": "GET"},
    )
    view = InMemoryGraphView([_pr("X.java", [m], [])])
    row = view.entity("com.acme.X.y")
    assert row is not None
    assert row.attributes.get("http_method") == "GET"


# ---------------------------------------------------------------------------
# outgoing() / incoming()
# ---------------------------------------------------------------------------
def test_outgoing_returns_edges_where_fqn_is_source() -> None:
    rels = [
        _rel(RelationKinds.CALLS, "com.acme.A.m", "com.acme.B.n", source="static_literal", confidence=0.9),
        _rel(RelationKinds.CALLS, "com.acme.A.m", "com.acme.C.o", source="runtime", confidence=0.95),
        _rel(RelationKinds.CALLS, "com.acme.Z.q", "com.acme.A.m"),
    ]
    pr = _pr(
        "A.java",
        [_method("com.acme.A.m"), _method("com.acme.B.n"), _method("com.acme.C.o"), _method("com.acme.Z.q")],
        rels,
    )
    view = InMemoryGraphView([pr])
    edges = view.outgoing("com.acme.A.m")
    assert {e.target for e in edges} == {"com.acme.B.n", "com.acme.C.o"}


def test_incoming_returns_edges_where_fqn_is_target() -> None:
    rels = [
        _rel(RelationKinds.CALLS, "com.acme.Z.q", "com.acme.A.m", source="runtime", confidence=0.95),
        _rel(RelationKinds.CALLS, "com.acme.Y.p", "com.acme.A.m", source="static_literal", confidence=0.9),
        _rel(RelationKinds.CALLS, "com.acme.A.m", "com.acme.B.n"),
    ]
    pr = _pr(
        "Many.java",
        [_method("com.acme.A.m"), _method("com.acme.Z.q"), _method("com.acme.Y.p"), _method("com.acme.B.n")],
        rels,
    )
    view = InMemoryGraphView([pr])
    edges = view.incoming("com.acme.A.m")
    assert {e.source for e in edges} == {"com.acme.Z.q", "com.acme.Y.p"}


def test_edge_row_carries_source_and_confidence_from_attributes() -> None:
    r = _rel(RelationKinds.CALLS, "A", "B", source="runtime", confidence=0.95)
    pr = _pr("x.java", [_method("A"), _method("B")], [r])
    view = InMemoryGraphView([pr])
    (edge,) = view.outgoing("A")
    assert edge.edge_source == "runtime"
    assert edge.confidence == pytest.approx(0.95)


def test_edge_row_without_source_defaults() -> None:
    r = _rel(RelationKinds.EXTENDS, "A", "B")
    pr = _pr(
        "x.java",
        [_class("A"), _class("B")],
        [r],
    )
    view = InMemoryGraphView([pr])
    (edge,) = view.outgoing("A")
    assert edge.edge_source is None
    # confidence 기본값은 1.0 (정적 확정 엣지)
    assert edge.confidence == pytest.approx(1.0)


def test_outgoing_incoming_missing_fqn_returns_empty() -> None:
    view = InMemoryGraphView([])
    assert view.outgoing("nope") == []
    assert view.incoming("nope") == []


def test_multiple_parse_results_merge() -> None:
    pr1 = _pr("A.java", [_method("A.m")], [_rel(RelationKinds.CALLS, "A.m", "B.n")])
    pr2 = _pr(
        "B.java",
        [_method("B.n"), _method("C.o")],
        [_rel(RelationKinds.CALLS, "B.n", "C.o")],
    )
    view = InMemoryGraphView([pr1, pr2])
    assert view.entity("A.m") is not None
    assert view.entity("B.n") is not None
    assert view.entity("C.o") is not None
    out_a = view.outgoing("A.m")
    assert [e.target for e in out_a] == ["B.n"]
    out_b = view.outgoing("B.n")
    assert [e.target for e in out_b] == ["C.o"]


def test_edge_kind_preserved() -> None:
    r = _rel(RelationKinds.PUBLISHES, "Producer.send", "OrderEvent")
    pr = _pr("P.java", [_method("Producer.send"), _class("OrderEvent")], [r])
    view = InMemoryGraphView([pr])
    (edge,) = view.outgoing("Producer.send")
    assert edge.kind == "publishes"
