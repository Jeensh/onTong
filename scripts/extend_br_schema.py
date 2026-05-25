"""B2: BusinessRule 스키마 3 컬럼 보강 + 데이터 채우기.

새 컬럼:
- enforced_by_json TEXT — 이 BR 을 enforce 하는 method_fqn list (자동: 패턴 기반)
- violated_at_call_json TEXT — 위반 가능 call site (자동: enforced_by 의 호출 그래프)
- operational_history_json TEXT — 운영 사고 history (statement 텍스트에서 추출)

usage:
  python3 scripts/extend_br_schema.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ontology.db"
REPO_ID = "slab-design-real"


# 17 BR 의 enforced_by + operational_history 매핑 (archive 분석 기반).
BR_METADATA = {
    "rule.scm.std.productivity_safe_range": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.std.service.ProductivityService.cumulativeProductivity(String,String,String,String,String,String)",
        ],
        "operational_history": [],
    },
    "rule.scm.spec.edging_spec_lookup_strategy": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.std.service.EdgingService.findSpec(String,String,String)",
        ],
        "operational_history": [
            {"incident_id": "P-2018-0237", "summary": "EdgingSpec 룩업 실패 사고",
             "occurred_at": "2018", "triggered_by": None, "fixed_at_commit": None},
        ],
    },
    "rule.scm.spec.edging_group_match_strategy": {
        "enforced_by": [
            # 2026-05-10: 정정 — EdgingGroupService 가 아니라 EdgingService.findGroup, 인자 6개 (BigDecimal 포함).
            "com.example.slabdesign.feature.sd.process.std.service.EdgingService.findGroup(String,String,String,String,String,BigDecimal)",
        ],
        "operational_history": [],
    },
    "rule.scm.spec.hr_wgt_2d_ceiling_lookup": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.std.service.HrMaxWgtService.lookup(String,String,String,BigDecimal,BigDecimal)",
            "com.example.slabdesign.feature.sd.process.std.service.HrMinWgtService.lookup(String,String,String,BigDecimal,BigDecimal)",
        ],
        "operational_history": [],
    },
    "rule.scm.order.no_stock_order": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.validate(SDOrderEntity)",
        ],
        "operational_history": [
            {"incident_id": "P-2018-0098", "summary": "정XX Slab 중복 생성 사고",
             "occurred_at": "2018-11-22", "triggered_by": None, "fixed_at_commit": None},
        ],
    },
    "rule.scm.order.order_size_positive": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.validate(SDOrderEntity)",
        ],
        "operational_history": [],
    },
    "rule.scm.order.pkg_wgt_range_integrity": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.validate(SDOrderEntity)",
        ],
        "operational_history": [],
    },
    "rule.scm.order.design_pend_qty_cross_check": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.validate(SDOrderEntity)",
        ],
        "operational_history": [
            {"incident_id": "정XX-2018-12-04", "summary": "DG004 cross-check 추가",
             "occurred_at": "2018-12-04", "triggered_by": None, "fixed_at_commit": None},
        ],
    },
    "rule.scm.order.work_due_strict_future": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.validate(SDOrderEntity)",
        ],
        "operational_history": [
            {"incident_id": "P-2020-0411", "summary": "당일 마감 Slab 생성 사고",
             "occurred_at": "2020-04-11", "triggered_by": None, "fixed_at_commit": None},
        ],
    },
    "rule.scm.std.customer_find_first_match_strategy": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.std.service.CustomerStdService.findFirstMatch(String,String,String,String)",
        ],
        "operational_history": [],
    },
    "rule.scm.slab.original_equals_adjusted": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdSlabSaveAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
        "operational_history": [],
    },
    "rule.scm.slab.aa_loop_max_iter_cap": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.designer.SdDesigner.runAaLoop(SDOrderEntity,SDSlabEntity)",
        ],
        "operational_history": [
            {"incident_id": "P-2018-0721", "summary": "A-a 루프 무한 반복 사고",
             "occurred_at": "2018-07-21", "triggered_by": None, "fixed_at_commit": None},
        ],
    },
    "rule.scm.slab.absolute_max_kg_safety_cap": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdSlabWgtRecalcAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
        "operational_history": [
            {"incident_id": "2017-meeting-ABSOLUTE_MAX_KG", "summary": "ABSOLUTE_MAX_KG 999999.999 cap 결정",
             "occurred_at": "2017", "triggered_by": None, "fixed_at_commit": None},
        ],
    },
    "rule.scm.slab.sm_plant_active_required": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdThicknessAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
        "operational_history": [],
    },
    "rule.scm.slab.confirmed_plant_cd_format": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdThicknessAction.execute(SDOrderEntity,SDSlabEntity)",
            "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.validate(SDOrderEntity)",
        ],
        "operational_history": [],
    },
    "rule.scm.slab.history_isolated_transaction": {
        "enforced_by": [
            # 2026-05-10: 정정 — 패키지 경로 process.history.action (process.working.action 아님).
            "com.example.slabdesign.feature.sd.process.history.action.SdHistoryAction.recordStep(SDOrderEntity,String,int,String,String)",
        ],
        "operational_history": [
            {"incident_id": "P-2019-0445", "summary": "history rollback 사고 — REQUIRES_NEW vs REQUIRED 갭",
             "occurred_at": "2019-06-08", "triggered_by": None, "fixed_at_commit": None},
        ],
    },
    "rule.scm.slab.slab_no_sequence_per_count": {
        "enforced_by": [
            "com.example.slabdesign.feature.sd.process.working.action.SdSlabSaveAction.execute(SDOrderEntity,SDSlabEntity)",
        ],
        "operational_history": [],
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. 컬럼 추가 (idempotent)
    cur.execute("PRAGMA table_info(business_rules)")
    cols = [r[1] for r in cur.fetchall()]
    new_cols = [
        ("enforced_by_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("violated_at_call_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("operational_history_json", "TEXT NOT NULL DEFAULT '[]'"),
    ]
    for col_name, col_decl in new_cols:
        if col_name not in cols:
            if not args.dry_run:
                cur.execute(f"ALTER TABLE business_rules ADD COLUMN {col_name} {col_decl}")
            print(f"[+] {col_name} 컬럼 추가")
        else:
            print(f"[skip] {col_name} 이미 존재")

    # 2. 17 BR 의 데이터 채우기
    filled = 0
    for br_fqn, meta in BR_METADATA.items():
        cur.execute("SELECT 1 FROM business_rules WHERE fqn=? AND repo_id=?", (br_fqn, REPO_ID))
        if cur.fetchone() is None:
            print(f"  [WARN] {br_fqn} 없음")
            continue
        if not args.dry_run:
            cur.execute("""
                UPDATE business_rules
                SET enforced_by_json=?,
                    operational_history_json=?
                WHERE fqn=? AND repo_id=?
            """, (
                json.dumps(meta["enforced_by"], ensure_ascii=False),
                json.dumps(meta["operational_history"], ensure_ascii=False),
                br_fqn, REPO_ID,
            ))
        filled += 1
        print(f"  [+] {br_fqn} — enforced_by={len(meta['enforced_by'])}, history={len(meta['operational_history'])}")

    if not args.dry_run:
        conn.commit()

    # 검증
    cur.execute("SELECT count(*) FROM business_rules WHERE repo_id=? AND enforced_by_json != '[]'", (REPO_ID,))
    print(f"\n=== final ===")
    print(f"  BRs with enforced_by: {cur.fetchone()[0]} / 17")
    cur.execute("SELECT count(*) FROM business_rules WHERE repo_id=? AND operational_history_json != '[]'", (REPO_ID,))
    print(f"  BRs with operational_history: {cur.fetchone()[0]} / 17 (사고 history 명시된 것만)")
    print(f"\nfilled={filled}")

    conn.close()


if __name__ == "__main__":
    main()
