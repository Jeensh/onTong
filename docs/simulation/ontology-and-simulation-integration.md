# 온톨로지 구성과 시뮬레이션 연결 — 통합 문서

> **목적**: 본 onTong 시스템에 구축된 Neo4j 3-Layer 온톨로지의 구조와, Section 3 (Simulation)이 그 위에서 어떻게 동작하는지를 한 문서로 정리한다.
>
> **작성일**: 2026-04-26
> **버전**: v1.0
> **선결 자료**: `ROADMAP-modeling-and-rebuild.md`, `ontology-modeling-spec.md`, `ontology-data-seed.md`, `section2-section3-protocol.md`

---

## 1. 개요 — 왜 온톨로지인가

ROADMAP의 핵심 설계 철학:

> **"도메인 지식이 Agent에 분산되어선 안 된다 — 모든 도메인 지식은 온톨로지에 집중되어야 한다."**

이 원칙을 지키기 위해 박판 Coil Slab 설계 도메인의 **업무 용어, 업무처리기준서, 소스 코드**를 Neo4j 단일 그래프 안에 **3-Layer 라벨로 분리하여 공존**시켰다. Section 3 (Simulation)의 모든 Agent는 자체 도메인 로직을 가지지 않고, 온톨로지에 Cypher로 질의해 결과를 가공하는 **얇은 호출자**이다.

### 결과 요약

```
Layer 1 (Business)   : 19 Term + 5 TermCategory
Layer 2 (Process)    : 12 Step + 14 Standard + 10 Variable + 1 ErrorCode
Layer 3 (Code)       : 83 Class + 198 Method + 14 Table
Bridge L1↔L2         : 15 REFERS_TO_PROCESS
Bridge L2↔L3         : 14 CALCULATES + 12 IMPLEMENTS + 14 RELATES_TO_STANDARD + 14 MAPS_TO_STANDARD

합계: 294 노드 / 313 관계
```

---

## 2. 3-Layer 구조 상세

### 2-1. Layer 1 — Business Ontology (업무 용어)

박판 Coil Slab 설계 도메인의 **개념·용어 사전**.

| 항목 | 수 | 예시 |
|------|---|------|
| `:TermCategory` | 5 | 단중 계열 / 치수 계열 / 설비 계열 / 개념 계열 / 에러 계열 |
| `:Term` | 19 | `term_edging` (Edging), `term_split_count` (분할수), `term_yield_rate` (실수율), `term_dg320` (DG320 에러) 등 |
| `:Term`-[`BELONGS_TO`]->`:TermCategory` | 19 | 모든 Term은 정확히 1개 카테고리에 속함 |
| `:Term`-[`IS_A`]->`:Term` | 6 | 주문단중/Slab단중/Target단중/포장단중 → 단중 |
| `:Term`-[`RELATED_TO`]->`:Term` | 3 | Edging ↔ 3pass / 열연목표폭, DG320 ↔ Edging |

**Term 노드 속성**: `id`, `korean_name`, `english_name`, `aliases[]`, `category`, `description`, `created_at`

**시드**: `backend/modeling/ontology/data/terms.json` (도메인 문서 §A에서 발췌)

### 2-2. Layer 2 — Process Ontology (업무처리기준서)

태스크 흐름도 SD030_01의 14단계 Slab 설계 프로세스를 그래프로 표현.

| 항목 | 수 | 예시 |
|------|---|------|
| `:Step` | 12 | Step 2 "1차 폭범위 계산", Step 13 "Target 폭 재계산 (3pass)" 등 (Step 9, 11은 Variable 출력 기준에서 제외) |
| `:Standard` | 14 | SC030 연주설비, SC070 Edging능력, SC290 특정고객사 등 |
| `:Variable` | 10 | 두께/목표폭/Slab단중/분할수/실수율/Edging능력 등 |
| `:ErrorCode` | 1 | DG320 (Edging 매칭 불가) |

**관계** (Step 내부 + Standard/Variable 의존):

