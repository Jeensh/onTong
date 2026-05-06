# 주문 (4 table → 1 Entity → 1 도메인) 매핑 설계

**질문**: "여러 테이블 → 주문 엔티티를 온톨로지로 어떻게 설정했어?"

## 실제 Java 구조 (slab-design-real)

slab-design 의 주문은 **3 layer 가 다른 표현** — 이게 drama DNA 핵심:

```
┌── DB Layer (4 정규화 table) ──────────────────────────┐
│ SD_ORDER_OS         (PK + 진척/재고/대기량/8 due/...) │
│ SD_ORDER_OM         (orderWidth/Length/pkgWgt/...)    │
│ SD_ORDER_QD         (gradeCd/hrTgtWidth1~5)           │
│ SD_ORDER_CHEMICAL   (8 성분 × min/max/aim = 24 col)   │
└────────────────────────────────────────────────────────┘
       ↓ JPO 4개 (DB mirror)
┌── Java Layer ──────────────────────────────────────────┐
│ SDOrderEntity (★ 통합 도메인 객체)                    │
│   = 4 JPO 의 모든 필드를 평탄화 + 작업용 필드 3개      │
│ SDOrderLogic (★ reflection 으로 JPO ↔ Entity 변환)    │
└────────────────────────────────────────────────────────┘
       ↓ feature 측이 SDOrderEntity 만 사용
┌── 도메인 (사람이 읽는 매뉴얼) ─────────────────────────┐
│ "주문" 은 4 부분으로 구성:                            │
│   - 주문스펙 (Os): 진척, 재고, 대기량, 8 공정 due     │
│   - 주문메타 (Om): 폭/길이/포장/고객/납기            │
│   - 품질데이터 (Qd): 강종, HR 타겟 폭 5종            │
│   - 화학성분 (Chemical): C/Si/Mn/P/S/Cr/Ni/Al × 3    │
└────────────────────────────────────────────────────────┘
```

**문제**: 같은 도메인 개념이 3 layer 에서 다르게 표현됨. 기존 ontology 도구는 보통 한 layer 만 잡음.

## 우리 모델이 푸는 방식

Two-Layer (Code / Domain) + Composition + **`TypeRealization.scope = primary | partial`** 가 핵심.

### Code Layer (5 CodeType — Java 그대로 mirror)

```python
CodeType("com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderOsJpo",
         kind=CLASS, role=INFRA)            # JPA entity, infra
CodeType(".SDOrderOmJpo",        kind=CLASS, role=INFRA)
CodeType(".SDOrderQdJpo",        kind=CLASS, role=INFRA)
CodeType(".SDOrderChemicalJpo",  kind=CLASS, role=INFRA)
CodeType(".domain.entity.SDOrderEntity",
         kind=CLASS, role=DOMAIN)           # 통합 도메인 entity
CodeType(".domain.logic.SDOrderLogic",
         kind=CLASS, role=DOMAIN)           # reflection mapper
```

### Domain Layer (5 BusinessTerm — 도메인 의미 그대로)

```python
BusinessTerm("term.scm.order", label="주문",
             kind=COMPOSITE, is_root_entity=True)

BusinessTerm("term.scm.order_spec", label="주문스펙",
             kind=COMPOSITE, struct_like_hint=True)
BusinessTerm("term.scm.order_meta", label="주문메타",
             kind=COMPOSITE, struct_like_hint=True)
BusinessTerm("term.scm.order_quality", label="품질데이터",
             kind=COMPOSITE, struct_like_hint=True)
BusinessTerm("term.scm.chemical", label="화학성분",
             kind=COMPOSITE, struct_like_hint=True)

# atomic leaves
BusinessTerm("term.scm.c_min", label="C 함량 하한",
             kind=ATOMIC, value_type=FLOAT, unit="%", range=[0.0, 1.0])
# ... 24개 chemistry atomic
# ... 8 due 날짜, polymerized 필드들
```

### Composition (도메인 분리 표현)

