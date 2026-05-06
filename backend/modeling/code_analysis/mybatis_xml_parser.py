"""P29-2 (2026-04-27) — MyBatis XML mapper 파싱.

`*Mapper.xml` 파일을 walk 하면서 각 `<select|insert|update|delete>` statement 를
ParseResult 로 emit. namespace + id → method FQN, sql 본문 → READS/WRITES_TABLE edge.

`<if test="...">`, `<choose>` 분기는 attributes 로 conditional column/branch 마킹.

설계 결정 :
  - sqlglot 사용 (NativeSqlAnalyzer 와 동일 dialect)
  - PoC : 단순 SQL 파싱 (subquery / CTE 다 잘 안 되어도 OK)
  - Confidence — `<if>` 가 있으면 0.7, 없으면 0.95
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)

logger = logging.getLogger(__name__)

_STMT_TAGS = {"select", "insert", "update", "delete"}
_TABLE_RX = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO|MERGE\s+INTO)\s+([A-Za-z_][A-Za-z0-9_\.]*)",
    re.IGNORECASE,
)


def parse_mybatis_xml_files(repo_root: Path, *, max_files: int = 5000) -> list[ParseResult]:
    """repo_root 아래에서 *Mapper.xml 모두 파싱."""
    results: list[ParseResult] = []
    candidates = []
    for ext in ("*.xml",):
        for path in repo_root.rglob(ext):
            if path.is_file() and "mapper" in path.name.lower():
                candidates.append(path)
            if len(candidates) >= max_files:
                break
    for xml_path in candidates:
        try:
            pr = _parse_one(xml_path)
            if pr is not None:
                results.append(pr)
        except Exception as e:
            logger.debug("MyBatis XML parse 실패 %s: %s", xml_path, e)
    return results


def _parse_one(xml_path: Path) -> ParseResult | None:
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    root = tree.getroot()
    if root.tag.lower() != "mapper":
        return None

    namespace = root.get("namespace") or ""
    if not namespace:
        return None

    entities: list[CodeEntity] = []
    relations: list[CodeRelation] = []

    for stmt in root:
        tag = stmt.tag.lower().split("}")[-1]   # remove xml namespace prefix if any
        if tag not in _STMT_TAGS:
            continue
        stmt_id = stmt.get("id")
        if not stmt_id:
            continue
        method_fqn = f"{namespace}.{stmt_id}"

        # SQL 본문 reconstruct (text + child <if>/<choose>/<foreach> 등 unconditional 부분만)
        unconditional_sql, conditional_branches = _reconstruct_sql(stmt)

        attrs: dict[str, object] = {
            "owner_kind": "mybatis_xml",
            "namespace": namespace,
            "stmt_kind": tag,
            "sql_text": unconditional_sql[:500],
            "has_dynamic_branches": bool(conditional_branches),
        }
        if conditional_branches:
            attrs["dynamic_branches"] = conditional_branches[:20]

        entities.append(CodeEntity(
            kind=EntityKinds.MAPPER_METHOD,
            qualified_name=f"{method_fqn}#xml",
            name=stmt_id,
            file_path=str(xml_path),
            line_start=1,
            line_end=1,
            attributes=attrs,
        ))

        # table edges
        edge_kind = RelationKinds.READS_TABLE if tag == "select" else RelationKinds.WRITES_TABLE
        # unconditional + 모든 conditional 의 합
        combined = unconditional_sql + " " + " ".join(b.get("sql", "") for b in conditional_branches)
        seen_tables = set()
        for m in _TABLE_RX.finditer(combined):
            tbl = m.group(1).strip().rstrip(",").lower()
            if tbl and tbl not in seen_tables and tbl not in ("dual",):
                seen_tables.add(tbl)
                # `<if>` 안에 있으면 conditional
                in_conditional = any(
                    tbl in b.get("sql", "").lower()
                    and tbl not in unconditional_sql.lower()
                    for b in conditional_branches
                )
                conf = 0.7 if in_conditional else 0.95
                relations.append(CodeRelation(
                    kind=edge_kind,
                    source=method_fqn,
                    target=tbl,
                    attributes={
                        "confidence": conf,
                        "dialect": "mybatis_xml",
                        "stmt_kind": tag,
                        "conditional": in_conditional,
                    },
                ))

    if not entities:
        return None
    return ParseResult(
        entities=entities,
        relations=relations,
        file_path=str(xml_path),
        language="MyBatisXML",
    )


def _reconstruct_sql(stmt: ET.Element) -> tuple[str, list[dict]]:
    """statement 의 text + child SQL 를 unconditional 과 conditional 로 분리.

    - text + tail 은 unconditional
    - <if>, <choose>, <when>, <otherwise>, <foreach> 안의 텍스트는 conditional
    - <include refid="..."/> 는 빈 placeholder (resolution 미구현)
    """
    unconditional: list[str] = []
    conditional: list[dict] = []

    if stmt.text:
        unconditional.append(stmt.text)

    for child in stmt:
        ctag = child.tag.lower().split("}")[-1]
        if ctag in ("if", "when", "otherwise", "foreach", "trim", "where", "set"):
            inner = _flatten_text(child)
            test = child.get("test") or child.get("refid") or ""
            conditional.append({
                "tag": ctag,
                "test": test,
                "sql": inner,
            })
        elif ctag == "choose":
            # nested when/otherwise — flatten recursively
            for sub in child:
                stag = sub.tag.lower().split("}")[-1]
                inner = _flatten_text(sub)
                test = sub.get("test") or ""
                conditional.append({
                    "tag": stag,
                    "test": test,
                    "sql": inner,
                })
        elif ctag == "include":
            # refid resolution 미구현 — placeholder 만
            unconditional.append(f"/* include {child.get('refid', '')} */")
        else:
            # unknown — flatten as unconditional
            unconditional.append(_flatten_text(child))

        if child.tail:
            unconditional.append(child.tail)

    return " ".join(unconditional), conditional


def _flatten_text(elem: ET.Element) -> str:
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_flatten_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts)


__all__ = ("parse_mybatis_xml_files",)
