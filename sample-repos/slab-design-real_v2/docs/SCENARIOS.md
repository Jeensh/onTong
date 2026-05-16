# 5 Golden Scenarios — slab-design-real_v2

`POST /api/sd/working/single?trace=true` 응답을 시나리오별 골든 파일과 매칭해 21-step 알고리즘의 정확도를 자동 회귀로 잡는다. 시드 fixture는 `slab-design-boot/src/main/resources/db/seed/{01_master,02_orders}.sql`. 골든은 `slab-design-boot/src/test/resources/golden/S{1..5}.json`.

전 시나리오 공통:

- `cmpCd = "K"`, `orgCd = "1"` (`orgCd` 컬럼 길이 1)
- `osProgress = 'C'` (designable), `closeFlag = NULL`, `stockCode = 0`
- 단위: 무게 = kg, 길이/폭 = mm
- `gradeCd = SS400` (S4만 SS41 — 경량 fail variant)
- `productCd = COIL`, `customerCd = CUST-001` (S4만 CUST-FAIL)

---

## confirmedPlantCd 인코딩

| pos | proc | 의미 / 시드 값 |
|-----|------|--------------|
| 0 | SM   | 제강. `K`(`PlantMappingService → CC1/M1`)로 고정 |
| 1 | HR   | 열연. `'1'`..`'5'` (`SelectedHrTgtWidthResolver`의 `ORDER_QD.HR_TGT_WIDTH_N` 컬럼 인덱스, **step 2 필수**: 공백이면 DG102) |
| 2 | HRF  | 열연 후처리 |
| 3 | CR   | 냉연 |
| 4 | ANL1 | 1차 소둔 |
| 5 | ANL2 | 2차 소둔 |
| 6 | GAL  | 도금 |
| 7 | CRF  | 냉연 후처리 |

공백(`' '`) = 비활성. 활성 공정은 `SD_PRODUCTIVITY_STD` lookup의 productivity 곱으로 누적실수율을 만든다. 5개 시나리오 모두 pos 0 = `K`, pos 1 = `1`이고, 그 외 pos는 시나리오 의도에 맞춰 활성/비활성을 분기한다.

---

## S1 — 일반 COIL 골든 패스

| | |
|---|---|
| `orderNo` | `ORD20260510001` |
| `confirmedPlantCd` | `K1 K    ` (SM, HR, CR) |
| 의도 | 21 step이 fail/retry 없이 진행되는 baseline |
| `designPendQty` | 10,000 kg / pkg 8,000–18,000 |
| `orderWgt` | 10,000–12,000 kg, 폭 1200, 길이 8500 |
| 기대 결과 | **슬랩 1매**, `splitCount = 1`, `errorCode = null`, `slabResults` 1행 |
| trace 관전 | step 1–7 ONE_SHOT, step 8–13 AA_LOOP iteration=1 (수렴), step 14 SKIP, step 15–21 FINAL/SAVE |

---

## S2 — 다중 슬랩 + A-a inner loop

| | |
|---|---|
| `orderNo` | `ORD20260510002` |
| `confirmedPlantCd` | `K1      ` (SM, HR만) |
| 의도 | `designPendQty` 50–60톤, 슬랩 다매 분할 |
| `designPendQty` | 55,000 kg / pkg 8,000–25,000 |
| `orderWgt` | 10,000–13,000 kg, 폭 1100, **길이 32,000(긴 코일)** — `firstWgtHigh`가 커서 알고리즘이 HR_MAX/secondWgt 캡 |
| 기대 결과 | **슬랩 3매**, `splitCount = 2` (A-a final adjust로 매수가 split 보다 1↑) |
| trace 관전 | step 8–13 iteration 다회. step 13 `slabCountInProgress = 3` 수렴 |

> **3매 vs 4매?** SPEC.md 초고는 4매 가정이었으나 시드 `CAST_SPEC.LENGTH_HIGH = 12000`이 `maxSplitCountUpper`를 캡하면서 3매가 실제 골든 결과. SCENARIOS의 truth는 골든 파일 (`S2.json`).

---

## S3 — A-a inner-loop fallback

| | |
|---|---|
| `orderNo` | `ORD20260510003` |
| `confirmedPlantCd` | `K1KK    ` (SM, HR, HRF, CR) |
| 의도 | step 9의 첫 분할수 시도가 step 10의 `pendQty in [splitWgtLow, splitWgtHigh]` 조건에서 fail → step 13으로 newCount 하향 후 재진입 |
| `designPendQty` | 35,000 kg / pkg 18,000–26,000 |
| `orderWgt` | 20,000–25,000 kg (좁은 밴드) |
| 기대 결과 | **슬랩 2매**, `splitCount = 1` → A-a recalc → `slabCountInProgress = 2` |
| trace 관전 | step 9 처음에는 slabCount=1. step 10 RETRY 후 step 13 `newCount=2`로 PASS. iteration 카운터 1 → 2 |

