"""One-shot seed — slab-v2-handoff.db 의 modeling 호환 테이블을 ontology.db 로 INSERT.

목적:
  sec3 multiturn agent 의 HybridOntologyClient 가 sec2 endpoint 본체 wire 를
  활용할 수 있도록 modeling 측 ontology.db 에 데이터 채움.

데이터 소스:
  - source = data/slab-v2-handoff.db  (sim_v2 가 만든 38 actions / 985 methods)
  - target = data/ontology.db          (modeling 측 store, 비어있던 상태)

복사 테이블 (양 DB schema 동일 — 첫 conversation 확인):
  - code_types, code_methods, code_fields
  - call_sites
  - business_terms, composition_edges, inheritance_edges, business_rules
  - actions, realizations, type_realizations
  - anchor_bindings

스키마 차이:
  - ontology.db code_methods PK = `fqn`
  - slab-v2-handoff code_methods PK = `(fqn, repo_id)` (multi-repo)
  - → ontology.db 에 같은 fqn 있을 시 충돌. 빈 DB 시 OK. INSERT OR IGNORE 사용.

실행:
  uv run python scripts/seed_modeling_from_sim_v2.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "slab-v2-handoff.db"
TARGET = ROOT / "data" / "ontology.db"

# 복사 순서 — FK 의존성 따라 (CASCADE 안 깨도록)
TABLES = [
    # Code Layer
    ("code_types",       "fqn"),
    ("code_methods",     "fqn"),
    ("code_fields",      None),       # composite PK
    ("call_sites",       "id"),
    # Domain Layer
    ("business_terms",   "fqn"),
    ("composition_edges", None),
    ("inheritance_edges", None),
    ("business_rules",   "fqn"),
    # Mapping Layer
    ("actions",          "fqn"),
    ("realizations",     None),
    ("type_realizations", None),
    ("anchor_bindings",  None),
]


def _column_list(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _copy_table(source: sqlite3.Connection, target: sqlite3.Connection, table: str) -> int:
    src_cols = _column_list(source, table)
    tgt_cols = _column_list(target, table)
    if not tgt_cols:
        print(f"  [skip] {table} — target 에 테이블 없음")
        return 0

    common = [c for c in src_cols if c in tgt_cols]
    if not common:
        print(f"  [skip] {table} — 공통 컬럼 없음")
        return 0

    col_list = ", ".join(common)
    rows = source.execute(f"SELECT {col_list} FROM {table}").fetchall()
    if not rows:
        print(f"  [empty] {table}")
        return 0

    placeholders = ", ".join(["?"] * len(common))
    inserted = 0
    for row in rows:
        try:
            target.execute(
                f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",
                row,
            )
            inserted += 1
        except sqlite3.Error as e:
            print(f"  [error] {table}: {e}")
            break
    return inserted


def main() -> int:
    if not SOURCE.exists():
        print(f"[fatal] source 없음: {SOURCE}")
        return 1
    if not TARGET.exists():
        print(f"[fatal] target 없음: {TARGET}")
        return 1

    print(f"source: {SOURCE}")
    print(f"target: {TARGET}")
    print()

    src = sqlite3.connect(str(SOURCE))
    tgt = sqlite3.connect(str(TARGET))
    tgt.execute("PRAGMA foreign_keys = OFF")   # FK 일시 OFF (순서 의존성 우회)
    try:
        for table, _pk in TABLES:
            count = _copy_table(src, tgt, table)
            print(f"  {table}: {count} rows")
        tgt.commit()
    finally:
        tgt.execute("PRAGMA foreign_keys = ON")
        src.close()
        tgt.close()

    print()
    print("seed 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
