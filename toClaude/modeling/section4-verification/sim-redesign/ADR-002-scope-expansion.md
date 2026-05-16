# ADR-002: System-agnostic + Recommendation Engine 으로 scope 확장

작성일: 2026-05-13
상태: 확정 (사용자 결정)
대상 세션: section4-verification / sim-redesign
선행: ADR-001 (Python = Java twin)

## 컨텍스트

ADR-001 + Anchored Twin Synthesizer 종합 설계 + DESIGN-WALKTHROUGH 작성 후, 사용자가 두 가지 근본 확장 요구:

> "v2는 단순 예시일 뿐이고, 복잡한 시스템을 다 커버할 수 있어야 하고, 시뮬레이션 에이전트에서 얻고싶은 통찰중에, 새로운 기능을 위해 테이블을 어떻게 변경하는 것이 좋을지도 추천할 수있도록 확장하고 싶은데 그 관점으로 다시 생각해볼래?"

## 두 가지 결정

### D1. System-agnostic

이전 설계의 v2-specific 가정 모두 일반화 대상:
- v2 의 79 distinct `target_slot` → 임의 system 의 slot set 흡수 가능
- v2 의 5 KNOWN_DIVERGENCE (BigDecimal/MathContext/RoundingMode/SdConstants/ValidationResult) → Java common idiom 의 일반화된 set, system 별 extension
- v2 의 4 Maven module (feature/store/facade/boot) → `code_types.role` (domain/infra/framework) 기반 자동 scope 분류
- v2 의 9 JPA repo → 일반화된 data access pattern (Spring Data JPA, MyBatis, JDBC, native SQL, NoSQL ORM 모두 흡수)
- v2 의 6 @Transactional site → tx boundary 의 추상 모델 (system 별 stub)

이전 설계의 mechanism 은 유효:
- 2-layer 합성기 (registry + AST walk) — 추상 mechanism
- Contract 1급 시민 (Protocol + smoke test + version pin) — 추상 mechanism
- Gap surface (ontology row 의 결정론적 함수) — system 무관
- Trace diff (per-action semantic) — system 무관

### D2. Recommendation Engine 추가 (1급 use case)

이전 use case 는 모두 **verification** 영역:
- UC1: 풀 시연 (twin = Java 와 byte-identical)
- UC2: 영향 분석 (input 변경의 trace diff)
- UC3: R5 (Java 수정 전후 trace diff)

신규 use case 는 **recommendation** 영역:
- **UC4: 스키마 추천** — "feature X 추가하려면 table 어떻게 바꿔야 해?"
- **UC5: 코드 추천 (잠재)** — "이 변경 위해 어떤 action / business rule 추가?"
- **UC6: 온톨로지 진화 (잠재)** — "이 feature 가 ontology 의 어디에 영향?"

Recommendation 은 **LLM-based reasoning**. Deterministic 합성기와 다른 mechanism. 둘은 같은 ontology + Java AST 자산을 공유하지만 engine 분리.

## 확장된 architecture

```
Simulation Agent
├── Verification Engine (deterministic, ADR-001/이전 설계)
│   ├── Anchored Twin Synthesizer
│   │   ├── Per-system Registry              ← 79 slot 의 일반화
│   │   ├── Per-system Contract Layer        ← Protocol + facade
│   │   └── Per-system Twin Scope Boundary   ← code_types.role 기반
│   ├── Twin Runner
│   ├── Oracle Differ
│   └── Trace Diff Analyzer                  ← UC2/UC3 의 mechanism
└── Recommendation Engine (LLM-based, 신규)
    ├── Schema Recommender (UC4)
    │   ├── Feature spec parser (natural language → semantic units)
    │   ├── Schema-aware ontology query
    │   ├── Migration diff proposer
    │   └── Twin regression validator        ← Verification Engine 호출
    ├── Code Recommender (UC5 — 잠재)
    ├── Ontology Evolver (UC6 — 잠재)
    └── Shared: LLM reasoning context (ontology + code AST + ER model)
```

