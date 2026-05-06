# Foundry Ontology vs onTong Schema — Side-by-Side

작성일: 2026-05-02
단계: Stage 2 (Stage 1 sweep + 2nd-pass web research 종합)
범위: **Schema-level 비교만**. UX 화면 비교는 Stage 3, 결정은 Stage 4.

태그 규칙
- `[확인]` — Foundry 공식 docs 직접 인용으로 검증
- `[추정]` — docs 발췌 + 추론, 확신 70~90%
- `[알 수 없음]` — 공개 docs 에서 못 찾음 (사유 명시)

---

## 0. 요약 (한눈에 보기)

**숫자 (rough count)**
- 양쪽이 거의 같은 facet : **약 14개** (primary key, base types, IS_A 의 abstract/interface, multi-implementation, action parameter visibility, action operation kind, function edit declaration, branching/PR, OAuth scope, semantic versioning idea, conflict 의 timestamp 전략, 등)
- 다르지만 양쪽 다 존재 : **약 11개** (link cardinality 표현, derived property vs Composition, MDO conflict 정책, schema migration 도구, agent tool 카탈로그, marking, mandatory control, value type wrapper, OSDK code-gen, lifecycle 표현, 파라미터 자동 생성)
- **우리만 있음** : **약 9개** — `VerificationLevel` 6단계, `DispatchSource` 9-enum (Java 콜사이트 다형성), `AnchorBinding` (fragment-level path), `MethodRole` 자동분류, `CodeTypeRole`, `ActionKind=workflow + sub_actions`, `TermKind` 의 atomic vs composite + 4 facet 조합, `BusinessRule` 1급 노드, `TypeRealization.scope=PARTIAL` (한 클래스가 여러 sub-term 부분 매핑)
- **그들만 있음** : **약 13개** — `Shared Property Type` (cross-type reuse), `Derived Property` (런타임 link aggregate), `Marking` (row-level security), `Cipher` 타입, `Time Series` 타입, `Multi-datasource Object Type` (column-wise join + property multiplicity 룰), `Submission Criteria` 별도 facet, Action `Side Effects` (notification/webhook), Action 의 hard scale limit, Function semantic versioning + immutable publish, Branching/Proposal 의 PR-like UI, Schema migration 8 종 predefined option, Agent tool calling 의 native parallel mode

**3 줄 요약**
- **차용해야 할 것**: Shared Property Type (도메인 atomic 재사용), Function semantic versioning (Action 진화 정책), Schema migration 의 predefined option set (코드 변경 → ontology 자동 마이그레이션 후보)
- **우리가 더 발전된 것**: 메서드 다형성 (`Realization.dispatch_source` 9-enum), fragment-level Anchor Binding, VerificationLevel 6단계 — *이 셋은 Foundry 가 코드 layer 자체가 없으므로 비교 불가능 영역*
- **양쪽 다 비어있는 것**: LLM tool description 의 자동 vs 수동 생성 정책 (양쪽 다 명문화 부족), Action lifecycle 의 draft/published 명시적 분리 (Foundry 도 docs 에 없음)

---

## 1. Object Type vs CodeType + BusinessTerm

