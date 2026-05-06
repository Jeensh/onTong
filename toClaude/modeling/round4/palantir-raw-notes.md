# Palantir Foundry Raw Notes — Stage 1

작성일: 2026-05-02
규칙: 영역별 raw 정보 정리. **이 단계에서는 우리(onTong) 와 비교/판단 노트 쓰지 말 것**. 사실 + 인용 + 의문점만.
태그: `[확인]` = 1 차 source 확인됨, `[추정]` = 2 차/검색 발췌 또는 추론, `[알 수 없음]` = 공개 자료에 없음.

---

## 영역 1 — Foundry Ontology 기본 모델

### 1.1 Object Type — facets

**무엇**: Object Type = "the schema definition of a real-world entity or event" 의 ontology 표현.

**필수 facet** [확인, S02]:
- ID (lowercase, dashes 가능, letter 시작)
- Display name (단수)
- Plural display name
- Backing datasource (writeback dataset 또는 transform output)
- API name (PascalCase, 1-100 chars, alphanumeric)
- ≥1 property
  - 그 중 하나는 Primary key
  - 그 중 하나는 Title key (둘이 같은 property 일 수 있음)

**선택 facet** [확인, S02]:
- Icon, color
- Description (Object Explorer 검색 결과에 노출)
- Groups (categorical 라벨)
- Aliases (검색 동의어)

**Reserved API names** [확인, S02]: `ontology`, `object`, `property`, `link`, `relation`, `rid`, `primaryKey`, `typeId`, `ontologyObject`.

**제약** [확인, S02]:
- Backing datasource 는 `MapType`/`StructType` column 가질 수 없음
- Property ID 변경은 referencing app 깨뜨림 — immutable 처럼 다뤄야 함

**의문점**:
- Status field (active / experimental / deprecated) 가 별도 facet 인가, metadata 인가? S03 에서 statuses 페이지 언급은 있으나 lifecycle 미상.
- Owner / Steward 같은 governance metadata 있나? [알 수 없음]
- Datasource 가 여러 개일 수 있나 (multi-source object type)? S29 에서 "multi-datasource object types" 언급 — Stage 2 에서 확인.

---

### 1.2 Object Type — Property kinds

**Base types** [확인, S04]: String, Integer, Boolean, Date, Timestamp, Array, Struct, Media Reference, Time Series, Attachment, Geopoint, Geoshape, Marking, Cipher, Vector, Float, Double, Decimal, Byte, Short, Long.

**Property 종류** [확인, S04]:
- Regular property — "the schema definition of a characteristic of a real-world entity or event"
- Derived property — 런타임 계산
- Edit-only property — 수정 컨텍스트에서만 보임
- Required property — 값 필수
- Shared property — 여러 type 에 reusable
- Title key property — 표시명 (String/Integer/Short/Date/Timestamp/Boolean/Byte/Long/Float/Double/Decimal/Array/Geopoint/Cipher 지원)
- Primary key property — 식별자 (String/Integer/Short 만 지원)
- Mandatory control property — system-enforced

**Derived property 상세** [확인, S05]:
> "Derived properties are properties that are calculated at runtime based on values from linked objects."
- 최대 3 단계 link traversal
- Aggregation 지원: avg, count, list collect 등
- 예: Department.average_employee_salary = avg(linked Employees.salary)

**의문점**:
- Derived property 가 query time 마다 recompute 인지, 캐시되는지? [알 수 없음]
- "Mandatory control property" 의 정확한 의미 — 시스템 metadata? security marking? [알 수 없음 — Stage 2 에서 확인]
- Vector 타입은 어떤 dimension/distance metric 지원? [알 수 없음]
- Function-backed property (function 결과를 property 로) 가능? S05 검색 결과 중 "Quiver derived property from function on objects" 가 있어 가능성 시사 — Stage 2 확인.

---

### 1.3 Link Type — facets & cardinality

**정의** [확인, S06]:
> "A link type is the schema definition of a relationship between two object types. A link refers to a single instance of that relationship between two objects in the same Ontology."

