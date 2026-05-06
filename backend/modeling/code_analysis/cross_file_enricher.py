"""OD-11-B6-4 — CrossFileEnricher repo-level post-batch.

Consumes per-file markers emitted by B6-1 (MapStruct implicit), B6-2 (BeanUtils),
and B6-3 (NativeSQL) and produces:
  - concrete PROPAGATES_TO edges for MapStruct implicit + BeanUtils intersections
  - DB_COLUMN nodes, READS/WRITES edges, and deduped DB_TABLE nodes for NativeSQL

Design:
  - In-place mutation of the input parse_results list:
    - New relations are appended to caller ParseResults.
    - Per-method attribute updates (beanutils_ambiguous_types) are applied
      in-place on the method's attributes dict.
    - A synthetic ParseResult(file_path="<db_schema>") is appended at the tail
      to hold repo-level DB_TABLE / DB_COLUMN entities.
  - CodeEntity / CodeRelation are frozen dataclasses, but attribute dicts are
    mutable, so marker writes happen on the dict directly.

Spec: toClaude/modeling/OD-11-B6-SPEC.md §6 (2026-04-19 rev.).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)

_SYNTHETIC_FILE_PATH = "<db_schema>"
_DYNAMIC = "<dynamic>"
_DIALECT_JPQL = "jpql"

_FIELD_EXCLUDED_NAMES = frozenset({"serialVersionUID", "$jacocoData"})
_FIELD_EXCLUDED_STATIC = frozenset({"static"})
_FIELD_EXCLUDED_TRANSIENT = frozenset({"transient"})


def enrich_repo(
    parse_results: list[ParseResult],
    class_index: dict[str, CodeEntity],
    field_index: dict[str, list[CodeEntity]],
) -> list[ParseResult]:
    """Finalize B6-1/2/3 markers and dedupe DB_TABLE/DB_COLUMN nodes.

    Mutates parse_results in-place and appends a synthetic ParseResult
    with file_path="<db_schema>" at the tail. Returns the same list object.
    """
    db_tables: dict[str, CodeEntity] = {}
    db_columns: dict[str, CodeEntity] = {}

    for pr in parse_results:
        _finalize_mapstruct_implicit(pr, class_index, field_index)
        _resolve_beanutils_intersections(pr, class_index, field_index)
        _resolve_native_sql(pr, class_index, db_tables, db_columns)

    # P30-1 — INTERCEPTS class → method fan-out
    intercepts_fanout = _expand_intercepts_to_methods(parse_results)

    # P30-2 — publisher → event_type → handler 직접 합성 엣지 (calls_via_event)
    event_chain_edges = _synthesize_event_chain_edges(parse_results)

    synth = ParseResult(
        entities=list(db_tables.values()) + list(db_columns.values()),
        relations=intercepts_fanout + event_chain_edges,
        file_path=_SYNTHETIC_FILE_PATH,
        language="java",
    )
    parse_results.append(synth)
    return parse_results


def _synthesize_event_chain_edges(parse_results: list[ParseResult]) -> list:
    """P30-2 — publisher method → event_type → handler method 의 직접 edge 합성.

    EventsAnalyzer 가 emit 한 PUBLISHES (publisher → event_type) + HANDLES (handler → event_type) 엣지를
    조합해서 publisher → handler 직접 calls_via_event 엣지를 추가. async marker 도 함께 attribute 로.
    """
    from collections import defaultdict
    from backend.modeling.code_analysis.parser_protocol import CodeRelation

    publishes_by_event: dict[str, list[str]] = defaultdict(list)
    handles_by_event: dict[str, list[str]] = defaultdict(list)
    async_methods: set[str] = set()
    tx_phase_by_method: dict[str, str] = {}

    for pr in parse_results:
        for e in pr.entities:
            if e.kind == "async_marker":
                attrs = e.attributes or {}
                method_fqn = attrs.get("method_fqn")
                if method_fqn:
                    if attrs.get("async"):
                        async_methods.add(str(method_fqn))
                    if attrs.get("tx_phase"):
                        tx_phase_by_method[str(method_fqn)] = str(attrs["tx_phase"])
        for rel in pr.relations:
            if rel.kind == "publishes":
                publishes_by_event[rel.target].append(rel.source)
            elif rel.kind == "handles":
                handles_by_event[rel.target].append(rel.source)

    out: list[CodeRelation] = []
    for event_fqn, publishers in publishes_by_event.items():
        for pub in publishers:
            for hdl in handles_by_event.get(event_fqn, []):
                attrs: dict[str, object] = {
                    "event_type": event_fqn,
                    "synthesized": True,
                }
                if hdl in async_methods:
                    attrs["async"] = True
                if hdl in tx_phase_by_method:
                    attrs["tx_phase"] = tx_phase_by_method[hdl]
                out.append(CodeRelation(
                    kind="calls_via_event",
                    source=pub,
                    target=hdl,
                    file_path="",
                    line=0,
                    attributes=attrs,
                ))
    return out


def _expand_intercepts_to_methods(parse_results: list[ParseResult]) -> list:
    """P30-1 — INTERCEPTS edge target 이 class FQN 인 경우, 그 class 의 public method 단위로 fan-out.

    원본 INTERCEPTS edge 는 그대로 유지하고 (class-level), 추가로 method-level synthesized edge 생성.
    """
    from backend.modeling.code_analysis.parser_protocol import CodeRelation, RelationKinds

    methods_by_class: dict[str, list[str]] = {}
    for pr in parse_results:
        for e in pr.entities:
            if e.kind == "method" and e.parent:
                # public visibility 만 (public 명시 없으면 default)
                vis = (e.attributes or {}).get("visibility", "package")
                if vis == "public" or vis == "package":
                    methods_by_class.setdefault(e.parent, []).append(e.qualified_name)

    out: list[CodeRelation] = []
    for pr in parse_results:
        for rel in pr.relations:
            if rel.kind != RelationKinds.INTERCEPTS:
                continue
            target = rel.target
            # target 이 class fqn 이면 method 단위로 expand
            method_fqns = methods_by_class.get(target)
            if not method_fqns:
                continue
            for mfqn in method_fqns:
                out.append(CodeRelation(
                    kind=RelationKinds.INTERCEPTS,
                    source=rel.source,
                    target=mfqn,
                    file_path=rel.file_path,
                    line=rel.line,
                    attributes={
                        **(rel.attributes or {}),
                        "fan_out_from_class": target,
                        "synthesized": True,
                    },
                ))
    return out


def build_indices(
    parse_results: Iterable[ParseResult],
) -> tuple[dict[str, CodeEntity], dict[str, list[CodeEntity]]]:
    """Build class/field indices and merge JPA annotation info into classes."""
    from backend.modeling.code_analysis.jpa_annotation_extractor import (
        JpaAnnotationExtractor,
    )

    class_index: dict[str, CodeEntity] = {}
    field_index: dict[str, list[CodeEntity]] = {}
    for pr in parse_results:
        for e in pr.entities:
            if e.kind in (
                EntityKinds.CLASS,
                EntityKinds.INTERFACE,
                EntityKinds.ENUM,
            ):
                class_index[e.qualified_name] = e
            elif e.kind == EntityKinds.FIELD and e.parent:
                field_index.setdefault(e.parent, []).append(e)

    extractor = JpaAnnotationExtractor()
    for class_fqn, class_entity in class_index.items():
        fields = field_index.get(class_fqn, [])
        extractor.merge_into(class_entity, fields)
    return class_index, field_index


def _resolve_type(
    type_name: str, class_index: dict[str, CodeEntity]
) -> list[str]:
    if type_name in class_index:
        return [type_name]
    suffix = "." + type_name
    return [fqn for fqn in class_index if fqn.endswith(suffix)]


def _eligible_field_names(
    class_fqn: str, field_index: dict[str, list[CodeEntity]]
) -> set[str]:
    fields = field_index.get(class_fqn, [])
    eligible: set[str] = set()
    for f in fields:
        if f.name in _FIELD_EXCLUDED_NAMES:
            continue
        mods = set(f.modifiers)
        if mods & _FIELD_EXCLUDED_STATIC:
            continue
        if mods & _FIELD_EXCLUDED_TRANSIENT:
            continue
        eligible.add(f.name)
    return eligible


def _finalize_mapstruct_implicit(
    pr: ParseResult,
    class_index: dict[str, CodeEntity],
    field_index: dict[str, list[CodeEntity]],
) -> None:
    existing = {
        (r.source, r.target)
        for r in pr.relations
        if r.kind == RelationKinds.PROPAGATES_TO
    }
    new_relations: list[CodeRelation] = []

    for entity in list(pr.entities):
        markers = entity.attributes.get("mapstruct_implicit_fields")
        if not markers:
            continue
        for marker in markers:
            src_candidates = _resolve_type(marker["src_type"], class_index)
            dst_candidates = _resolve_type(marker["dst_type"], class_index)
            if len(src_candidates) != 1 or len(dst_candidates) != 1:
                continue
            src_fqn = src_candidates[0]
            dst_fqn = dst_candidates[0]
            mapper_fqn = marker["mapper_fqn"]
            via_method = f"{mapper_fqn}.{marker['method']}"

            intersection = _eligible_field_names(src_fqn, field_index) & _eligible_field_names(dst_fqn, field_index)
            for fname in intersection:
                src_qn = f"{src_fqn}.{fname}"
                dst_qn = f"{dst_fqn}.{fname}"
                if (src_qn, dst_qn) in existing:
                    continue
                existing.add((src_qn, dst_qn))
                new_relations.append(
                    CodeRelation(
                        kind=RelationKinds.PROPAGATES_TO,
                        source=src_qn,
                        target=dst_qn,
                        attributes={
                            "via_methods": [via_method],
                            "confidence": 0.9,
                            "implicit": True,
                            "mapper_fqn": mapper_fqn,
                        },
                    )
                )
    pr.relations.extend(new_relations)


def _resolve_beanutils_intersections(
    pr: ParseResult,
    class_index: dict[str, CodeEntity],
    field_index: dict[str, list[CodeEntity]],
) -> None:
    emitted: set[tuple[str, str]] = set()
    new_relations: list[CodeRelation] = []

    for entity in list(pr.entities):
        markers = entity.attributes.get("beanutils_calls")
        if not markers:
            continue
        ambiguous: list[dict[str, object]] = []
        for marker in markers:
            src_candidates = _resolve_type(marker["src_type"], class_index)
            dst_candidates = _resolve_type(marker["dst_type"], class_index)
            if len(src_candidates) != 1 or len(dst_candidates) != 1:
                ambiguous.append(
                    {
                        "call_line": marker.get("line"),
                        "src_candidates": list(src_candidates),
                        "dst_candidates": list(dst_candidates),
                    }
                )
                continue
            src_fqn = src_candidates[0]
            dst_fqn = dst_candidates[0]
            ignore = set(marker.get("ignore") or [])
            intersection = (
                _eligible_field_names(src_fqn, field_index)
                & _eligible_field_names(dst_fqn, field_index)
            ) - ignore
            caller = entity.qualified_name
            for fname in intersection:
                src_qn = f"{src_fqn}.{fname}"
                dst_qn = f"{dst_fqn}.{fname}"
                if (src_qn, dst_qn) in emitted:
                    continue
                emitted.add((src_qn, dst_qn))
                new_relations.append(
                    CodeRelation(
                        kind=RelationKinds.PROPAGATES_TO,
                        source=src_qn,
                        target=dst_qn,
                        attributes={
                            "via_methods": [caller],
                            "confidence": marker["confidence"],
                            "library": marker["library"],
                        },
                    )
                )
        if ambiguous:
            prior = entity.attributes.get("beanutils_ambiguous_types") or []
            entity.attributes["beanutils_ambiguous_types"] = list(prior) + ambiguous
    pr.relations.extend(new_relations)


def _resolve_native_sql(
    pr: ParseResult,
    class_index: dict[str, CodeEntity],
    db_tables: dict[str, CodeEntity],
    db_columns: dict[str, CodeEntity],
) -> None:
    new_relations: list[CodeRelation] = []
    snapshot = list(pr.relations)
    for idx, rel in enumerate(snapshot):
        if rel.kind not in (RelationKinds.READS_TABLE, RelationKinds.WRITES_TABLE):
            continue
        attrs = rel.attributes
        target_table = rel.target
        if target_table == _DYNAMIC:
            continue

        if attrs.get("dialect") == _DIALECT_JPQL:
            resolved_table, _ = _resolve_jpql_to_table(target_table, class_index)
            if resolved_table and resolved_table != target_table:
                rewritten = replace(rel, target=resolved_table)
                pr.relations[idx] = rewritten
                rel = rewritten
                target_table = resolved_table

        jpa_class_fqn = _find_class_for_table(target_table, class_index)
        reverse_cols: dict[str, str] = {}
        if jpa_class_fqn:
            jpa_cols = class_index[jpa_class_fqn].attributes.get("jpa_columns") or {}
            for field_name, col_name in jpa_cols.items():
                if isinstance(col_name, str):
                    reverse_cols[col_name.lower()] = field_name

        if target_table not in db_tables:
            db_tables[target_table] = CodeEntity(
                kind=EntityKinds.DB_TABLE,
                qualified_name=target_table,
                name=target_table,
                file_path=_SYNTHETIC_FILE_PATH,
                line_start=0,
                line_end=0,
            )

        edge_kind = (
            RelationKinds.READS
            if rel.kind == RelationKinds.READS_TABLE
            else RelationKinds.WRITES
        )
        confidence = attrs.get("confidence", 1.0)
        columns = attrs.get("columns") or []
        for col in columns:
            if col == _DYNAMIC:
                continue
            col_lower = col.lower()
            col_qn = f"{target_table}.{col_lower}"
            field_fqn: str | None = None
            if jpa_class_fqn and col_lower in reverse_cols:
                field_fqn = f"{jpa_class_fqn}.{reverse_cols[col_lower]}"
            if col_qn not in db_columns:
                col_attrs: dict[str, object] = {"table": target_table}
                if field_fqn:
                    col_attrs["field_fqn"] = field_fqn
                db_columns[col_qn] = CodeEntity(
                    kind=EntityKinds.DB_COLUMN,
                    qualified_name=col_qn,
                    name=col_lower,
                    file_path=_SYNTHETIC_FILE_PATH,
                    line_start=0,
                    line_end=0,
                    attributes=col_attrs,
                )
            edge_attrs: dict[str, object] = {"confidence": confidence}
            if field_fqn:
                edge_attrs["field_fqn"] = field_fqn
            new_relations.append(
                CodeRelation(
                    kind=edge_kind,
                    source=rel.source,
                    target=col_qn,
                    attributes=edge_attrs,
                )
            )
    pr.relations.extend(new_relations)


def _resolve_jpql_to_table(
    entity_token: str, class_index: dict[str, CodeEntity]
) -> tuple[str | None, str | None]:
    token_lower = entity_token.lower()
    for class_fqn, class_entity in class_index.items():
        jpa_entity_name = class_entity.attributes.get("jpa_entity_name")
        if isinstance(jpa_entity_name, str) and jpa_entity_name.lower() == token_lower:
            jpa_table = class_entity.attributes.get("jpa_table")
            if isinstance(jpa_table, str) and jpa_table:
                return jpa_table.lower(), class_fqn
            return token_lower, class_fqn
        simple = class_fqn.rsplit(".", 1)[-1]
        if simple.lower() == token_lower:
            jpa_table = class_entity.attributes.get("jpa_table")
            if isinstance(jpa_table, str) and jpa_table:
                return jpa_table.lower(), class_fqn
    return None, None


def _find_class_for_table(
    table_name: str, class_index: dict[str, CodeEntity]
) -> str | None:
    table_lower = table_name.lower()
    for class_fqn, class_entity in class_index.items():
        jpa_table = class_entity.attributes.get("jpa_table")
        if isinstance(jpa_table, str) and jpa_table.lower() == table_lower:
            return class_fqn
    return None


__all__ = ["enrich_repo", "build_indices"]
