# DRAMA_DNA — Inventory of Intentional Legacy Patterns

This is the catalog of **intentional** legacy patterns in `slab-design`. They are the demo material for the modernization tool. **Do not "fix" them.**

Each entry: the pattern, where it lives, why it's there, what tool feature it demos.

---

## 1. 비표준 컬럼명 (non-standardized column names for the same concept)

The strongest seed. Same domain concept appears under different field names across tables — the legacy mess every Korean SI 시스템 has.

### 품종/품명 chaos

| Table | Column | Java field |
|-------|--------|-----------|
| `SD_HR_SPEC` | `PRODUCT_TYPE_CD` | `productTypeCd` |
| `SD_CUSTOMER_STD` | `PRODUCT_NAME_CD` | `productNameCd` |
| `SD_PRODUCTIVITY_STD` | `PRODUCT_KIND_CD` | `prodKindCd` |
| `SD_CAST_SPEC` | `PROD_TYPE_CD` (abbrev.) | `prodTypeCd` |

Same value, 4 different column names, 4 different camelCase variants.

### 공정 (plant code) chaos

| Table | Column | Notes |
|-------|--------|-------|
| `SD_ORDER_OS` | `CONFIRMED_PLANT_CD` | 8-char composite |
| `SD_HR_SPEC` | `HR_PLANT_CD` | single-char (HR slot) |
| `SD_CAST_SPEC` | `SM_PLANT_CD` | single-char (SM slot) |
| `SD_ORDER_OS` | `SM_DUE` / `HR_DUE` / `HRF_DUE` … | 8 separate columns instead of array |

### Demos

- 온톨로지 매핑: tool detects these are the same concept across columns
- 영향도 분석: "rename `PRODUCT_TYPE_CD` to `PRODUCT_KIND_CD`" → tool finds all 4 sites

---

## 2. 우선순위가 코드에 박힌 룰 (priority encoded as control flow)

`SdOrderValidator` runs 5 checks in order; first fail short-circuits.

```java
if ((r = checkStockOrder(order)) != null) return r;        // DG001
if ((r = checkOrderSize(order)) != null) return r;         // DG002
if ((r = checkPkgWgtRange(order)) != null) return r;       // DG003
if ((r = checkDesignPendQty(order)) != null) return r;     // DG004
if ((r = checkWorkDue(order)) != null) return r;           // DG005
```

The order is meaningful (DG001 재고 must run first because stock orders should never reach later checks). It's not in any rule table — only in code.

### Demos

- 영향도 분석: "what happens if DG003 runs before DG002?" → simulator shows different fail rates
- 온톨로지: extract these as ordered rules into a rule registry

---

## 3. 깊이 4+ 중첩 if/switch

`SdSecondWgtHighAction` — package weight upper bound determination has nested branches for `custStd` null-handling and ABSOLUTE_MAX_KG safety net.

`SdOrderValidator.checkWorkDue` — nested loop+if for active-process due date checks across 8 processes.

### Demos

- 자동 simplification 제안 (early return / strategy pattern)
- 시뮬레이션: refactor variant comparison

---

## 4. 공유 상태 (shared mutable state on Entity)

`SDOrderEntity` carries **DB columns** + **working fields** (`selectedHrTgtWidth`, `specificGravity`, `productivity`) populated mid-algorithm. The same object mutates across `Action` calls.

```java
public class SDOrderEntity {
    // DB-mapped
    private String cmpCd;
    private BigDecimal orderWidth;
    // ...

    // Phase 1 working fields (mutated by hrResolver / gravity / productivity)
    private BigDecimal selectedHrTgtWidth;
    private BigDecimal specificGravity;
    private BigDecimal productivity;
}
```

`SDSlabEntity` does the same with 22+ working fields for step intermediates.

### Demos

- 영향도: tracing where each working field gets read/written
- 모더나이즈: extract into immutable per-step DTO chain

---

## 5. 리플렉션 디스패치 (reflection-based JPO ↔ Entity mapping)

`SDOrderLogic.toEntity()` walks 4 JPO objects (Os/Om/Qd/Chemical) by reflection and copies fields into `SDOrderEntity` using name matching.

When two JPOs have the same field name, last-write wins.

### Demos

- 정적 분석으로 reflection 매핑 트레이스
- 매핑 룰 자동 추출 (which field comes from which JPO)

---

## 6. 2D sheet lookup

