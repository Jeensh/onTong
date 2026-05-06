# P3-1: slab-design-real 데모 repo 깊이 파악

**완료**: 2026-05-02
**목적**: Phase 3 wiring 의 모든 자동 추출 / 자동 매핑 / 데모 시연의 기반 데이터.

## 도메인 — 한국 철강 제조 SCM (slab design)

CLAUDE.md 표현: **"intentional drama DNA" 가득한 legacy victim codebase**.
- 21-step slab design 알고리즘
- 4-module Maven (Java 21 + Spring Boot 3.4)
- 12 JPA tables (실제 DB 없음, dialect compile-time only)
- 122 Java 파일 (target/ 제외)

## 모듈 구조 (clean layered)

```
boot (5)   ──▶  facade (6, REST)   ──▶  feature (49, 알고리즘)  ──▶  store (62, JPO+Entity+Repo)
```

## 자동 추출 예상 — Phase 3 wiring 기준

| Layer | 추출 예상 |
|---|---|
| **CodeType** | ~120 (Java 파일과 거의 1:1, role 자동 분류 — entity/jpo=infra, controller/service=domain) |
| **CodeMethod** | ~600+ (모든 public/protected method) |
| **Action 후보** | **~32** (Method.role=business 추정): SdDesigner (21 step orchestrator), SdDriver, SdOrderValidator (DG001~005 5종), SdProductClassifier, 21 Action 클래스 (SdLengthRangeAction, SdFinalLengthRangeAction, SdSlabSaveAction 등), 5 Controller |
| **BusinessTerm 후보** | **~30** (Entity 12개 + 도메인 glossary 18개): 슬랩, 주문, 강종, 품종, 실수율, 단중, 8공정, EDGING, ... |
| **TypeRealization** | ~12 (Entity ↔ BusinessTerm name match) |
| **Realization** | ~32+ (Action ↔ 구현 메서드, primary/partial) |

## 핵심 디렉토리 (Action 매핑 우선순위)

```
slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/
├── designer/        SdDesigner.java                    [21-step orchestrator, 324 LOC]
├── driver/          SdDriver.java                      [batch flow]
└── process/
    ├── working/
    │   ├── action/  16 Action class (★ 매핑 핵심)
    │   │   - SdConstraintCheckAction
    │   │   - SdFinalLengthRangeAction / SdFinalWidthRangeAction
    │   │   - SdFirstWeightAction / SdInitialSlabWgtAction
    │   │   - SdLengthRangeAction / SdMaxSplitCountAction
    │   │   - SdObjectiveAction / SdOrderExtractor
    │   │   - SdOrderValidator (★ DG001~005, 88 LOC, 풍부한 author 코멘트)
    │   │   - SdProductClassifier
    │   │   - SdSecondWgtHighAction / SdSecondWgtLowAction
    │   │   - SdSlabCountAction / SdSlabSaveAction
    │   │   - SdSlabSizeCalcAction / SdSlabWgtRecalcAction
    │   │   - SdSplitRangeAction / SdTargetLengthAction / SdTargetWidthAction
    │   ├── service/   helper/lookup
    │   └── wrapper/   ValidationResult, SdErrorCode 등
    ├── std/         std service lookups
    └── history/     hist 적재
```

## 핵심 BusinessTerm 후보 (CLAUDE.md glossary 기반)

| Java 식별자 | 한국어 label | TermKind | 비고 |
|---|---|---|---|
| Slab / SDSlabEntity | 슬랩 | composite | output of SM → input HR |
| Order / SDOrderEntity | 주문 | composite, root_entity | customer order |
| OrderOs | 주문스펙 | composite, struct_like | spec table |
| OrderChemical | 화학성분 | composite, struct_like | 1:N |
| OrderQd | 품질데이터 | composite, struct_like | |
| Grade | 강종 | atomic (string) | steel chemistry grade |
| Product | 품종/품명 | atomic, **3 aliases** (PRODUCT_TYPE/NAME/KIND_CD) ★ | |
| ProductivityRate | 실수율 | atomic (float) | cumulative |
| UnitWeight | 단중 | atomic (float, kg) | |
| PackagingWeight | 포장단중 | atomic, struct_like (low/high) | |
| ConfirmedPlantCd | 확정공정코드 | atomic (string, 8-char) | 공정 별 plant char |
| Plant | 공장 | atomic | 8 process plants |
| Process | 공정 | atomic, enum | SM/HR/HRF/CR/ANL1/ANL2/GAL/CRF |
| EdgingRule | EDGING 룰 | composite | wildcard `*` fallback |
| Cmpcd | 회사 | atomic (string) | composite key part 1 |
| OrgCd | 소 | atomic (string) | composite key part 2 |
| ValidationResult | 검증결과 | composite | DG001~005 + DG101~109 |
| SdErrorCode | 에러코드 | atomic, enum | DG001~109 |
| HrSpec / CastSpec / EdgingSpec / EdgingGroup | (각 spec) | composite | 4 spec tables |
| CustomerStd / HrMinWgt / HrMaxWgt / ProductivityStd | (각 룰 master) | composite | 4 rule masters |
| SlabResult / SlabDesignHist | 결과/이력 | composite | result + history |