| 관계 | 수 | 의미 |
|------|---|------|
| `:Step`-[`PRECEDES`]->`:Step` | 11 | Step 흐름 (1→2→3→…→14) |
| `:Step`-[`DEPENDS_ON {via_variable}`]->`:Step` | 2 | Step 10/12가 Step 8 결과(SlabWeight) 의존 |
| `:Step`-[`USES_STANDARD`]->`:Standard` | 22 | Step별 사용 SC 기준 |
| `:Step`-[`REQUIRES_INPUT`]->`:Variable` | 12 | Step 입력 변수 |
| `:Step`-[`PRODUCES_OUTPUT`]->`:Variable` | 7 | Step 출력 변수 |
| `:Standard`-[`CONSTRAINS`]->`:Variable` | 5 | SC가 변수의 값 범위 제약 |
| `:Step`-[`TRIGGERS_ON_FAIL`]->`:ErrorCode` | 1 | Step 2 → DG320 |

**시드**: `data/steps.json`, `standards.json`, `variables.json`, `error_codes.json`

### 2-3. Layer 3 — Code Ontology (소스 코드)

Spring Boot 시스템(`sample-repos/scm-demo/`)을 자동 추출한 결과.

| 항목 | 수 | 예시 |
|------|---|------|
| `:Class` | 83 | `WidthRangeCalculator`, `SlabDesignService`, `SDHsmEdgingSpecForm` 등 |
| `:Method` | 198 | `calculatePrimaryWidthRange`, `calculateTargetWidthFor3Pass` 등 |
| `:Table` | 14 | `TB_C40_050SC030` ~ `TB_C40_050SC370` |

**관계**:

| 관계 | 수 | 의미 |
|------|---|------|
| `:Class`-[`CONTAINS`]->`:Method` | 198 | 모든 메서드는 정확히 1개 클래스 안에 |
| `:Table`-[`MAPS_TO_STANDARD`]->`:Standard` | 14 | TB_C40_050SC*** ↔ SC*** |

**추출 방법**: 원래 jQAssistant Maven 플러그인을 사용할 예정이었으나, jQAssistant 2.x가 외부 Neo4j(`bolt://localhost:7687`) 연결 옵션을 무시하고 embedded store에만 결과를 저장하는 한계가 있어, 대안으로 **`tree-sitter-java`로 Java 소스를 직접 파싱**하여 동일한 결과를 얻는다 (`backend/modeling/ontology/builders/layer3_code.py`).

---

## 3. Bridge 관계 — Layer 간 연결 (★ 온톨로지 가치의 핵심)

세 Layer가 따로 떨어져 있으면 의미가 없다. **Bridge 관계가 도메인 추적을 가능하게 한다**.

### 3-1. Layer 1 ↔ Layer 2

```cypher
(:Term)-[:REFERS_TO_PROCESS {role}]->(:Step)
// role: input / output / internal / error_trigger
```

15건. 시드 `data/bridges.json`에서 정의. 예:
- `Edging` → Step 2 (internal), Step 13 (internal)
- `분할수` → Step 7 (output), Step 8 (internal)
- `DG320` → Step 2 (error_trigger)

### 3-2. Layer 2 ↔ Layer 3 (자동 매핑 ★)

| 관계 | 수 | 매핑 방식 |
|------|---|---------|
| `:Method`-[`CALCULATES`]->`:Step` | 14 | **메서드명 정규식** (`^calculatePrimaryWidth.*` → Step 2) |
| `:Class`-[`IMPLEMENTS`]->`:Step` | 12 | Method-CONTAINS-Class + Method-CALCULATES-Step에서 자동 유도 |
| `:Class`-[`RELATES_TO_STANDARD`]->`:Standard` | 14 | **Form 클래스명 매핑** (`SDHsmEdgingSpecForm` → SC070) |
| `:Table`-[`MAPS_TO_STANDARD`]->`:Standard` | 14 | 테이블명 패턴 (`TB_C40_050SC070` → SC070) |

이 자동 매핑은 **명명 규칙**이 정확히 지켜질 때만 동작한다 (§5 참고).

---