**Cardinality + backing 매트릭스** [확인, S07]:

| Cardinality | Backing |
|---|---|
| One-to-One | Foreign Key |
| One-to-Many | Foreign Key (1쪽이 PK, many쪽이 FK) |
| Many-to-One | Foreign Key 또는 Backing Object |
| Many-to-Many | Join Table (별도 dataset) |

**Many-Many backing 상세** [확인, S06, S07]:
> "In the case of link types where object types are related with a many-to-many cardinality, datasources back the link types themselves."
- Join table 은 양쪽 PK 의 모든 조합을 포함하는 dataset
- 시스템이 "automatically generate a join table" 가능

**Object-backed link** [확인, S07]:
- 두 object 사이에 intermediary object type 둠
- 양쪽 모두 many-to-one link 로 intermediary 와 연결
- → 사실상 우리가 말하는 "association class" 패턴

**Direction** [확인, S06]:
- 화살표로 표시 (Employee → Employer)
- Self-referential link: `Direct Report ↔ Manager` (양방향 명명)
- → 양방향 reference name 을 각각 가짐 (S07 의 "Display name for each side")

**Cross-ontology link** [확인, S06]:
> "Links between object types across different Ontologies is not supported."

**의문점**:
- Link type 자체가 properties 를 가질 수 있나? (관계의 attribute, e.g., assignment_date) [알 수 없음 — 아마 backing object 패턴으로만 가능]
- Link 의 cardinality 변경 (1-many → many-many) 마이그레이션 가능한가? [알 수 없음]

---

### 1.4 Interfaces (inheritance / abstract type)

**무엇** [확인, S08]: Foundry 의 inheritance 메커니즘. Abstract type 정의 → 여러 concrete object type 이 implement.

**예시** [확인, S08]: `Airport implements Facility` — Airport 의 concrete link type 들이 Facility 의 interface link type constraint 를 충족.

**인용** [확인, S08]:
> "When an object implements an interface with an interface link type constraint, concrete link types on the object type are used to fulfill interface link type constraints."

**의문점**:
- Interface 가 property 도 declare 가능한가? (S08 페이지는 link type constraint 만 다룸)
- Interface 끼리 inheritance 가능한가? [알 수 없음]
- Multi-implementation (한 type 이 여러 interface) 가능한가? [추정: 가능, Java 와 유사]
- Action / Function 도 interface 기반으로 polymorphic dispatch 되나? [알 수 없음]

---

### 1.5 Action Type — facets

**정의** [확인, S09]: "a set of changes or edits to objects, property values, and links that a user can take at once." Single transaction.

**5 facet** [확인, S09]:
1. **Parameters** — user input form
2. **Rules** — 어떤 변경을 적용할지 (modify/create/delete)
3. **Submission Criteria** — validation conditions
4. **Side Effects** — notifications, webhooks
5. **Security/Permissions** — role-based

**Action operation type** [확인, S10]:
- Create object
- Modify object
- Delete object
- (Link 변경도 포함됨 — S09 의 "create links" 언급)

**Parameter types** [확인, S11]:
- Base types (string/number/boolean/date 등)
- Object reference (dropdown)
- Object set
- Struct
- Attachment
- List (primitive max 10,000 elements; object ref max 1,000)

**Parameter 설정** [확인, S11]:
- Visibility (visible / hidden)
- Editability
- Default value (e.g., "Current object" 환경변수)
- Conditional 표시
- Multiple choice constraint (allowed values)
- "automatically created based by the Rule" — Rule 정의하면 parameter 자동 생성됨 [확인, S10]

**Submission Criteria** [확인, S12]:
> "Submission criteria (formerly known as validations) are the conditions that determine whether an action can be submitted."
- Conditions + operators
- Attachment, object set parameter 는 criteria 에서 사용 불가

**Rules — 로직 정의 방식** [확인, S10]:
- Rules tab 에서 어떤 property 를 어떻게 수정할지 declarative 정의
- 또는 function-backed action (Function 결과를 적용)

