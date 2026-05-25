"""slab-design 21-step 카탈로그 — walkthrough.md 와 ontology action 을 1:1 매핑.

이 모듈은 simulation agent 가 사용자 질문에 관련된 step 들을 찾고, 각 step 의
입력·출력·계산식·근거를 합성해 보여주는 단일 source of truth.

주의: 이 카탈로그 자체는 walkthrough.md 정독 후 정적으로 만든 것이지만, 런타임에는
ontology business_terms / actions API 호출로만 답변을 만든다. 즉 카탈로그가 step→
ontology action_fqn 매핑을 제공하고, 실제 입력 term / formula 출처는 ontology 가
공급한다.

Phase / step_no 매핑:
  Phase 1   — 사전 검사 + 작업용 필드  (validator, classifier, hr_tgt_width, density, productivity)
  Phase 2-A — slab 데이터 만들기 (step 1~7)
  Phase 2-B — A-a 루프 (step 8~15)
  Phase 2-C — 최종 폭/길이 (step 16~19)
  Save      — DB 저장 (step 20) + history (매 step)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Phase = Literal["phase1", "phase2a", "phase2b", "phase2c", "save"]


@dataclass
class StepSpec:
    step_no: int | None             # None 이면 phase1 의 사전 단계
    phase: Phase
    title: str                       # 한국어 한 줄
    purpose: str                     # 이 step 이 답하는 질문 (한 줄)
    formula: str                     # 핵심 공식 (있으면)
    input_terms: list[str]           # ontology business_term fqn 또는 한국어 입력
    output_field: str                # SDSlabEntity 필드
    action_fqn: str | None           # ontology action.scm.*
    base_tables: list[str]           # 참조 기준 테이블
    keywords: list[str]              # 사용자 질문 매칭용 (한국어 + 영문)
    notes: str = ""                  # 비즈니스 통찰 한 줄


STEP_CATALOG: list[StepSpec] = [
    # ── Phase 1 — 사전 검사 + 작업용 필드 ────────────────────────────────────
    StepSpec(
        step_no=None, phase="phase1",
        title="DG 검증 (5종)",
        purpose="주문이 설계 가능한 상태인지 사전 점검",
        formula="DG001~005: 재고/사이즈/단중범위/공장 due 5가지 검사",
        input_terms=["term.scm.order.order"],
        output_field="(validator 통과 여부)",
        action_fqn=None,
        base_tables=["ORDER_OS", "ORDER_OM"],
        keywords=["검증", "validator", "DG001", "DG002", "DG003", "DG004", "DG005", "사전 점검"],
        notes="하나라도 실패하면 설계 자체가 막힘 — fail-fast",
    ),
    StepSpec(
        step_no=None, phase="phase1",
        title="품종 분류 (Classifier)",
        purpose="COIL / FS / PLATE 등 품종별 알고리즘 진입점 결정",
        formula="productCd 에 따라 분기",
        input_terms=["term.scm.order.product_cd"],
        output_field="(알고리즘 진입점)",
        action_fqn=None,
        base_tables=["ORDER_OM"],
        keywords=["품종", "classifier", "COIL", "FS", "PLATE", "분류"],
        notes="품종마다 thickness/width/length 기준이 모두 다름",
    ),
    StepSpec(
        step_no=None, phase="phase1",
        title="열연 목표 폭 선택",
        purpose="confirmedPlantCd[1] 의 HR 자리에 따라 ORDER_QD 의 HR_TGT_WIDTH_N 중 하나 선택",
        formula="selectedHrTgtWidth = ORDER_QD.HR_TGT_WIDTH_{plantCd[1]}",
        input_terms=["term.scm.shared.confirmed_plant_cd"],
        output_field="selectedHrTgtWidth",
        action_fqn=None,
        base_tables=["ORDER_QD"],
        keywords=["열연 목표 폭", "hrTgtWidth", "confirmedPlantCd", "HR 폭"],
        notes="이 값이 step 2 의 폭 범위 계산에 들어감",
    ),
    StepSpec(
        step_no=None, phase="phase1",
        title="누적 실수율 (Productivity)",
        purpose="SM·HR·HRF·CR 등 활성 공정의 productivity 를 곱해 누적 실수율 계산",
        formula="productivity = ∏(SD_PRODUCTIVITY_STD where plantCd[i] != ' ')",
        input_terms=["term.scm.shared.confirmed_plant_cd", "term.scm.product.productivity_std"],
        output_field="productivity",
        action_fqn="action.scm.product.cumulative_productivity",
        base_tables=["SD_PRODUCTIVITY_STD"],
        keywords=["실수율", "productivity", "누적", "공정", "손실"],
        notes="알고리즘 전반의 핵심 — Slab↔코일 환산. 예: 0.903 이면 1톤 Slab → 0.903톤 코일",
    ),
    # ── Phase 2-A — Slab 데이터 만들기 (step 1~7) ──────────────────────────
    StepSpec(
        step_no=1, phase="phase2a",
        title="Slab 두께 결정",
        purpose="CAST_SPEC 룩업으로 Slab 두께 1개 값 결정",
        formula="thickness = CAST_SPEC[smCd, castCd, machineCd, productCd].SLAB_THICKNESS",
        input_terms=["term.scm.shared.confirmed_plant_cd", "term.scm.order.product_cd"],
        output_field="slabThickness",
        action_fqn="action.scm.thickness_실행",
        base_tables=["CAST_SPEC"],
        keywords=["두께", "thickness", "slabThickness", "연주설비"],
        notes="공장+품종이 정해지면 두께는 사실상 1 값으로 고정",
    ),
    StepSpec(
        step_no=2, phase="phase2a",
        title="Slab 폭 범위 (1차)",
        purpose="연주+열연+EDGING 폭 능력 교집합으로 폭 범위 결정",
        formula="widthLow  = max(CAST.WIDTH_LOW,  HR.WIDTH_LOW,  hrTgtWidth+EDGING.CAP_LOW)\n"
                "widthHigh = min(CAST.WIDTH_HIGH, HR.WIDTH_HIGH, hrTgtWidth+EDGING.CAP_HIGH)",
        input_terms=["term.scm.spec.cast_spec", "term.scm.spec.hr_spec", "term.scm.spec.edging_group"],
        output_field="firstWidthLow / firstWidthHigh",
        action_fqn="action.scm.width_range_실행",
        base_tables=["CAST_SPEC", "HR_SPEC", "EDGING_GROUP", "EDGING_SPEC"],
        keywords=["폭", "width", "widthLow", "widthHigh", "edging", "폭 범위"],
        notes="3개 설비 중 가장 좁은 것이 결과를 결정 (binding constraint)",
    ),
    StepSpec(
        step_no=3, phase="phase2a",
        title="Slab 길이 범위 (1차)",
        purpose="연주+열연 길이 능력 교집합",
        formula="lengthLow  = max(CAST.LENGTH_LOW,  HR.LENGTH_LOW)\n"
                "lengthHigh = min(CAST.LENGTH_HIGH, HR.LENGTH_HIGH)",
        input_terms=["term.scm.spec.cast_spec", "term.scm.spec.hr_spec"],
        output_field="firstLengthLow / firstLengthHigh",
        action_fqn="action.scm.length_range_실행",
        base_tables=["CAST_SPEC", "HR_SPEC"],
        keywords=["길이", "length", "lengthLow", "lengthHigh"],
        notes="EDGING 영향 없음 — 연주·열연만 본다",
    ),
    StepSpec(
        step_no=4, phase="phase2a",
        title="1차 무게 범위 (순수 계산)",
        purpose="두께·폭·길이 양 끝값으로 무게 범위 산출",
        formula="wgt = thickness × width × length × density × 1e-6\n"
                "  (density = 7.82 g/cm³, 결과 단위 kg)",
        input_terms=["term.scm.thickness", "term.scm.slab.width", "term.scm.slab.length"],
        output_field="firstWgtLow / firstWgtHigh",
        action_fqn="action.scm.first_weight_실행",
        base_tables=[],
        keywords=["1차 단중", "first weight", "무게", "단중", "weight"],
        notes="비중 (밀도) 은 강철 고정값 7.82",
    ),
    StepSpec(
        step_no=5, phase="phase2a",
        title="2차 무게 하한",
        purpose="압연 MIN + 고객사 MIN 으로 단중 하한 보강",
        formula="secondWgtLow = max(firstWgtLow, HR_MIN_WGT[t≥thk, w≥widthLow], CUSTOMER_STD.PKG_WGT_LOW)",
        input_terms=["term.scm.hr_min_wgt", "term.scm.customer_std"],
        output_field="secondWgtLow",
        action_fqn="action.scm.second_wgt_low_실행",
        base_tables=["HR_MIN_WGT", "CUSTOMER_STD"],
        keywords=["단중 하한", "MIN_WGT", "secondWgtLow", "HR_MIN"],
        notes="고객사 등록 안 됐으면 무시. 압연이 보통 binding",
    ),
    StepSpec(
        step_no=6, phase="phase2a",
        title="2차 무게 상한 ★",
        purpose="압연 MAX + 고객사 + 설계대기량 상한 으로 무게 상한 좁힘",
        formula="yieldAdjustedHigh = designPendQtyHigh / productivity\n"
                "secondWgtHigh = min(firstWgtHigh, HR_MAX_WGT, CUSTOMER_STD.PKG_WGT_HIGH, yieldAdjustedHigh)",
        input_terms=["term.scm.hr_max_wgt", "term.scm.customer_std", "term.scm.order.order"],
        output_field="secondWgtHigh",
        action_fqn="action.scm.second_wgt_high_실행",
        base_tables=["HR_MAX_WGT", "CUSTOMER_STD", "ORDER_OS"],
        keywords=["단중 상한", "MAX_WGT", "secondWgtHigh", "HR_MAX", "설계대기량", "yieldAdjusted"],
        notes="설계대기량이 자주 binding — 큰 Slab 만들어 봐야 의미 없음 신호",
    ),
    StepSpec(
        step_no=7, phase="phase2a",
        title="최대 분할수 결정",
        purpose="Slab 1장에서 코일 최대 몇 개까지 자를 수 있는지",
        formula="raw = secondWgtHigh / orderWgtHigh / productivity\n"
                "maxSplitCountUpper = ceil(raw)",
        input_terms=["term.scm.slab.weight", "term.scm.order.order"],
        output_field="maxSplitCountUpper",
        action_fqn="action.scm.max_split_count_실행",
        base_tables=[],
        keywords=["분할수", "split count", "maxSplit", "분할"],
        notes="A-a 루프의 시작점. 여기서부터 split--로 줄여가며 탐색",
    ),
    # ── Phase 2-B — A-a 루프 (step 8~15) ──────────────────────────────────
    StepSpec(
        step_no=8, phase="phase2b",
        title="분할 단중 범위",
        purpose="현 split 에서 Slab이 가져야 할 단중 범위 계산",
        formula="orderRangeLow  = orderWgtLow  × split / productivity\n"
                "orderRangeHigh = orderWgtHigh × split / productivity\n"
                "splitWgtLow  = max(orderRangeLow, secondWgtLow)\n"
                "splitWgtHigh = min(orderRangeHigh, secondWgtHigh)\n"
                "if Low > High → DG108 → split-- 재시도",
        input_terms=["term.scm.slab.weight"],
        output_field="splitWgtLow / splitWgtHigh",
        action_fqn="action.scm.split_range_실행",
        base_tables=[],
        keywords=["분할 단중", "splitWgt", "DG108", "A-a 루프"],
        notes="A-a 루프의 첫 게이트 — 실패 시 split--",
    ),
    StepSpec(
        step_no=9, phase="phase2b",
        title="Slab 매수",
        purpose="설계대기량을 splitWgtHigh 로 나눠 Slab 몇 장 필요한지",
        formula="raw = designPendQtyHigh / productivity / splitWgtHigh\n"
                "slabCount = floor(raw)",
        input_terms=[],
        output_field="slabCountInProgress",
        action_fqn="action.scm.slab.slab_count_실행",
        base_tables=[],
        keywords=["매수", "slabCount", "장수", "몇 장"],
        notes="0 매수면 step 12 fallback 으로 매수+1",
    ),
    StepSpec(
        step_no=10, phase="phase2b",
        title="초기 Slab 무게 검사",
        purpose="slabWgt × 매수가 설계대기량 범위 안에 들어가는지 확인",
        formula="slabWgt = splitWgtHigh\n"
                "totalProduced = slabWgt × slabCount\n"
                "yieldLow  = orderWgtLow  / productivity\n"
                "yieldHigh = orderWgtHigh / productivity\n"
                "PASS if yieldLow ≤ totalProduced ≤ yieldHigh",
        input_terms=[],
        output_field="slabWgtInProgress",
        action_fqn="action.scm.slab.initial_slab_wgt_실행",
        base_tables=[],
        keywords=["Slab 무게 검사", "initialSlabWgt", "yield range"],
        notes="PASS 면 A-a 루프 탈출 — split/매수 확정",
    ),
    StepSpec(
        step_no=12, phase="phase2b",
        title="Slab 무게 재계산 (fallback)",
        purpose="step 10 실패 시 매수+1 로 다시 slabWgt 계산",
        formula="slabCount += 1\nslabWgt = designPendQty / productivity / slabCount\nrecheck range",
        input_terms=[],
        output_field="slabWgtInProgress, slabCountInProgress",
        action_fqn="action.scm.slab.slab_wgt_recalc_실행",
        base_tables=[],
        keywords=["재계산", "recalc", "fallback", "매수+1"],
        notes="이것도 실패하면 split-- 재시도",
    ),
    # ── Phase 2-C — 최종 폭/길이 역산 (step 16~19) ─────────────────────────
    StepSpec(
        step_no=16, phase="phase2c",
        title="최종 폭 범위 (역산)",
        purpose="Slab 무게에서 거꾸로 폭 범위 계산",
        formula="finalWidthLow  = ceil( slabWgt × 1e6 / (lengthHigh × thickness × density) )\n"
                "finalWidthHigh = floor(slabWgt × 1e6 / (lengthLow  × thickness × density) )",
        input_terms=["term.scm.slab.weight", "term.scm.thickness", "term.scm.slab.length"],
        output_field="finalWidthLow / finalWidthHigh",
        action_fqn="action.scm.final_width_range_실행",
        base_tables=[],
        keywords=["최종 폭", "finalWidth", "역산"],
        notes="길이 양 끝값으로 폭 양 끝 — 자유도가 줄어든 단계",
    ),
    StepSpec(
        step_no=17, phase="phase2c",
        title="최종 길이 범위 (역산)",
        purpose="Slab 무게에서 거꾸로 길이 범위 계산",
        formula="raw = slabWgt × 1e6 / (width × thickness × density)\n"
                "finalLengthLow  = max(raw_at_widthHigh, firstLengthLow)\n"
                "finalLengthHigh = min(raw_at_widthLow,  firstLengthHigh)",
        input_terms=["term.scm.slab.weight", "term.scm.thickness", "term.scm.slab.width"],
        output_field="finalLengthLow / finalLengthHigh",
        action_fqn="action.scm.final_length_range_실행",
        base_tables=[],
        keywords=["최종 길이", "finalLength", "역산"],
        notes="",
    ),
    StepSpec(
        step_no=18, phase="phase2c",
        title="목표 폭 결정 ★ (10mm 단위)",
        purpose="실제 제조할 Slab 폭 1 값 (10mm 단위 ceiling)",
        formula="raw = splitWgtHigh × 1e6 / (finalLengthHigh × thickness × density)\n"
                "targetSlabWidth = ceil(raw / 10) × 10\n"
                "(out of range 면 finalWidthLow 로 fallback)",
        input_terms=["term.scm.slab.weight", "term.scm.slab.length", "term.scm.thickness"],
        output_field="targetSlabWidth",
        action_fqn="action.scm.target_width_실행",
        base_tables=[],
        keywords=["목표 폭", "targetWidth", "targetSlabWidth"],
        notes="현장 가공 편의 위해 10mm 단위로 깔끔하게",
    ),
    StepSpec(
        step_no=19, phase="phase2c",
        title="목표 길이 결정 (1mm 단위)",
        purpose="목표 폭에 맞춰 길이 역산 후 1mm 단위 floor",
        formula="targetSlabLength = floor(slabWgt × 1e6 / (targetSlabWidth × thickness × density))",
        input_terms=["term.scm.slab.weight", "term.scm.thickness"],
        output_field="targetSlabLength",
        action_fqn="action.scm.target_length_실행",
        base_tables=[],
        keywords=["목표 길이", "targetLength", "targetSlabLength"],
        notes="이 시점에 Slab 사이즈 (두께·폭·길이) 완전 확정",
    ),
    # ── Save (step 20 + history) ────────────────────────────────────────────
    StepSpec(
        step_no=20, phase="save",
        title="SLAB_RESULT 저장",
        purpose="확정된 Slab 데이터를 DB 에 매수 만큼 insert",
        formula="for i in range(slabCount): INSERT INTO SLAB_RESULT (...)",
        input_terms=["term.scm.slab.slab"],
        output_field="(DB insert)",
        action_fqn="action.scm.slab.slab_save_실행",
        base_tables=["SLAB_RESULT"],
        keywords=["저장", "save", "SLAB_RESULT", "DB insert"],
        notes="slabNo 는 SlabNoSequence 가 발급. 매 step 별 SLAB_DESIGN_HIST 도 같이 적재",
    ),
]


# 키워드 → step 매칭 ────────────────────────────────────────────────────────

PHASE_LABELS = {
    "phase1":  "Phase 1 — 사전 검사·작업용 필드",
    "phase2a": "Phase 2-A — Slab 데이터 만들기",
    "phase2b": "Phase 2-B — A-a 루프 (분할수×매수 탐색)",
    "phase2c": "Phase 2-C — 최종 폭/길이 역산",
    "save":    "Save — DB 저장",
}


def steps_matching_query(query: str, max_n: int = 6) -> list[StepSpec]:
    """사용자 질문에서 키워드 매칭으로 관련 step 들 반환 (score 정렬).

    2026-05-25: 매칭 안 되면 의도별 default step set 도 반환 — 모든 의도에서
    walkthrough 카드가 노출되도록.
    """
    if not query:
        return []
    q = query.lower()
    scored: list[tuple[int, StepSpec]] = []
    for s in STEP_CATALOG:
        score = 0
        for kw in s.keywords:
            kl = kw.lower()
            if kl in q:
                score += max(1, len(kw) // 2)
        if score > 0:
            scored.append((score, s))
    if scored:
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:max_n]]

    # fallback — 질문 의도 추정으로 default step set
    if any(k in q for k in ("시뮬", "설계 결과", "돌려", "전체 설계")):
        defaults = ["phase1", "phase2a", "save"]
        out = [s for s in STEP_CATALOG if s.phase in defaults]
        return out[:max_n + 2]
    if any(k in q for k in ("어디", "위치", "어느 단계")):
        return [s for s in STEP_CATALOG if s.step_no in (1, 4, 6, 7, 8, 18, 19, 20)][:max_n]
    if any(k in q for k in ("신규", "추가", "들어오면", "강종", "고객사", "품종")):
        # hypothesis — 전 흐름 (Phase 1 + 2-A + Save)
        return [s for s in STEP_CATALOG if s.step_no in (1, 4, 6, 8, 18, 20)
                or s.phase == "phase1"][:max_n]
    if any(k in q for k in ("뭐야", "무엇", "뭐고", "이란", "관련", "어떻게 쓰여", "어떤", "어디서 쓰여")):
        # explain — Phase 1 (사전 환산) 위주 + 핵심 출력 step
        out = [s for s in STEP_CATALOG if s.phase == "phase1"]
        out += [s for s in STEP_CATALOG if s.step_no in (4, 6, 20)]
        return out[:max_n]
    return []


def steps_in_phase(phase: Phase) -> list[StepSpec]:
    return [s for s in STEP_CATALOG if s.phase == phase]


def step_by_no(no: int) -> StepSpec | None:
    return next((s for s in STEP_CATALOG if s.step_no == no), None)


def step_to_dict(s: StepSpec) -> dict:
    return {
        "step_no": s.step_no,
        "phase": s.phase,
        "phase_label": PHASE_LABELS.get(s.phase, s.phase),
        "title": s.title,
        "purpose": s.purpose,
        "formula": s.formula,
        "input_terms": s.input_terms,
        "output_field": s.output_field,
        "action_fqn": s.action_fqn,
        "base_tables": s.base_tables,
        "keywords": s.keywords,
        "notes": s.notes,
    }
