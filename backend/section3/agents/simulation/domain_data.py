"""slab-design-real_v2 의 도메인 데이터 surface helper.

slab-design 의 H2 는 in-memory + same-JVM 이라 외부 JDBC 접근 불가. 대신
(1) JPA Entity 파일 grep 으로 schema 추출
(2) seed SQL 파일 파싱으로 row 데이터 추출
(3) 필요 시 Java :8080 REST API 호출
세 가지를 합성해서 시뮬에이전트가 "현재 시스템에 어떤 table 과 row 가 있는가"
를 사용자에게 보여준다.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(os.environ.get(
    "SLAB_DESIGN_REPO",
    "/Users/jiyoon/claude/onTong/sample-repos/slab-design-real_v2",
))
JPA_ROOT = REPO_ROOT / "slab-design-store/src/main/java"
JPA_FILE_PATTERNS = ("*Jpo.java", "*Entity.java")
SEED_FILES = [
    REPO_ROOT / "slab-design-boot/src/main/resources/db/seed/01_master.sql",
    REPO_ROOT / "slab-design-boot/src/main/resources/db/seed/02_orders.sql",
]


# ─────────────────────────────────────────────────────────────────────────────
# 모델
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ColumnDef:
    name: str
    java_field: str
    is_pk: bool = False
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    type_hint: str = ""


@dataclass
class TableDef:
    table_name: str         # "CAST_SPEC"
    jpa_class: str          # "CastSpecJpo"
    jpa_file: str           # 상대 경로
    columns: list[ColumnDef] = field(default_factory=list)
    pk_columns: list[str] = field(default_factory=list)
    category: str = "unknown"  # std / order / result / history


@dataclass
class TableRow:
    table_name: str
    values: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# JPA Entity 파일 파싱
# ─────────────────────────────────────────────────────────────────────────────


_TABLE_RE = re.compile(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"')
_COLUMN_RE = re.compile(
    r'(@Id\s+)?@Column\s*\(\s*name\s*=\s*"([^"]+)"'
    r'(?:[^)]*length\s*=\s*(\d+))?'
    r'(?:[^)]*precision\s*=\s*(\d+))?'
    r'(?:[^)]*scale\s*=\s*(\d+))?',
)
_FIELD_RE = re.compile(r'(private|public)\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*;')


def _categorize(jpa_file: str) -> str:
    if "/std/" in jpa_file:
        return "std"   # 기준 데이터 (master)
    if "/working/" in jpa_file and "Result" in jpa_file:
        return "result"
    if "/working/" in jpa_file:
        return "order"
    if "/history/" in jpa_file:
        return "history"
    return "other"


def _glob_jpa_files() -> list[Path]:
    out: list[Path] = []
    if not JPA_ROOT.exists():
        return out
    for pat in JPA_FILE_PATTERNS:
        out.extend(JPA_ROOT.rglob(pat))
    return sorted(out)


@lru_cache(maxsize=1)
def list_tables() -> list[TableDef]:
    tables: list[TableDef] = []
    for fp in _glob_jpa_files():
        text = fp.read_text(encoding="utf-8", errors="ignore")
        tm = _TABLE_RE.search(text)
        if not tm:
            continue
        table_name = tm.group(1)
        # 모든 @Column + 직후 java field name 매핑은 단순화 — 같은 라인 또는 다음 라인의
        # `private TYPE name;` 잡기
        columns: list[ColumnDef] = []
        pk_columns: list[str] = []
        for cm in _COLUMN_RE.finditer(text):
            is_pk = bool(cm.group(1))
            cname = cm.group(2)
            length = int(cm.group(3)) if cm.group(3) else None
            precision = int(cm.group(4)) if cm.group(4) else None
            scale = int(cm.group(5)) if cm.group(5) else None
            # 같은 column annotation 뒤 가까이의 field 이름
            after = text[cm.end():cm.end() + 400]
            fm = _FIELD_RE.search(after)
            jfield = fm.group(3) if fm else ""
            type_hint = fm.group(2) if fm else ""
            columns.append(ColumnDef(
                name=cname, java_field=jfield, is_pk=is_pk,
                length=length, precision=precision, scale=scale,
                type_hint=type_hint,
            ))
            if is_pk:
                pk_columns.append(cname)

        jpa_class = fp.stem
        rel = str(fp.relative_to(REPO_ROOT))
        tables.append(TableDef(
            table_name=table_name, jpa_class=jpa_class, jpa_file=rel,
            columns=columns, pk_columns=pk_columns,
            category=_categorize(rel),
        ))
    return tables


def get_table(name: str) -> TableDef | None:
    for t in list_tables():
        if t.table_name.upper() == name.upper():
            return t
    return None


# ─────────────────────────────────────────────────────────────────────────────
# seed SQL 파싱
# ─────────────────────────────────────────────────────────────────────────────


_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+(?:\([^)]*\)[^)]*)*)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)


def _parse_values(s: str) -> list[Any]:
    """단순 SQL VALUES 토큰화 — 문자열·숫자·NULL·DATE 'x'."""
    out: list[Any] = []
    cur = ""
    depth = 0
    in_quote = False
    i = 0
    while i < len(s):
        ch = s[i]
        if in_quote:
            cur += ch
            if ch == "'" and (i + 1 >= len(s) or s[i + 1] != "'"):
                in_quote = False
        elif ch == "'":
            cur += ch
            in_quote = True
        elif ch == "(":
            depth += 1; cur += ch
        elif ch == ")":
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            out.append(_coerce(cur.strip()))
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        out.append(_coerce(cur.strip()))
    return out


def _coerce(tok: str) -> Any:
    if not tok or tok.upper() == "NULL":
        return None
    if tok.startswith("'") and tok.endswith("'"):
        return tok[1:-1].replace("''", "'")
    if tok.upper().startswith("DATE "):
        return tok[5:].strip("'")
    if tok.upper().startswith("TIMESTAMP "):
        return tok[10:].strip("'")
    try:
        if "." in tok:
            return float(tok)
        return int(tok)
    except ValueError:
        return tok


@lru_cache(maxsize=1)
def _parse_all_seeds() -> dict[str, list[TableRow]]:
    out: dict[str, list[TableRow]] = {}
    for sp in SEED_FILES:
        if not sp.exists():
            logger.warning("seed file missing: %s", sp)
            continue
        text = sp.read_text(encoding="utf-8", errors="ignore")
        # SQL line comment 제거
        text = re.sub(r"--[^\n]*\n", "\n", text)
        for m in _INSERT_RE.finditer(text):
            table = m.group(1).upper()
            cols = [c.strip() for c in m.group(2).split(",")]
            vals = _parse_values(m.group(3))
            row = TableRow(
                table_name=table,
                values={c: v for c, v in zip(cols, vals)},
            )
            out.setdefault(table, []).append(row)
    return out


def list_rows(table_name: str, limit: int = 50) -> list[TableRow]:
    return _parse_all_seeds().get(table_name.upper(), [])[:limit]


def table_row_count(table_name: str) -> int:
    return len(_parse_all_seeds().get(table_name.upper(), []))