| facet | Foundry Object Type | onTong (어디 매핑) | 같음/다름/없음 | 비고 |
|---|---|---|---|---|
| primary identifier | required, single column property; String / Integer / Short 만 | `CodeType.fqn` (Java FQN) + `BusinessTerm.fqn` (term.<domain>.<name>) | **다름** | 그들은 instance-level PK, 우리는 type-level FQN. instance PK 는 우리는 없음 (우리는 schema 만, 데이터 없음) |
| display name | `Display name` (단수) + `Plural display name` 둘 다 필수 | `BusinessTerm.label` (단수만) | **다름** | 우리 plural 없음. 한국어 plural 은 morphology 가 약해 가치 낮음 [추정] |
| API name | PascalCase, 1-100 chars, alphanumeric, **9 reserved** | 우리는 reserved name 정책 없음 | **없음** (우리) | onTong 에 reserved 정책 추가 검토 |
| description | `Description` (Object Explorer 노출) | `BusinessTerm.description` + `CodeType` 은 description 없음 | 같음 (term) / 없음 (code) | CodeType 에 description 필드 추가 검토 |
| icon / color | 선택 facet | 없음 | **없음** | UI 차원, 비핵심 |
| groups (categorical) | 선택 facet, Object Explorer sidebar 그룹화 | `BusinessTerm.domain` (string) | 같음 (얕게) | 그들 multi-group, 우리 single domain string |
| aliases (검색 동의어) | 선택 facet, 검색 hit | `BusinessTerm.aliases: list[str]` | **같음** | 거의 동일 의도. 우리 demo 의 "품종" 4 alias 시나리오 정합 |
| backing datasource | 필수 1 개; multi-source 는 MDO 별도 facet | `TypeRealization` (n:m 다대다) | **다름 (강함)** | 우리는 한 BusinessTerm ↔ N CodeType 자유로움. 그들은 1 ObjectType ↔ MDO (≤70 datasource) 인데 property multiplicity 금지 |
| status (active/legacy/planned-deprecation) | metadata facet [확인, S03] | 없음 | **없음** | 차용 후보 — Action.kind 옆에 lifecycle status 추가 |
| owner / steward | [알 수 없음 — Foundry docs 미언급] | 없음 | 양쪽 비어있음 | 거버넌스 추가 시 양쪽 결함 |
| reserved API name 정책 | 9개 (`ontology`, `object`, `property`, `link`, `relation`, `rid`, `primaryKey`, `typeId`, `ontologyObject`) | 없음 | **없음** | 차용 검토 — 우리 path syntax 충돌 방지 |
| immutability of property ID | "changing property IDs breaks those applications" [확인, S02] | `CodeType.fqn`, `BusinessTerm.fqn` 은 frozen Pydantic | 같음 | 양쪽 다 immutable 처럼 다룸 |
| **abstract/interface** | Interface object (별도 entity) | `CodeType.kind=ABSTRACT_CLASS / INTERFACE` + `BusinessTerm.is_abstract / is_interface` | 다름 — 표현 위치 | 우리는 facet 으로, 그들은 별도 entity (Interface) |
| **multi-implementation** | "implements multiple capability interfaces" [확인, extend-interface] | `Inheritance(kind=IMPLEMENTS)` 다중 가능 | **같음** | 동등 |
| **interface 끼리 inheritance** | "An interface can extend any number of other interfaces" [확인] | `extends_interfaces: list[str]` 또는 `Inheritance(extends)` for term | **같음** | 우리도 가능 (CodeType.extends_interfaces, term Inheritance EXTENDS chain) |
| 분류/role | 명시적 role 없음 (group 만) | `CodeTypeRole` (DOMAIN/FRAMEWORK/INFRA/UNKNOWN) | **우리만** | code-layer 자동 분류 — Foundry 는 코드 layer 없음 |
| code <-> 의미 분리 (Two-Layer) | 한 ObjectType 안에 합쳐짐 | CodeType ⊥ BusinessTerm (TypeRealization 으로 연결) | **우리만** | 우리 demo 의 SDOrderEntity ↔ 주문 PARTIAL 시나리오 |
| value-type 메타 (unit/range) | "Value types are semantic wrappers... metadata and constraints" [확인, S03] | `BusinessTerm` 의 `unit`, `range`, `enum_values` | **같음 (개념)** | 그들 Value Type = 별도 reusable wrapper. 우리는 term 자체에 inline. **차용 후보**: Foundry 식 reusable Value Type (atomic term 모듈화) |

(소계: 18 행, 깊이 충분)

---

## 2. Action Type vs Action

