# Palantir Sources Index — Stage 1 Sweep

작성일: 2026-05-02
용도: onTong (BusinessTerm/Action/TypeRealization) 설계 reference. Foundry Ontology schema/UX 비교.
범위: 이 단계는 raw 정보 수집만. 결정/synthesis 는 Stage 2-4.

신뢰도 표기:
- ⭐⭐⭐ 공식 docs (palantir.com/docs)
- ⭐⭐ 공식 GitHub README / 공식 blog
- ⭐ 외부 블로그 / 커뮤니티 / 마케팅 페이지

---

## 1. 공식 문서 — Ontology 핵심 모델

### S01. Ontology Overview
- URL: https://www.palantir.com/docs/foundry/ontology/overview
- 제목/저자: "Overview • Ontology" (Palantir 공식 docs)
- 한 줄 요약: Object/Link/Action/Function 4 가지 ontology element 정의. 가장 위에서 봐야 할 entry.
- 핵심 발견: "The Ontology sits on top of the digital assets integrated into the Palantir platform...and connects them to their real-world counterparts." Object Type = semantic 매핑, Action Type = "kinetic elements that enable operational change", Function = "author and evolve business logic with arbitrary complexity".
- 신뢰도: ⭐⭐⭐

### S02. Object Type 생성 가이드
- URL: https://www.palantir.com/docs/foundry/object-link-types/create-object-type
- 한 줄 요약: Object Type 의 필수/선택 필드 전체 enumeration.
- 핵심 발견: 필수 = ID, Display name, Plural display name, Backing datasource, API name, ≥1 property. Property 는 primary key + title key 지정 필수. Reserved API name 9 개 (`ontology`, `object`, `property`, `link`, `relation`, `rid`, `primaryKey`, `typeId`, `ontologyObject`).
- 신뢰도: ⭐⭐⭐

### S03. Object/Link Types Reference
- URL: https://www.palantir.com/docs/foundry/object-link-types/type-reference
- 한 줄 요약: Type 시스템 reference (base types, value types, statuses).
- 핵심 발견: "Value types are semantic wrappers around a field type comprised of metadata and constraints that can enhance type safety, improve expressiveness, and provide additional context." Statuses 존재 (active / Legacy / Planned deprecation 등) 하지만 별도 페이지.
- 신뢰도: ⭐⭐⭐

### S04. Properties Overview
- URL: https://www.palantir.com/docs/foundry/object-link-types/properties-overview
- 한 줄 요약: Property 종류 + base type 목록.
- 핵심 발견: Base types = String, Integer, Boolean, Date, Timestamp, Array, Struct, Media Reference, Time Series, Attachment, Geopoint, Geoshape, Marking, Cipher, Vector, Float, Double, Decimal, Byte, Short, Long. Property 종류: regular, derived, edit-only, required, shared, title key, primary key, mandatory control. Primary key 는 String / Integer / Short 만 지원.
- 신뢰도: ⭐⭐⭐

### S05. Derived Properties
- URL: https://www.palantir.com/docs/foundry/object-link-types/derived-properties (검색 결과)
- 한 줄 요약: 런타임에 linked objects 로부터 계산되는 property.
- 핵심 발견: "Derived properties are properties that are calculated at runtime based on values from linked objects." 최대 3 단계 link 까지 traversal. Aggregation (avg, count, list collect) 지원.
- 신뢰도: ⭐⭐⭐

### S06. Link Types Overview
- URL: https://www.palantir.com/docs/foundry/object-link-types/link-types-overview
- 한 줄 요약: Link 정의, cardinality, backing 방식.
- 핵심 발견: "A link type is the schema definition of a relationship between two object types. A link refers to a single instance of that relationship." many-to-many 는 join table 로 backing, 1-many/1-1 은 foreign key. Cross-Ontology link 불가.
- 신뢰도: ⭐⭐⭐

### S07. Create Link Type
- URL: https://www.palantir.com/docs/foundry/object-link-types/create-link-type
- 한 줄 요약: Link 만들기 step-by-step. Cardinality 별 backing 방식 표.
- 핵심 발견: 4 가지 cardinality (1-1, 1-many, many-1, many-many) + 3 가지 backing (Foreign Key / Join Table / Backing Object). Many-1 은 FK 또는 backing object 둘 다 가능. Object-backed link 는 intermediary object 와 양쪽 many-1 link 필요.
- 신뢰도: ⭐⭐⭐

