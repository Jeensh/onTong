"""OD-11-B7-2 : Runtime trace collector.

JVM Agent (B9) 또는 사전 기록된 JSON 파일에서 reflection / 일반 호출 trace 를 받아
synthetic `ParseResult(file_path="<runtime>")` 로 변환하는 수집기 인터페이스와
병합기. 실제 instrumentation 은 B9 Slab sample repo 수령 이후 `toClaude/temp-runtime/`
에서 구현. 이 단계는 Protocol + DTO + `JsonFileCollector` + `merge_runtime_traces`
까지 확정 (SPEC §Q3 "Protocol+DTO only" 범위).

디자인 :
  - Coexist 3-way : 같은 call-site 에 B7-1 `static_unresolved` 와 B7-2 `runtime`
    엣지가 병존. runtime 이 static_unresolved 를 덮어쓰지 않는다. (Q2 결정)
  - synthetic `ParseResult(file_path="<runtime>")` : CrossFileEnricher 의
    `"<db_schema>"` 와 동일 패턴. graph_writer 가 file_path 를 파일 경로가 아닌
    심볼릭 네임스페이스로 취급.
  - 중복 병합 : 같은 `(method_fqn, line, api, resolved_target)` trace 는 한 엣지로
    `sample_count` 합산. 다른 target 은 분기 유지 (동적 dispatch 표현).
  - `getMethod`/`getField` 류는 runtime trace 에서만 REFLECTS_AS 엣지 emit + class
    레벨 CALLS 병행. B7-1 는 static_unresolved 로 남겨둠.

Spec: `toClaude/modeling/OD-11-B7-SPEC.md` §6.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)

_RUNTIME_FILE_PATH = "<runtime>"
_RUNTIME_SOURCE = "runtime"
_RUNTIME_CONFIDENCE = 0.95

# API → 엣지 분류. class-lookup → CALLS only. method/field-lookup → CALLS (to class)
# + REFLECTS_AS (to member). getBean / Class.forName / ClassLoader 계열은 class.
_METHOD_LOOKUP_APIS = frozenset(
    {
        "getMethod",
        "getDeclaredMethod",
        "getMethods",
        "getDeclaredMethods",
        "Method.invoke",
    }
)
_FIELD_LOOKUP_APIS = frozenset(
    {
        "getField",
        "getDeclaredField",
        "getFields",
        "getDeclaredFields",
    }
)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReflectionTrace:
    """Single observed reflection call-site resolution.

    `method_fqn` : 호출을 수행한 caller METHOD FQN (Spring AOP proxy 가 아닌 실 메서드).
    `api`        : "Class.forName" / "getBean" / "getMethod" 등.
    `line`       : 소스 라인. B5-8 marker 의 `line` 과 매칭 키로 사용.
    `resolved_target` : 런타임이 실제로 로드/리플렉션 해소한 FQN.
                        class-lookup → CLASS FQN, method-lookup → METHOD FQN.
    `sample_count`    : 동일 trace 관측 횟수. 중복 병합 시 합산.
    """

    method_fqn: str
    api: str
    line: int
    resolved_target: str
    sample_count: int = 1


@dataclass(frozen=True)
class CallTrace:
    """Non-reflection 일반 런타임 호출 trace (B8 확장 여지).

    예: APM / tracing agent 가 찍은 caller → callee 엣지. static analyzer 가 놓친
    interface polymorphism / lambda / proxy 경로 검증에 사용.
    """

    caller_fqn: str
    callee_fqn: str
    sample_count: int = 1


# ---------------------------------------------------------------------------
# Collector Protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class RuntimeCollector(Protocol):
    """JVM Agent / JSON 파일 / DB 등 소스 무관 수집기 인터페이스.

    duck-typed: subclassing 불필요. 두 메서드 시그니처만 맞으면 `isinstance(obj,
    RuntimeCollector)` 도 통과 (`@runtime_checkable`).
    """

    def load_reflection_traces(self) -> list[ReflectionTrace]: ...
    def load_call_traces(self) -> list[CallTrace]: ...


# ---------------------------------------------------------------------------
# Reference implementation — JSON file
# ---------------------------------------------------------------------------
_REQUIRED_REF_FIELDS = ("method_fqn", "api", "line", "resolved_target")
_REQUIRED_CALL_FIELDS = ("caller_fqn", "callee_fqn")


class JsonFileCollector:
    """Reads traces from a JSON file. Schema in SPEC §6.2.

    Loads lazily per call. Fail-fast on missing required fields (ValueError).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load_reflection_traces(self) -> list[ReflectionTrace]:
        payload = self._read()
        raw = payload.get("reflection_traces", [])
        out: list[ReflectionTrace] = []
        for item in raw:
            _require_fields(item, _REQUIRED_REF_FIELDS, context="reflection_trace")
            out.append(
                ReflectionTrace(
                    method_fqn=str(item["method_fqn"]),
                    api=str(item["api"]),
                    line=int(item["line"]),
                    resolved_target=str(item["resolved_target"]),
                    sample_count=int(item.get("sample_count", 1)),
                )
            )
        return out

    def load_call_traces(self) -> list[CallTrace]:
        payload = self._read()
        raw = payload.get("call_traces", [])
        out: list[CallTrace] = []
        for item in raw:
            _require_fields(item, _REQUIRED_CALL_FIELDS, context="call_trace")
            out.append(
                CallTrace(
                    caller_fqn=str(item["caller_fqn"]),
                    callee_fqn=str(item["callee_fqn"]),
                    sample_count=int(item.get("sample_count", 1)),
                )
            )
        return out

    def _read(self) -> dict:
        with self._path.open("r", encoding="utf-8") as f:
            return json.load(f)