| facet | Foundry Action Type | onTong Action | 같음/다름/없음 | 비고 |
|---|---|---|---|---|
| 정의 | "set of changes or edits to objects, property values, and links that a user can take at once" [확인, S09] | `Action` 1급 노드, kind ∈ {pure_function, effectful, workflow} | **개념 같음** | 둘 다 1급 동사 |
| **5 facet 구성** | Parameters / Rules / Submission Criteria / Side Effects / Security | params / preconditions / postconditions / effects / realizations | **다름 (구조)** | 그들 Submission Criteria + Side Effects 별도. 우리 pre/postconditions + effects 단일 묶음 |
| 파라미터 자동 생성 | "Parameter is automatically created based on the Rule" [확인, S10] | 자동 생성 X — 사용자가 직접 또는 method signature 추출 | **다름** | 그들 declarative Rule → param 역추론. 우리 Java method signature → param 역추론 (P3-3 자동 매핑) |
| param 표현력 | base + object ref + object set + struct + attachment + list (≤10K primitive / ≤1K obj) | `ActionParam.type` ∈ {primitive, object_ref}; list 미지원 명시 | **우리가 약함** | 차용 후보: list / struct param. Action 이 collection 받는 케이스 다수 |
| param visibility / editability / conditional / default | 4종 모두 [확인, S11] | 없음 (UI 단까지 안 내려옴) | **없음 (우리)** | 데모용 폼 자동생성 시 차용 후보 |
| output 표현 | implicit (action 자체가 commit) | `ActionOutput` (type + object_ref_term) 명시 | **우리가 더** | 우리는 pure_function 케이스 때문에 output 분리 |
| validation | `Submission Criteria` 별도 facet [확인, S12]; conditions + operators | `preconditions: list[BusinessRule.fqn]` (1급 노드 참조) | **같음 (의도)** / 다름 (구조) | 우리 BusinessRule 1급 노드라 재사용 강함. 그들 inline 조건이라 Action 마다 중복 가능 |
| side effect | notification / webhook 정형 facet | `ActionEffect(op, target_term, target_attr)` | **다름 (의미)** | 그들 = 외부 통지. 우리 = ontology mutation 의미 (CREATE/MUTATE/DELETE/READ). 영역이 다름 — 양쪽 다 보강 필요 |
| Rules vs Function-backed | Rules (declarative) 또는 Function-backed (code) [확인, S09] | `Action.kind` + `realizations` (Java method 직매핑) | **같음 (개념)** | 우리는 항상 code-backed (Java method). Foundry 는 두 mode |
| **kind=workflow + sub_actions** | Logic Block 의 sequential chain 으로 비슷하게 (block = sub-action) | `Action.kind=WORKFLOW` + `sub_actions: list[Action.fqn]` | **다름 (위치)** | 그들 Logic 안에 chain. 우리 ontology 안에 workflow 1급 |
| operation type | Create / Modify / Delete object + Link 변경 [확인] | `ActionEffect.op` enum | **같음** | 동등 |
| transaction model | Single transaction 보장 [확인, S09]; ≤50 object types, ≤10K objects | 명시적 트랜잭션 모델 없음 (시뮬 컨텍스트라 commit 없음) | **다름** | 우리는 ontology 가 read-only schema, 트랜잭션 무관 |
| **scale limits (hard)** | 50 obj types / 10K obj / 32KB-3MB edit / ≤500 노티 | 없음 | **없음** | 우리는 시뮬 schema 라 무관. 차용 가치 낮음 |
| **lifecycle / draft-published** | [알 수 없음 — docs overview 에 없음, S09 직접 fetch 도 미언급]. Workshop/Object View 에는 publish 패턴 있음 [확인, versions docs] | `VerificationLevel` 6단계 (UNMAPPED→DRAFT→SIGNATURE_LOCKED→BODY_ANCHORED→SIM_VERIFIED→PR_PROVEN) | **우리만 (명시적)** | Foundry 가 명문화 안 한 영역 — 우리가 우위 |
| **versioning** | Function 은 SemVer + immutable publish [확인]. Action 자체 versioning 은 [알 수 없음] | 없음 (우리도 schema mutation 만) | 양쪽 약함 (Action) | 차용 후보: SemVer for Action |
| polymorphic dispatch (override) | [알 수 없음] — interface 에 action 가능 여부 미문서화 | `Realization(applies_to_code_type_fqn, is_override)` + 9-enum dispatch_source | **우리만** | Java 다형성을 ontology 에 1급으로. 차별화 강점 |
| security / permission | facet 5, role-based [확인] | 없음 | **없음** | 우리 demo 단계라 미고려 |
| param ↔ anchor binding | 없음 (그들은 코드 layer 없음) | `AnchorBinding` (fragment-level path) | **우리만** | 차별화 |

(소계: 18 행)

---

## 3. Link Type vs Inheritance + Composition + TypeRealization + Realization

Foundry 는 **Link Type 단일 추상**으로 inheritance 빼고는 다 표현. 우리는 **4 가지 다른 관계 타입** (Inheritance / Composition / TypeRealization / Realization). 표현력 비교.

| facet | Foundry Link Type | onTong (어떤 관계) | 같음/다름/없음 | 비고 |
|---|---|---|---|---|
| 기본 정의 | "schema definition of a relationship between two object types" [확인, S06] | 4종 (IS_A, HAS_A, code↔term, action↔method) | **다름 (분해 정도)** | 우리는 의미별 분리 |
| **IS_A** | Interface 메커니즘 별도 [확인, S08] | `Inheritance(kind=EXTENDS\|IMPLEMENTS)` | **같음** | 동등 |
| interface ↔ interface | extend any number [확인] | `extends_interfaces`, term `Inheritance` chain | **같음** | 동등 |
| **HAS_A (composition)** | many-1 link / 1-many link / object-backed link 로 표현 (별도 entity 필요) | `Composition(parent, child, role_name, cardinality)` | **다름 (구조)** | 우리 composition 은 directed + role + cardinality 1급. 그들 composition 은 link cardinality 의 패턴화 |
| cardinality | 4종 (1-1, 1-N, N-1, N-N) | 4종 (1:1, 0:1, 1:N, 0:N) | **같음** | 거의 동일. 차이: 그들 N-N 은 join table, 우리 0:N optional 명시 |
| backing 방식 | FK / Join Table / Backing Object | 우리는 schema only, backing 없음 | 무관 | 우리 단계 차이 |
| direction (양방향 명명) | "Display name for each side" [확인, S07] | `Composition.role_name` 단방향만 | **다름** | 차용 후보: reverse_role_name 추가 |
| link 자체 properties | [알 수 없음 — 공식 미언급]. Object-backed link (intermediate object) 패턴으로만 가능 | 없음. Composition 도 properties 없음 | **양쪽 비어있음** | 양쪽 다 결함. 차용/검토 후보 |
| cross-ontology | 불가 [확인, S06] | repo_id 분리 — 같은 ontology 안에서만 연결 | **같음 (정책)** | 우리도 repo_id 경계 |
| **code ↔ semantic** | 같은 ObjectType 에 합쳐짐 (별도 link 없음) | `TypeRealization(code_type, term, scope=PRIMARY\|PARTIAL)` | **우리만** | Two-Layer 핵심. Foundry 는 한 ObjectType 안에 의미·구현 합침 |
| **PARTIAL realization** (한 클래스가 여러 sub-term 부분 매핑) | 없음. MDO column-wise 가 가까운데 property multiplicity 금지 [확인] | `TypeRealization.scope=PARTIAL` 다중 가능 | **우리만 (강함)** | demo 의 SDOrderEntity → 4 sub-term partial 시나리오. Foundry 는 표현 불가 |
| **method ↔ action 다형성** | Action 의 polymorphic 여부 [알 수 없음] | `Realization(code_method_fqn, applies_to_code_type_fqn, is_override, dispatch_source)` | **우리만** | Java override / impl 를 1급으로 |
| dispatch source 추론 | 없음 (코드 layer 자체 부재) | `DispatchSource` 9-enum | **우리만** | D3 7-case + user_confirmed + static_unresolved |