### S08. Interface Link Types
- URL: https://www.palantir.com/docs/foundry/interfaces/interface-link-types-overview
- 한 줄 요약: Foundry 의 inheritance/abstract type 메커니즘.
- 핵심 발견: "When an object implements an interface with an interface link type constraint, concrete link types on the object type are used to fulfill interface link type constraints." 예: Airport implements Facility. Property 도 interface 가능한지는 이 페이지에서 확인 안 됨.
- 신뢰도: ⭐⭐⭐

---

## 2. 공식 문서 — Action Types

### S09. Action Types Overview
- URL: https://www.palantir.com/docs/foundry/action-types/overview
- 한 줄 요약: Action = "set of changes or edits to objects, property values, and links that a user can take at once".
- 핵심 발견: 5 facet — Parameters, Rules, Submission Criteria, Side Effects (notifications/webhooks), Security/Permissions. Single transaction 으로 여러 object 동시 edit. "changes... will be committed to the Ontology when the user takes the action" — writeback dataset 으로 반영.
- 신뢰도: ⭐⭐⭐

### S10. Action Types Getting Started
- URL: https://www.palantir.com/docs/foundry/action-types/getting-started
- 한 줄 요약: Rules-based 로직 정의 walkthrough.
- 핵심 발견: 사용자가 채우는 항목 — Display name / Change object operation type (e.g., Modify) / Target object type / Properties to modify / Description. Parameter 는 "automatically created based by the Rule" — Rule 정의하면 parameter 가 자동 생성됨.
- 신뢰도: ⭐⭐⭐

### S11. Action Parameter Overview
- URL: https://www.palantir.com/docs/foundry/action-types/parameter-overview
- 한 줄 요약: Action parameter 의 visibility/validation/binding.
- 핵심 발견: "parameters are the interface between the Rules and other Foundry applications, such as Workshop, Slate, and Object Views." 각 parameter 는 visibility, editability, default value, conditional 설정 가능.
- 신뢰도: ⭐⭐⭐

### S12. Submission Criteria
- URL: https://www.palantir.com/docs/foundry/action-types/submission-criteria
- 한 줄 요약: Validation = submission criteria. business rule 을 data editing permission 에 인코딩.
- 핵심 발견: "Submission criteria (formerly known as validations) are the conditions that determine whether an action can be submitted." Conditions + operators 조합. attachment / object set parameter 는 criteria 에서 제외.
- 신뢰도: ⭐⭐⭐

### S13. Action Scale & Property Limits
- URL: https://www.palantir.com/docs/foundry/action-types/scale-property-limits
- 한 줄 요약: Action 의 hard 숫자 limit.
- 핵심 발견: Object types per action submission ≤ 50. Objects per action ≤ 10,000. Edit size: 32KB (OSv1) / 3MB (OSv2). Batch calls per action ≤ 10,000 (or 20 for non-batched function-backed). Notification recipients ≤ 500 (50 if function-rendered). Primitive list parameter ≤ 10,000 elements; object reference list ≤ 1,000.
- 신뢰도: ⭐⭐⭐

---

## 3. 공식 문서 — Functions

### S14. Functions Overview
- URL: https://www.palantir.com/docs/foundry/functions/overview
- 한 줄 요약: Server-side code (TS/Python) 가 Ontology 와 first-class 통합.
- 핵심 발견: "Functions enable code authors to write logic that can be executed quickly in operational contexts." TS v1, TS v2, Python 지원. 호출 컨텍스트: Workshop / Action (function-backed) / Slate / Quiver / Pipeline Builder. Pure 와 side-effecting 의 명시적 구분은 없으나 edit 은 별도 decorator 로 declare.
- 신뢰도: ⭐⭐⭐

### S15. Function Ontology Edits
- URL: https://www.palantir.com/docs/foundry/functions/edits-overview
- 한 줄 요약: Function 이 Ontology 를 mutate 하는 방식.
- 핵심 발견: "An Ontology edit is the act of creating, modifying, or deleting an object." TS v1: `@OntologyEditFunction` + `@Edits([Type])`. TS v2: `Edits` type from `@osdk/functions`. Python: `@function(edits=[Type])`. **Caveat**: "Changes to objects and links are propagated to the object set APIs after your function has finished executing." → 함수 내 search 는 pending edit 반영 안 됨.
- 신뢰도: ⭐⭐⭐

---

## 4. 공식 문서 — AIP / Agent

