"""OD-11-B7-1 : Reflection literal resolver.

Repo-level post-processor that promotes B5-8/B7-0 `reflection_calls` markers with
`arg_kind == "literal"` into `CALLS` edges by matching against `class_index` and
`bean_index`. Non-literal args (`variable` / `concat` / `type` / `other`) are left
for B7-2 runtime collector.

Design:
  - Mirrors the CrossFileEnricher pattern — per-file analyzer leaves markers,
    repo-level helper emits edges (SPEC §0.5).
  - Output edges always have `attributes["source"]` ∈ {"static_literal", "static_unresolved"}
    so downstream Impact Analysis queries can slice by confidence tier (Q2 Coexist 3-way).
  - `getMethod` / `getField` / `Proxy.newProxyInstance` are deferred — they need
    receiver-type tracking (stored in a separate marker which B7-1 PoC does not yet add).

Spec: `toClaude/modeling/OD-11-B7-SPEC.md` §5.
"""
from __future__ import annotations

from typing import Iterable

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)

_CONFIDENCE_MATCH = 0.9
_CONFIDENCE_UNRESOLVED = 0.4

_SOURCE_STATIC_LITERAL = "static_literal"
_SOURCE_STATIC_UNRESOLVED = "static_unresolved"

_UNRESOLVED_TARGET = "<reflection-site>"

# APIs handled in B7-1 (literal-only). Others are deferred.
_API_GET_BEAN = "getBean"
_API_CLASS_FORNAME = "Class.forName"


def build_bean_index(parse_results: Iterable[ParseResult]) -> dict[str, CodeEntity]:
    """Build `bean_name → SPRING_BEAN CodeEntity` from DIAnalyzer output.

    Relies on `DIAnalyzer` recording `attributes["bean_name"]` on each
    `SPRING_BEAN` entity. `@Component("name")` → explicit; unnamed stereotype →
    camelCase; `@Bean(name="x")` / `@Bean` method → explicit or method name.

    Collision rule: first-seen wins (parser order). Real projects should not
    have duplicate bean names; if they do, this mirrors Spring's ambiguous-bean
    behavior and downstream users can check class_index for all candidates.
    """
    out: dict[str, CodeEntity] = {}
    for pr in parse_results:
        for e in pr.entities:
            if e.kind != EntityKinds.SPRING_BEAN:
                continue
            name = e.attributes.get("bean_name")
            if not isinstance(name, str) or not name:
                continue
            out.setdefault(name, e)
    return out


def resolve_reflection_literals(
    parse_results: list[ParseResult],
    class_index: dict[str, CodeEntity],
    bean_index: dict[str, CodeEntity],
) -> list[ParseResult]:
    """In-place: append `CALLS` edges for literal-arg reflection markers.

    Per marker with `arg_kind == "literal"`:
      - `getBean("name")`   → bean_index lookup → class FQN target
      - `Class.forName("FQN")` → class_index lookup → class FQN target
      - Match → `CALLS{source:static_literal, confidence:0.9}`
      - Miss  → `CALLS{source:static_unresolved, confidence:0.4, reason}` with
                `target="<reflection-site>"` sentinel
      - Other APIs (`getMethod`, `getField`, `Proxy.newProxyInstance`) → skip
        (need receiver-type tracking; deferred)

    Non-literal arg_kinds are skipped (B7-2 runtime collector handles them).
    Returns the same list (caller identity preserved).
    """
    for pr in parse_results:
        new_edges: list[CodeRelation] = []
        for entity in pr.entities:
            if entity.kind not in (EntityKinds.METHOD, EntityKinds.CONSTRUCTOR):
                continue
            markers = entity.attributes.get("reflection_calls")
            if not isinstance(markers, list):
                continue
            for marker in markers:
                if not isinstance(marker, dict):
                    continue
                edge = _resolve_marker(
                    marker,
                    caller_fqn=entity.qualified_name,
                    class_index=class_index,
                    bean_index=bean_index,
                    file_path=pr.file_path,
                )
                if edge is not None:
                    new_edges.append(edge)
        pr.relations.extend(new_edges)
    return parse_results


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _resolve_marker(
    marker: dict,
    *,
    caller_fqn: str,
    class_index: dict[str, CodeEntity],
    bean_index: dict[str, CodeEntity],
    file_path: str,
) -> CodeRelation | None:
    if marker.get("arg_kind") != "literal":
        return None

    api = marker.get("api")
    arg = marker.get("arg")
    line = marker.get("line")
    if not isinstance(api, str) or not isinstance(arg, str):
        return None

    if api == _API_GET_BEAN:
        bean = bean_index.get(arg)
        if bean is not None:
            return _edge_match(caller_fqn, bean.qualified_name, api, arg, line, file_path)
        return _edge_unresolved(caller_fqn, api, arg, line, "bean_not_found", file_path)

    if api == _API_CLASS_FORNAME:
        if arg in class_index:
            return _edge_match(caller_fqn, arg, api, arg, line, file_path)
        return _edge_unresolved(caller_fqn, api, arg, line, "class_not_found", file_path)

    # getMethod / getField / Proxy.newProxyInstance — deferred (B7-2+).
    return None


def _edge_match(
    caller_fqn: str,
    target_fqn: str,
    api: str,
    arg: str,
    line: object,
    file_path: str,
) -> CodeRelation:
    attrs: dict[str, object] = {
        "source": _SOURCE_STATIC_LITERAL,
        "confidence": _CONFIDENCE_MATCH,
        "api": api,
        "arg": arg,
    }
    if isinstance(line, int):
        attrs["line"] = line
    return CodeRelation(
        kind=RelationKinds.CALLS,
        source=caller_fqn,
        target=target_fqn,
        file_path=file_path,
        line=line if isinstance(line, int) else None,
        attributes=attrs,
    )


def _edge_unresolved(
    caller_fqn: str,
    api: str,
    arg: str,
    line: object,
    reason: str,
    file_path: str,
) -> CodeRelation:
    attrs: dict[str, object] = {
        "source": _SOURCE_STATIC_UNRESOLVED,
        "confidence": _CONFIDENCE_UNRESOLVED,
        "api": api,
        "arg": arg,
        "arg_kind": "literal",
        "reason": reason,
    }
    if isinstance(line, int):
        attrs["line"] = line
    return CodeRelation(
        kind=RelationKinds.CALLS,
        source=caller_fqn,
        target=_UNRESOLVED_TARGET,
        file_path=file_path,
        line=line if isinstance(line, int) else None,
        attributes=attrs,
    )


__all__ = (
    "build_bean_index",
    "resolve_reflection_literals",
)