(소계: 13 행)

---

## 4. Function Type vs (우리는 Action.kind=pure_function 으로 통합)

| facet | Foundry Function | onTong | 같음/다름/없음 | 비고 |
|---|---|---|---|---|
| 분리 여부 | Function 은 1급 별도 entity [확인, S14] | 통합. `ActionKind.PURE_FUNCTION` 으로 표현 | **다름 (의도적)** | 우리 Q1' = A 결정 — 단일 Action + kind. 사용자 회의에서 통합 결정 |
| 언어 | TS v1, TS v2, Python | Python (시뮬 generator) | 다름 | 우리는 시뮬 layer 라 Python 만 |
| edit declaration | `@OntologyEditFunction` / `@function(edits=[...])` | `effects` 필드 (정형 ActionEffect) | **다름 (선언 위치)** | 그들 코드 decorator. 우리 ontology metadata |
| pending edit visibility | "propagated... after your function has finished executing" [확인, S15] | 우리 시뮬 sandbox — 매번 fresh state | **다름 (모델)** | 우리 sim 은 생성된 Python code 라 함수 내 state 보임 |
| 호출 컨텍스트 | Workshop / Action / Slate / Quiver / Pipeline / AIP Logic | A2 Simulation Agent / RAG agent (planned) | 다름 | 우리 단일 컨텍스트 |
| **versioning** | SemVer X.Y.Z, immutable publish [확인] | 없음 | **없음 (우리)** | 차용 후보 |
| version range pinning | `>=1.2.3 <2.0.0` 지원 [확인] | 없음 | 없음 | 차용 검토 |
| 자동 호환성 검사 | "Adding a required input" / "Changing output type from integer to string" 자동 경고 [확인] | 없음 (수동 confirm 만) | 없음 | 차용 강력 후보 — 시뮬 결과 호환성 자동 체크 |

**이 영역의 결론**: Foundry 가 Function 을 별도 entity 로 분리한 이유는 *"같은 코드를 여러 Action 에서 재사용"* + *"데이터 변환·조회 logic 의 first-class 위치 부여"*. 우리는 Java method 자체가 first-class 라 Function 분리가 필요 없으나, **Function 의 versioning + 호환성 검사 메커니즘** 은 우리 Action 진화에 차용 가치 있음.

---

## 5. Interface (Foundry) vs (우리는?)

**Stage 1 의문점 1번 답** — 부분 해소.

**Foundry Interface 가 declare 가능한 것** [확인, create-interface + extend-interface]:
- ✅ **Properties** — local property 또는 shared property; required / optional 구분
- ✅ **Link constraints** — 다른 interface 또는 object type 으로의 link
- ✅ **Multi-implementation** — 한 object type 이 여러 interface 구현 가능
- ✅ **Interface chaining** — "An interface can extend any number of other interfaces"
- ⚠️ **Actions** — docs 에서 명시적 언급 없음 [알 수 없음 — interface 가 action contract 를 declare 할 수 있는지]

> "For required properties, any object type that implements the interface must provide a mapping from a local property to the interface property." [확인]

> "Extending an interface allows you to compose interfaces together, creating a new, more specific interface." [확인]

**우리(onTong) 의 대응** — 이미 다 있음:
- ✅ Properties → `BusinessTerm.is_interface=True` 인 composite term + `Composition` 으로 part 명시
- ✅ Link constraints → term 간 `Composition` 또는 `Inheritance` 로 표현
- ✅ Multi-implementation → `Inheritance(kind=IMPLEMENTS)` 다중 가능
- ✅ Interface chaining → `Inheritance(EXTENDS)` chain (term ↔ term)
- ✅ Actions → `Action.declared_on_term=<interface term>` + `Realization` polymorphic dispatch (우리는 명시적, Foundry 보다 강할 수 있음 [추정])