### S16. AIP Logic Overview
- URL: https://www.palantir.com/docs/foundry/logic/overview
- 한 줄 요약: No-code LLM function builder.
- 핵심 발견: "a no-code development environment for building, testing, and releasing functions powered by LLMs." Logic functions take ontology objects/strings as input, return objects/strings or apply edits. Edits 는 자동 적용 또는 human review 로 staging 가능.
- 신뢰도: ⭐⭐⭐

### S17. AIP Logic Blocks
- URL: https://www.palantir.com/docs/foundry/logic/blocks
- 한 줄 요약: Logic 의 block 종류 6 가지.
- 핵심 발견: Use LLM / Apply action / Execute function / Conditional / Loop / Create variable. Sequential chain. **Tool calling 모델 인용**: "LLMs do not have direct access to tools; LLMs can only ask to use tools, and these tool calls are then executed by AIP Logic within the invoking user's permissions." 4 가지 LLM tool: Apply actions, Call function, Query objects, Calculator.
- 신뢰도: ⭐⭐⭐

### S18. AIP Logic Getting Started
- URL: https://www.palantir.com/docs/foundry/logic/getting-started
- 한 줄 요약: Logic editor 의 input(A)/blocks(B)/outputs(C) 구조.
- 핵심 발견: Debugger 가 LLM chain-of-thought (CoT) 표시. 입력 버전 저장해서 unit test 가능. "The output of a block can be used in subsequent blocks."
- 신뢰도: ⭐⭐⭐

### S19. Agent Studio Tools (a.k.a. Chatbot Studio)
- URL: https://www.palantir.com/docs/foundry/agent-studio/tools
- 한 줄 요약: Agent (현재 명칭 Chatbot) 의 tool catalog.
- 핵심 발견: 6 종 tool: Action / Object query / Function / Update application variable / Command / Request clarification. (legacy: Ontology semantic search — deprecated). Action tool 은 "configured to run automatically or to run after confirmation from the user" — HITL 옵션. 두 tool calling mode: Prompted (single tool) vs Native (multi-tool parallel).
- 신뢰도: ⭐⭐⭐

### S20. Agent Studio Overview
- URL: https://www.palantir.com/docs/foundry/agent-studio/overview/
- 한 줄 요약: Chatbot 빌더 — LLM + ontology + 문서 + tool.
- 핵심 발견: Chatbot 은 "deployable internally in the platform and externally". Retrieval context = application variables / documents / ontology / tools.
- 신뢰도: ⭐⭐⭐

---

## 5. 공식 문서 — UX 및 검색

### S21. Object Explorer Getting Started
- URL: https://www.palantir.com/docs/foundry/object-explorer/getting-started
- 한 줄 요약: Object 발견용 entry point UI.
- 핵심 발견: 상단 global search bar + 좌측 sidebar (object type group + Favorites). 각 group 안에서 graph viz 로 link type 표시. Type-ahead 매칭. Preview panel 에 description / properties / linked types / "Start Exploration" 버튼.
- 신뢰도: ⭐⭐⭐

### S22. Object Explorer Search Syntax
- URL: https://www.palantir.com/docs/foundry/object-explorer/search-syntax
- 한 줄 요약: 검색 연산자 카탈로그.
- 핵심 발견: AND / OR / NOT, exact phrase ("..."), wildcard `?` (single char) `*` (zero+ chars, leading-and-trailing 미지원), fuzzy `~`. **Field-scoped search (property:value) 는 명시적으로 안 보임** — Stage 2 에서 확인 필요.
- 신뢰도: ⭐⭐⭐

### S23. Workshop / Slate / Quiver 비교
- URL: https://www.palantir.com/docs/foundry/app-building/overview + https://www.palantir.com/docs/foundry/getting-started/application-reference
- 한 줄 요약: 3 가지 application 빌더의 역할 분담.
- 핵심 발견: Workshop = 저~중복잡도, 낮은 유지비. Slate = HTML/CSS/JS 커스터마이즈, 고복잡도. Quiver = exploratory analysis, dashboard 발행 가능. Object Explorer + Quiver 는 walk-up usable, Workshop/Slate 는 builder 가 만들어야 함.
- 신뢰도: ⭐⭐⭐

### S24. Workshop Object View Widget
- URL: https://www.palantir.com/docs/foundry/workshop/widgets-object-view
- 한 줄 요약: 한 object instance 를 dashboard 에 embed.
- 핵심 발견: Input object set 으로 표시 대상 결정. Full / panel / object instance / adaptive / object set view 모드.
- 신뢰도: ⭐⭐⭐

---

## 6. 공식 문서 — Branching / Governance

