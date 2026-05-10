// step_id → 한국어 라벨 mapping. UI 전반에서 영문 step_id 옆에 한국어 부제로 표시.
//
// 기준: backend/simulation/sandbox/registry.py 의 STEP_REGISTRY + Java 21단계 알고리즘.

export interface StepLabel {
  ko: string; // 한국어 라벨 (간결, 메뉴/뱃지용)
  description: string; // 한 줄 설명 (툴팁용)
  stepNo?: number; // Java 알고리즘 21단계 중 몇 번째인지 (해당되면)
}

export const STEP_LABELS: Record<string, StepLabel> = {
  validator: {
    ko: "검증 (DG001~005)",
    description: "재고 / 사이즈 / 포장단중 / 설계대기량 / 작업기한일 5종 검증",
  },
  productivity: {
    ko: "누적 실수율",
    description: "활성 공정의 실수율 곱 (HR × HRF × ANL1 …)",
  },
  thickness: {
    ko: "1차 두께 결정",
    description: "CAST_SPEC 룩업 → Slab 두께 산정",
    stepNo: 1,
  },
  width_range: {
    ko: "1차 폭 범위",
    description: "CAST_SPEC ∩ HR_SPEC ∩ EDGING 폭 범위",
    stepNo: 2,
  },
  length_range: {
    ko: "1차 길이 범위",
    description: "CAST_SPEC ∩ HR_SPEC 길이 범위",
    stepNo: 3,
  },
  second_wgt: {
    ko: "단중 하/상한 (격자 룩업)",
    description: "HR_MIN/MAX_WGT 2D 격자에서 단중 하한/상한 룩업",
    stepNo: 5,
  },
  max_split: {
    ko: "최대 분할수",
    description: "A-a 루프 시작점 — 최대 분할수 산정",
    stepNo: 7,
  },
  split_range: {
    ko: "분할 범위 (단중 ∩ 주문)",
    description: "분할수를 고려한 단중 범위 계산",
    stepNo: 8,
  },
  slab_count: {
    ko: "Slab 매수",
    description: "floor(설계대기량 ÷ 누적실수율 ÷ 단중)",
    stepNo: 9,
  },
  slab_weight: {
    ko: "Slab 단중",
    description: "설계대기량 만족 점검 + Slab 단중 결정",
    stepNo: 10,
  },
  final_width_range: {
    ko: "최종 폭 범위",
    description: "최종 폭 하/상한 결정",
    stepNo: 16,
  },
  final_length_range: {
    ko: "최종 길이 범위",
    description: "최종 길이 하/상한 결정",
    stepNo: 17,
  },
  target_size: {
    ko: "목표 폭 / 길이",
    description: "최종 목표 폭/길이 산정",
    stepNo: 18,
  },
  plant_mapping_migrate: {
    ko: "PlantMapping 마이그",
    description: "변경 전·후 룩업 결과 비교 — 어느 주문이 깨지는지 시뮬",
  },
  pipeline: {
    ko: "기본 파이프라인",
    description: "검증 → 실수율 → 분할 → 매수 → 단중 (간단 e2e)",
  },
  pipeline_full: {
    ko: "전체 파이프라인",
    description: "validate → step 1~19 전체 흐름 (가장 풍부)",
  },
};

/** step_id → 한국어 라벨. mapping 없으면 step_id 그대로. */
export function getStepLabel(stepId: string | null | undefined): string {
  if (!stepId) return "—";
  return STEP_LABELS[stepId]?.ko ?? stepId;
}

/** step_id → "한국어 라벨 (영문 ID)" 형태 — 양쪽 다 보고 싶을 때. */
export function formatStep(stepId: string | null | undefined): string {
  if (!stepId) return "—";
  const m = STEP_LABELS[stepId];
  if (!m) return stepId;
  return `${m.ko} · ${stepId}`;
}

/** step_id → 설명. 툴팁 / 부제 용. */
export function getStepDescription(stepId: string | null | undefined): string {
  if (!stepId) return "";
  return STEP_LABELS[stepId]?.description ?? "";
}

/** step_id → 한국어 + Step 번호 prefix. (예: "Step 9 — Slab 매수") */
export function getStepWithNumber(stepId: string | null | undefined): string {
  if (!stepId) return "—";
  const m = STEP_LABELS[stepId];
  if (!m) return stepId;
  return m.stepNo ? `Step ${m.stepNo} — ${m.ko}` : m.ko;
}
