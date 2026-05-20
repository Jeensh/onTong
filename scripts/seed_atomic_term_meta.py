"""F0-6 — atomic term value_type / unit / range 시드.

페르소나 C (소라, 신규 룰 추가 주니어) 가 지적: 두께/너비/길이 같은 핵심 atomic term 이
value_type/unit/range 다 비어있어서 단위 변환 안전성 보장 불가 → 시니어 의존.

대상 7개 (slab-design-real-v2):
  - 두께 (thickness)       → float, mm,  range [0.1, 500]
  - 길이 (slab.length)     → float, mm,  range [3000, 12000]
  - 너비 (slab.width)      → float, mm,  range [600, 2300]
  - 중량 (slab.weight)     → float, kg,  range [1000, 30000]
  - 슬라브 매수 (slab.slab_count) → int, ea, range [1, 20]
  - 분할 (slab.split)      → int, ea,  range [1, 10]
  - 마진 (margin)          → float, mm, range [0, 100]

범위는 실 plant spec 이 아닌 합리적 추정. 사용자가 validator 룰 짤 때 단위 만이라도
명확히 보이는 것이 1차 목표. 이후 확정값으로 force update 권장.
"""
from __future__ import annotations

import json
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "ontology.db"
REPO_ID = "slab-design-real-v2"

# fqn → (value_type, unit, range_lo, range_hi)
SEEDS: dict[str, tuple[str, str, float, float]] = {
    "term.scm.thickness":         ("float", "mm",   0.1,    500.0),
    "term.scm.slab.length":       ("float", "mm",   3000.0, 12000.0),
    "term.scm.slab.width":        ("float", "mm",   600.0,  2300.0),
    "term.scm.slab.weight":       ("float", "kg",   1000.0, 30000.0),
    "term.scm.slab.slab_count":   ("int",   "ea",   1.0,    20.0),
    "term.scm.slab.split":        ("int",   "ea",   1.0,    10.0),
    "term.scm.margin":            ("float", "mm",   0.0,    100.0),
}


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"DB not found: {DB}")

    # backup before write
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DB.with_suffix(f".db.bak-atomic-meta-{ts}")
    shutil.copy(DB, bak)
    print(f"backup → {bak}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # peek schema — column 이름은 BusinessTermRow 와 일치해야 함
    cols = [r[1] for r in cur.execute("PRAGMA table_info(business_terms)").fetchall()]
    assert "value_type" in cols, f"value_type column missing — found {cols}"
    assert "unit" in cols, f"unit column missing — found {cols}"
    assert "range" in cols or "range_json" in cols, f"range column missing — found {cols}"
    range_col = "range" if "range" in cols else "range_json"

    updated = 0
    skipped = 0
    for fqn, (vt, unit, lo, hi) in SEEDS.items():
        row = cur.execute(
            f"SELECT fqn, value_type, unit, {range_col} FROM business_terms WHERE fqn=? AND repo_id=?",
            (fqn, REPO_ID),
        ).fetchone()
        if row is None:
            print(f"  ✗ {fqn} — not found")
            skipped += 1
            continue
        # 기존 값 보존 — 이미 채워진 row 는 건드리지 않음 (idempotent)
        if row["value_type"] and row["value_type"] != "-" and row["value_type"] not in ("", None):
            existing_vt = row["value_type"]
            if existing_vt != vt:
                print(f"  ⊖ {fqn} — already has value_type={existing_vt} (seed wanted {vt}), skip")
                skipped += 1
                continue
        range_json = json.dumps([lo, hi])
        cur.execute(
            f"""UPDATE business_terms
                SET value_type=?, unit=?, {range_col}=?
                WHERE fqn=? AND repo_id=?""",
            (vt, unit, range_json, fqn, REPO_ID),
        )
        print(f"  ✓ {fqn} ← vt={vt} unit={unit} range=[{lo},{hi}]")
        updated += 1

    conn.commit()
    conn.close()
    print(f"\nupdated {updated} / skipped {skipped}")


if __name__ == "__main__":
    main()