### S25. Foundry Branching Lifecycle
- URL: https://www.palantir.com/docs/foundry/foundry-branching/branching-lifecycle-usage
- 한 줄 요약: Branch → propose → review → merge.
- 핵심 발견: 5 stage: Create / Edit / Propose / Review / Merge. 각 branch 는 single Ontology 에 묶임. **Git 과 차이**: "the state of data (such as transactional history) is not copied over from branches" — merge 가 transactional history 보존 안 함. Ontology 변경은 ≥1 editor 의 positive approval 필요.
- 신뢰도: ⭐⭐⭐

### S26. Ontology Proposals (검색 결과)
- URL: https://www.palantir.com/docs/foundry/ontologies/ontologies-proposals (404 상태이지만 검색 발췌 확보)
- 한 줄 요약: PR-like merge mechanism for ontology.
- 핵심 발견: "A proposal is analogous to a Pull Request in a version control system, specifically tailored for Ontology branches." Stages: Preparing → In Review → Merge proposal. 한 proposal 안에 여러 ontology resource 가 묶임 — reviewer 가 한 명 추가되면 모든 resource 에 적용.
- 신뢰도: ⭐⭐ (직접 페이지 fetch 실패, 검색 발췌 기반)

---

## 7. 공식 문서 — Pipeline / Data → Ontology

### S27. Pipeline Builder Ontology Output
- URL: https://www.palantir.com/docs/foundry/pipeline-builder/outputs-add-ontology-output
- 한 줄 요약: Dataset 변환 결과 → Ontology object/link.
- 핵심 발견: Pipeline Builder 안에서 직접 object types, link types, time series 추가/편집 가능. Ontology Manager 에 가지 않아도 됨. Transform node 선택 → "Add output > New object type" → Ontology 선택.
- 신뢰도: ⭐⭐⭐

### S28. Pipeline Builder Outputs Overview
- URL: https://www.palantir.com/docs/foundry/pipeline-builder/outputs-overview
- 한 줄 요약: Output = dataset / virtual table / ontology element.
- 핵심 발견: "Outputs in Pipeline Builder are the result of transforms... can be datasets, virtual tables, or Ontology components such as object types, object link types, or time series."
- 신뢰도: ⭐⭐⭐

---

## 8. 공식 문서 — Storage / Scale

### S29. Object Storage V2 Overview
- URL: https://www.palantir.com/docs/foundry/object-backend/overview
- 한 줄 요약: OSv2 가 OSv1 (Phonograph) 를 대체. 인덱싱과 쿼리 분리.
- 핵심 발견: OSv1 EOL = 2026-06-30. OSv2 는 Object Data Funnel 서비스로 indexing 분리. Spark-based query layer for Search Arounds. **Scale**: "tens of billions of objects for a single object type". Default 10,000 objects per Action edit (확장 가능). Properties per object type ≤ 2,000. Search Around default 100,000.
- 신뢰도: ⭐⭐⭐

### S30. Object Set Service (OSS) — 검색 발췌
- URL: https://www.palantir.com/docs/foundry/object-databases/* (검색 결과)
- 한 줄 요약: 읽기 전담 service.
- 핵심 발견: "Object Set Service (OSS) is the service responsible for serving reads from the Ontology." OSv1 = Phonograph (legacy). OSv2 는 OSS + Funnel + 다양한 backend DB ("specialized object databases"). 구체적 DB (Postgres / Elasticsearch) 는 docs 에 명시 없음.
- 신뢰도: ⭐⭐ (구체 backend 미공개)

### S31. Ontology Volume Usage
- URL: https://www.palantir.com/docs/foundry/ontologies/volume-usage
- 한 줄 요약: 비용 산정 단위 = GB-Month.
- 핵심 발견: "Ontology volume can be larger than dataset volume because Ontology data cannot be compressed, and Ontology indexing requires additional storage to facilitate faster queries." Hourly 측정 후 monthly 평균. Many-many link table 은 link 수에 linear 하게 증가. Hard limit 은 명시 없음.
- 신뢰도: ⭐⭐⭐

### S32. Indexing Compute Usage
- URL: https://www.palantir.com/docs/foundry/ontologies/compute-usage
- 한 줄 요약: Indexing compute 비용 모델.
- 핵심 발견: "Ontology can search through billions of records by evaluating up to 1000x fewer records using its indexing and pruning capabilities." Pruning = data 일부 traversal. OSv1 Phonograph 는 distributed 인덱스 + horizontally scalable cluster.
- 신뢰도: ⭐⭐⭐

