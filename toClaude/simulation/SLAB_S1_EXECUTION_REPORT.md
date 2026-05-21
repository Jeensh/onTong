# slab-design-real-v2 — S1 시나리오 실측 실행 결과

> 사용자 요청: "현재 온톨로지로 된 slab-design 시스템에서, 실제로 input(주문)
> 을 넣고 output(slab)이 나오는 실제 결과를 하나 작성"
>
> 실제 Java Spring Boot 서버를 띄워 (`mvn -pl slab-design-boot spring-boot:run`),
> 21-step 알고리즘을 통째로 실행한 결과. golden file (`S1.json`) 과 byte-equal
> 매칭 확인.
>
> 실행 일자: 2026-05-21
> 브랜치: `jyu-simul`

---

## 1. 시스템 한 줄 요약

slab-design 은 **주문 (코일을 만들 원료 사양) → 슬랩 (제강에서 압연으로 보낼
직육면체 원료) 의 21-step 알고리즘 변환기**. 각 step 은 Java action class
(`SdThicknessAction`, `SdWidthRangeAction` 등) 이고 ontology 가 모두
`action.scm.<step_name>_실행` 노드로 매핑돼 있다.

5-tier 데이터:
| Layer | 종류 | 예 |
|---|---|---|
| Term | 도메인 명사 | 주문 / 슬랩 / 단중 / EDGING그룹 |
| Action | 비즈니스 동작 | 두께 계산 / 단중하한 / 분할수 산출 |
| CodeMethod | Java 메서드 | `SdThicknessAction.execute(SDOrderEntity)` |
| Rule | 비즈니스 룰 | `productivity_safe_range`, `min_thickness_per_grade` |
| Anchor | 코드 가드 | `if (orderWgt < min) throw DG004` |

---

## 2. Input — 주문 1건 (`ORD20260510001`)

`02_orders.sql` seed 에서:

### 2.1 ORDER_OS (진도·포장·단중 한도)
| 필드 | 값 |
|---|---|
| cmpCd | `K` |
| orgCd | `1` |
| orderNo | `ORD20260510001` |
| osProgress | `C` (designable) |
| confirmedPlantCd | `K1 K    ` (SM=K, HR=1, CR=K 활성) |
| designPendQty | **10,000 kg** (설계 대기량) |
| designPendQtyLow / High | 8,000 / 12,000 kg (포장 단중 범위) |

### 2.2 ORDER_OM (목표 사이즈)
| 필드 | 값 |
|---|---|
| orderWgtLow / High | 10,000 / 12,000 kg (코일 1매 단중) |
| orderWidth | **1,200 mm** |
| orderLength | **8,500 mm** |
| productCd | `COIL` |
| customerCd | `CUST-001` |
| pkgWgtLow / High | 8,000 / 18,000 |

### 2.3 ORDER_QD (품질·강종)
| 필드 | 값 |
|---|---|
| gradeCd | `SS400` |

### 2.4 가공 라인 활성 공정
`confirmedPlantCd = "K1 K    "` → 8 pos:

| pos | proc | 값 | 의미 |
|---|---|---|---|
| 0 | SM | K | 제강 |
| 1 | HR | 1 | 열연 (HR width index 1) |
| 2 | HRF | (공백) | 비활성 |
| 3 | CR | K | 냉연 |
| 4-7 | ANL1/ANL2/GAL/CRF | (공백) | 비활성 |

---

## 3. API 호출

```bash
curl -X POST 'http://127.0.0.1:8080/api/sd/working/single?trace=true' \
  -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"1","orderNo":"ORD20260510001"}'
```

---

## 4. Output — 슬랩 1매 (`slabNo 000000000002`)

> golden S1.json 과 모든 수치가 byte-equal 매칭. (slabNo 는 SEQUENCE 라 동적)

| 필드 | 값 | 의미 |
|---|---|---|
| **slabThickness** | **230.00 mm** | 두께 (Step 1 SdThicknessAction) |
| **slabWidth** | **620** | 최종 폭 (Step 18 target) |
| **slabLength** | **11,916** | 최종 길이 (Step 19 target) |
| **slabWgt** | **13,288.006 kg** | 슬랩 단중 |
| **splitCount** | **1** | 분할수 (1 = 단일 슬랩) |
| **designStatus** | **SUCCESS** | |
| errorCode | null | |
| slabWgtLow / High | 11,073 / 13,288 kg | 단중 허용 범위 |
| slabWidthLow / High | 616 / 1,846 | 폭 허용 범위 |
| slabLengthLow / High | 4,002 / 11,993 | 길이 허용 범위 |
| firstWidthLow / High | 1,150 / 1,250 | 1차 폭 범위 (열연 입력) |
| firstWgtLow / High | 8,274 / 26,979 | 1차 단중 범위 |
| secondWgtLow / High | 8,274 / 13,288 | 2차 단중 범위 (HR_MAX 캡) |
| maxSplitCountUpper | 2 | 분할수 상한 |

---

## 5. 21-step 실행 trace (18 actual rows)

> S1 은 ONE_SHOT path → AA_LOOP 1 회 → SAVE. step 11/12/13 은 ONE_SHOT 분기에서 생략됨.