def _require_fields(item: dict, fields: Iterable[str], *, context: str) -> None:
    missing = [f for f in fields if f not in item]
    if missing:
        raise ValueError(
            f"{context} missing required field(s): {', '.join(missing)} (item={item!r})"
        )


# ---------------------------------------------------------------------------
# Merger
# ---------------------------------------------------------------------------
def merge_runtime_traces(
    parse_results: list[ParseResult],
    collector: RuntimeCollector,
    class_index: dict[str, CodeEntity],
) -> list[ParseResult]:
    """Append a synthetic `ParseResult(file_path="<runtime>")` with runtime edges.

    Per `ReflectionTrace` (filtered to known caller METHOD):
      - class-lookup api → `CALLS{source:runtime, 0.95}` to `resolved_target`
      - method-lookup api → `CALLS` to class part (split on last `.`)
                          + `REFLECTS_AS{source:runtime, 0.95}` to full FQN
      - field-lookup api → same as method-lookup (field FQN target for REFLECTS_AS)

    Per `CallTrace` (filtered to known caller METHOD):
      - `CALLS{source:runtime, 0.95}` caller → callee

    Duplicate key `(source, target, kind, line, api)` → one edge, `sample_count` summed.
    Other traces diverge: different `resolved_target` at same call-site → two edges
    (captures dynamic dispatch).

    `class_index` : currently only used for symmetry with B7-1; resolved_target is
    assumed trustworthy (runtime observed it). Future: cross-check that the trace
    target exists in the parsed graph; mismatches would be a B9 instrumentation bug.

    Returns parse_results with the synthetic ParseResult appended (mutates caller).
    """
    method_fqns = _collect_method_fqns(parse_results)

    # edge aggregation : key → attrs accumulator
    agg: dict[tuple, dict] = {}

    for trace in collector.load_reflection_traces():
        if trace.method_fqn not in method_fqns:
            continue
        for kind, target in _edge_targets(trace):
            key = (
                RelationKinds.CALLS if kind == "calls" else RelationKinds.REFLECTS_AS,
                trace.method_fqn,
                target,
                trace.line,
                trace.api,
            )
            if key in agg:
                agg[key]["sample_count"] += trace.sample_count
            else:
                agg[key] = {
                    "source": _RUNTIME_SOURCE,
                    "confidence": _RUNTIME_CONFIDENCE,
                    "api": trace.api,
                    "sample_count": trace.sample_count,
                }

    for trace in collector.load_call_traces():
        if trace.caller_fqn not in method_fqns:
            continue
        key = (
            RelationKinds.CALLS,
            trace.caller_fqn,
            trace.callee_fqn,
            None,
            None,
        )
        if key in agg:
            agg[key]["sample_count"] += trace.sample_count
        else:
            agg[key] = {
                "source": _RUNTIME_SOURCE,
                "confidence": _RUNTIME_CONFIDENCE,
                "sample_count": trace.sample_count,
            }

    relations: list[CodeRelation] = []
    for (kind, src, tgt, line, _api), attrs in agg.items():
        relations.append(
            CodeRelation(
                kind=kind,
                source=src,
                target=tgt,
                file_path=_RUNTIME_FILE_PATH,
                line=line,
                attributes=dict(attrs),
            )
        )

    parse_results.append(
        ParseResult(
            entities=[],
            relations=relations,
            file_path=_RUNTIME_FILE_PATH,
            language="java",
        )
    )
    return parse_results


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _collect_method_fqns(parse_results: Iterable[ParseResult]) -> set[str]:
    out: set[str] = set()
    for pr in parse_results:
        for e in pr.entities:
            if e.kind in (EntityKinds.METHOD, EntityKinds.CONSTRUCTOR):
                out.add(e.qualified_name)
    return out


def _edge_targets(trace: ReflectionTrace) -> list[tuple[str, str]]:
    """Return [(edge_kind, target_fqn), ...] for the trace.

    edge_kind ∈ {"calls", "reflects_as"}.
    """
    if trace.api in _METHOD_LOOKUP_APIS or trace.api in _FIELD_LOOKUP_APIS:
        # resolved_target is member FQN (com.x.Foo.calc). Split once from the right.
        class_fqn, sep, _member = trace.resolved_target.rpartition(".")
        if not sep:
            # malformed: no class prefix → only REFLECTS_AS with no class edge.
            return [("reflects_as", trace.resolved_target)]
        return [
            ("calls", class_fqn),
            ("reflects_as", trace.resolved_target),
        ]
    # class-lookup (Class.forName / getBean / newInstance / Proxy.newProxyInstance 등)
    return [("calls", trace.resolved_target)]


__all__ = (
    "ReflectionTrace",
    "CallTrace",
    "RuntimeCollector",
    "JsonFileCollector",
    "merge_runtime_traces",
)