---

## 9. SDK / GitHub

### S33. OSDK TypeScript Repo
- URL: https://github.com/palantir/osdk-ts
- 한 줄 요약: Client-side ontology SDK (npm).
- 핵심 발견: 패키지 구조 — `@osdk/client` (core), `@osdk/api`, `@osdk/foundry-sdk-generator`, `@osdk/oauth`, `@osdk/widget.client-react`. Public OAuth (browser) + Confidential client (server). Node 18.19+ / 20 / 22 / 24 (25 미지원). React widget 패키지 존재 → Frontend stack 에 React 사용 단서.
- 신뢰도: ⭐⭐

### S34. OSDK Overview Docs
- URL: https://www.palantir.com/docs/foundry/ontology-sdk/overview
- 한 줄 요약: SDK 의 언어 지원 + auth 모델.
- 핵심 발견: TypeScript (NPM), Python (Pip/Conda), Java (Maven), OpenAPI (any). "The OSDK uses a token that is scoped only to the ontological entities you want your application to access" — token 은 ontology 단위 scope. "types and functions are generated from your Ontology" — code generation 모델.
- 신뢰도: ⭐⭐⭐

### S35. Ontology Starter React App
- URL: https://github.com/palantir/ontology-starter-react-app
- 한 줄 요약: Foundry Ontology 위에 React 앱을 만드는 reference.
- 핵심 발견: 검색 결과만 — 직접 fetch 안 함. Stage 2 에서 코드 직접 보면 client-side object query / action invocation 패턴 알 수 있음.
- 신뢰도: ⭐⭐ (미확인)

---

## 10. Engineering Blog

### S36. Ontology-Oriented Software Development (Palantir Blog)
- URL: https://blog.palantir.com/ontology-oriented-software-development-68d7353fdb12
- 한 줄 요약: Palantir 가 주장하는 ontology-first dev 패러다임.
- 핵심 발견: **직접 fetch 실패** (Medium 인증 redirect). Stage 2 에서 다시 시도 또는 archive.org 활용 필요.
- 신뢰도: ⭐⭐ (미확인)

### S37. AI Infrastructure & Ontology (Palantir + NVIDIA)
- URL: https://blog.palantir.com/ai-infrastructure-and-ontology-78b86f173ea6
- 한 줄 요약: Palantir + NVIDIA partnership 발표 (2025-10-28).
- 핵심 발견: 검색 발췌만 확보. 12-layer agentic architecture 언급. Stage 2 에서 직접 확인 필요.
- 신뢰도: ⭐⭐ (검색 발췌)

### S38. Connecting AI to Decisions with the Palantir Ontology
- URL: https://blog.palantir.com/connecting-ai-to-decisions-with-the-palantir-ontology-c73f7b0a1a72
- 한 줄 요약: Data/Logic/Action triad + agent 의 ontology memory 활용.
- 핵심 발견 (검색 발췌): "Every decision is comprised of data..., logic..., and action.... The Ontology integrates these three constituent elements of decision-making into a scalable, dynamic, collaborative foundation." "Agents query billions of objects, orchestrate thousands of actions, and operate under the same security governance as human employees." 직접 fetch 실패.
- 신뢰도: ⭐⭐ (검색 발췌)

---

## 11. 외부 분석 (참고용 — 비공식)

### S39. anandbg.com — 12-layer Agentic Architecture
- URL: https://anandbg.com/blog/palantir-aip-end-to-end-agentic-architecture
- 한 줄 요약: Palantir AIP 의 layered architecture 분석.
- 핵심 발견: 검색 발췌 — Stage 2 에서 직접 확인 가치.
- 신뢰도: ⭐ (외부)

### S40. Chanon Roy — Slate vs Workshop vs OSDK (Medium)
- URL: https://chanonroy.medium.com/palantir-slate-vs-workshop-vs-osdk-2467028567a8
- 한 줄 요약: 3 가지 선택지 비교.
- 신뢰도: ⭐ (외부, 검증 안 함)

---

## 종합

- 직접 fetch 성공: 24 페이지 (대부분 ⭐⭐⭐ 공식 docs)
- 검색 발췌만: 16 페이지
- 인증 차단 (Medium): blog.palantir.com 4 페이지 — Stage 2 에서 archive.org 또는 다른 경로
- 미확인 (시간 부족): YouTube 영상, 채용 공고, Akshay Krishnaswamy 인터뷰 — Stage 2 에서 옵션