**Lifecycle** [확인, S09]:
- "changes... will be committed to the Ontology when the user takes the action"
- writeback dataset 에 반영
- **draft → published 의 명시적 lifecycle 은 docs overview 에 없음** — Stage 2 에서 확인

**Scale limits** [확인, S13]:
- Object types per submission ≤ 50
- Objects per submission ≤ 10,000
- Edit size ≤ 32KB (OSv1) / 3MB (OSv2)
- Batch calls ≤ 10,000 (or 20 for non-batched function-backed)
- Notification recipients ≤ 500 (50 if function-rendered)

**의문점**:
- Action 의 versioning / 이전 버전 호출 가능? [알 수 없음]
- Rules 와 Function-backed 의 power/complexity trade-off — 언제 어느 쪽? [알 수 없음]
- 하나의 Action 이 여러 object type 에 동시 변경 — 트랜잭션 isolation 모델은? [알 수 없음]
- Side effect 의 ordering 보장? webhook 이 ontology commit 전/후? [알 수 없음]

---

### 1.6 Function Type

**무엇** [확인, S14]:
> "Functions enable code authors to write logic that can be executed quickly in operational contexts, such as dashboards and applications designed to empower decision-making processes."

**언어** [확인, S14]:
- TypeScript v1, TypeScript v2
- Python

**Edit declaration** [확인, S15]:
- TS v1: `@OntologyEditFunction` + `@Edits([Employee])`
- TS v2: `Edits` type + `createEditBatch` from `@osdk/functions`
- Python: `@function(edits=[Employee])` parameter

**Caveat** [확인, S15]:
> "Changes to objects and links are propagated to the object set APIs after your function has finished executing."
→ Function 내에서 edit 후 search 해도 pending 변경은 안 보임. 개발자가 manual 처리 필요.

**호출 컨텍스트** [확인, S14]:
- Workshop (variables, derived columns, charts)
- Action (function-backed action)
- Slate (frontend backend)
- Quiver (custom metrics)
- Pipeline Builder (Python sidecar)
- AIP Logic (Execute function block)

**Pure vs side-effecting** [확인, S14]: 명시적 분류 없음. Edit decorator 유무로 구분.

**의문점**:
- Function 의 timeout / 메모리 limit? [알 수 없음]
- Cold start? [알 수 없음]
- External webhook call (3rd party API) 지원? [추정: 가능, S14 에서 "query external systems via webhooks" 언급]
- Function versioning / publishing — staging vs production? [알 수 없음 — S14 에서 sidebar 에 "Function versioning" 항목 존재하나 미확인]

---

## 영역 2 — Data → Ontology 매핑

### 2.1 Pipeline Builder

**무엇** [확인, S27, S28]:
> "Outputs in Pipeline Builder are the result of transforms... can be datasets, virtual tables, or Ontology components such as object types, object link types, or time series."

**워크플로** [확인, S27]:
1. Dataset import / transform 정의
2. Transform node 선택 → "Add output > New object type"
3. (multi-ontology 환경이면) ontology 선택
4. Property mapping (column → property) — 자동 매칭
5. Build → ontology element 생성

**의의**: Ontology Manager 따로 안 가도 pipeline 안에서 object/link/time series 정의 가능.

### 2.2 Code Repository / Code Workbook

[알 수 없음 — 이 영역 직접 fetch 안 함. Stage 2 에서 docs/foundry/code-repositories 확인 필요]

### 2.3 우리의 TypeRealization PRIMARY/PARTIAL 같은 partial-mapping?

**확인된 것**:
- 자동 column → property 매핑 [확인, S02, S07]
- Property 가 매핑 안 되면 "discarded during this step" 가능 [확인, S02]
- Backing datasource 변경 가능 [확인]

**없는 듯한 것** [추정]:
- "이 property 는 100% mapped, 이 property 는 70% confidence" 같은 명시적 partial 표시 — docs 에서 못 찾음
- Mapping 의 confidence/quality metric — Foundry 는 그냥 "매핑됐다 / 안됐다" 의 binary 인 듯

