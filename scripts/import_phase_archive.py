"""Phase A/B/C archive 의 atomic 16 + BR 12 + AnchorBinding 9 를 ontology DB 에 import.

Source: toClaude/modeling/{round6-live-authoring, phase-b-archive-confirm, phase-c-archive-confirm}.html
Target: data/ontology.db
Repo:   slab-design-real

usage:
  python scripts/import_phase_archive.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ontology.db"
REPO_ID = "slab-design-real"
SOURCE_TAG = "archive-html"


# ──────────────────────────────────────────────────────────────────
# atomic 16 (Phase A 7 + B 6 + C 3)
# ──────────────────────────────────────────────────────────────────
ATOMICS: list[dict] = [
    # ── Phase A (7) ─────────────────────────────────────────────
    {"fqn": "term.scm.shared.cmp", "label": "회사", "domain": "scm.shared",
     "description": "모든 entity 공유 — 회사 코드. 길이 2 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["회사", "company"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.org", "label": "소", "domain": "scm.shared",
     "description": "모든 entity 공유 — 사업소 코드. 길이 1 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["소", "사업소", "org"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.proc", "label": "공정", "domain": "scm.shared",
     "description": "공정 코드. 8 enum: SM/HR/HRF/CR/ANL1/ANL2/GAL/CRF.",
     "value_type": "string", "unit": None, "range_json": None,
     "enum_values_json": json.dumps(["SM", "HR", "HRF", "CR", "ANL1", "ANL2", "GAL", "CRF"]),
     "aliases_json": json.dumps(["공정", "process"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.grade", "label": "강종", "domain": "scm.shared",
     "description": "자유 식별자. 길이 10 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["강종", "grade"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.product_kind", "label": "품종", "domain": "scm.shared",
     "description": "4-7 alias chaos (drama DNA). 길이 3~4 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["품종", "productKind", "kind"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.customer", "label": "고객사", "domain": "scm.shared",
     "description": "Customer/Productivity/Order 공유.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["고객사", "customer", "고객"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.confirmed_plant_cd", "label": "확정통과공장코드", "domain": "scm.shared",
     "description": "encoding: 자리 i ↔ proc[i], activation: ' '=비활성. 길이 8 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["확정통과공장코드", "confirmedPlantCd"], ensure_ascii=False)},
    # ── Phase B (6) ─────────────────────────────────────────────
    {"fqn": "term.scm.shared.hr_plant_cd", "label": "열연공장코드", "domain": "scm.shared",
     "description": "related_atomic: confirmed_plant_cd[1] = proc[1]=HR. 길이 1 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["열연공장코드", "hrPlantCd"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.sm_cd", "label": "제강코드", "domain": "scm.shared",
     "description": "confirmed_plant_cd[0] = proc[0]=SM. 길이 1 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["제강코드", "smCd"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.cast_cd", "label": "연주코드", "domain": "scm.shared",
     "description": "PlantMappingService sm→cast 매핑. 길이 4 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["연주코드", "castCd"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.machine_cd", "label": "머신코드", "domain": "scm.shared",
     "description": "PlantMappingService sm→machine 매핑. 길이 4 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["머신코드", "machineCd"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.edging_group_cd", "label": "엣징그룹코드", "domain": "scm.shared",
     "description": "EdgingGroup PK. 길이 10 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["엣징그룹코드", "edgingGroupCd"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.priority", "label": "우선순위", "domain": "scm.shared",
     "description": "tiebreaker semantic (PRIORITY ASC).",
     "value_type": "integer", "unit": None, "range_json": json.dumps({"min": 0}),
     "enum_values_json": None,
     "aliases_json": json.dumps(["우선순위", "priority"], ensure_ascii=False)},
    # ── Phase C (3) ─────────────────────────────────────────────
    {"fqn": "term.scm.shared.order_no", "label": "주문번호", "domain": "scm.shared",
     "description": "unique per (cmp, org). 길이 20 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["주문번호", "orderNo"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.slab_no", "label": "슬랩번호", "domain": "scm.shared",
     "description": "generated_by SlabNoSequence. 길이 20 string.",
     "value_type": "string", "unit": None, "range_json": None, "enum_values_json": None,
     "aliases_json": json.dumps(["슬랩번호", "slabNo"], ensure_ascii=False)},
    {"fqn": "term.scm.shared.specific_gravity", "label": "비중", "domain": "scm.shared",
     "description": "강종별 비중 (specific gravity).",
     "value_type": "decimal", "unit": None, "range_json": json.dumps({"min": 0.0}),
     "enum_values_json": None,
     "aliases_json": json.dumps(["비중", "specificGravity"], ensure_ascii=False)},
]


# ──────────────────────────────────────────────────────────────────
# BusinessRule 12 (Phase A 1 + B 3 + C 8)
# (5개 DG006~DG010 은 archive 에 명시 부족 — design-gaps 후속)
# ──────────────────────────────────────────────────────────────────
BUSINESS_RULES: list[dict] = [
    # ── Phase A (1) ─────────────────────────────────────────────
    {"fqn": "rule.scm.std.productivity_safe_range",
     "statement": "실수율 범위 (0.5 ≤ p ≤ 1.0). cumulativeProductivity 결과의 안전 영역.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.std.productivity_std"])},
    # ── Phase B (3) ─────────────────────────────────────────────
    {"fqn": "rule.scm.spec.edging_spec_lookup_strategy",
     "statement": "EdgingSpec 3-단계 룩업 정책 (exact → partial → wildcard).",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.spec.edging_spec"])},
    {"fqn": "rule.scm.spec.edging_group_match_strategy",
     "statement": "EdgingGroup AND 매칭 + PRIORITY ASC 전략.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.spec.edging_group"])},
    {"fqn": "rule.scm.spec.hr_wgt_2d_ceiling_lookup",
     "statement": "HrMinWgt / HrMaxWgt 2D ceiling lookup.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.spec.hr_min_wgt", "term.scm.spec.hr_max_wgt"])},
    # ── Phase C (8) ─────────────────────────────────────────────
    {"fqn": "rule.scm.order.no_stock_order",
     "statement": "재고주문 (STOCK_CODE=1) 은 설계 대상 아님. (DG001)",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.order"])},
    {"fqn": "rule.scm.order.order_size_positive",
     "statement": "주문 폭/길이 모두 양수. (DG002)",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.order"])},
    {"fqn": "rule.scm.order.pkg_wgt_range_integrity",
     "statement": "포장단중 하/상한 양수 + 하한≤상한. (DG003)",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.order"])},
    {"fqn": "rule.scm.order.design_pend_qty_cross_check",
     "statement": "설계대기량 양수 + 상한≥포장단중하한. (DG004)",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.order"])},
    {"fqn": "rule.scm.order.work_due_strict_future",
     "statement": "활성공정의 *Due + WORK_DUE 모두 미래 날짜. (DG005)",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.order"])},
    {"fqn": "rule.scm.std.customer_find_first_match_strategy",
     "statement": "Customer 매칭 + PRIORITY ASC + first row 선택 전략. (Phase A retroactive)",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.std.customer_design_limit"])},
    {"fqn": "rule.scm.slab.original_equals_adjusted",
     "statement": "원본 컬럼 = 조정 컬럼 (9 pairs invariant). SlabResult 의 무결성 BR.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.slab_result"])},
    {"fqn": "rule.scm.slab.aa_loop_max_iter_cap",
     "statement": "A-a 루프 최대 반복 횟수 cap. (P-2018-0721 사고 회귀)",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.slab_result"])},
    # ── Phase C — 21-step body (3) — 2nd extraction (archive line 1440~1452, 1598~1600) ─
    {"fqn": "rule.scm.slab.absolute_max_kg_safety_cap",
     "statement": "ABSOLUTE_MAX_KG (999,999.999 kg) safety cap. 2017년 운영 회의 결정 history.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.slab_result"])},
    {"fqn": "rule.scm.slab.sm_plant_active_required",
     "statement": "SdThicknessAction (step 1) 진입 시 confirmedPlantCd[0] (제강 위치) 가 ' ' 비활성 X. 비활성 시 DG101 throw.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.shared.confirmed_plant_cd", "term.scm.slab.slab_result"])},
    {"fqn": "rule.scm.slab.confirmed_plant_cd_format",
     "statement": "confirmedPlantCd 는 NULL/empty/length<8 X. 형식 위반 시 DG101 (Thickness) / DG005 (Validator) throw.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.shared.confirmed_plant_cd"])},
    # ── Phase C — Save + history (2) — 2nd extraction (archive line 1723~1731, 1897~1898) ──
    {"fqn": "rule.scm.slab.history_isolated_transaction",
     "statement": "SdHistoryAction 별 @Transactional 메서드 isolation. P-2019-0445 history. javadoc REQUIRES_NEW vs 실제 default REQUIRED 갭은 design-gap #36 으로 트래킹.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.slab.slab_result"])},
    {"fqn": "rule.scm.slab.slab_no_sequence_per_count",
     "statement": "매수 row 복제 패턴 — 1st = pre-generate / 2~Nth = SlabNoSequence.next 호출.",
     "severity": "error",
     "terms_ref_json": json.dumps(["term.scm.shared.slab_no", "term.scm.slab.slab_result"])},
]


# ──────────────────────────────────────────────────────────────────
# AnchorBinding 9 (Phase A — Round 6: cumulativeProductivity 7 + findFirstMatch 2)
# ──────────────────────────────────────────────────────────────────
ANCHOR_BINDINGS: list[dict] = [
    # ── cumulativeProductivity (7) ──────────────────────────────
    {"id": "anchor_cumul_prod_invalid_check",
     "anchor_locator": "confirmedPlantCd == null || length < 8",
     "code_method_fqn": "ProductivityService.cumulativeProductivity",
     "target_action_fqn": "action.scm.std.cumulative_productivity",
     "target_slot": "atomic.confirmed_plant_cd.invalid_check",
     "confidence": 0.85,
     "rationale": "Phase A Round 6 anchor — 입력 무결성 가드"},
    {"id": "anchor_cumul_prod_default_literal",
     "anchor_locator": "DEFAULT_PRODUCTIVITY = 0.95",
     "code_method_fqn": "ProductivityService.cumulativeProductivity",
     "target_action_fqn": "action.scm.std.cumulative_productivity",
     "target_slot": "rule.scm.std.productivity_safe_range.fallback",
     "confidence": 0.9,
     "rationale": "Phase A Round 6 anchor — invalid 시 fallback 값"},
    {"id": "anchor_cumul_prod_loop_bound",
     "anchor_locator": "literal 8",
     "code_method_fqn": "ProductivityService.cumulativeProductivity",
     "target_action_fqn": "action.scm.std.cumulative_productivity",
     "target_slot": "atomic.scm.shared.proc.enum_size",
     "confidence": 0.95,
     "rationale": "Phase A Round 6 anchor — proc 8 enum 길이"},
    {"id": "anchor_cumul_prod_activation_check",
     "anchor_locator": "charAt(i) == ' '",
     "code_method_fqn": "ProductivityService.cumulativeProductivity",
     "target_action_fqn": "action.scm.std.cumulative_productivity",
     "target_slot": "atomic.confirmed_plant_cd.activation_check",
     "confidence": 0.9,
     "rationale": "Phase A Round 6 anchor — confirmed_plant_cd[i] activation"},
    {"id": "anchor_cumul_prod_proc_codes",
     "anchor_locator": "PROC_CODES[i]",
     "code_method_fqn": "ProductivityService.cumulativeProductivity",
     "target_action_fqn": "action.scm.std.cumulative_productivity",
     "target_slot": "atomic.scm.shared.proc.enum_values[i]",
     "confidence": 0.95,
     "rationale": "Phase A Round 6 anchor — proc enum 값 매핑"},
    {"id": "anchor_cumul_prod_multiply_local",
     "anchor_locator": "product = product.multiply(p)",
     "code_method_fqn": "ProductivityService.cumulativeProductivity",
     "target_action_fqn": "action.scm.std.cumulative_productivity",
     "target_slot": "aggregation.multiply",
     "confidence": 0.85,
     "rationale": "Phase A Round 6 anchor — 누적 곱 aggregation"},
    {"id": "anchor_cumul_prod_return",
     "anchor_locator": "return product",
     "code_method_fqn": "ProductivityService.cumulativeProductivity",
     "target_action_fqn": "action.scm.std.cumulative_productivity",
     "target_slot": "facet.productivity",
     "confidence": 0.9,
     "rationale": "Phase A Round 6 anchor — 결과 facet"},
    # ── findFirstMatch (2) ──────────────────────────────────────
    {"id": "anchor_customer_empty_check",
     "anchor_locator": "matches.isEmpty() → null",
     "code_method_fqn": "CustomerStdService.findFirstMatch",
     "target_action_fqn": "action.scm.std.match_customer_limit_for_order",
     "target_slot": "action.metadata.fallback_kind",
     "confidence": 0.85,
     "rationale": "Phase A Round 6 anchor — 매칭 없을 시 skip 정책"},
    {"id": "anchor_customer_first_match",
     "anchor_locator": "matches.get(0)",
     "code_method_fqn": "CustomerStdService.findFirstMatch",
     "target_action_fqn": "action.scm.std.match_customer_limit_for_order",
     "target_slot": "action.metadata.tiebreaker",
     "confidence": 0.85,
     "rationale": "Phase A Round 6 anchor — PRIORITY ASC tiebreaker"},
]


def insert_atomics(conn: sqlite3.Connection, dry_run: bool) -> int:
    cur = conn.cursor()
    inserted = 0
    for atom in ATOMICS:
        if dry_run:
            cur.execute("SELECT 1 FROM business_terms WHERE fqn = ?", (atom["fqn"],))
            if cur.fetchone():
                print(f"  [skip — exists] {atom['fqn']}")
                continue
            print(f"  [would insert] {atom['fqn']} / {atom['label']}")
            inserted += 1
            continue
        cur.execute("""
            INSERT OR IGNORE INTO business_terms (
                fqn, label, aliases_json, domain, description, kind,
                is_abstract, is_interface, is_root_entity, struct_like_hint,
                value_type, unit, range_json, enum_values_json,
                confirmed, repo_id, source
            ) VALUES (?, ?, ?, ?, ?, 'atomic', 0, 0, 0, 0, ?, ?, ?, ?, 1, ?, ?)
        """, (
            atom["fqn"], atom["label"], atom["aliases_json"],
            atom["domain"], atom["description"],
            atom["value_type"], atom["unit"],
            atom["range_json"], atom["enum_values_json"],
            REPO_ID, SOURCE_TAG,
        ))
        if cur.rowcount > 0:
            inserted += 1
            print(f"  [+] {atom['fqn']} / {atom['label']}")
        else:
            print(f"  [skip — exists] {atom['fqn']}")
    return inserted


def insert_business_rules(conn: sqlite3.Connection, dry_run: bool) -> int:
    cur = conn.cursor()
    inserted = 0
    for br in BUSINESS_RULES:
        if dry_run:
            cur.execute("SELECT 1 FROM business_rules WHERE fqn = ?", (br["fqn"],))
            if cur.fetchone():
                print(f"  [skip — exists] {br['fqn']}")
                continue
            print(f"  [would insert] {br['fqn']} / sev={br['severity']}")
            inserted += 1
            continue
        cur.execute("""
            INSERT OR IGNORE INTO business_rules (
                fqn, statement, severity, terms_ref_json,
                source, confirmed, repo_id
            ) VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (
            br["fqn"], br["statement"], br["severity"], br["terms_ref_json"],
            SOURCE_TAG, REPO_ID,
        ))
        if cur.rowcount > 0:
            inserted += 1
            print(f"  [+] {br['fqn']}")
        else:
            print(f"  [skip — exists] {br['fqn']}")
    return inserted