## 핵심 Action 후보 (자동 매핑 first-cut)

| Java method | Action label | kind | declared_on_term | preconditions |
|---|---|---|---|---|
| `SdDesigner.design()` | 슬랩설계_실행 | workflow | 주문 | DG001~005 모두 |
| `SdOrderValidator.validate(SDOrderEntity)` | 주문_정합성_점검 | pure_function | 주문 | rule.스톡주문, rule.폭길이, rule.포장단중, rule.설계대기량, rule.작업기한 |
| `SdProductClassifier.classify(...)` | 제품_분류 | pure_function | 주문 | |
| `SdLengthRangeAction.execute(...)` | 1차_길이범위_산정 | pure_function | 슬랩 | DG102 (HR_SPEC) |
| `SdFinalLengthRangeAction.execute(...)` | 최종_길이범위_산정 | pure_function | 슬랩 | |
| `SdSlabSaveAction.execute(...)` | 슬랩결과_저장 | effectful | 슬랩, 슬랩결과 | |
| 21 Action 클래스 각 execute | (각 step) | pure_function/effectful | | |
| 5 RestController endpoint | (REST entry) | effectful | | |

## Drama DNA (자동 매핑이 잘 풀어야 할 핵심 도전)

1. **품종/품명 chaos** — 같은 BusinessTerm `품종` 에 4 aliases 자동 매핑 필요:
   - SD_HR_SPEC.PRODUCT_TYPE_CD → productTypeCd
   - SD_CUSTOMER_STD.PRODUCT_NAME_CD → productNameCd
   - SD_PRODUCTIVITY_STD.PRODUCT_KIND_CD → prodKindCd
   - SD_CAST_SPEC.PROD_TYPE_CD → prodTypeCd
2. **공정 chaos** — `공정` 8개 가 단일 8-char column + 8 separate due column 으로 표현
3. **DG001~005 short-circuit** — `SdOrderValidator` 의 5 if return — 우선순위가 코드에 박힘. preconditions[] 의 순서가 의미 가짐.
4. **SDOrderLogic reflection** — JPO ↔ Entity 매핑이 reflection. Anchor 추출 어려움 (특수 case).

## 시연 시나리오 (사용자 demo 용)

| # | 시나리오 | 보일 것 |
|---|---|---|
| **S1** | 신규 사용자 첫 진입 | repo import 분석 → CodeType 트리 + Action 자동 후보 30+ + 매핑 큐 |
| **S2** | "품종" 매핑 | 4 다른 컬럼이 같은 BusinessTerm `품종` 에 매핑 — 온톨로지 매핑 강점 |
| **S3** | DG003 우선순위 변경 영향 | Backward 모드 — 변경 시 어느 Action 영향 받는지 cascade |
| **S4** | SdLengthRangeAction 시뮬 | Detail → Split mode → anchor 매핑 → A2 Simulation Agent 시뮬 |
| **S5** | Top-down 그래프 | L1 SCM 도메인 → L2 slab design 그룹 → L3 21 Action → L4 메서드 → L5 anchor micro |

## P3-2 ~ P3-7 plan

다음 step 들이 위 데이터를 어떻게 활용:

- **P3-2 Import**: `POST /api/ontology/repos/import` — sample-repos/slab-design-real path → java_parser → 122 ParseResult → adapter → ~120 CodeType + ~600 CodeMethod + N CallSite → CodeLayerStore.upsert
- **P3-3 자동 매핑**: Method.role=business (~32) → Action 후보. CodeType.role=domain → BusinessTerm 후보. CamelCase + glossary alias → confirmed=False 상태로 큐에 쌓임
- **P3-4 Frontend Import UI**: top bar 또는 modal — path 입력 + SSE 진행률
- **P3-5 xyflow + dagre**: Graph mode 가 실제 데이터 기반. 122 노드 → community detection 또는 hierarchical layout
- **P3-6 큐 처리**: confirm/reject API + UI
- **P3-7 시연**: scenarios 5종 끝-끝