```python
# 주문 = 주문스펙 + 주문메타 + 품질 + 화학성분 (1:1 모두)
Composition(parent="term.scm.order", child="term.scm.order_spec",     role="spec")
Composition(parent="term.scm.order", child="term.scm.order_meta",     role="meta")
Composition(parent="term.scm.order", child="term.scm.order_quality",  role="quality")
Composition(parent="term.scm.order", child="term.scm.chemical",       role="chemical")

# 화학성분 = C/Si/Mn/... × min/max/aim
Composition(parent="term.scm.chemical", child="term.scm.c_min", role="C.min")
Composition(parent="term.scm.chemical", child="term.scm.c_max", role="C.max")
Composition(parent="term.scm.chemical", child="term.scm.c_aim", role="C.aim")
# ... 24개
```

### Mapping Layer (★ scope = primary | partial 의 power)

여기가 핵심:

```python
# JPO 4개는 각자 sub-term 의 primary 매핑
TypeRealization(code="SDOrderOsJpo",       term="term.scm.order_spec",    scope=PRIMARY)
TypeRealization(code="SDOrderOmJpo",       term="term.scm.order_meta",    scope=PRIMARY)
TypeRealization(code="SDOrderQdJpo",       term="term.scm.order_quality", scope=PRIMARY)
TypeRealization(code="SDOrderChemicalJpo", term="term.scm.chemical",      scope=PRIMARY)

# SDOrderEntity 는 주문 의 primary
TypeRealization(code="SDOrderEntity", term="term.scm.order", scope=PRIMARY)

# ★ 그리고 PARTIAL — 같은 SDOrderEntity 가 4 sub-term 에도 partial 매핑
TypeRealization(code="SDOrderEntity", term="term.scm.order_spec",    scope=PARTIAL,
                rationale="평탄화된 OS 필드들 — confirmedPlantCd, smDue 등")
TypeRealization(code="SDOrderEntity", term="term.scm.order_meta",    scope=PARTIAL,
                rationale="평탄화된 OM 필드들 — orderWidth, pkgWgtLow 등")
TypeRealization(code="SDOrderEntity", term="term.scm.order_quality", scope=PARTIAL,
                rationale="평탄화된 QD 필드들")
TypeRealization(code="SDOrderEntity", term="term.scm.chemical",      scope=PARTIAL,
                rationale="평탄화된 24개 chemistry 필드")
```

## 왜 이렇게 — 3 layer 의 reality 모두 보존

| 질문 | 답 |
|---|---|
| "SDOrderEntity 의 cMin 필드는 어느 도메인 개념?" | 화학성분의 C.min (PARTIAL TypeRealization 이 단서) |
| "SD_ORDER_QD 테이블이 변경되면 영향?" | TypeRealization PRIMARY (term.order_quality) → SDOrderQdJpo 변경. 영향 받는 모든 Action 자동 추적. |
| "주문 도메인 전체 구조 보고 싶다" | term.order 의 effective_parts → 4 sub-term + chemical 의 24 atomic 까지 자동 traversal |
| "Java 코드 수정 시 어느 도메인 영향?" | code → primary/partial TypeRealization 따라 도메인 측 list |
| "기준서 매뉴얼이 '화학성분' 이라 부름 — 코드 어디?" | term.chemical → primary realization (Jpo) + partial (Entity) 둘 다 추출 |

## Anchor binding 의 power — fragment-level

`SdOrderValidator.validate(SDOrderEntity)` 의 anchor:

```java
// SdOrderValidator.java
if (entity.getStockCode() == 1) return DG001;          // ← anchor: field_access
if (entity.getOrderWidth().compareTo(BigDecimal.ZERO) <= 0)  // ← anchor: field_access + literal:0
    return DG002;
if (entity.getPkgWgtHigh().compareTo(entity.getPkgWgtLow()) < 0)  // ← branch
    return DG003;
```

