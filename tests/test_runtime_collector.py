"""OD-11-B7-2 TDD — runtime_collector.

JVM Agent (B9) 로부터 받을 reflection / call trace 를 synthetic
`ParseResult(file_path="<runtime>")` 로 변환하는 수집기 인터페이스.

이 단계에서는 Protocol + DTO + JSON 파일 reference collector + `merge_runtime_traces`
병합기까지 확정한다. 실제 instrumentation (ByteBuddy / java.lang.instrument) 은
B9 Slab sample repo 수령 이후 `toClaude/temp-runtime/` 에서 구현.

Spec: `toClaude/modeling/OD-11-B7-SPEC.md` §6.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)
from backend.modeling.code_analysis.runtime_collector import (
    CallTrace,
    JsonFileCollector,
    ReflectionTrace,
    RuntimeCollector,
    merge_runtime_traces,
)


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


def _method(fqn: str, reflection_calls=None) -> CodeEntity:
    attrs: dict[str, object] = {}
    if reflection_calls is not None:
        attrs["reflection_calls"] = list(reflection_calls)
    return CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name=fqn,
        name=fqn.rsplit(".", 1)[-1],
        file_path=f"{fqn.rsplit('.', 2)[-2]}.java",
        line_start=1,
        line_end=100,
        attributes=attrs,
    )


def _pr(file_path: str, entities, relations=()) -> ParseResult:
    return ParseResult(
        entities=list(entities),
        relations=list(relations),
        file_path=file_path,
        language="java",
    )


def _indices(parse_results: list[ParseResult]) -> dict[str, CodeEntity]:
    idx: dict[str, CodeEntity] = {}
    for pr in parse_results:
        for e in pr.entities:
            if e.kind in (EntityKinds.CLASS, EntityKinds.INTERFACE, EntityKinds.ENUM):
                idx[e.qualified_name] = e
    return idx


class _FakeCollector:
    """Duck-typed collector for Protocol conformance tests."""

    def __init__(self, ref_traces=(), call_traces=()):
        self._ref = list(ref_traces)
        self._call = list(call_traces)

    def load_reflection_traces(self) -> list[ReflectionTrace]:
        return list(self._ref)

    def load_call_traces(self) -> list[CallTrace]:
        return list(self._call)


def _find_runtime_pr(parse_results: list[ParseResult]) -> ParseResult:
    for pr in parse_results:
        if pr.file_path == "<runtime>":
            return pr
    raise AssertionError("synthetic <runtime> ParseResult not emitted")


# ---------------------------------------------------------------------------
# DTO shape
# ---------------------------------------------------------------------------
def test_reflection_trace_is_frozen_dataclass() -> None:
    t = ReflectionTrace(
        method_fqn="com.x.Orders.dispatch",
        api="Class.forName",
        line=15,
        resolved_target="com.x.FooShipper",
    )
    with pytest.raises(Exception):
        t.api = "changed"  # type: ignore[misc]
    assert t.sample_count == 1  # default


def test_call_trace_is_frozen_dataclass() -> None:
    t = CallTrace(caller_fqn="a.b.C.m", callee_fqn="a.b.D.n")
    with pytest.raises(Exception):
        t.caller_fqn = "x"  # type: ignore[misc]
    assert t.sample_count == 1


# ---------------------------------------------------------------------------
# Reflection trace → runtime edge
# ---------------------------------------------------------------------------
def test_reflection_trace_class_lookup_emits_runtime_calls() -> None:
    prs = [
        _pr("Orders.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")]),
        _pr("FooShipper.java", [_class("com.x.FooShipper")]),
    ]
    class_index = _indices(prs)
    collector = _FakeCollector(
        ref_traces=[
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="Class.forName",
                line=15,
                resolved_target="com.x.FooShipper",
                sample_count=127,
            )
        ]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    edges = [r for r in runtime_pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source == "com.x.Orders.dispatch"
    assert edge.target == "com.x.FooShipper"
    assert edge.attributes["source"] == "runtime"
    assert edge.attributes["confidence"] == 0.95
    assert edge.attributes["api"] == "Class.forName"
    assert edge.attributes["sample_count"] == 127
    assert edge.line == 15


def test_reflection_trace_method_lookup_emits_reflects_as_and_calls() -> None:
    """`getMethod` trace 는 class 로 CALLS + method 로 REFLECTS_AS 모두 emit.

    B9 런타임이 `clazz.getMethod("calc")` 에서 해소한 타깃은 METHOD FQN
    (`com.x.FooShipper.calc`). 그 prefix (`com.x.FooShipper`) 는 class FQN.
    Impact Analysis BFS 가 class-granularity 와 method-granularity 양쪽에서 도달
    가능해야 하므로 두 엣지 모두 emit.
    """
    prs = [
        _pr("Orders.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")]),
        _pr("FooShipper.java", [_class("com.x.FooShipper"), _method("com.x.FooShipper.calc")]),
    ]
    class_index = _indices(prs)
    collector = _FakeCollector(
        ref_traces=[
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="getMethod",
                line=20,
                resolved_target="com.x.FooShipper.calc",
            )
        ]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    calls = [r for r in runtime_pr.relations if r.kind == RelationKinds.CALLS]
    reflects = [r for r in runtime_pr.relations if r.kind == RelationKinds.REFLECTS_AS]
    assert len(calls) == 1
    assert calls[0].target == "com.x.FooShipper"
    assert calls[0].attributes["source"] == "runtime"
    assert len(reflects) == 1
    assert reflects[0].target == "com.x.FooShipper.calc"
    assert reflects[0].attributes["source"] == "runtime"
    assert reflects[0].attributes["confidence"] == 0.95


def test_runtime_trace_coexists_with_static_unresolved() -> None:
    """Same call-site can carry B7-1 `static_unresolved` + B7-2 `runtime` side-by-side."""
    caller = _method(
        "com.x.Orders.dispatch",
        reflection_calls=[
            {"api": "getBean", "arg": "dynamicName", "arg_kind": "variable", "line": 30}
        ],
    )
    static_unresolved_edge = CodeRelation(
        kind=RelationKinds.CALLS,
        source="com.x.Orders.dispatch",
        target="<reflection-site>",
        file_path="Orders.java",
        line=30,
        attributes={
            "source": "static_unresolved",
            "confidence": 0.4,
            "api": "getBean",
            "arg": "dynamicName",
            "arg_kind": "variable",
            "reason": "arg_not_literal",
        },
    )
    prs = [
        _pr("Orders.java", [_class("com.x.Orders"), caller], relations=[static_unresolved_edge]),
        _pr("BarShipper.java", [_class("com.x.BarShipper")]),
    ]
    class_index = _indices(prs)
    collector = _FakeCollector(
        ref_traces=[
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="getBean",
                line=30,
                resolved_target="com.x.BarShipper",
            )
        ]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    # static_unresolved remains on its owning ParseResult, untouched.
    owning_pr = [pr for pr in out if pr.file_path == "Orders.java"][0]
    static_edges = [
        r for r in owning_pr.relations
        if r.attributes.get("source") == "static_unresolved"
    ]
    assert len(static_edges) == 1
    # runtime edge on synthetic ParseResult.
    runtime_pr = _find_runtime_pr(out)
    runtime_edges = [
        r for r in runtime_pr.relations
        if r.attributes.get("source") == "runtime"
    ]
    assert len(runtime_edges) == 1
    assert runtime_edges[0].target == "com.x.BarShipper"


def test_trace_method_fqn_not_in_parse_results_is_skipped() -> None:
    prs = [_pr("Orders.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")])]
    class_index = _indices(prs)
    collector = _FakeCollector(
        ref_traces=[
            ReflectionTrace(
                method_fqn="com.unknown.Ghost.method",
                api="Class.forName",
                line=5,
                resolved_target="com.x.FooShipper",
            )
        ]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    assert runtime_pr.relations == []


def test_same_call_site_different_targets_emits_two_edges() -> None:
    """Dynamic dispatch: same (method_fqn, line) resolves to 2 different targets."""
    prs = [
        _pr("Orders.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")]),
        _pr("FooShipper.java", [_class("com.x.FooShipper")]),
        _pr("BarShipper.java", [_class("com.x.BarShipper")]),
    ]
    class_index = _indices(prs)
    collector = _FakeCollector(
        ref_traces=[
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="getBean",
                line=40,
                resolved_target="com.x.FooShipper",
                sample_count=60,
            ),
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="getBean",
                line=40,
                resolved_target="com.x.BarShipper",
                sample_count=40,
            ),
        ]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    edges = [r for r in runtime_pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 2
    targets = {e.target for e in edges}
    assert targets == {"com.x.FooShipper", "com.x.BarShipper"}
    by_target = {e.target: e for e in edges}
    assert by_target["com.x.FooShipper"].attributes["sample_count"] == 60
    assert by_target["com.x.BarShipper"].attributes["sample_count"] == 40


def test_duplicate_traces_merged_with_summed_sample_count() -> None:
    """Two identical (method_fqn, line, api, target) traces → one edge, sample_count summed."""
    prs = [
        _pr("Orders.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")]),
        _pr("FooShipper.java", [_class("com.x.FooShipper")]),
    ]
    class_index = _indices(prs)
    collector = _FakeCollector(
        ref_traces=[
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="getBean",
                line=50,
                resolved_target="com.x.FooShipper",
                sample_count=7,
            ),
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="getBean",
                line=50,
                resolved_target="com.x.FooShipper",
                sample_count=5,
            ),
        ]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    edges = [r for r in runtime_pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    assert edges[0].attributes["sample_count"] == 12


# ---------------------------------------------------------------------------
# Call trace (non-reflection)
# ---------------------------------------------------------------------------
def test_call_trace_emits_runtime_calls_edge() -> None:
    prs = [
        _pr("Ctrl.java", [_class("com.x.Ctrl"), _method("com.x.Ctrl.createOrder")]),
        _pr("Service.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")]),
    ]
    class_index = _indices(prs)
    collector = _FakeCollector(
        call_traces=[
            CallTrace(
                caller_fqn="com.x.Ctrl.createOrder",
                callee_fqn="com.x.Orders.dispatch",
                sample_count=127,
            )
        ]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    edges = [r for r in runtime_pr.relations if r.kind == RelationKinds.CALLS]
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source == "com.x.Ctrl.createOrder"
    assert edge.target == "com.x.Orders.dispatch"
    assert edge.attributes["source"] == "runtime"
    assert edge.attributes["confidence"] == 0.95
    assert edge.attributes["sample_count"] == 127


def test_call_trace_unknown_caller_skipped() -> None:
    prs = [_pr("Service.java", [_method("com.x.Orders.dispatch")])]
    class_index = _indices(prs)
    collector = _FakeCollector(
        call_traces=[CallTrace(caller_fqn="com.unknown.Ghost.m", callee_fqn="x")]
    )
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    assert runtime_pr.relations == []


# ---------------------------------------------------------------------------
# Empty / synthetic ParseResult
# ---------------------------------------------------------------------------
def test_empty_traces_still_emits_synthetic_parse_result() -> None:
    prs = [_pr("Orders.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")])]
    class_index = _indices(prs)
    out = merge_runtime_traces(prs, _FakeCollector(), class_index)
    runtime_pr = _find_runtime_pr(out)
    assert runtime_pr.file_path == "<runtime>"
    assert runtime_pr.language == "java"
    assert runtime_pr.entities == []
    assert runtime_pr.relations == []


# ---------------------------------------------------------------------------
# JsonFileCollector — schema validation
# ---------------------------------------------------------------------------
def test_json_file_collector_roundtrip(tmp_path: Path) -> None:
    payload = {
        "version": "1.0",
        "repo_id": "slab-engine",
        "reflection_traces": [
            {
                "method_fqn": "com.acme.OrderService.dispatch",
                "api": "ApplicationContext.getBean",
                "line": 15,
                "resolved_target": "com.acme.FooShipper",
                "sample_count": 127,
            }
        ],
        "call_traces": [
            {
                "caller_fqn": "com.acme.OrderController.createOrder",
                "callee_fqn": "com.acme.OrderService.dispatch",
                "sample_count": 127,
            }
        ],
    }
    fp = tmp_path / "trace.json"
    fp.write_text(json.dumps(payload))
    collector = JsonFileCollector(fp)
    ref = collector.load_reflection_traces()
    assert len(ref) == 1
    assert ref[0].method_fqn == "com.acme.OrderService.dispatch"
    assert ref[0].sample_count == 127
    call = collector.load_call_traces()
    assert len(call) == 1
    assert call[0].callee_fqn == "com.acme.OrderService.dispatch"


def test_json_file_collector_missing_required_field_raises(tmp_path: Path) -> None:
    payload = {
        "reflection_traces": [
            # missing `resolved_target`
            {"method_fqn": "a.b.C.m", "api": "Class.forName", "line": 1}
        ],
        "call_traces": [],
    }
    fp = tmp_path / "bad.json"
    fp.write_text(json.dumps(payload))
    collector = JsonFileCollector(fp)
    with pytest.raises(ValueError, match="resolved_target"):
        collector.load_reflection_traces()


# ---------------------------------------------------------------------------
# Protocol duck typing
# ---------------------------------------------------------------------------
def test_fake_collector_satisfies_protocol() -> None:
    """Any class with matching signatures works with merge_runtime_traces."""
    prs = [_pr("Orders.java", [_class("com.x.Orders"), _method("com.x.Orders.dispatch")])]
    class_index = _indices(prs)
    collector = _FakeCollector(
        ref_traces=[
            ReflectionTrace(
                method_fqn="com.x.Orders.dispatch",
                api="Class.forName",
                line=1,
                resolved_target="com.x.Orders",
            )
        ]
    )
    # No subclassing of RuntimeCollector required.
    assert isinstance(collector, RuntimeCollector)
    out = merge_runtime_traces(prs, collector, class_index)
    runtime_pr = _find_runtime_pr(out)
    assert len(runtime_pr.relations) == 1