**핵심 차이**:
- Foundry Interface = **Object Type 의 abstract subset (별도 entity)**
- onTong = `BusinessTerm.is_interface` **facet** (kind 별도 안 만들고 boolean flag)
- *어느 쪽이 나은가*: 이 결정은 Stage 4 회의 안건. **별도 entity 안 만든 우리 모델이 더 단순**하지만, Foundry 처럼 분리하면 "interface 만 검색" 같은 UX 가 자연스러워짐.

**[알 수 없음] 영역**:
- Foundry interface 가 action contract (메서드 시그니처 같은) 를 declare 할 수 있는지. docs 에서 명시 발견 못 함 — interface 의 main 단서는 property + link 만.
- Stage 3 UX 단계에서 Foundry 의 interface UI 직접 보면 답 나올 가능성.

---

## 6. AIP Logic / Agent (Foundry) vs (우리 향후 A2 Simulation Agent)

**Stage 1 의문점 2번 답** — **부분 해소** (가장 미진한 영역).

### 6.1 LLM tool description 메커니즘 — 핵심 의문

> "Instructions, tool descriptions, and variable descriptions are compiled into the raw system prompt for the LLM." [확인, agent-studio core-concepts]

> "Tool descriptions should provide the LLM with concrete steps on how and when to use that specific piece of context." [확인]

**확인된 것**:
- Tool description 이 system prompt 로 compile 됨 (concat 방식 [추정])
- Native tool calling mode 는 모델의 native function-calling 사용 — 즉, 모델 SDK 의 JSON schema 형식에 맞춰 tool spec 변환 필요 [추정]

**[알 수 없음 — 사유: 직접 fetch 한 tools page / core-concepts page 모두 mechanics 미공개]**:
- Tool description 이 Action / Function / Object Type 의 `description` 필드에서 **자동 pull** 되는가, 아니면 agent 빌더가 **수동 작성** 하는가?
- Action parameter 의 visibility/editability/conditional 설정이 LLM tool param schema 로 자동 변환되는가?
- 두 가능성:
  - (A) **자동**: Action.description + params → JSON schema 자동 생성 → 일관성 확보 비용 X
  - (B) **수동**: agent 빌더가 tool 별 description 따로 작성 → 자유도 ↑, 일관성 비용 ↑
- Stage 3 에서 실제 Agent Studio UI 스크린샷 보면 답 명확.

**우리(onTong) 의 대응**:
- 우리 RAG agent 의 wiki_search / wiki_write 등 tool 은 **수동 description** (현재 코드 기준). 
- Action 1급 노드의 `description` + `params` + `output` 은 **이미 LLM tool spec 으로 자동 변환 가능한 구조** (Pydantic → JSON Schema 자동).
- → **차용 후보 (강력)**: Action.description + params → A2 Simulation Agent 의 tool spec **자동 생성** 파이프라인. 우리 schema 가 Foundry 보다 정형화돼 있어 자동 생성이 더 쉬울 수 있음.

### 6.2 Tool 카탈로그

| Foundry Agent Tool | onTong 대응 (현재/계획) | 같음/다름 |
|---|---|---|
| Action | `Action` invoke (planned A2) | 같음 |
| Object Query | wiki_search / metadata_index search | 같음 (의도) |
| Function | (우리는 Action.pure_function 통합) | 같음 (개념) |
| Update application variable | 없음 (UI state 별도) | 없음 |
| Command (cross-app trigger) | 없음 | 없음 |
| Request clarification | (planned, RAG agent 가 question 던지는 패턴) | 같음 (의도) |
| ~~Ontology semantic search (deprecated)~~ | wiki_search 가 임베딩 + BM25 hybrid | **우리만 (현재)** |

### 6.3 Tool calling mode

| 모드 | Foundry | onTong |
|---|---|---|
| Prompted | prompt 안에 instruction, single tool at a time | 우리 RAG agent 도 prompted 패턴 |
| Native parallel | 모델 native function-calling, 병렬 멀티 [확인] | 미구현 [확인 — react_agent.py 는 ReAct loop sequential] |

**차용 후보**: Native parallel mode (Anthropic Claude tool_use 가 이미 지원 — 미활용).

### 6.4 보안 / acting user

> "LLMs do not have direct access to tools; LLMs can only ask to use tools, and these tool calls are then executed by AIP Logic within the invoking user's permissions." [확인, S17]

- 우리 현재 RAG agent 도 동일 모델 (사용자 세션 권한으로 tool 실행). 차이 없음.

---

## 7. Lifecycle / Versioning

**Stage 1 의문점 3번 답** — 부분 해소 (Action 자체 versioning 은 여전히 [알 수 없음]).

### 7.1 Foundry 의 lifecycle 표현

| Resource | lifecycle 메커니즘 |
|---|---|
| **Object Type** | Status field (active / Legacy / Planned deprecation) [확인, S03] |
| **Action Type** | [알 수 없음 — overview 직접 fetch 도 명시 없음]. Workshop 패턴 (auto-publish 옵션) 차용 추정 [추정] |
| **Function** | SemVer X.Y.Z + pre-release (1.2.3-rc1) + immutable publish + version range pin [확인] |
| **Workshop module** | Versions dialog, auto-publish 옵션 [확인] |
| **Object View** | "Save and publish" 버튼, 자동 publish 옵션 [확인] |
| **Branching** | 5-stage (Create → Edit → Propose → Review → Merge) [확인, S25] |

