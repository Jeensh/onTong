# ALGORITHM — 21-step Slab Design

The full slab design algorithm implemented in `SdDesigner`. Reference for understanding what each step does and where it lives.

## Phase 1 — 사전 처리

| # | Stage | Class | What |
|---|-------|-------|------|
| P1.1 | 정합성 점검 | `SdOrderValidator` | DG001–005 short-circuit. Fail → history fail row + skip |
| P1.2 | 제품 분류 | `SdProductClassifier` | COIL only. 그 외 silent skip |
| P1.3.a | HR target width 결정 | `SelectedHrTgtWidthResolver` | order.orderWidth basis 후보 lookup |
| P1.3.b | 비중 캐시 | `SpecificGravityProvider` | 7.82 상수 (강종별 분기 자리만 마련) |
| P1.3.c | 누적 실수율 캐시 | `ProductivityService.cumulativeProductivity` | 활성 공정 8 자리 곱 |

## Phase 2 — 알고리즘

### One-shot (steps 1–7)

| # | Step | Class | Output → SDSlabEntity |
|---|------|-------|----------------------|
| 1 | Slab 두께 산정 | `SdThicknessAction` | `slabThickness` |
| 2 | 1차 폭 범위 산정 | `SdWidthRangeAction` | `firstWidthLow`, `firstWidthHigh` |
| 3 | 1차 길이 범위 산정 | `SdLengthRangeAction` | `firstLengthLow`, `firstLengthHigh` |
| 4 | 1차 단중 산정 | `SdFirstWeightAction` | `firstWgt` |
| 5 | 2차 단중 하한 | `SdSecondWgtLowAction` | `secondWgtLow` |
| 6 | 2차 단중 상한 | `SdSecondWgtHighAction` | `secondWgtHigh` |
| 7 | 최대 분할수 산정 | `SdMaxSplitCountAction` | `maxSplitCount` |

### A-a 루프 (steps 8–15)

```
splitCount = maxSplitCount
loop:
  step 8:  SdSplitRangeAction       → split 단위 범위
  step 9:  SdSlabCountAction        → 매수 산정
  step 10: SdInitialSlabWgtAction   → 초기 Slab 단중
  step 12-13: SdSlabWgtRecalcAction → 재산정
  if 12-13 통과:
     break (loop 탈출)
  else:
     splitCount -= 1
     if splitCount < 1:
        throw DG fail
```

### One-shot (steps 16–19)

| # | Step | Class | Output |
|---|------|-------|--------|
| 16 | 최종 폭 범위 | `SdFinalWidthRangeAction` | `finalWidthLow`, `finalWidthHigh` |
| 17 | 최종 길이 범위 | `SdFinalLengthRangeAction` | `finalLengthLow`, `finalLengthHigh` |
| 18 | 목표 폭 | `SdTargetWidthAction` | `targetWidth` |
| 19 | 목표 길이 | `SdTargetLengthAction` | `targetLength` |

### Save (steps 20–21)

| # | Step | Class | Action |
|---|------|-------|--------|
| 20 | SLAB_RESULT 저장 | `SdSlabSaveAction` | 매수만큼 row 저장 (원본 + `_1` suffix 컬럼 동시 채움) |
| 21 | History 적재 | `SdHistoryAction` (wrapper) | 각 step 별로 SLAB_DESIGN_HIST row |

## DG error codes

### Validation (DG001–005, in SdOrderValidator)

| Code | 의미 |
|------|------|
| DG001 | 재고주문 (STOCK_CODE=1) — 새 설계 대상 아님 |
| DG002 | 주문 폭/길이 양수 아님 |
| DG003 | 포장단중 하/상한 invalid |
| DG004 | 설계대기량 + 포장단중 cross-check fail (상한 ≥ 포장단중하한) |
| DG005 | 작업기한일 (활성 공정 8 due + ORDER_OM.WORK_DUE) 미래 날짜 아님 |

### Algorithm (DG101–109)

| Code | 의미 | 등장 step |
|------|------|----------|
| DG101 | CAST_SPEC 미존재 | 1, 3 |
| DG102 | HR_SPEC 미존재 | 2, 3 |
| DG103 | EDGING_GROUP 미존재 | 2 |
| DG104 | 폭 범위 invalid | 2 |
| DG105 | 길이 범위 invalid | 3 |
| DG106 | 단중 산정 invalid | 4–6 |
| DG107 | 최대 분할수 invalid | 7 |
| DG108 | A-a 루프 탈출 실패 | 12–13 |
| DG109 | 최종 폭/길이 invalid | 16–17 |

(EDGING_SPEC 미존재는 DG 코드 없이 IllegalStateException — 사용자 사양)

## Key data shapes

### confirmedPlantCd (8-char)

Position-encoded plant code per process:

```
position 0 1 2 3 4 5 6 7
process  SM HR HRF CR ANL1 ANL2 GAL CRF
```

Char `' '` (space) at position N = process N inactive. Active char = the plant code for that process at that company-org.

Example: `"K     P "` = SM at Kwangyang, GAL at Pohang, others inactive.

### Cumulative productivity

```
result = 1.0
for each active position i:
  productivity_i = lookup(cmpCd, orgCd, PROC_CODES[i], grade, prodKind, customer) ?? 0.95
  result *= productivity_i
```

Cached on `SDOrderEntity.productivity`.

### `_1` suffix (SLAB_RESULT)

```
TARGET_WIDTH    ← step 18 output (원본)
TARGET_WIDTH_1  ← initially same; downstream operator may adjust
TARGET_LENGTH   ← step 19 output (원본)
TARGET_LENGTH_1 ← initially same
SLAB_WGT        ← step 12-13 output (원본)
SLAB_WGT_1      ← initially same
```

## Save patterns

- `SLAB_RESULT` rows = `slabCount` (step 9 output) per order
- Each row gets a unique 12-digit zero-padded slabNo from `SlabNoSequence`
- `SLAB_DESIGN_HIST` = one row per step (success or fail), JSON snapshot of slab state at that point

## Where to read code

| Want to see... | File |
|----------------|------|
| Top-level orchestration | `slab-design-feature/.../sd/designer/SdDesigner.java` |
| Batch entry | `slab-design-feature/.../sd/driver/SdDriver.java` |
| HTTP entry | `slab-design-facade/.../rest/working/SdWorkingController.java` |
| Validation | `slab-design-feature/.../action/SdOrderValidator.java` |
| Each step action | `slab-design-feature/.../action/Sd*Action.java` |
| Std service lookups | `slab-design-feature/.../std/service/*Service.java` |
| Error codes | `slab-design-feature/.../wrapper/SdErrorCode.java` |
| History wrapper | `slab-design-feature/.../history/action/SdHistoryAction.java` |