**의문점**:
- Multi-source object type — 한 object type 의 다른 property 를 다른 dataset 에서 가져올 수 있나? [추정: S29 에서 "multi-datasource object types" 언급으로 가능. 어떻게 conflict 처리하는지는 미확인]
- Property mapping rule (e.g., regex, function transform) 정의 가능? [추정: Pipeline transform 으로 처리]

---

## 영역 3 — UX 화면들

### 3.1 Object Explorer

**Layout** [확인, S21]:
- 상단: global search bar
- 좌측: sidebar — object type group + Favorites
- 중앙: object type group cards + 각 group 안에 graph viz (link 표시)

**검색 기능** [확인, S22]:
- Operator: AND / OR / NOT
- Exact phrase: `"yellow cab"`
- Wildcard: `?` (single char), `*` (zero+); leading-and-trailing `*row*` 미지원
- Fuzzy: `quikc~`
- Field-scoped (property:value) 명시적 언급 없음

**Object Type Detail (preview panel)** [확인, S21]:
- Description
- Properties
- Linked object types
- "Start Exploration" 버튼

**Object Set 빌더** [확인, S21]: "Compare object sets", "Save lists" 언급. 별도 빌더 화면 디테일은 S21 에 없음 — Stage 2 확인.

**의문점**:
- Object type 이 1000+ 개일 때 graph viz 처리? cluster collapse? [알 수 없음 — Stage 2]
- Property:value 검색 syntax 가 정말 없나, 아니면 별도 페이지? [Stage 2 확인]

### 3.2 Workshop / Slate / Quiver / Object View

**Workshop** [확인, S23]:
- Drag-drop dashboard / app builder
- Object Set Filter Variable / Filter List / Object View widget 등
- "low to moderate complexity, lower maintenance cost"

**Slate** [확인, S23]:
- HTML/CSS/JS 커스터마이즈
- "may be a better fit if heavy customization is needed"

**Quiver** [확인, S23]:
- Exploratory analysis
- Quiver Analysis → publish as Quiver Dashboard
- Walk-up usable

**Object View** [확인, S24]:
- Workshop widget — 한 object instance 표시
- Full / panel / object instance / adaptive / object set view

### 3.3 AIP Logic Editor

**Layout** [확인, S18]: input(A) / blocks(B) / outputs(C) 좌측 패널.
**Debugger** [확인, S18]: 실행 후 LLM chain-of-thought 표시. Block card expand/collapse. 입력 버전 저장 → unit test.

### 3.4 AIP Agent / Chatbot Studio

**Tools 카탈로그** [확인, S19]:
- Action (HITL 가능)
- Object query
- Function
- Update application variable
- Command (다른 앱에서 trigger)
- Request clarification (사용자에게 추가 정보 요청)

**Tool calling mode** [확인, S19]:
- Prompted: prompt 안에 instruction 삽입, single tool at a time
- Native: 모델 native function-calling, parallel multi-tool

**의문점**:
- Tool 추가 시 description / parameter schema 어떻게 정의하는가? [알 수 없음]
- Multi-agent / agent handoff? [알 수 없음]

### 3.5 Branching / Merge UI

**Workflow** [확인, S25]:
- Create / Edit / Propose / Review / Merge
- Code Repos / Pipeline Builder / Ontology Manager / Workshop / Global Branching app 모두에서 branch 시작
- Each branch ↔ single Ontology

**Proposal** [확인, S26 (검색 발췌)]:
> "A proposal is analogous to a Pull Request in a version control system, specifically tailored for Ontology branches."
- Stages: Preparing → In Review → Merge proposal
- 한 proposal 안 여러 ontology resource 묶임 → reviewer 1명 추가 = 모든 resource 에 적용

**Git 과 차이** [확인, S25]:
> "Merging incurs additional processing... the state of data (such as transactional history) is not copied over from branches."
- Merge 가 transactional history 보존 안 함
- Self-approval 가능 (충분 권한이면)