## 4. 빌더 코드 구조

### 4-1. 디렉토리

```
backend/modeling/ontology/
├── client.py                    # OntologyClient (Neo4j 연결, get_client/close_client)
├── builders/
│   ├── layer1_business.py       # Layer 1 빌드 (Term + TermCategory)
│   ├── layer2_process.py        # Layer 2 빌드 (Step + Standard + Variable + ErrorCode)
│   ├── layer3_code.py           # Layer 3 빌드 (tree-sitter Java 파싱 → Class + Method + Table)
│   └── bridges.py               # Bridge 관계 (L1↔L2 + L2↔L3 + 정규식 + Form 매핑)
├── data/
│   ├── terms.json               # 19 Term + 5 Category + 9 관계
│   ├── steps.json               # 12 Step + 11 PRECEDES + 2 DEPENDS_ON
│   ├── standards.json           # 14 Standard + 22 USES_STANDARD
│   ├── variables.json           # 10 Variable + 17 inputs/outputs + 5 CONSTRAINS
│   ├── error_codes.json         # 1 ErrorCode + 1 TRIGGERS_ON_FAIL
│   ├── bridges.json             # 15 REFERS_TO_PROCESS (Term ↔ Step)
│   └── tables.json              # 14 Table (TB_C40_050SC***)
├── queries/
│   ├── impact_queries.py        # Agent 1 (영향도 traversal)
│   ├── test_data_queries.py     # Agent 2 (변수 의존성 + 테스트 케이스)
│   └── locator_queries.py       # Agent 3 (Term 검색 + path)
└── api/
    └── ontology_router.py       # FastAPI 라우터 (POST /query, GET /graph/stats, /term/search)
```

### 4-2. 빌드 순서

```bash
source venv/bin/activate

# Layer 1: 19 Term + 5 Category
python -m backend.modeling.ontology.builders.layer1_business

# Layer 2: 12 Step + 14 Standard + 10 Variable + 1 ErrorCode
python -m backend.modeling.ontology.builders.layer2_process

# Layer 3: 83 Class + 198 Method + 14 Table (Java 소스 파싱)
python -m backend.modeling.ontology.builders.layer3_code

# Bridge: 15 REFERS_TO_PROCESS + 14 CALCULATES + 14 RELATES_TO_STANDARD
python -m backend.modeling.ontology.builders.bridges
```

모든 빌더는 **멱등성 보장**: 두 번 실행해도 같은 결과. 각 빌더는 자기 Layer만 `clear` 후 적재하므로 다른 Layer에 영향 없음.

---

## 5. ★ 명명 규칙 (절대 어기지 말 것)

자동 매핑이 동작하려면 다음을 반드시 지킨다.

### 5-1. 메서드명 → Step (`backend/modeling/ontology/builders/bridges.py`)

```python
METHOD_TO_STEP_PATTERNS = [
    (r"^calculate.*Target.*Width.*[Ff]or.*3[Pp]ass.*", 13),
    (r"^calculate.*SecondaryWeight.*Lower.*", 5),
    (r"^calculate.*SecondaryWeight.*Upper.*", 6),
    (r"^calculate.*Thickness.*", 1),
    (r"^calculate.*PrimaryWidth.*", 2),
    (r"^calculate.*PrimaryLength.*", 3),
    (r"^calculate.*PrimaryWeight.*", 4),
    (r"^calculate.*UnitCount.*", 8),
    (r"^calculate.*Split.*Count.*", 7),
    (r"^check.*TargetWeight.*", 9),
    (r"^calculate.*SecondaryWidth.*", 10),
    (r"^calculate.*SecondaryLength.*", 11),
    (r"^calculate.*Target.*Length.*", 14),
    (r"^calculate.*Target.*Width.*", 12),
]
```

### 5-2. Form 클래스 → SC