각 anchor 는 **fragment-level** 로 BusinessTerm 슬롯에 binding (Q4'=A 정합):

```python
AnchorBinding(
    locator="field_access:entity.stockCode",
    code_method_fqn="com.example...SdOrderValidator.validate",
    target_action_fqn="action.scm.주문_정합성_점검",
    target_slot="params[0].spec.stockCode",  # ★ 평탄화 entity 의 필드를 도메인 분리 path 로
)

AnchorBinding(
    locator="field_access:entity.orderWidth",
    target_slot="params[0].meta.orderWidth",  # ★ 같은 Entity 의 다른 필드는 다른 도메인 sub-term
)

AnchorBinding(
    locator="field_access:entity.cMin",
    target_slot="params[0].chemical.C.min",
)
```

**시뮬 시 진가**: PythonGenerator 가 sandbox dataclass 를 만들 때 — 도메인 측 분리 트리 (주문→spec/meta/quality/chemical) 로 짜고, getter 만 entity 평탄화 필드에 매핑. 코드 측 평탄화 vs 도메인 측 분리 가 동시 보존.

## Drama DNA — 다른 자주 나오는 패턴

### 품종 chaos (4 컬럼이 같은 BusinessTerm)

```python
BusinessTerm("term.scm.product_type", label="품종",
             aliases=["productTypeCd", "productNameCd", "prodKindCd", "prodTypeCd"])

# 4 다른 CodeType 의 4 다른 field 가 모두 같은 BusinessTerm 의 atomic
TypeRealization(code="HrSpecJpo",         term="term.scm.product_type", scope=PARTIAL,
                rationale="field PRODUCT_TYPE_CD")
TypeRealization(code="CustomerStdJpo",    term="term.scm.product_type", scope=PARTIAL,
                rationale="field PRODUCT_NAME_CD")
TypeRealization(code="ProductivityStdJpo", term="term.scm.product_type", scope=PARTIAL,
                rationale="field PRODUCT_KIND_CD")
TypeRealization(code="CastSpecJpo",       term="term.scm.product_type", scope=PARTIAL,
                rationale="field PROD_TYPE_CD")
```

→ 사용자가 "품종" 검색 → 4 코드 위치 즉시. 변경 시 4 곳 자동 patch.

### Reflection mapping — SDOrderLogic

```python
# CodeMethod.role = ADAPTER (자동 분류 — 변환만 하고 비즈니스 의미 X)
CodeMethod("SDOrderLogic.fromJpoToEntity", role=ADAPTER)
# Action 매핑 면제 (Q2' 정합 — adapter 는 매핑 큐에 안 올라감)
```

→ reflection 은 anchor 추출 어려운 특수 case. 우리 모델은 ADAPTER role 로 분리해 Action 매핑 큐 노이즈 X.

## 자동 추출 흐름 (P3-3 자동 매핑)

slab-design-real import 시 자동으로:

1. **CodeType ~120 추출** — Java parser 가 122 파일 → CodeType
2. **Class.role 자동 분류**:
   - `*Jpo`, `*Repository` → INFRA
   - `*Entity`, `*Logic`, `*Action`, `*Service`, `*Designer` → DOMAIN
3. **BusinessTerm 후보 자동 생성** (DOMAIN role 클래스 + glossary 매칭):
   - SDOrderEntity → 주문 (root_entity 추정 — designer 가 입력으로 받음)
   - SDOrderOsJpo → 주문스펙 (suffix Os 정규식)
   - SDOrderChemicalJpo → 화학성분
4. **Composition 자동 후보** — Entity 의 4 종 필드 그룹 (OS/OM/QD/CHEMICAL prefix) 발견 → 4 sub-term 분리 제안
5. **TypeRealization PRIMARY** 자동 + PARTIAL 후보 (사용자 큐로)
6. **AnchorBinding** — `entity.field` 패턴 → `params[?].sub.field` slot 후보

사용자는 큐에서 confirm 만 하면 됨.

## 결론

데모 repo 의 4 table → 1 Entity → 1 도메인 시나리오는 우리 모델의 4가지 핵심 기능을 동시 시연:

1. **Two-Layer 분리** — Java 평탄화 ≠ 도메인 분리, 둘 다 보존
2. **Composition** — 도메인 측 4 sub-term 트리
3. **TypeRealization scope=PARTIAL** — 같은 Entity 가 여러 sub-term 에 부분 매핑
4. **Fragment-level AnchorBinding + path syntax** — Entity 의 cMin 필드가 chemical.C.min 슬롯으로

팔란티어가 못 다루는 것:
- DB 정규화 (4 table) ↔ Java 평탄화 (1 Entity) 의 mismatch 시각화 X
- Reflection mapping 의 ADAPTER 분리 X
- Drama DNA (품종 4 alias) 의 unified BusinessTerm + multi PARTIAL realization X
