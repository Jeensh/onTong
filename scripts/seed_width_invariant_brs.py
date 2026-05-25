"""R5-4 — atomic term 의 invariant BR 시드.

페르소나 B (인시던트 SRE): SdFinalWidthRangeAction 진입 시 "관련" 탭 BR 0건.
width/length/thickness/weight 같은 핵심 atomic term 을 ref 하는 BR 이 시드에 없어서
"이 action 깨지면 어떤 invariant 위반" 답 불가능. 5개 invariant 룰 추가.

각 룰은:
  - terms_ref 에 atomic term FQN 포함 → TabImpact "관련 BR (term 공유)" 트리거
  - enforced_by 에 관련 step Action 의 method fqn 포함 → "직접 enforced" 트리거
  - severity = hard
  - operational_history = [] (사고 이력 없음, invariant 만)
"""
from __future__ import annotations

import json
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "ontology.db"
REPO_ID = "slab-design-real-v2"

# fqn, statement, severity, terms_ref, enforced_by_method_fqns
BRS = [
    (
        "rule.scm.slab.width_range_integrity",
        "slab 폭 범위 무결성 — finalWidthLow ≤ finalWidthHigh, 둘 다 양수. "
        "1차 폭 범위 / 최종 폭 범위 모든 산정 결과의 invariant.",
        "hard",
        ["term.scm.slab.width"],
        [
            "com.example.slabdesign.feature.sd.process.working.action.SdFinalWidthRangeAction.execute(SDOrderEntity,SDSlabEntity)",
            "com.example.slabdesign.feature.sd.process.working.action.SdWidthRangeAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
    ),
    (
        "rule.scm.slab.length_range_integrity",
        "slab 길이 범위 무결성 — finalLengthLow ≤ finalLengthHigh, 둘 다 양수. "
        "1차 길이 범위 / 최종 길이 범위 산정 결과의 invariant.",
        "hard",
        ["term.scm.slab.length"],
        [
            "com.example.slabdesign.feature.sd.process.working.action.SdFinalLengthRangeAction.execute(SDOrderEntity,SDSlabEntity)",
            "com.example.slabdesign.feature.sd.process.working.action.SdLengthRangeAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
    ),
    (
        "rule.scm.slab.thickness_positive_range",
        "slab 두께 양수 + 허용 범위 [0.1, 500] mm. "
        "step 1 SdThicknessAction 진입 직후 결정값 검증.",
        "hard",
        ["term.scm.thickness"],
        [
            "com.example.slabdesign.feature.sd.process.working.action.SdThicknessAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
    ),
    (
        "rule.scm.slab.weight_range_integrity",
        "slab 단중 양수 + firstWgtLow ≤ firstWgtHigh ≤ secondWgtHigh. "
        "1차 단중 / 2차 단중 산정 결과의 invariant.",
        "hard",
        ["term.scm.slab.weight"],
        [
            "com.example.slabdesign.feature.sd.process.working.action.SdFirstWeightAction.execute(SDOrderEntity,SDSlabEntity)",
            "com.example.slabdesign.feature.sd.process.working.action.SdSecondWgtLowAction.execute(SDOrderEntity,SDSlabEntity)",
            "com.example.slabdesign.feature.sd.process.working.action.SdSecondWgtHighAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
    ),
    (
        "rule.scm.slab.slab_count_positive_integer",
        "slab 매수 양의 정수 + max_split_count 이내. A-a iteration loop 의 무한 방지 가드.",
        "hard",
        ["term.scm.slab.slab_count"],
        [
            "com.example.slabdesign.feature.sd.process.working.action.SdMaxSplitCountAction.execute(SDOrderEntity,SDSlabEntity)",
            "com.example.slabdesign.feature.sd.process.working.action.SdSlabCountAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
    ),
]


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"DB not found: {DB}")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DB.with_suffix(f".db.bak-width-br-seed-{ts}")
    shutil.copy(DB, bak)
    print(f"backup → {bak}")

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    added, skipped = 0, 0
    for fqn, stmt, severity, terms_ref, enforced_by in BRS:
        row = cur.execute(
            "SELECT fqn FROM business_rules WHERE fqn=? AND repo_id=?", (fqn, REPO_ID),
        ).fetchone()
        if row is not None:
            print(f"  ⊖ {fqn} — already exists, skip (use force=True manually)")
            skipped += 1
            continue
        cur.execute(
            """INSERT INTO business_rules
                (fqn, statement, severity, terms_ref_json, source, confirmed, repo_id,
                 enforced_by_json, violated_at_call_json, operational_history_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fqn, stmt, severity,
                json.dumps(terms_ref),
                "user",
                1,
                REPO_ID,
                json.dumps(enforced_by),
                json.dumps([]),
                json.dumps([]),
            ),
        )
        print(f"  ✓ {fqn} (severity={severity}, terms_ref={terms_ref}, enforced_by={len(enforced_by)})")
        added += 1

    conn.commit()
    conn.close()
    print(f"\nadded {added} / skipped {skipped}")


if __name__ == "__main__":
    main()