```python
FORM_TO_STANDARD = {
    "SDCastMachineSpecForm":         "SC030",
    "SDHsmMachineSpecForm":          "SC040",
    "SDCoilOutDiaRestricForm":       "SC060",
    "SDHsmEdgingSpecForm":           "SC070",
    "SDHrEdgingSpecGroupForm":       "SC071",
    "SDHsmWeightMinForm":            "SC080",
    "SDStdRollMaxUnitForm":          "SC090",
    "SDCsmMinWgtForm":               "SC100",
    "SDOemWgtMaxRangeForm":          "SC110",
    "SDWgtSatisfactionConstForm":    "SC160",
    "SDHotCoilNotCuttableSpecForm":  "SC170",
    "SDSlabDesignLimitationForm":    "SC270",
    "SDSpecificCustomerWgtRestriForm": "SC290",
    "SDDeliveryAllowanceForm":       "SC370",
}
```

### 5-3. 테이블명

`TB_C40_050SC{030|040|060|070|071|080|090|100|110|160|170|270|290|370}` (총 14개)

명명 규칙을 어기면 **온톨로지 가치의 80%가 사라진다** (자동 매핑이 깨져 Bridge 관계가 안 만들어짐).

---

## 6. 시뮬레이션과의 연결 — Section 3가 온톨로지를 쓰는 방식

### 6-1. 호출 흐름

```
[Frontend Section 3 UI]
   │ POST /api/simulation/agents/{impact|test-data|locator}
   │ POST /api/simulation/agents/explorer/{search|expand|path}
   ▼
[Section 3 Agent 백엔드]  backend/simulation/agents/
   │ OntologyClient.query()  (in-process 모드)
   ▼
[Section 2 라우터]  backend/modeling/ontology/api/ontology_router.py
   │ Cypher 쿼리 실행
   ▼
[Neo4j (Layer 1 + 2 + 3 + Bridge)]
   │ rows + ontology_trace {nodes, edges, cypher}
   ▼
[Frontend OntologySubgraphView]
   - SVG + 물리 시뮬 force-directed 레이아웃
   - 그룹별 색상 (term=amber, step=purple, standard=emerald, method=blue, class=indigo, table=cyan)
   - highlight (seed) + pathEdgeKeys (경로) + onNodeClick (drill-down)
```

### 6-2. 4개 Agent별 온톨로지 활용

#### 📊 Agent 1 — 영향도 파악 (`agents/agent1_impact.py`)

| target_type | 핵심 Cypher | 결과 그래프 |
|------------|-----------|-----------|
| `table` | `(t:Table)-[:MAPS_TO_STANDARD]->(:Standard)<-[:USES_STANDARD]-(:Step)<-[:CALCULATES]-(:Method)` | 변경 테이블 → SC → Step → Method traversal |
| `method` | `(m:Method)-[:CALCULATES]->(s:Step)`, `(s)-[:PRECEDES\|DEPENDS_ON*1..3]->(s2)` | 메서드 → 직접/다운스트림 Step |
| `standard_value` | table과 유사 | SC 변경 시 영향받는 Step+Method |
| **`order`** | `(s:Step)-[:USES_STANDARD]->(:Standard)`, `(:Method)-[:CALCULATES]->(s)` | **14 Step 전체 + 사용 SC + 매핑 Method가 한 그래프로** |

응답 필드: `summary`, `direct_impact`, `indirect_impact`, `risk_level`, **`ontology_trace: {nodes, edges, seed_ids, cypher}`**

#### 🧪 Agent 2 — 테스트 데이터 (`agents/agent2_test_data.py`)

```cypher
MATCH (s:Step {step_number: $n})
OPTIONAL MATCH (s)-[:REQUIRES_INPUT]->(i:Variable)
OPTIONAL MATCH (s)-[:PRODUCES_OUTPUT]->(o:Variable)
OPTIONAL MATCH (s)-[:USES_STANDARD]->(std:Standard)
OPTIONAL MATCH (s)-[:TRIGGERS_ON_FAIL]->(e:ErrorCode)
RETURN ...
```

각 Variable의 `valid_range`를 Cypher로 가져와 **정상/경계값/에러** 케이스를 산술로 합성. 데이터 의존성(`data_dependencies`)은 SC → Table 매핑(`MAPS_TO_STANDARD`)을 역추적해 도출.