**의문점**:
- Conflict resolution UI 어떻게 생겼나? [알 수 없음 — S25 에 "Rebasing and conflict resolution" 페이지 언급만]
- Property rename 같은 destructive 변경의 backward compat 처리? [알 수 없음]

---

## 영역 4 — Scale 전략

### 4.1 Object Storage V2 (OSv2)

**Architecture** [확인, S29]:
- OSv1 (Phonograph) = legacy, EOL 2026-06-30
- OSv2 = "separates dimensions of concern that had been consolidated in OSv1"
- Object Data Funnel service → indexing orchestration
- Object Set Service (OSS) → read serving
- Spark-based query layer for Search Arounds & aggregations

**Scale** [확인, S29]:
- Object 수: "tens of billions of objects for a single object type"
- Properties per object type ≤ 2,000
- Objects per Action ≤ 10,000 default (확장 가능)
- Search Around default ≤ 100,000

**Indexing 기술** [알 수 없음, S29, S30]:
- Docs 는 "specialized object databases" 라고만. 구체적으로 Elasticsearch / Postgres / 자체 인지 미공개.
- 검색 결과 발췌에서 Phonograph 는 "distributed set of indices in a durable, horizontally scalable cluster" 이라고만.

### 4.2 Indexing 비용 모델

**Volume metric** [확인, S31]:
- 단위: GB-Month
- 측정: hourly → monthly 평균
- "Ontology data cannot be compressed" — dataset 보다 ontology volume 이 큼
- Many-many link table 은 link 수 linear 증가

**Pruning** [확인, S32]:
> "search through billions of records by evaluating up to 1000x fewer records"
- Index 기반 pruning

### 4.3 Graph viz scale

[알 수 없음] — S21 의 group 별 graph viz 가 1000+ object type 일 때 어떻게 처리되는지 docs 미언급. Stage 2 에서 확인 필요.

### 4.4 의문점

- 100K+ object type 단일 ontology 가 supported scenario 인가? [알 수 없음 — docs 는 "billions of objects" 만 강조, type 개수 언급 없음]
- Search index 생성/업데이트 latency? [알 수 없음]
- 우리(onTong) 의 5K class 시나리오는 Foundry 에선 trivial size 인 듯 [추정]

---

## 영역 5 — AIP Logic / Agent (LLM layer)

### 5.1 AIP Logic 본질

**정의** [확인, S16]:
> "a no-code development environment for building, testing, and releasing functions powered by LLMs."
- Logic function 이 곧 Foundry function
- Input/output: ontology objects 또는 strings
- Edit 자동 적용 또는 staged for human review

**Block 6 종** [확인, S17]:
1. Use LLM — prompt + tools
2. Apply action — LLM 안 거치고 직접 action 호출
3. Execute function — TS/Python/Logic function 호출
4. Conditional — true/false 분기
5. Loop — collection iterate
6. Create variable

**Tool 4 종 (LLM block 안에서)** [확인, S17]:
1. Apply actions
2. Call function
3. Query objects
4. Calculator

**보안 모델 인용** [확인, S17]:
> "LLMs do not have direct access to tools; LLMs can only ask to use tools, and these tool calls are then executed by AIP Logic within the invoking user's permissions."

### 5.2 AIP Agent / Chatbot

**Tool 6 종** [확인, S19]: Action / Object query / Function / Update application variable / Command / Request clarification. (legacy: Ontology semantic search — deprecated)

**Tool calling mode** [확인, S19]: Prompted vs Native. Native = parallel multi-tool, 더 빠름.

**HITL** [확인, S19]: Action tool 은 "configured to run automatically or to run after confirmation from the user".

### 5.3 Context window 관리

[알 수 없음] — Docs overview 에 명시 없음. Retrieval context 종류 (application var / docs / ontology / tools) 만 언급.

### 5.4 의문점