---

## S4 — DG004 validator cross-check fail

| | |
|---|---|
| `orderNo` | `ORD20260510004` |
| `confirmedPlantCd` | `K1      ` (SM, HR만) |
| 의도 | Phase 1 validator의 `checkDesignPendQty` — `pkgWgtLow > designPendQtyHigh` 조건 → DG004 |
| `designPendQty` | 10,000 kg, **`designPendQtyHigh = 12,000`** |
| `pkgWgt` | **`pkgWgtLow = 20,000`**, `pkgWgtHigh = 22,000` (Low > pendHigh!) |
| `gradeCd` | `SS41`, `customerCd` = `CUST-FAIL` (별도 EDGING 그룹 — 도달은 안 함) |
| 기대 결과 | **슬랩 0매**, `errorCode = "DG004"`, `errorMessage` 한국어, `SLAB_DESIGN_HIST` 1행(stepNo 0 — VALIDATION) |
| trace 관전 | trace 1행만, `status = SKIP`, `phase = "PHASE_1"`, `stepName = "VALIDATION_FAILED"` |

---

## S5 — 최소 활성 공정

| | |
|---|---|
| `orderNo` | `ORD20260510005` |
| `confirmedPlantCd` | `K1     K` (SM, HR, CRF) |
| 의도 | step 2 `HR` 외 가장 짧은 활성 시퀀스. CRF는 누적 productivity에만 영향, step 흐름엔 무영향 |
| `designPendQty` | 8,000 kg / pkg 5,000–12,000 |
| `orderWgt` | 6,000–10,000 kg, 폭 1100, 길이 7000 |
| 기대 결과 | **슬랩 1매**, `splitCount = 1`, productivity = `prod_SM × prod_HR × prod_CRF` |
| trace 관전 | S1과 거의 동일 흐름이지만 누적 productivity 값이 다름 → 이후 단중 컷 다름 |

---

## 골든 비교 — 휘발성 필드

`ScenarioGoldenTest.normalizeVolatile()`가 비교 전 normalize:

| 필드 | 처리 |
|------|-----|
| `trace[].elapsedMs` | 키 자체 제거 (시간은 재현 불가) |
| `trace[].input.slabNo` | `"__SEQ__"` 치환 (sequence-derived) |
| `trace[].output.slabNo` | `"__SEQ__"` 치환 |
| `slabResults[].slabNo` | `"__SEQ__"` 치환 |
| `slabResults[].createdAt` | `"__TS__"` 치환 |

그 외 모든 필드는 byte-equal. 이 normalize는 골든 capture와 비교 양쪽에 적용되므로 골든 파일도 `__SEQ__`/`__TS__`로 저장된다.

---

## 골든 재생성 절차

알고리즘이 의도된 변경을 받았을 때(예: 새 step 추가, 정렬 기준 변경, action 분기 수정):

```bash
GOLDEN_REGEN=true \
  ./mvnw -pl slab-design-boot test -Dtest=ScenarioGoldenTest
```

위 명령은 normalize된 응답을 그대로 `src/test/resources/golden/S{1..5}.json`에 덮어쓴다.

이후 사람이:

1. `git diff slab-design-boot/src/test/resources/golden/` 로 변경분 검토
2. step 변경의 의도와 일치하는지 확인 (DG 코드, 슬랩 수, 결과 폭/길이/단중)
3. 통과 시 commit
4. 다음 회귀에서 동일 normalize 후 byte-equal로 검사

`GOLDEN_REGEN=true`를 켜지 않으면 매 테스트는 골든 byte-equal 비교 → 의도 외 변경은 `assertThat(actual).isEqualTo(expected)` 실패로 잡힌다.

`@BeforeEach`가 `POST /api/sd/seed/reset`을 호출하므로 5개 시나리오 사이의 상태 누수는 없다.

---

## 시나리오 메타 API

런타임에서도 같은 메타를 조회 가능 (UI / 외부 도구 진입점):

```bash
curl -s 'http://localhost:8080/api/sd/seed/scenarios' | jq .
```

응답 schema는 `ScenarioMeta` 레코드(`id`, `orderNo`, `description`, `confirmedPlantCd`, `expectedOutcome`).