응답 그래프: Step + Variable(REQUIRES_INPUT/PRODUCES_OUTPUT) + Standard(USES_STANDARD) + ErrorCode(TRIGGERS_ON_FAIL).

#### 🗺 Agent 3 — 위치 파악 (`agents/agent3_locator.py`)

자연어 입력 → **3단계 키워드 추출**:
1. `parameters["keyword"]` 명시값 (`explicit`)
2. **Gemini 2.5 flash** LLM (`llm`) — 한국어 조사 제거 / SC코드 인식
3. fallback: split + stopwords (`split`)

추출된 키워드 → Term 검색 → 경로 traversal:
```cypher
MATCH (t:Term) WHERE t.korean_name CONTAINS $kw OR t.english_name CONTAINS $kw OR ANY(a IN t.aliases WHERE a CONTAINS $kw)
MATCH (t)-[:REFERS_TO_PROCESS]->(s:Step)<-[:CALCULATES]-(m:Method)<-[:CONTAINS]-(c:Class)
```

응답 그래프: Term seed + 매칭 Step/Method/Table + **path_edge_keys** (경로만 보라색 진하게).

> LLM 사용 위치는 **자연어 키워드 추출 한 곳뿐**. 도메인 추론(매칭, 경로 결정)은 모두 Cypher가 한다. Gemini 미설정 시 자동으로 split fallback.

#### 🌐 Agent 4 — 온톨로지 익스플로러 (`agents/agent4_explorer.py`)

| 엔드포인트 | 역할 |
|----------|------|
| `GET /explorer/search?q=...&groups=...` | 라벨/이름/그룹 자유 검색 (LIKE 매칭, 30건 limit) |
| `POST /explorer/expand {node_id, hops}` | 노드 1-2 hop 이웃 추출 |
| `POST /explorer/path {from_id, to_id}` | 두 노드 간 `shortestPath` (max 5 hops) |
| `GET /ontology-graph?scope=...` | 전역 그래프 (design-flow / term-process / method-step / all) |

UI에서 그래프 노드 클릭 → 같은 노드를 새 seed로 expand → **drill-down 탐색**.

### 6-3. 백엔드 응답 공통 필드 — `ontology_trace`

모든 Agent 응답은 `ontology_trace`를 포함:

```json
{
  "nodes": [{ "id": "...", "label": "...", "group": "term|step|standard|method|class|table|order|variable|errorcode" }],
  "edges": [{ "from": "...", "to": "...", "label": "REL_TYPE" }],
  "seed_ids": ["..."],
  "path_edge_keys": ["from->to"],
  "cypher": "MATCH ..."
}
```

Frontend `OntologySubgraphView`는 이 필드를 그대로 받아 force-directed 레이아웃으로 그린다.

---

## 7. Spring Boot 시스템과의 관계

`sample-repos/scm-demo/`는 **Layer 3의 자동 추출 대상**이다. 시스템이 명명 규칙을 따르면 온톨로지에 자동으로 등록된다.

| Spring Boot 산출물 | 온톨로지 매핑 |
|------------------|------------|
| `service/SlabDesignService.java`의 14 calculate 메서드 | `:Method`-[`CALCULATES`]->`:Step` |
| `form/SDxxxForm.java` 14개 | `:Class`-[`RELATES_TO_STANDARD`]->`:Standard` |
| `domain/standards/Sc***Entity.java`의 `@Table(name = "TB_C40_050SC***")` | `:Table` 노드 + `MAPS_TO_STANDARD` |
| `service/StreamingSlabDesignService.java` (SSE) | (시뮬레이션 도구로 사용 가능, 현재 직접 통합 안 함) |

Spring Boot 코드가 변경되어 메서드를 추가하면 `layer3_code.py` + `bridges.py` 재실행만으로 온톨로지가 갱신된다.

---

## 8. 검증 쿼리 — 통합이 잘 됐는지

### 8-1. Layer별 카운트