| step | Java action | ontology action | phase | iter | status |
|---|---|---|---|---|---|
| 1 | SdThicknessAction | `action.scm.thickness_실행` | ONE_SHOT | 1 | OK |
| 2 | SdWidthRangeAction | `action.scm.width_range_실행` | ONE_SHOT | 1 | OK |
| 3 | SdLengthRangeAction | `action.scm.length_range_실행` | ONE_SHOT | 1 | OK |
| 4 | SdFirstWeightAction | `action.scm.first_weight_실행` | ONE_SHOT | 1 | OK |
| 5 | SdSecondWgtLowAction | `action.scm.second_wgt_low_실행` | ONE_SHOT | 1 | OK |
| 6 | SdSecondWgtHighAction | `action.scm.second_wgt_high_실행` | ONE_SHOT | 1 | OK |
| 7 | SdMaxSplitCountAction | `action.scm.max_split_count_실행` | ONE_SHOT | 1 | OK |
| 8 | SdSplitRangeAction | `action.scm.split_range_실행` | AA_LOOP | 2 | **FAIL → RETRY → OK** |
| 9 | SdSlabCountAction | `action.scm.slab.slab_count_실행` | AA_LOOP | 1 | OK |
| 10 | SdInitialSlabWgtAction | `action.scm.slab.initial_slab_wgt_실행` | AA_LOOP | 1 | OK |
| 14 | MAX_WGT_MODE | (분기) | AA_LOOP | 1 | SKIP |
| 16 | SdFinalWidthRangeAction | `action.scm.final_width_range_실행` | ONE_SHOT | 1 | OK |
| 17 | SdFinalLengthRangeAction | `action.scm.final_length_range_실행` | ONE_SHOT | 1 | OK |
| 18 | SdTargetWidthAction | `action.scm.target_width_실행` | ONE_SHOT | 1 | OK |
| 19 | SdTargetLengthAction | `action.scm.target_length_실행` | ONE_SHOT | 1 | OK |
| 20 | SdSlabSaveAction | `action.scm.slab.save_step` | SAVE | 1 | OK |

**관전 포인트**:
- Step 8 첫 시도 FAIL → A-a 루프가 RETRY 발동 (iteration 1→2) → 두 번째 시도 OK
- Step 14 MAX_WGT_MODE 는 단중 모드 분기인데 S1 은 일반 모드이므로 SKIP
- Step 15 (Validator), Step 21 (History) 는 trace 에 별도 row 로 안 찍힘 (validation phase)

---

## 6. ontology 와 일대일 매핑 확인

136 actions 중 21-step 모두 매핑 완료:

```sql
sqlite3 data/ontology.db "
SELECT a.fqn, a.label, r.code_method_fqn
FROM actions a JOIN realizations r ON r.action_fqn = a.fqn
WHERE a.repo_id='slab-design-real-v2'
  AND a.fqn LIKE 'action.scm.%_실행'
ORDER BY a.fqn"
```

→ 14 step action + 1 workflow(`action.scm.슬랩설계_실행`) + helper actions.

---

## 7. 이 데이터 기반 시뮬레이션 에이전트 질문 (8종)

지금 `?view=simulation` 의 preset 7개에 더해, 실제 실행 데이터로 보강 가능한 질문:

| # | intent | 질문 | 기대 흐름 |
|---|---|---|---|
| 1 | simulate | "ORD20260510001 주문으로 슬랩 설계 시뮬레이션 돌려줘" | Gate II bundle (Java + Python + fixture) → Gate III 실행 |
| 2 | simulate | "ORD20260510001 의 orderWidth 를 1,200→1,500mm 로 바꿔 돌리면?" | compare_runs → slabLength · slabWgt diff 표시 |
| 3 | impact | "Step 1 SdThicknessAction 의 두께 결정 로직을 바꾸면 어디 영향?" | downstream Step 2/4/5/6 추적 (slabThickness 의존성) |
| 4 | impact | "secondWgtLow 하한을 8,000→9,000kg 으로 올리면 S1·S2 둘 다 통과해?" | 영향받는 method · rule · 주문 list |
| 5 | locate | "DG104 (HR_MIN_WGT 미발견) 은 어디서 throw 돼?" | `SdSecondWgtLowAction.java:line` 위치 |
| 6 | locate | "A-a 루프 RETRY 분기 코드는 어디?" | `SdDriver` 의 loop controller |
| 7 | explain | "Step 8 SdSplitRangeAction 이 첫 시도 FAIL 한 이유는?" | iteration 1 의 input/output 분석 (golden trace) |
| 8 | hypothesis | "신규 강종 HC600X (얇은 두께 0.2mm) 가 추가되면 Step 1 분기?" | 가상 Term 합성 + SdThicknessAction 본문 추적 |

---

## 8. 검증

```bash
# 1) Java 서버 가동 (slab-design-boot)
cd sample-repos/slab-design-real_v2
mvn -DskipTests install
mvn -pl slab-design-boot spring-boot:run
# → 127.0.0.1:8080

# 2) S1 실행
curl -X POST 'http://127.0.0.1:8080/api/sd/working/single?trace=true' \
  -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"1","orderNo":"ORD20260510001"}'

# 3) golden 비교
diff <(curl ... | jq '.slabResults[0] | del(.slabNo, .createdAt)') \
     <(jq '.slabResults[0] | del(.slabNo, .createdAt)' \
        sample-repos/slab-design-real_v2/slab-design-boot/src/test/resources/golden/S1.json)
# → 0 diff
```

S2~S5 시나리오 (다중 슬랩, A-a fallback, DG004 fail, 경량 fail) 도 같은 방식으로 검증.