- AIP Logic 의 Use LLM block 에서 어떤 LLM 모델 선택 가능? Claude / GPT / Gemini? Anthropic / OpenAI / NVIDIA? [추정: 다 됨, 2025 NVIDIA 통합 발표]
- Tool 의 description 을 누가 어떻게 작성하나? Object Type 의 description 을 자동으로 LLM tool spec 으로 변환? [알 수 없음 — 매우 중요한 의문]
- Logic function 의 "staged for human review" 는 PR 같은 것? Action submission queue? [알 수 없음]

---

## 영역 6 — 거버넌스

### 6.1 권한 모델

**Project / Permission** [추정, S15]:
- Function/Action 은 "platform function permissions" 적용
- OSDK token 은 "scoped only to the ontological entities" [확인, S34]
- "user's own permissions to the data" 도 별도 적용 [확인, S34]

**Marking** [확인, S04]: Property base type 에 "Marking" 존재 → 데이터 row 단위 security label.

**Action permission** [확인, S09]: facet 5 = Security/Permissions, role-based.

### 6.2 Branching / Audit

**Branch 승인** [확인, S25]:
- Code/pipeline: local protection policies
- Ontology: ≥1 editor 의 positive approval
- Self-approval 가능 (충분 권한)

**Audit log** [알 수 없음 — Stage 2 에서 audit 페이지 확인]

### 6.3 Schema 변경 backward compat

**Property ID** [확인, S02]:
> "Once saved and referenced in applications, changing property IDs breaks those applications"
→ Property ID 는 immutable 처럼 다뤄야 함.

**Cardinality 변경** [알 수 없음]

**Type evolution** [알 수 없음 — 예: String → Integer 변경 가능?]

### 6.4 의문점

- Audit log 가 ontology 변경 / action 실행 / function 호출 모두 기록하나? [알 수 없음]
- Sensitive marking propagation 규칙? [알 수 없음]
- AIP Agent 가 한 action 호출했을 때 그 action 의 acting user 는 누구로 기록? (agent? invoking user? service account?) [알 수 없음 — S17 인용 "invoking user's permissions" 보면 invoking user 인 듯]

---

## 영역 7 — SDK / Frontend Stack 단서

### 7.1 OSDK TypeScript

**Packages** [확인, S33]:
- `@osdk/client` (core)
- `@osdk/api`
- `@osdk/foundry-sdk-generator` — code generation
- `@osdk/oauth`
- `@osdk/widget.client-react` — React 사용 단서

**Auth** [확인, S33]:
- Public OAuth client (browser)
- Confidential client (server-side service user)

**Code gen 모델** [확인, S34]:
> "types and functions are generated from your Ontology"
→ Ontology schema → typed client. 우리 OSDK 와 유사한 패턴.

**Node**: 18.19+ / 20 / 22 / 24 (25 unsupported)

**의문점**:
- Frontend stack 자체 (Foundry UI 는 React + Blueprint?) — `palantir/blueprint` 가 있다는 건 아는데 실제 Foundry app 에서 쓰는지 미확인. Stage 2 에서 확인.
- Object query 의 client-side 문법 (e.g., `client.objects.Employee.where(...).fetchPage()` 식) — 직접 README/code 미확인. Stage 2 에서 OSDK README 깊게.

---

## 종합 요약 — Stage 1 한계

**높은 확신으로 답할 수 있는 것**:
- Object Type 의 schema (필수/선택 facet)
- Property base type 카탈로그
- Link type cardinality + backing
- Action type 5 facet + scale limit
- Function 의 edit declaration 패턴
- AIP Logic block 6 종 + tool 4 종
- AIP Agent tool 6 종 + 두 calling mode
- Branching 5 stage + ontology proposal = PR

**아직 못 답하는 것**:
- Interface 의 property declaration 가능 여부
- Action 의 draft → published lifecycle
- Function versioning
- Object Storage 의 실제 backend DB
- 1000+ object type 일 때 graph viz UX
- LLM tool 의 description schema (자동 생성? 수동?)
- Audit log 범위
- Property type evolution rules
- Conflict resolution UI

이런 의문은 Stage 2 (schema deep-dive) 에서 더 좁은 source 들로 파고들 것.