```cypher
MATCH (t:Term)         RETURN count(t)  // 19
MATCH (s:Step)         RETURN count(s)  // 12
MATCH (std:Standard)   RETURN count(std) // 14
MATCH (c:Class)        RETURN count(c)  // 83
MATCH (m:Method)       RETURN count(m)  // 198
```

### 8-2. 검증 쿼리 6 — 3-Layer 통합 (가장 임팩트 있는 쿼리)

```cypher
MATCH (t:Term {korean_name: 'Edging'})
      -[:REFERS_TO_PROCESS]->(s:Step)
      <-[:CALCULATES]-(m:Method)
      <-[:CONTAINS]-(c:Class)
RETURN c.name AS class, m.name AS method, s.step_number AS step
ORDER BY step
```

기대 결과:

```
class                    | method                          | step
WidthRangeCalculator     | calculatePrimaryWidthRange      | 2
WidthRangeCalculator     | calculateTargetWidthFor3Pass    | 13
```

자연어 단어 하나(`Edging`)에서 Spring Boot 메서드까지 한 쿼리로 추적된다.

### 8-3. 검증 쿼리 4 — Term ↔ Step

```cypher
MATCH (t:Term {korean_name: 'Edging'})-[:REFERS_TO_PROCESS]->(s:Step)
RETURN s.step_number, s.korean_name
// 기대: Step 2, Step 13
```

---

## 9. UI 시각화 — `OntologySubgraphView`

`frontend/src/components/simulation/shared/OntologySubgraphView.tsx`

**기술 선택**: 외부 라이브러리(D3, vis-network 등) 없이 **SVG + 자체 물리 시뮬**.

| 힘 | 효과 |
|----|------|
| Coulomb 반발 (`5500/r²`) | 노드끼리 떨어뜨림 |
| Spring (`k=0.04, len=110`) | 연결된 쌍을 가까이 |
| Center pull (`0.005`) | 화면 중앙 정렬 |
| Damping (`0.78`) | 진동 안정화 |

**props**:
- `nodes`, `edges`: 백엔드 `ontology_trace`에서 그대로
- `highlightIds`: seed (변경 대상, 검색 결과) 강조
- `pathEdgeKeys`: 경로 edge만 보라색
- `onNodeClick`: drill-down (Agent 4 익스플로러에서 활용)

**그룹별 색상** (`group` 속성 기준):
- `term` (amber), `step` (purple), `standard` (emerald), `method` (blue), `class` (indigo), `table` (cyan), `order` (red, 변경 대상 강조), `variable` (lime), `errorcode` (red)

---

## 10. 참고 문서

| 문서 | 역할 |
|------|------|
| [`ROADMAP-modeling-and-rebuild.md`](./ROADMAP-modeling-and-rebuild.md) | 4주 통합 로드맵 |
| [`ontology-modeling-spec.md`](./ontology-modeling-spec.md) | 3-Layer 명세 |
| [`ontology-data-seed.md`](./ontology-data-seed.md) | 시드 JSON 정의 |
| [`section2-section3-protocol.md`](./section2-section3-protocol.md) | API 계약 (Pydantic 모델) |
| [`../slab-design/slab-design-domain-knowledge.md`](../slab-design/slab-design-domain-knowledge.md) | 박판 Slab 설계 도메인 지식 |
| [`../slab-design/slab-design-system-spec.md`](../slab-design/slab-design-system-spec.md) | Spring Boot 시스템 명세 |

---

## 11. 한 줄 요약

> **"박판 Slab 설계 도메인의 업무 용어 → 업무 프로세스 → Spring Boot 소스 코드를 Neo4j 3-Layer 온톨로지(294 노드 / 313 관계)로 연결하고, Section 3의 4개 Agent가 자체 도메인 로직 없이 온톨로지에 Cypher로 질의해 영향도/테스트 데이터/위치 파악/그래프 탐색을 수행한다. 모든 응답에는 force-directed로 시각화 가능한 `ontology_trace`가 포함되며, LLM은 자연어 키워드 추출 한 곳에만 사용된다."**