핵심 통찰: **Verification Engine 은 Recommendation Engine 의 oracle**.
- Recommendation 이 "schema X 바꾸면 어떻게 돼?" 추론할 때
- Verification 이 "현재 twin 으로 simulate 해보자" 답변

## 새로 필요한 것

### 1. Schema Layer in ontology (신규)
현 ontology 4-layer (Code/Domain/Mapping/Simulation) 에 5번째 layer 추가:
- **Schema Layer** — tables, columns, FK, indexes, constraints
- **Schema↔Code mapping** — JPO (Java persistence object) entity ↔ table, field ↔ column

v2 의 9 JPA repo + JPO 가 자연스럽게 schema layer 의 1차 소스.

### 2. Recommendation Engine 의 LLM context
- Read: ontology 전체 + Java AST + 변경 이력 (git)
- Reason: feature spec → existing artifact 와 gap 식별 → 변경 proposal
- Validate: Verification Engine 호출 → "이 변경 후 twin 이 어떻게 동작?"
- Output: structured proposal (schema diff SQL + code stub + ontology additions)

### 3. System-pluggable boundary
- 새 system 추가 시 필요한 설정:
  - `roles.json` — code_types.role 자동 분류 규칙 (system 별)
  - `contracts/<system>/` — per-system Protocol definitions
  - `registry/<system>/` — per-system slot templates
  - `stubs/<system>/` — per-system framework adapter (Spring → mock, JPA → in-memory, etc.)

## 영향받는 후속 결정 (이전 grill 트리 reframe)

| 이전 grill | Reframe 후 |
|---|---|
| G1: Twin scope (v2 4-module) | G1': **자동 scope (code_types.role 기반)** + 사용자 override 가능. v2 는 default rule 의 한 instance |
| G2: JPA 9 repo 처리 | G2': **일반화된 data access stub** — JPA / MyBatis / JDBC / NoSQL 의 stub 패턴 모두 흡수 |
| G3: Spring DI | G3': **DI framework abstract** — Spring / Guice / 다른 DI 모두 stub pattern |
| G4: @Transactional | G4': **TX boundary abstract** — system 별 stub |
| G5: Contract Protocol schema | G5': **per-system contract 확장** — base contract + system extensions |
| G6: R3 tolerance | (유지) |
| G7: Registry 52 entry | G7': **system 별 registry 작성** — 한 system 의 entry 작성 + reuse |
| G8: Section 2 quality gate | G8': **system-agnostic quality gate** — anchor coverage / role coverage 등 universal metric |
| G9: Impact analysis surface | (유지) |
| G10: AST parser | (유지) |
| (신규) G11: Schema Layer ontology 모델 | 신규 |
| (신규) G12: Recommendation Engine LLM 인터페이스 | 신규 |
| (신규) G13: Verification ↔ Recommendation 통신 | 신규 |

## 미해결 — 다음 단계로 위임

- **G11-G13 신규 grill 항목** 추가 grilling 필요
- **G1-G10 reframe 후 재검토** — 일반화 후 같은 답이 나오는지 확인
- **두 engine 의 통합 spec 작성** — Verification + Recommendation 이 동일 ontology / artifact 공유하는 방식
- **새 4-agent exploration?** — 확장 scope 에 대해 system-agnostic / schema rec / two-engine integration / skeptic 재탐색 가능

## 참조

- ADR-001 (Python = Java twin) — 유효, recommendation engine 의 verification oracle 로 활용
- DESIGN-SYNTHESIS.html — 유효, mechanism level. v2-specific 부분은 generalize
- DESIGN-WALKTHROUGH.html — 유효, UC1-UC3. UC4 추가 필요
- 메모리 `project_decisions_v4_action.md` — 4-layer ontology. 5번째 Schema Layer 추가 필요
- 메모리 `feedback_simulation_design.md` — Code = ground truth 유지. 단 ground truth 외 reasoning 영역도 가능 (recommendation)