> "Versions for function releases are chosen by their publishers and are immutable after creation." [확인]

> "Adding a required input to a function's signature" or "Changing the output type of a function's signature from an integer to a string" are flagged as incompatible. [확인]

### 7.2 우리(onTong) 의 VerificationLevel — 비교

```
UNMAPPED → DRAFT → SIGNATURE_LOCKED → BODY_ANCHORED → SIM_VERIFIED → PR_PROVEN
```

**우리 vs Foundry**:
- Foundry SemVer = **release axis** (publish 됐고 캘러가 어느 버전 호출하느냐)
- onTong VerificationLevel = **신뢰도 axis** (얼마나 검증됐느냐 — sim 통과? PR 까지?)
- → **두 axis 는 직교**. 양쪽 다 가져도 충돌 없음.

**차용 후보**:
1. **Action 에 SemVer**: `Action.version: str = "1.0.0"` 추가 + 호환성 자동 검사 (param 추가/삭제, output type 변경)
2. **Status field**: `Action.status` ∈ {experimental, active, legacy, deprecated} — Object Explorer 식 검색 필터
3. **Pre-release 표기**: `1.0.0-draft1` 등으로 사용자 confirm 전 상태 표시

### 7.3 Branching / Proposal — 우리 v3 결정과 거의 동일

- Foundry: 5-stage + Proposal = PR-like
- onTong: Q-D 결정 = "draft PR 까지 만들어진 적 = `PR_PROVEN`" — 비슷한 흐름이나 우리는 Foundry 처럼 plat form 안 PR 이 아니라 **외부 git PR**.
- **차용 후보**: Foundry 처럼 *ontology 안에서 propose* + *reviewer 한 명에 모든 resource 묶음 적용* 패턴. 우리는 현재 아카이브에 없음.

---

## 8. Schema Evolution / Migration

**Stage 1 의문점 4번 답** — **잘 해소됨**.

### 8.1 Foundry 의 schema migration 메커니즘 [확인]

OSv2 의 8 종 predefined migration:

1. **Drop all property edits** — 한 property 의 user edit 전부 제거
2. **Drop all struct field edits** — struct field 의 edit 전부 제거
3. **Drop all edits** — 모든 object 를 datasource 값으로 reset
4. **Move edits** — replacement property/datasource 로 이동
5. **Move struct field edits** — struct field 간 edit 이동
6. **Cast property to new type** — type 변경 (int→string 등)
7. **Cast struct field to new type** — struct field type 변경
8. **Revert migration** — 이전 migration 되돌리기

**Breaking changes** [확인]:
- Backing datasource 변경
- Primary key 변경
- Property data type 변경
- User edit 가진 property 삭제
- Struct field type 변경

> "OSv2 provides a schema migration framework with a list of predefined migrations that can be applied to existing user edits after a breaking schema change." [확인]

**핵심 차이 (OSv1 vs OSv2)**:
> "In Object Storage V1 (Phonograph)... user edits cannot be migrated in OSv1; instead, breaking changes will result in the loss of existing user edits unless time-consuming and complex manual intervention can be performed." [확인]

### 8.2 우리(onTong) 의 대응

**현재 상태**: 거의 없음.
- `CodeType.fqn` rename → 모든 referencing TypeRealization / Realization / AnchorBinding 깨짐. 자동 마이그레이션 없음.
- `BusinessTerm.fqn` rename 도 마찬가지.
- Java 코드의 method signature 변경 → Realization 의 anchor binding 깨짐.

**차용 후보 (강함)**:
- 우리는 **Java 코드 변경 → ontology 마이그레이션** 흐름이 핵심.
- Foundry 의 8-option set 을 우리 맥락으로 매핑:
  - "Method signature 변경" → drop binding / move binding / cast param type
  - "CodeType FQN rename" (refactoring) → move all bindings
  - "BusinessTerm split" (한 term 을 두 개로) → 사용자 cue + manual partition
- → **Stage 4 회의 안건**: schema migration framework 설계.

### 8.3 Property ID immutability — 양쪽 정책 동일

> "Once saved and referenced in applications, changing property IDs breaks those applications" [확인, S02]

- 우리도 frozen Pydantic + fqn 은 immutable 처럼 다룸.

---

## 9. Multi-source Mapping

**Stage 1 의문점 5번 답** — **잘 해소됨**.

### 9.1 Foundry MDO (Multi-Datasource Object Type) [확인]

**구조**:
- **Column-wise MDO** (지원): "join-like... distinct subsets of properties for an object type can be integrated from different datasources"
- **Row-wise MDO** (미지원): "Foundry only supports column-wise MDOs and does not support row-wise MDOs"
- 최대 70 datasource, OSv2 전용

