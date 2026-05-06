"""Repo-level Java parsing helper — 12-analyzer + cross-file enrich + JSON rehydrate.

Extracted from `scripts/dump_entities_snapshot.py` so the same pipeline is reachable
from FastAPI runtime (RepositoryRegistry) without invoking the script.

Two entry points :
    parse_repo(repo_path) -> list[ParseResult]            : fresh from .java sources
    rehydrate_from_snapshot(snapshot_dict) -> list[...]   : load cached entities.json

`build_default_parser()` returns the canonical 12-analyzer JavaParser.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterable

from backend.modeling.code_analysis.cross_file_enricher import (
    build_indices,
    enrich_repo,
)
from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    ParseResult,
)
from backend.modeling.code_analysis.spring import (
    AopAnalyzer,
    BeanUtilsAnalyzer,
    ConfigPropertiesAnalyzer,
    DIAnalyzer,
    EventsAnalyzer,
    HttpAnalyzer,
    JpaAnalyzer,
    MapStructAnalyzer,
    NativeSqlAnalyzer,
    ProfileAnalyzer,
    ReflectionAnalyzer,
    ScheduledAnalyzer,
)


def build_default_parser() -> tuple[JavaParser, list[str]]:
    """15-analyzer 일괄 구성 (P29-1/2 후 — 12 + Tx + Async + MyBatisMapper)."""
    from .spring import (
        AsyncAnalyzer,
        MyBatisMapperAnalyzer,
        TransactionalAnalyzer,
    )
    analyzers = [
        DIAnalyzer(),
        AopAnalyzer(),
        HttpAnalyzer(),
        EventsAnalyzer(),
        ScheduledAnalyzer(),
        ProfileAnalyzer(),
        ReflectionAnalyzer(),
        MapStructAnalyzer(),
        BeanUtilsAnalyzer(),
        NativeSqlAnalyzer(),
        ConfigPropertiesAnalyzer(),
        JpaAnalyzer(),
        # P29-1
        TransactionalAnalyzer(),
        AsyncAnalyzer(),
        # P29-2
        MyBatisMapperAnalyzer(),
    ]
    return JavaParser(spring_analyzers=analyzers), [type(a).__name__ for a in analyzers]


def parse_repo(
    repo_path: Path,
    *,
    on_progress: Callable[[str, int, int], None] | None = None,
    parser: JavaParser | None = None,
) -> list[ParseResult]:
    """Walk all `.java` files under repo_path, parse with 12-analyzer, run cross-file enrich.

    `on_progress(stage, done, total)` 콜백 — SSE 라이브 진행 표시용.
        stages : "discovering" → "parsing" (per-file done/total) → "enriching" → "complete"
    """
    parser = parser or build_default_parser()[0]

    if on_progress:
        on_progress("discovering", 0, 0)
    files = sorted(repo_path.rglob("*.java"))
    total = len(files)
    if on_progress:
        on_progress("discovering", 0, total)

    parse_results: list[ParseResult] = []
    for idx, fp in enumerate(files, start=1):
        text = fp.read_text(encoding="utf-8")
        parse_results.append(parser.parse_file(fp, text))
        if on_progress:
            on_progress("parsing", idx, total)

    # P29-2 — MyBatis XML mapper 파일 파싱
    try:
        from .mybatis_xml_parser import parse_mybatis_xml_files
        xml_results = parse_mybatis_xml_files(repo_path)
        parse_results.extend(xml_results)
    except Exception:
        pass

    if on_progress:
        on_progress("enriching", 0, 0)
    class_index, field_index = build_indices(parse_results)
    enrich_repo(parse_results, class_index, field_index)

    if on_progress:
        on_progress("complete", total, total)
    return parse_results


def serialize_parse_results(
    parse_results: Iterable[ParseResult], repo_path: Path,
) -> dict:
    """Same shape as scripts/dump_entities_snapshot.py output (without metadata header)."""
    files_section: dict[str, dict] = {}
    totals = {"files": 0, "entities": 0, "relations": 0, "errors": 0}
    for pr in parse_results:
        try:
            rel_path = str(Path(pr.file_path).relative_to(repo_path))
        except ValueError:
            rel_path = pr.file_path
        files_section[rel_path] = {
            "language": pr.language,
            "errors": list(pr.errors),
            "entities": [asdict(e) for e in pr.entities],
            "relations": [asdict(r) for r in pr.relations],
        }
        totals["files"] += 1
        totals["entities"] += len(pr.entities)
        totals["relations"] += len(pr.relations)
        totals["errors"] += len(pr.errors)
    return {"files": files_section, "totals": totals}


def rehydrate_from_snapshot(snapshot: dict, repo_path: Path) -> list[ParseResult]:
    """Read a snapshot dict (entities.json) and rebuild list[ParseResult].

    Used at startup to skip re-parsing when `<repo>/.analyzed/entities.json` exists.
    """
    out: list[ParseResult] = []
    files_section = snapshot.get("files") or {}
    for rel_path, fe in files_section.items():
        abs_path = str(repo_path / rel_path)
        entities = [_rehydrate_entity(e, abs_path) for e in fe.get("entities", [])]
        relations = [_rehydrate_relation(r, abs_path) for r in fe.get("relations", [])]
        out.append(ParseResult(
            entities=entities,
            relations=relations,
            file_path=abs_path,
            language=fe.get("language", "Java"),
            errors=list(fe.get("errors", []) or []),
        ))
    return out


def _rehydrate_entity(d: dict, fallback_path: str) -> CodeEntity:
    return CodeEntity(
        kind=d["kind"],
        qualified_name=d["qualified_name"],
        name=d["name"],
        file_path=d.get("file_path") or fallback_path,
        line_start=int(d.get("line_start", 0)),
        line_end=int(d.get("line_end", 0)),
        modifiers=list(d.get("modifiers", []) or []),
        parent=d.get("parent"),
        attributes=dict(d.get("attributes") or {}),
    )


def _rehydrate_relation(d: dict, fallback_path: str) -> CodeRelation:
    return CodeRelation(
        kind=d["kind"],
        source=d["source"],
        target=d["target"],
        file_path=d.get("file_path") or fallback_path,
        line=d.get("line"),
        attributes=dict(d.get("attributes") or {}),
    )


__all__ = (
    "build_default_parser",
    "parse_repo",
    "serialize_parse_results",
    "rehydrate_from_snapshot",
)
