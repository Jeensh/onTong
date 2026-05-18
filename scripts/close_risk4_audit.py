"""Close Risk 4 — add missing action mappings + descriptions for 11 high-risk
Java methods in slab-design-real-v2 domain-role classes (DG001-005 +
SdDesigner orchestrator + SdSlabSaveAction projection).

Idempotent: actions use INSERT OR IGNORE; realizations are checked for
duplicates via the unique (action_fqn, code_method_fqn, applies_to_code_type_fqn)
constraint before insert.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

REPO_ID = "slab-design-real-v2"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ontology.db"

# ──────────────────────────────────────────────────────────────────────
# Group A — DG rule production methods. We add realizations of the EXISTING
# test-named actions to the production methods (option (i): multi-realization).
# This makes both test + production method discoverable under the rule action.
# ──────────────────────────────────────────────────────────────────────
GROUP_A_REALIZATIONS: list[dict] = [
    {
        "action_fqn": "action.scm.order.dg001_stock_order_returns_fail",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkStockOrder(SDOrderEntity)",
    },
    {
        "action_fqn": "action.scm.order.dg002_null_order_length_returns_fail",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkOrderSize(SDOrderEntity)",
    },
    {
        "action_fqn": "action.scm.order.dg002_zero_order_width_returns_fail",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkOrderSize(SDOrderEntity)",
    },
    {
        "action_fqn": "action.scm.order.dg003_negative_pkg_wgt_low_returns_fail",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkPkgWgtRange(SDOrderEntity)",
    },
    {
        "action_fqn": "action.scm.order.dg003_pkg_wgt_low_greater_than_high_returns_fail",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkPkgWgtRange(SDOrderEntity)",
    },
    {
        "action_fqn": "action.scm.order.dg004_design_pend_qty_high_below_pkg_wgt_low_returns_fail",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkDesignPendQty(SDOrderEntity)",
    },
    {
        "action_fqn": "action.scm.order.dg005_inactive_process_due_ignored_returns_pass",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkWorkDue(SDOrderEntity)",
    },
    {
        "action_fqn": "action.scm.order.dg005_past_due_date_returns_fail",
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator.checkWorkDue(SDOrderEntity)",
    },
]

# ──────────────────────────────────────────────────────────────────────
# Group B + C — NEW actions for orchestrator + projection methods.
# Each entry produces 1 action row + 1 realization row.
# ──────────────────────────────────────────────────────────────────────
NEW_ACTIONS: list[dict] = [
    # ───── Group B: SdDesigner orchestrator (5 methods) ─────
    {
        "fqn": "action.scm.slab.run_aa_loop",
        "label": "run_aa_loop",
        "domain": "scm.slab",
        "description": (
            "SdDesigner 의 step 8~15 A-a 수렴 루프. slab.maxSplitCountUpper 부터 "
            "1 까지 분할수를 감소시키며 각 반복마다 currentSplitCount 를 set, "
            "그 다음 SdSplitRangeAction(8) / SdSlabCountAction(9) / "
            "SdInitialSlabWgtAction(10) 을 tryStep 으로 silent 호출. "
            "step 10 이 true 면 step 11 implicit 로 간주하고 즉시 return, "
            "false 면 SdSlabWgtRecalcAction(13) 으로 fallback 하여 true 면 "
            "step 15 implicit 로 return. 분할수 max~1 전부 실패 시 "
            "AlgorithmException(step=8, code=ALG_NO_CONVERGENCE) throw. "
            "내부 iteration 은 history 미적재 — Designer 가 수렴 후 1 row "
            "(A_A_LOOP_CONVERGED) 만 기록한다."
        ),
        "code_method_fqn": "com.example.slabdesign.feature.sd.designer.SdDesigner.runAaLoop(SDOrderEntity,SDSlabEntity,TraceCollector)",
        "effects": ["mutates:slab.currentSplitCount", "throws:AlgorithmException(ALG_NO_CONVERGENCE)"],
    },
    {
        "fqn": "action.scm.slab.try_step",
        "label": "try_step",
        "domain": "scm.slab",
        "description": (
            "A-a 루프 내부의 단일 step silent 시도 wrapper. step.run(order, slab) "
            "호출 후 정상 return 시 true. AlgorithmException 발생 시 errorCode 가 "
            "DG108 (ALG_ITERATION_NEEDED) 이면 재시도 신호로 false 반환 — trace "
            "있으면 recordRetry 로 RETRY 이벤트 적재. 그 외 errorCode 는 outer "
            "catch 로 throw propagate. trace 있을 때만 trace.wrap 으로 step 별 "
            "input/output snapshot 기록한다 (history 미적재)."
        ),
        "code_method_fqn": "com.example.slabdesign.feature.sd.designer.SdDesigner.tryStep(int,String,SDOrderEntity,SDSlabEntity,TraceCollector,int,AlgorithmStep)",
        "effects": ["delegates:AlgorithmStep.run", "catches:AlgorithmException(ALG_ITERATION_NEEDED)"],
    },
    {
        "fqn": "action.scm.slab.execute_with_history",
        "label": "execute_with_history",
        "domain": "scm.slab",
        "description": (
            "one-shot step 1~7 / 16~19 의 표준 wrapper. step.run(order, slab) 호출 "
            "후 성공 시 historyAction.recordStep(order, slab.slabNo, stepNo, "
            "stepName, snapshotSlab(slab)) 로 SLAB_DESIGN_HIST 1 row 적재. "
            "실패 (AlgorithmException) 는 outer try-catch 가 처리하므로 history "
            "는 적재되지 않는다. trace 있으면 trace.wrap 으로 ONE_SHOT 카테고리 "
            "snapshot 함께 기록."
        ),
        "code_method_fqn": "com.example.slabdesign.feature.sd.designer.SdDesigner.executeWithHistory(int,String,String,SDOrderEntity,SDSlabEntity,TraceCollector,AlgorithmStep)",
        "effects": ["delegates:AlgorithmStep.run", "writes:SLAB_DESIGN_HIST"],
    },
    {
        "fqn": "action.scm.slab.save_step",
        "label": "save_step",
        "domain": "scm.slab",
        "description": (
            "step 20 SLAB_RESULT 저장 wrapper. SdSlabSaveAction.execute(order, slab) "
            "에 위임하여 매수개 row 를 SLAB_RESULT 테이블에 INSERT 한 뒤 저장된 "
            "slabNo 리스트를 반환. trace 있으면 trace.wrap 으로 SAVE 카테고리 + "
            "savedSlabNos.size 를 output snapshot 에 포함 기록한다. "
            "SdDesigner 가 이 결과로 SLAB_RESULT_SAVED history row 를 적재."
        ),
        "code_method_fqn": "com.example.slabdesign.feature.sd.designer.SdDesigner.saveStep(SDOrderEntity,SDSlabEntity,TraceCollector)",
        "effects": ["delegates:SdSlabSaveAction.execute", "writes:SLAB_RESULT"],
    },
    {
        "fqn": "action.scm.slab.create_initial_slab",
        "label": "create_initial_slab",
        "domain": "scm.slab",
        "description": (
            "Phase 2 진입 시 SDSlabEntity 신규 인스턴스 생성 + 초기화. "
            "order 로부터 cmpCd / orgCd / orderNo / confirmedPlantCd / "
            "possiblePlantCd 를 복사. slabNo 는 SlabNoSequence.next() 로 "
            "12자리 sequence 발급. designStatus='IN_PROGRESS' 로 set. "
            "리턴된 slab 이 21-step 알고리즘 전체의 mutable container 가 된다."
        ),
        "code_method_fqn": "com.example.slabdesign.feature.sd.designer.SdDesigner.createInitialSlab(SDOrderEntity)",
        "effects": ["creates:SDSlabEntity", "calls:SlabNoSequence.next"],
    },
    # ───── Group C: SdSlabSaveAction projection (1 method) ─────
    {
        "fqn": "action.scm.slab.apply_algorithm_results_to_final_fields",
        "label": "apply_algorithm_results_to_final_fields",
        "domain": "scm.slab",
        "description": (
            "step 20 직전 invariant — 알고리즘 결정값을 SLAB_RESULT 컬럼의 "
            "원본 (no suffix) + 조정 (_1) 양쪽에 동일하게 복사한다. "
            "9 쌍 projection: (slabWidth ← targetSlabWidth), "
            "(slabWidthHigh ← finalWidthHigh), (slabWidthLow ← finalWidthLow), "
            "(slabLength ← targetSlabLength), (slabLengthHigh ← finalLengthHigh), "
            "(slabLengthLow ← finalLengthLow), (slabWgt ← slabWgtInProgress), "
            "(slabWgtHigh ← splitWgtHigh), (slabWgtLow ← splitWgtLow), + "
            "splitCount ← optimalSplitCount. 알고리즘 직후 원본=조정. "
            "사이즈 조정 단계에서 _1 만 갱신될 자리를 미리 동일값으로 채우는 "
            "design intent."
        ),
        "code_method_fqn": "com.example.slabdesign.feature.sd.process.working.action.SdSlabSaveAction.applyAlgorithmResultsToFinalFields(SDSlabEntity)",
        "effects": [
            "mutates:slab.slabWidth", "mutates:slab.slabWidth1",
            "mutates:slab.slabLength", "mutates:slab.slabLength1",
            "mutates:slab.slabWgt", "mutates:slab.slabWgt1",
            "mutates:slab.splitCount",
        ],
    },
]


def _append_marker(desc: str, code_method_fqn: str) -> str:
    return desc + "\n\n자동 추천 — " + code_method_fqn


def _ensure_realization(
    cur: sqlite3.Cursor, action_fqn: str, code_method_fqn: str,
    rationale: str,
) -> tuple[bool, str]:
    """Return (created, status). status one of: 'created', 'exists',
    'action_missing', 'method_missing'."""
    # Verify code_method exists
    row = cur.execute(
        "SELECT 1 FROM code_methods WHERE fqn = ? AND repo_id = ?",
        (code_method_fqn, REPO_ID),
    ).fetchone()
    if row is None:
        return False, "method_missing"

    # Verify action exists
    row = cur.execute(
        "SELECT 1 FROM actions WHERE fqn = ? AND repo_id = ?",
        (action_fqn, REPO_ID),
    ).fetchone()
    if row is None:
        return False, "action_missing"

    # Already exists?
    row = cur.execute(
        "SELECT 1 FROM realizations "
        "WHERE action_fqn = ? AND code_method_fqn = ? "
        "AND applies_to_code_type_fqn IS NULL",
        (action_fqn, code_method_fqn),
    ).fetchone()
    if row is not None:
        return False, "exists"

    cur.execute(
        "INSERT INTO realizations "
        "(action_fqn, code_method_fqn, applies_to_code_type_fqn, "
        " is_override, dispatch_source, confidence, scope, confirmed, "
        " rationale, repo_id) "
        "VALUES (?, ?, NULL, 0, 'audit', 1.0, 'primary', 1, ?, ?)",
        (action_fqn, code_method_fqn, rationale, REPO_ID),
    )
    return True, "created"


def _insert_action(cur: sqlite3.Cursor, entry: dict) -> bool:
    """INSERT OR IGNORE the action row. Return True if a new row created."""
    description = _append_marker(entry["description"], entry["code_method_fqn"])
    cur.execute(
        "INSERT OR IGNORE INTO actions "
        "(fqn, label, aliases_json, domain, description, kind, is_abstract, "
        " declared_on_term, params_json, output_json, "
        " preconditions_json, postconditions_json, effects_json, "
        " sub_actions_json, verification_level, signature_locked_at, "
        " confirmed_by, repo_id) "
        "VALUES (?, ?, '[]', ?, ?, 'effectful', 0, NULL, '[]', NULL, "
        "        '[]', '[]', ?, '[]', 'signature_locked', NULL, "
        "        'audit_risk4_close', ?)",
        (
            entry["fqn"], entry["label"], entry["domain"], description,
            json.dumps(entry["effects"]), REPO_ID,
        ),
    )
    return cur.rowcount > 0


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # ─── Baseline counts ─────────────────────────────────────
    before_actions = cur.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    before_real = cur.execute("SELECT COUNT(*) FROM realizations").fetchone()[0]
    before_sim = cur.execute(
        "SELECT COUNT(*) FROM actions WHERE verification_level='sim_verified'"
    ).fetchone()[0]
    print(f"BEFORE: actions={before_actions} realizations={before_real} sim_verified={before_sim}")

    # ─── Group A: add 8 production realizations to existing DG actions ───
    created_a, skipped_a, missing_a = 0, 0, 0
    for entry in GROUP_A_REALIZATIONS:
        ok, status = _ensure_realization(
            cur, entry["action_fqn"], entry["code_method_fqn"],
            "Risk 4 audit — DG rule production method (multi-realization with test)",
        )
        if ok:
            created_a += 1
            print(f"  [A+] {entry['action_fqn']} <- {entry['code_method_fqn'].rsplit('.', 1)[-1]}")
        elif status == "exists":
            skipped_a += 1
            print(f"  [A=] {entry['action_fqn']} already linked — skip")
        else:
            missing_a += 1
            print(f"  [A!] {entry['action_fqn']} — {status}")

    # ─── Groups B + C: 6 NEW actions + their realizations ────
    created_actions, created_real_bc, missing_bc = 0, 0, []
    new_action_fqns: list[str] = []
    for entry in NEW_ACTIONS:
        if _insert_action(cur, entry):
            created_actions += 1
            print(f"  [N+] action {entry['fqn']}")
        else:
            print(f"  [N=] action {entry['fqn']} already exists — kept")
        new_action_fqns.append(entry["fqn"])

        ok, status = _ensure_realization(
            cur, entry["fqn"], entry["code_method_fqn"],
            "Risk 4 audit — orchestrator / projection method gap",
        )
        if ok:
            created_real_bc += 1
            print(f"  [N+] real   {entry['fqn']} <- {entry['code_method_fqn'].rsplit('.', 1)[-1]}")
        elif status == "exists":
            print(f"  [N=] real   {entry['fqn']} already linked — skip")
        else:
            missing_bc.append((entry["fqn"], status))
            print(f"  [N!] real   {entry['fqn']} — {status}")

    conn.commit()

    # ─── Verification (via verify_action) ────────────────────
    print("\n--- Verification ---")
    from backend.modeling.code_layer.store import session_scope
    from backend.sim_v2.core.verification.action_method_verifier import verify_action
    from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
        ActionView,
    )

    verify_results: list[tuple[str, str, tuple]] = []
    with session_scope() as session:
        for entry in NEW_ACTIONS:
            av = ActionView(
                fqn=entry["fqn"],
                label=entry["label"],
                code_method_fqn=entry["code_method_fqn"],
                repo_id=REPO_ID,
            )
            r = verify_action(session, av)
            verify_results.append((entry["fqn"], r.status, r.notes))
            note_str = (" | " + "; ".join(r.notes)) if r.notes else ""
            print(f"  {r.status:>16}  {entry['fqn']}{note_str}")

    # Promote VERIFIED ones to sim_verified
    promoted = 0
    for action_fqn, status, _notes in verify_results:
        if status == "VERIFIED":
            cur.execute(
                "UPDATE actions "
                "SET verification_level='sim_verified', "
                "    confirmed_by='audit_risk4_close_verified' "
                "WHERE fqn = ? AND repo_id = ?",
                (action_fqn, REPO_ID),
            )
            promoted += cur.rowcount

    conn.commit()
    print(f"\nPromoted to sim_verified: {promoted}")

    # ─── Final counts ────────────────────────────────────────
    after_actions = cur.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    after_real = cur.execute("SELECT COUNT(*) FROM realizations").fetchone()[0]
    after_sim = cur.execute(
        "SELECT COUNT(*) FROM actions WHERE verification_level='sim_verified'"
    ).fetchone()[0]
    print(f"\nAFTER:  actions={after_actions} realizations={after_real} sim_verified={after_sim}")
    print(f"DELTA:  actions+{after_actions-before_actions} realizations+{after_real-before_real} sim_verified+{after_sim-before_sim}")

    conn.close()


if __name__ == "__main__":
    main()