**핵심 제약**:
> "Property multiplicity is currently not supported. This means that a specific property of an object type must come from one—and only one—of the input datasources." [확인]
- 예외: Primary key 는 모든 datasource 에 존재 필수 (join key)

**Conflict resolution** (user edit vs datasource update) [확인]:
- **Always Apply**: user edit 가 항상 우선
- **Conditional (Timestamp-based)**: user edit timestamp ≥ datasource timestamp 일 때만 적용
- 다른 datasource property 끼리는 conflict 자체 발생 X (multiplicity 금지)

**permissions on missing source**:
> "When users lack permissions on certain input datasources, the properties mapped from those datasources will appear as null when displaying an object to the user." [확인]

### 9.2 우리(onTong) 의 PRIMARY/PARTIAL — 비교

```
TypeRealization(code_type, term, scope=PRIMARY|PARTIAL, confidence, rationale)
```

**우리 demo (slab-design 주문 시나리오)**:
- `SDOrderEntity` ← PRIMARY → `term.scm.order` (전체)
- `SDOrderEntity` ← **PARTIAL** → `term.scm.order_spec` (rationale: 평탄화된 OS 필드들)
- `SDOrderEntity` ← **PARTIAL** → `term.scm.order_meta`
- `SDOrderEntity` ← **PARTIAL** → `term.scm.order_quality`
- `SDOrderEntity` ← **PARTIAL** → `term.scm.chemical`
- 동시에 `SDOrderOsJpo` ← PRIMARY → `term.scm.order_spec` (DB-side primary)

**vs Foundry MDO**:

| facet | Foundry MDO | onTong PARTIAL | 같음/다름 |
|---|---|---|---|
| 한 source 가 여러 target 에 mapped | 금지 (property multiplicity 미지원) | 가능 (PARTIAL 다중) | **우리만** |
| 한 target 이 여러 source 에서 받음 | column-wise MDO 로 가능 (≤70 ds) | 가능 (PARTIAL 다중 from different code_type) | **같음** |
| conflict resolution | Always-Apply / Timestamp 2종 | 우리는 schema only, conflict 없음 | 무관 |
| confidence / rationale | 없음 (binary mapping) | `confidence: float`, `rationale: str` | **우리만** |

**핵심 차별화**: 우리 PARTIAL 은 **"같은 클래스가 여러 의미로 부분 해석된다"** 는 표현. Foundry 는 **"여러 dataset 이 한 object type 의 다른 속성을 채운다"** 는 표현. 의미 영역이 다름 — 우리는 **semantic interpretation (1:N)**, 그들은 **physical sourcing (N:1)**.

→ slab-design 의 SDOrderEntity (1 클래스가 4 sub-term 에 분해 매핑) 시나리오는 **Foundry 의 MDO 로 표현 불가**. 우리 schema 만의 표현력. (단, demo 영역 제한 — 일반 LOB 앱에서 얼마나 자주 등장하는지는 unknown)

---

## 10. Schema 차원의 결정 (Stage 4 inputs)

### 10.1 차용 필수 후보 (강함, Stage 4 결정 전)

1. **Shared Property Type** (Foundry) → onTong **Reusable Atomic Term**
   - 같은 atomic (예: "C 함량") 을 여러 composite term 에서 재사용. 현재 우리는 fqn 으로 reference 가능하나, "shared" 메타 명시 + UI 의 globe icon 같은 시각화 부족.
   - 비용: 낮음 (이미 fqn ref 가능, metadata 추가만)

2. **Function/Action SemVer + 호환성 자동 검사** (Foundry)
   - `Action.version: str = "1.0.0"` + param 추가/output type 변경 시 자동 경고
   - 비용: 중 (validator 작성)

3. **Schema Migration framework — 8 predefined options** (Foundry OSv2)
   - 우리 맥락 = Java code refactoring → ontology 마이그레이션
   - drop binding / move binding / cast type / split term / merge term 등
   - 비용: 높음 (Stage 4 별도 안건)

4. **Action description → LLM tool spec 자동 변환 파이프라인**
   - Pydantic Action → JSON Schema → Anthropic tool spec
   - 비용: 낮음 (Pydantic 의 model_json_schema() 활용)

5. **Status field on Object Type** → onTong `Action.status` / `BusinessTerm.status`
   - {experimental, active, legacy, deprecated}
   - 비용: 낮음

### 10.2 차용 안 함 (의도적 차이)

1. **Function 별도 entity 화** — 우리 Q1' = A 결정. 단일 Action + kind 로 통합. 변경 X.
2. **Single transaction model** — 우리 시뮬 schema 라 트랜잭션 무관.
3. **Side Effects = notification/webhook** — 우리 effects 는 ontology mutation 의미. 영역 다름.
4. **OSDK code generation** — 우리는 ontology = 시뮬 input, 별도 client SDK 불필요.
5. **Plural display name** — 한국어 plural morphology 약함.

