"""One-shot consolidation — slab-design-real_v2 (underscore) + slab-design-real-v2 (dash) → 단일 dash.

배경:
  Java parser 가 path basename 으로 `slab-design-real_v2` (underscore) 생성,
  sim_v2 / handoff DB 는 `slab-design-real-v2` (dash) 사용. fqn PK 충돌로 seed 가 대부분 skip.

작업:
  Phase 1: underscore → dash repo_id 마이그레이션 (충돌 시 dash 유지)
  Phase 2: slab-v2-handoff.db 에서 누락된 confirmed 데이터 재시드 (UPSERT)
  Phase 3: 검증

실행:
  uv run python scripts/consolidate_v2_repo.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "ontology.db"
HANDOFF = ROOT / "data" / "slab-v2-handoff.db"

OLD = "slab-design-real_v2"   # underscore (Java parser auto-import)
NEW = "slab-design-real-v2"   # dash (handoff + sim_v2 canonical)


def phase1_migrate(conn: sqlite3.Connection) -> None:
    """underscore → dash 마이그레이션. 충돌 시 dash 우선 (confirmed 보존)."""
    print(f"\n=== Phase 1: {OLD} → {NEW} 마이그레이션 ===")
    cur = conn.cursor()

    # 1. code_methods: PK=fqn. dash 0, underscore 1081 → 단순 UPDATE.
    cur.execute(f"UPDATE code_methods SET repo_id=? WHERE repo_id=?", (NEW, OLD))
    print(f"  code_methods: {cur.rowcount} renamed")

    # 2. call_sites: PK=id. dash 0, underscore 2298 → 단순 UPDATE.
    cur.execute(f"UPDATE call_sites SET repo_id=? WHERE repo_id=?", (NEW, OLD))
    print(f"  call_sites: {cur.rowcount} renamed")

    # 3. code_types: PK=fqn. dash 6 우선.
    cur.execute(
        "DELETE FROM code_types WHERE repo_id=? AND fqn IN ("
        "  SELECT fqn FROM code_types WHERE repo_id=?"
        ")",
        (OLD, NEW),
    )
    dropped = cur.rowcount
    cur.execute("UPDATE code_types SET repo_id=? WHERE repo_id=?", (NEW, OLD))
    print(f"  code_types: {dropped} duplicates dropped, {cur.rowcount} renamed")

    # 4. business_terms: PK=fqn. dash 17 우선.
    cur.execute(
        "DELETE FROM business_terms WHERE repo_id=? AND fqn IN ("
        "  SELECT fqn FROM business_terms WHERE repo_id=?"
        ")",
        (OLD, NEW),
    )
    dropped = cur.rowcount
    cur.execute("UPDATE business_terms SET repo_id=? WHERE repo_id=?", (NEW, OLD))
    print(f"  business_terms: {dropped} duplicates dropped, {cur.rowcount} renamed")

    # 5. actions: PK=fqn. dash 2 우선.
    cur.execute(
        "DELETE FROM actions WHERE repo_id=? AND fqn IN ("
        "  SELECT fqn FROM actions WHERE repo_id=?"
        ")",
        (OLD, NEW),
    )
    dropped = cur.rowcount
    cur.execute("UPDATE actions SET repo_id=? WHERE repo_id=?", (NEW, OLD))
    print(f"  actions: {dropped} duplicates dropped, {cur.rowcount} renamed")

    # 6. realizations: UNIQUE(action_fqn, code_method_fqn, applies_to_code_type_fqn). dash 2 우선.
    cur.execute(
        "DELETE FROM realizations WHERE repo_id=? AND (action_fqn, code_method_fqn, COALESCE(applies_to_code_type_fqn,'')) IN ("
        "  SELECT action_fqn, code_method_fqn, COALESCE(applies_to_code_type_fqn,'') FROM realizations WHERE repo_id=?"
        ")",
        (OLD, NEW),
    )
    dropped = cur.rowcount
    cur.execute("UPDATE realizations SET repo_id=? WHERE repo_id=?", (NEW, OLD))
    print(f"  realizations: {dropped} duplicates dropped, {cur.rowcount} renamed")

    # 7. type_realizations: UNIQUE(code_type_fqn, term_fqn, scope). dash 5 우선.
    cur.execute(
        "DELETE FROM type_realizations WHERE repo_id=? AND (code_type_fqn, term_fqn, scope) IN ("
        "  SELECT code_type_fqn, term_fqn, scope FROM type_realizations WHERE repo_id=?"
        ")",
        (OLD, NEW),
    )
    dropped = cur.rowcount
    cur.execute("UPDATE type_realizations SET repo_id=? WHERE repo_id=?", (NEW, OLD))
    print(f"  type_realizations: {dropped} duplicates dropped, {cur.rowcount} renamed")

    # 8. anchor_bindings: underscore 0 → no-op
    # 9. business_rules: underscore 0 → no-op


def _column_list(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _upsert_table(
    target: sqlite3.Connection,
    source: sqlite3.Connection,
    table: str,
    natural_keys: list[str] | None = None,
) -> tuple[int, int]:
    """handoff → target UPSERT.

    PK=fqn 테이블: INSERT OR REPLACE (PK 자동 매칭).
    UNIQUE composite 테이블: natural_keys 기준 기존 행 DELETE 후 INSERT.
    """
    src_cols = _column_list(source, table)
    tgt_cols = _column_list(target, table)
    common = [c for c in src_cols if c in tgt_cols]
    if not common:
        return 0, 0

    col_list = ", ".join(common)
    src_rows = source.execute(f"SELECT {col_list} FROM {table}").fetchall()
    if not src_rows:
        return 0, 0

    if natural_keys:
        # DELETE existing matching rows, then INSERT.
        # `id` INTEGER PK 가 autoincrement 이므로 INSERT 시 제외 (handoff id 충돌 회피).
        insert_cols = [c for c in common if c != "id"]
        col_idx = {c: common.index(c) for c in insert_cols}
        deleted = 0
        for row in src_rows:
            key_vals = tuple(row[common.index(k)] for k in natural_keys)
            placeholders = " AND ".join(f"{k} IS ?" for k in natural_keys)
            cur = target.execute(
                f"DELETE FROM {table} WHERE {placeholders}", key_vals
            )
            deleted += cur.rowcount
        insert_rows = [tuple(row[col_idx[c]] for c in insert_cols) for row in src_rows]
        placeholders = ", ".join(["?"] * len(insert_cols))
        target.executemany(
            f"INSERT INTO {table} ({', '.join(insert_cols)}) VALUES ({placeholders})",
            insert_rows,
        )
        return deleted, len(src_rows)
    else:
        # INSERT OR REPLACE — PK 매칭
        placeholders = ", ".join(["?"] * len(common))
        target.executemany(
            f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
            src_rows,
        )
        return 0, len(src_rows)


def phase2_reseed(target: sqlite3.Connection, source: sqlite3.Connection) -> None:
    """handoff DB 에서 confirmed 데이터 재시드 (REPLACE — 기존 행 덮어쓰기)."""
    print(f"\n=== Phase 2: handoff DB 에서 confirmed 데이터 REPLACE ===")

    # PK=fqn — INSERT OR REPLACE 으로 자동 매칭
    for table in ("code_types", "code_methods", "business_terms", "actions", "business_rules"):
        _, inserted = _upsert_table(target, source, table)
        print(f"  {table}: {inserted} replaced")

    # UNIQUE composite
    deleted, inserted = _upsert_table(
        target, source, "realizations",
        natural_keys=["action_fqn", "code_method_fqn", "applies_to_code_type_fqn"],
    )
    print(f"  realizations: {deleted} replaced ({inserted} inserted)")

    deleted, inserted = _upsert_table(
        target, source, "type_realizations",
        natural_keys=["code_type_fqn", "term_fqn", "scope"],
    )
    print(f"  type_realizations: {deleted} replaced ({inserted} inserted)")

    # anchor_bindings PK=id (string) — INSERT OR REPLACE
    _, inserted = _upsert_table(target, source, "anchor_bindings")
    print(f"  anchor_bindings: {inserted} replaced")

    # call_sites PK=id (string) — INSERT OR REPLACE
    _, inserted = _upsert_table(target, source, "call_sites")
    print(f"  call_sites: {inserted} replaced")

    # code_fields (no repo_id, no PK conflict source)
    _, inserted = _upsert_table(target, source, "code_fields")
    print(f"  code_fields: {inserted} replaced")


def phase3_verify(target: sqlite3.Connection) -> None:
    print(f"\n=== Phase 3: 검증 ===")
    print(f"  repo_id={NEW} per table:")
    for table in (
        "code_types", "code_methods", "business_terms", "actions",
        "business_rules", "realizations", "type_realizations", "anchor_bindings", "call_sites",
    ):
        cur = target.execute(f"SELECT COUNT(*) FROM {table} WHERE repo_id=?", (NEW,))
        total = cur.fetchone()[0]
        if table in ("actions",):
            confirmed = target.execute(
                f"SELECT COUNT(*) FROM {table} WHERE repo_id=? AND confirmed_by IS NOT NULL",
                (NEW,),
            ).fetchone()[0]
            print(f"    {table:25s}: {total:5d} (confirmed_by NOT NULL: {confirmed})")
        elif table in ("business_terms", "business_rules", "realizations", "type_realizations", "anchor_bindings"):
            confirmed = target.execute(
                f"SELECT COUNT(*) FROM {table} WHERE repo_id=? AND confirmed=1",
                (NEW,),
            ).fetchone()[0]
            print(f"    {table:25s}: {total:5d} (confirmed: {confirmed})")
        else:
            print(f"    {table:25s}: {total:5d}")

    leftover = target.execute(
        "SELECT 'code_methods' AS t, COUNT(*) FROM code_methods WHERE repo_id=?"
        " UNION ALL SELECT 'actions', COUNT(*) FROM actions WHERE repo_id=?"
        " UNION ALL SELECT 'code_types', COUNT(*) FROM code_types WHERE repo_id=?",
        (OLD, OLD, OLD),
    ).fetchall()
    print(f"\n  leftover {OLD}: {leftover}")


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"target not found: {TARGET}")
    if not HANDOFF.exists():
        raise SystemExit(f"handoff DB not found: {HANDOFF}")

    target = sqlite3.connect(TARGET)
    source = sqlite3.connect(HANDOFF)
    target.execute("PRAGMA foreign_keys=OFF")  # bulk operations

    try:
        target.execute("BEGIN")
        phase1_migrate(target)
        phase2_reseed(target, source)
        target.execute("COMMIT")
    except Exception:
        target.execute("ROLLBACK")
        raise

    phase3_verify(target)

    target.close()
    source.close()
    print("\n✅ consolidation 완료")


if __name__ == "__main__":
    main()