def insert_anchor_bindings(conn: sqlite3.Connection, dry_run: bool) -> int:
    cur = conn.cursor()
    inserted = 0
    for ab in ANCHOR_BINDINGS:
        if dry_run:
            cur.execute("SELECT 1 FROM anchor_bindings WHERE id = ?", (ab["id"],))
            if cur.fetchone():
                print(f"  [skip — exists] {ab['id']}")
                continue
            print(f"  [would insert] {ab['id']} / {ab['anchor_locator']}")
            inserted += 1
            continue
        cur.execute("""
            INSERT OR IGNORE INTO anchor_bindings (
                id, anchor_locator, code_method_fqn,
                target_action_fqn, target_slot, confidence,
                source, confirmed, rationale, repo_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            ab["id"], ab["anchor_locator"], ab["code_method_fqn"],
            ab["target_action_fqn"], ab["target_slot"], ab["confidence"],
            SOURCE_TAG, ab["rationale"], REPO_ID,
        ))
        if cur.rowcount > 0:
            inserted += 1
            print(f"  [+] {ab['id']}")
        else:
            print(f"  [skip — exists] {ab['id']}")
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        print(f"DB: {DB_PATH}")
        print(f"repo_id: {REPO_ID}")
        print(f"source: {SOURCE_TAG}")
        print(f"mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}\n")

        print("=== atomic 16 ===")
        a_count = insert_atomics(conn, args.dry_run)

        print("\n=== BusinessRule 12 ===")
        b_count = insert_business_rules(conn, args.dry_run)

        print("\n=== AnchorBinding 9 ===")
        ab_count = insert_anchor_bindings(conn, args.dry_run)

        if not args.dry_run:
            conn.commit()
            print(f"\n✓ Committed. atomic +{a_count} / BR +{b_count} / AnchorBinding +{ab_count}")
        else:
            print(f"\n[DRY-RUN] atomic ~{a_count} / BR ~{b_count} / AnchorBinding ~{ab_count}")

        # 검증 쿼리
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM business_terms WHERE kind='atomic' AND repo_id=?", (REPO_ID,))
        a_total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM business_rules WHERE repo_id=?", (REPO_ID,))
        b_total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM anchor_bindings WHERE repo_id=?", (REPO_ID,))
        ab_total = cur.fetchone()[0]

        print(f"\n=== 최종 카운트 (slab-design-real) ===")
        print(f"  atomic:        {a_total}  (target 16)")
        print(f"  BusinessRule:  {b_total}  (target 17, archive 명시 12)")
        print(f"  AnchorBinding: {ab_total}  (target 9)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