### 10.3 검토 필요 (Stage 4 회의 안건)

1. **Interface 를 별도 entity 로 분리할까, 현재 facet 으로 둘까** — Foundry 는 분리 (검색/필터 UX 자연), 우리는 facet (단순). 결정 보류.
2. **Composition 의 reverse_role_name 추가 여부** — Foundry 양방향 명명 차용?
3. **Link 자체 properties 표현** — Composition 에 attributes 추가 (예: assignment_date)? 양쪽 다 약한 영역.
4. **Foundry 식 ontology-internal Proposal** vs 외부 git PR — 결정 v3 와 충돌 가능.
5. **Reserved API name 정책** — 우리 path syntax (params[0].spec.field) 충돌 방지용.
6. **Value Type 의 reusable wrapper** — atomic term 을 wrapper 로 모듈화할지, 현재처럼 inline 둘지.

---

## 11. 신뢰도 + 한계

### 11.1 섹션별 신뢰도

| 섹션 | docs 기반 비율 | 추정/의견 비율 | 비고 |
|---|---|---|---|
| §1 Object Type | 90% docs | 10% 추정 | Foundry side 매우 단단 |
| §2 Action Type | 80% docs | 20% 추정 | Action lifecycle 만 [알 수 없음] |
| §3 Link Type | 75% docs | 25% 추정 | 우리 4종 분해 비교는 우리 schema 기반 |
| §4 Function | 95% docs | 5% 추정 | versioning page 직접 fetch 성공 |
| §5 Interface | 70% docs | 30% 추정 | "interface 가 action declare 가능한가" 미답 |
| §6 AIP Agent tool description | **40% docs / 60% 추정** | — | **가장 약한 섹션** — Foundry 가 mechanics 미공개 |
| §7 Lifecycle | 70% docs | 30% 추정 | Action versioning 만 미답 |
| §8 Schema Migration | 90% docs | 10% 추정 | 8-option 명확 |
| §9 Multi-source | 95% docs | 5% 추정 | MDO + conflict resolution docs 풍부 |

### 11.2 추가 research 가 필요한 것 (Stage 3 / Stage 4)

1. **Agent Studio UI 의 tool 등록 화면** — description 수동 vs 자동 mechanics 답하려면 UI 스크린샷 또는 video 필요. 공식 docs 의 mechanics 페이지가 비어있어 외부 영상/블로그 fallback.
2. **Action Type lifecycle (draft/published)** — Foundry community forum 또는 Workshop versions 페이지의 action-specific 섹션 확인.
3. **Foundry 의 Object Type 1000+ 시나리오** — 우리 5K 클래스 시나리오 비교용. Stage 3 UX 분석 시 graph viz 한계 확인.
4. **Foundry 의 polymorphic action dispatch** — interface 기반 action override 가 가능한지. Stage 3 에서 Logic 의 Apply Action block 분석.

### 11.3 본 비교 의 한계

- **Foundry 의 internal data model 은 black box**. docs 는 user-facing API 만 노출. 실제 OSv2 의 internal entity table 구조는 미공개 (S30 인용: "specialized object databases" 만 명시).
- **우리 schema 는 시뮬 layer 라 instance 데이터 없음**. Foundry 는 production data platform. 비교가 *schema-level 만* 유효 — runtime/scale/perf 비교는 무의미.
- **Use case 차이**: Foundry = 일반 LOB 앱 ontology + agent. onTong = 코드 분석 + 시뮬레이션 ontology. 같은 "ontology" 단어 쓰지만 사용 목적 다름.
- **언어 / 한국어 자료 부재**: docs 영문만. 한국 LOB 시나리오에서의 Foundry 사용 사례 자료 부족.

---

## Appendix: 인용 모음 (영문 보존)

- "The Ontology sits on top of the digital assets integrated into the Palantir platform...and connects them to their real-world counterparts." (S01)
- "A link type is the schema definition of a relationship between two object types." (S06)
- "set of changes or edits to objects, property values, and links that a user can take at once" (S09)
- "LLMs do not have direct access to tools; LLMs can only ask to use tools, and these tool calls are then executed by AIP Logic within the invoking user's permissions." (S17)
- "A proposal is analogous to a Pull Request in a version control system, specifically tailored for Ontology branches." (S26)
- "Versions for function releases are chosen by their publishers and are immutable after creation." (functions-versioning)
- "OSv2 provides a schema migration framework with a list of predefined migrations that can be applied to existing user edits after a breaking schema change." (schema-migrations)
- "Property multiplicity is currently not supported. This means that a specific property of an object type must come from one—and only one—of the input datasources." (multi-datasource-objects)
- "An interface can extend any number of other interfaces." (extend-interface)
- "For required properties, any object type that implements the interface must provide a mapping from a local property to the interface property." (create-interface)
- "Instructions, tool descriptions, and variable descriptions are compiled into the raw system prompt for the LLM." (agent-studio core-concepts)

끝.