`HrMinWgtService` / `HrMaxWgtService` — table is essentially a 2-axis matrix (e.g., 강종 × 두께 buckets). Implemented as flat row table with composite key + range queries.

### Demos

- 매핑: 자동 인식 of (axis1, axis2) → value structure
- 시뮬레이션: edit one cell → impact on slab count

---

## 7. `*` wildcard fallback

`EDGING_SPEC` keys may use `*` to match any value when no exact match exists. `EdgingService` falls back from exact → partial → wildcard.

```java
// Pseudocode
exact = lookup(grade, productType, edgingGroup);
if (exact != null) return exact;
wildcard = lookup("*", productType, edgingGroup);
if (wildcard != null) return wildcard;
// ...
```

### Demos

- 영향도: "remove wildcard rule" → which orders fall through?
- 매핑: detect wildcard semantics automatically

---

## 8. A-a 분할 루프 (algorithm fallback iteration)

Steps 8~15 form a loop:
- A-step: try with maxSplitCount slabs
- If 12-13 produces invalid weights → fallback to (maxSplitCount - 1)
- Continue until splitCount = 1
- If still invalid → DG fail

This is a state machine encoded as a `while` loop with mutable counters.

### Demos

- 시뮬레이션: visualize loop iteration paths
- 모더나이즈: state-machine extraction

---

## 9. 원본 / 조정 `_1` 컬럼 suffix

`SLAB_RESULT` has duplicate columns for "original" vs "adjusted" values:
- `TARGET_WIDTH` / `TARGET_WIDTH_1`
- `TARGET_LENGTH` / `TARGET_LENGTH_1`
- `SLAB_WGT` / `SLAB_WGT_1`

The original is the algorithm output; `_1` is what (potentially) gets adjusted by downstream operators.

### Demos

- 매핑: detect `_1` suffix as "adjusted version of X"
- 영향도: "operator changed _1 value" → trace back to original

---

## 10. Magic numbers + commented-out alternatives

Examples:
- `ABSOLUTE_MAX_KG = 999999.999` (`SdSecondWgtHighAction`)
- `DEFAULT_PRODUCTIVITY = 0.95` (`ProductivityService`) — commented note shows it was 0.90 → 0.92 → 0.95 over years
- `MIN_VALID_PRODUCTIVITY = 0.50` / `MAX_VALID_PRODUCTIVITY = 1.0` — declared but not used (defense logic commented out)

### Demos

- 매핑: detect "abandoned defense logic" patterns
- 영향도: "uncomment cap logic" → simulation impact

---

## 11. 한·영 혼용 주석·네이밍

Method names in English (`cumulativeProductivity`), comments and string messages in Korean (`"포장 단중 하한 > 상한 (range integrity violation)"`), variable abbreviations mixing Korean phonetic concepts with English.

### Demos

- Tool i18n awareness — code search across language

---

## 12. @author 시그너처 + 운영이슈 history

Every major file has multi-author javadoc with dates spanning 2017-2022, plus 운영이슈 P-YYYY-XXXX historical references.

```java
/**
 * @author 김XX (2017-08-30 최초작성, 3종 점검)
 * @author 정XX (2018-12-04 설계대기량 cross-check 추가)
 * @author 박XX (2020-06-15 5종 통합 short-circuit 구조로 리팩토링)
 *
 * 운영이슈 P-2018-0098 (2018-11-22):
 *   - 재고주문 일부가 신규 설계 대상으로 들어와 슬랩 중복 생성
 *   - 해결: STOCK_CODE=1 일 때 즉시 fail (DG001) — 정XX 패치
 */
```

### Demos

- Codebase archeology — tool reconstructs intent from history comments

---

## 13. 미사용 import / dead code

Some files have commented-out methods (`breakdownByProcess` in `ProductivityService`) that are "preserved for analysis" but never called.

### Demos

- Tool detects dead code reliably

---

## 14. DG error code 분산

DG codes are defined in `SdErrorCode` enum, but their **assignment to validations** is implicit (in code structure). DG003 vs DG004 distinction: only the validator method knows which is which.

### Demos

- 자동 카탈로그 생성 from enum + usage sites

---

## 15. Composite key everywhere (회사·소)

Every table has `(cmpCd, orgCd, ...)` composite PK using `@IdClass`. Even `SD_HR_MIN_WGT` and `SD_HR_MAX_WGT` (which logically might be global rules) are scoped per company-org.

### Demos

- 매핑: composite PK 패턴 자동 인식
- "광양·포항 same rule but different rows" — duplicate detection
