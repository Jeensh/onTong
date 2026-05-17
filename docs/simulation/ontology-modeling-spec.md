# 섹션 2 (Modeling) — 온톨로지 구축 명세서

> **대상**: Claude Code
> **목적**: Section 2 Modeling 섹션에 Neo4j 기반 3-Layer 온톨로지를 구축한다.
> **현재 상태**: `backend/modeling/` 폴더는 존재하나 온톨로지 구축은 미시작
> **선결 조건**: Neo4j 컨테이너 동작, `backend/shared/contracts/` 사용 가능
> **버전**: v1.0

---

## 0. 배경 및 목표

### 0-1. 왜 두 개의 온톨로지를 만드는가

지난 회의에서 결정된 방향:
- **온톨로지 1 — 업무처리기준서 ↔ 소스 연결**: 업무 프로세스(태스크 흐름도, SC 기준 등)와 Spring Boot 소스(클래스, 메서드, 테이블)를 매핑
- **온톨로지 2 — 업무 용어 사전**: 철강 도메인의 업무 용어를 별도로 관리

이 두 온톨로지를 **하나의 Neo4j 그래프 안에서 라벨로 분리하여 공존**시킨다. 이를 **3-Layer 구조**로 구현한다.

### 0-2. 3-Layer 구조

```
Layer 1 — Business (업무 용어 온톨로지)
  └── :Term, :TermCategory  (~20 노드)

Layer 2 — Process (업무처리기준서)
  └── :Step, :Standard, :Variable, :ErrorCode  (~50 노드)

Layer 3 — Code (소스 코드 온톨로지)
  └── :Class, :Method, :Table, :Column  (~300 노드, 자동 추출)
```

각 Layer는 다음 Bridge 관계로 연결된다:
- **Layer 1 → 2**: `(:Term)-[:REFERS_TO_PROCESS]->(:Step)`
- **Layer 2 → 3**: `(:Class)-[:IMPLEMENTS]->(:Step)`, `(:Method)-[:CALCULATES]->(:Step)`, `(:Table)-[:MAPS_TO_STANDARD]->(:Standard)`

### 0-3. 섹션3과의 관계

이 온톨로지는 섹션3의 3개 고정 Agent가 사용한다. 따라서 **Agent의 쿼리 패턴이 동작하도록 그래프를 구성**해야 한다. (자세한 Agent 명세는 `section3-rebuild-spec.md` 참고)

---

## 1. 작업 폴더 구조

`backend/modeling/` 아래에 다음 구조를 추가한다. **기존 modeling 코드는 건드리지 않는다.**

```
backend/modeling/
├── (기존 파일들 그대로)
└── ontology/                          ← 신규 추가
    ├── __init__.py
    ├── client.py                      ← Neo4j 연결 클라이언트
    ├── builders/
    │   ├── __init__.py
    │   ├── layer1_business.py         ← Layer 1 빌더
    │   ├── layer2_process.py          ← Layer 2 빌더
    │   ├── layer3_code.py             ← Layer 3 빌더 (jQAssistant 결과 정규화)
    │   ├── bridges.py                 ← Layer 간 Bridge 관계 빌더
    │   └── build_all.py               ← 전체 빌드 오케스트레이터
    ├── data/                          ← 시드 데이터 (Layer 1, 2)
    │   ├── terms.json
    │   ├── steps.json
    │   ├── standards.json
    │   ├── variables.json
    │   ├── error_codes.json
    │   └── bridges.json
    ├── schema/
    │   ├── constraints.cypher         ← 제약조건 + 인덱스
    │   └── reset.cypher               ← 전체 그래프 초기화 스크립트
    ├── queries/
    │   ├── __init__.py
    │   ├── impact_queries.py          ← Agent 1용 영향도 쿼리
    │   ├── test_data_queries.py       ← Agent 2용 테스트 데이터 쿼리
    │   ├── locator_queries.py         ← Agent 3용 자연어→소스 쿼리
    │   └── common_queries.py          ← 공통 유틸 쿼리
    ├── api/
    │   ├── __init__.py
    │   └── ontology_router.py         ← FastAPI 라우터
    └── tests/
        ├── __init__.py
        ├── test_client.py
        ├── test_builders.py
        └── test_queries.py
```

**시드 데이터는 `ontology-data-seed.md` 문서를 참고해서 만들 것.**

---

## 2. 환경 셋업

### 2-1. docker-compose.yml에 Neo4j 추가

```yaml
services:
  # ... 기존 서비스들
  
  neo4j:
    image: neo4j:5-community
    container_name: ontong-neo4j
    restart: unless-stopped
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-ontong_password_2026}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_memory_heap_initial__size=512m
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=512m
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./backend/modeling/ontology/schema/imports:/var/lib/neo4j/import
    networks:
      - ontong-network
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  neo4j_data:
  neo4j_logs:
```

### 2-2. .env.example 추가

```bash
# Neo4j (Section 2 Modeling Ontology)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=ontong_password_2026
```

### 2-3. Python 의존성

`pyproject.toml`에 추가:
```toml
[tool.poetry.dependencies]
neo4j = "^5.20.0"
```

---

## 3. Layer 1 — Business Ontology (업무 용어)

### 3-1. 노드 라벨

```
:Term
:TermCategory
```

### 3-2. 노드 속성

```cypher
(:Term {
  id: STRING (unique),       // 'term_edging'
  korean_name: STRING,        // 'Edging'
  english_name: STRING,       // 'Edging'
  aliases: [STRING],          // ['에징']
  category: STRING,           // 'concept' | 'weight' | 'dimension' | 'equipment' | 'error'
  description: STRING,
  created_at: DATETIME
})

(:TermCategory {
  id: STRING (unique),        // 'cat_weight'
  korean_name: STRING,        // '단중 계열'
  description: STRING
})
```

### 3-3. 관계

```cypher
(:Term)-[:BELONGS_TO]->(:TermCategory)
(:Term)-[:IS_A]->(:Term)
(:Term)-[:RELATED_TO]->(:Term)
(:Term)-[:SYNONYM_OF]->(:Term)
```

### 3-4. 카테고리 5종 (확정)

| 카테고리 ID | 한글명 |
|-----------|--------|
| cat_weight | 단중 계열 |
| cat_dimension | 치수 계열 |
| cat_equipment | 설비 계열 |
| cat_concept | 개념 계열 |
| cat_error | 에러 계열 |

### 3-5. 시드 데이터

`ontology-data-seed.md`의 Section A 참고. **19개의 Term을 처음에 입력**한다.

---

## 4. Layer 2 — Process Ontology (업무처리기준서)

### 4-1. 노드 라벨

```
:Step          // 태스크 흐름도의 각 Step
:Standard      // SC030~SC370 등 16종 기준
:Variable      // 입출력 변수
:ErrorCode     // DG320 등 에러
:TestPattern   // 테스트 케이스 메타 (Agent 2용)
```

### 4-2. 노드 속성

```cypher
(:Step {
  id: STRING (unique),         // 'step_2'
  step_number: INTEGER,        // 2
  korean_name: STRING,         // '1차 폭범위 계산'
  english_name: STRING,
  description: STRING,
  formula: STRING,             // 핵심 계산식 (참고)
  task_id: STRING,             // 'SD030_01'
  step_type: STRING            // 'calculation' | 'check' | 'loop' | 'branch'
})

(:Standard {
  id: STRING (unique),         // 'std_sc070'
  code: STRING (unique),       // 'SC070'
  korean_name: STRING,         // '열연Edging능력기준'
  english_name: STRING,
  category: STRING             // 'equipment_capability' | 'weight_constraint' | etc
})

(:Variable {
  id: STRING (unique),
  name: STRING,                // 'TargetWidth'
  korean_name: STRING,
  type: STRING,                // 'integer' | 'float' | 'range' | 'enum'
  unit: STRING,                // 'mm' | 'kg' | 'ratio'
  valid_range: STRING          // '[900, 1600]' (선택)
})

(:ErrorCode {
  code: STRING (unique),       // 'DG320'
  korean_message: STRING,
  cause: STRING,
  trigger_condition: STRING
})
```

### 4-3. 관계

```cypher
(:Step)-[:USES_STANDARD]->(:Standard)
(:Step)-[:REQUIRES_INPUT]->(:Variable)
(:Step)-[:PRODUCES_OUTPUT]->(:Variable)
(:Step)-[:PRECEDES]->(:Step)
(:Step)-[:TRIGGERS_ON_FAIL]->(:ErrorCode)
(:Step)-[:DEPENDS_ON {via_variable: STRING}]->(:Step)
(:Standard)-[:CONSTRAINS]->(:Variable)
```

### 4-4. SC 기준 16종 (확정)

| Code | 한글명 |
|------|------|
| SC030 | 연주설비사양기준 |
| SC040 | 열연설비사양기준 |
| SC060 | 코일외경제한기준 |
| SC070 | 열연Edging능력기준 |
| SC071 | 열연Edging규격그룹기준 |
| SC080 | 열연압연Min단중기준 |
| SC090 | 열연압연Max단중기준 |
| SC100 | 냉연최소단중하한기준 |
| SC110 | 임가공생산가능단중상한기준 |
| SC160 | 단중만족상수 |
| SC170 | 코일분할불가기준 |
| SC270 | 전강Slab설계제약기준 |
| SC290 | 특정고객사설계제한기준 |
| SC370 | 박판인도허용상한주문량보정기준 |

### 4-5. Step 12종 (확정 — Coil Slab 설계 기준)

`ontology-data-seed.md`의 Section B 참고.

---

## 5. Layer 3 — Code Ontology (소스 코드)

### 5-1. 자동 추출 (jQAssistant)

대상: `sample-repos/scm-demo/src/main/java/com/ontong/scm/`

`sample-repos/scm-demo/pom.xml`에 jQAssistant Maven 플러그인 추가:

```xml
<plugin>
    <groupId>com.buschmais.jqassistant</groupId>
    <artifactId>jqassistant-maven-plugin</artifactId>
    <version>2.4.0</version>
    <executions>
        <execution>
            <goals>
                <goal>scan</goal>
                <goal>analyze</goal>
            </goals>
        </execution>
    </executions>
    <configuration>
        <storeUri>bolt://localhost:7687</storeUri>
        <storeUsername>neo4j</storeUsername>
        <storePassword>${NEO4J_PASSWORD}</storePassword>
    </configuration>
</plugin>
```

### 5-2. 노드 라벨 (정규화 후)

```
:Class
:Method  
:Table
:Column
```

### 5-3. 정규화 규칙

jQAssistant가 만든 `:Type` 노드를 우리 스키마에 맞게 변환:

```cypher
// jQAssistant :Type 중 우리 도메인만 :Class로
MATCH (c:Type) WHERE c.fqn STARTS WITH 'com.ontong.scm'
SET c:Class
SET c.id = 'cls_' + replace(toLower(c.name), '.', '_')

// :Method에 ID 부여
MATCH (m:Method)<-[:DECLARES]-(c:Class)
SET m.id = 'method_' + toLower(c.name) + '_' + toLower(m.name)
```

### 5-4. 테이블/컬럼 추가

DB 스키마 정보(`information_schema`)에서 `TB_C40_050SC%` 패턴의 16개 테이블을 별도 추출하여 `:Table` 노드 생성.

테이블 시드 데이터는 `ontology-data-seed.md`의 Section C 참고.

### 5-5. 관계

```cypher
(:Class)-[:CONTAINS]->(:Method)
(:Method)-[:CALLS]->(:Method)
(:Method)-[:READS_FROM]->(:Table)
(:Method)-[:WRITES_TO]->(:Table)
(:Table)-[:HAS_COLUMN]->(:Column)
```

---

## 6. Layer 간 Bridge 관계

이게 온톨로지의 **핵심 가치**다.

### 6-1. Layer 1 → Layer 2

```cypher
(:Term)-[:REFERS_TO_PROCESS {role: STRING}]->(:Step)
// role: 'input' | 'output' | 'internal' | 'error_trigger'
```

매핑 데이터: `ontology-data-seed.md`의 Section D 참고.

### 6-2. Layer 2 → Layer 3

```cypher
(:Class)-[:IMPLEMENTS]->(:Step)
(:Method)-[:CALCULATES]->(:Step)
(:Table)-[:MAPS_TO_STANDARD]->(:Standard)
```

#### Method ↔ Step 매핑 전략

이 매핑이 **가장 어려운 부분**이다. 3단계로 처리한다:

**Stage 1**. **Naming Convention 패턴 매칭** (자동, 70%)
```python
PATTERNS = {
    r"calculate.*Thickness.*": 1,
    r"calculate.*PrimaryWidth.*": 2,
    r"calculate.*PrimaryLength.*": 3,
    r"calculate.*PrimaryWeight.*": 4,
    r"calculate.*SecondaryWeight.*Lower.*": 5,
    r"calculate.*SecondaryWeight.*Upper.*": 6,
    r"calculate.*Split.*Count.*": 7,
    r"calculate.*Target.*Weight.*": 8,
    r"calculate.*SecondaryWidth.*": 10,
    r"calculate.*Target.*Width.*": 12,
    r"calculate.*Target.*Width.*3[Pp]ass.*": 13,
    r"calculate.*Target.*Length.*": 14,
}
```

**Stage 2**. **Javadoc + LLM 추정** (반자동, 20%)
```python
async def map_method_to_step_with_llm(method_name, javadoc, signature):
    prompt = f"""
다음 Java 메서드가 Slab 설계 프로세스의 어느 Step에 해당하는지 판단하시오.

메서드 시그니처: {signature}
주석: {javadoc}

Step 목록 (12개):
1. 두께 계산
2. 1차 폭범위 계산
... (전체 12개)

응답: Step 번호만 (예: 2). 매핑 불가능하면 0.
"""
    # LLM 호출 후 정수로 변환
```

**Stage 3**. **수동 검증** (10%)
- LLM 추정값과 실제가 다를 수 있음
- 매핑 로그를 출력하여 사람이 확인할 수 있게

#### Form 클래스 ↔ SC 기준 자동 매핑

```cypher
// Form 클래스 명명 규칙: SD<카테고리>SpecForm 또는 SD<카테고리>RestricForm
MATCH (c:Class) 
WHERE c.name = 'SDHsmEdgingSpecForm'
MATCH (std:Standard {code: 'SC070'})
MERGE (c)-[:RELATES_TO_STANDARD]->(std)

// 16개 매핑 룰 일괄 작성
```

매핑 테이블은 `ontology-data-seed.md`의 Section E 참고.

---

## 7. 빌더 코드 인터페이스

각 빌더는 다음 인터페이스를 구현한다.

```python
# backend/modeling/ontology/builders/_base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class OntologyBuilder(ABC):
    """모든 빌더의 공통 인터페이스"""
    
    @abstractmethod
    def clear(self) -> None:
        """기존 데이터 삭제 (멱등성 보장)"""
        ...
    
    @abstractmethod
    def build(self) -> Dict[str, Any]:
        """빌드 실행. 반환값: {nodes_created, relationships_created, ...}"""
        ...
    
    @abstractmethod
    def verify(self) -> Dict[str, bool]:
        """빌드 결과 검증. 반환값: {'check_name': True/False}"""
        ...
```

### 7-1. 통합 빌드 (`build_all.py`)

```python
"""
전체 온톨로지 빌드 진입점
실행: python -m backend.modeling.ontology.builders.build_all
"""
from .layer1_business import Layer1Builder
from .layer2_process import Layer2Builder
from .layer3_code import Layer3Builder
from .bridges import BridgeBuilder

def build_all(skip_layer3: bool = False):
    """
    skip_layer3: Layer 3는 jQAssistant 실행 후에만 가능하므로 옵션
    """
    print("🏗️  온톨로지 전체 빌드 시작\n")
    
    # Layer 1
    Layer1Builder().build()
    
    # Layer 2  
    Layer2Builder().build()
    
    # Bridge (Layer 1 ↔ 2)
    BridgeBuilder().build_layer1_to_layer2()
    
    if not skip_layer3:
        # Layer 3 (정규화만 — 실제 추출은 jQAssistant)
        Layer3Builder().build()
        
        # Bridge (Layer 2 ↔ 3)
        BridgeBuilder().build_layer2_to_layer3()
    
    print("\n✅ 전체 빌드 완료")

if __name__ == "__main__":
    import sys
    skip = "--skip-layer3" in sys.argv
    build_all(skip_layer3=skip)
```

---

## 8. API 노출

### 8-1. shared/contracts/ontology.py 추가

`backend/shared/contracts/ontology.py`:

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
from enum import Enum

class Intent(str, Enum):
    QUERY = "query"
    SIMULATE = "simulate"
    IMPACT_ANALYSIS = "impact_analysis"
    OPTIMIZE = "optimize"
    EXPLAIN = "explain"

class Status(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NEED_MORE_INFO = "need_more_info"
    UNSUPPORTED = "unsupported"
    ERROR = "error"

class OntologyRequest(BaseModel):
    request_id: str
    intent: Intent
    natural_language: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None

class MissingInfoQuestion(BaseModel):
    field: str
    question: str
    input_type: Literal["select", "text", "date_range", "structured_form"]
    options: Optional[List[Dict[str, str]]] = None

class OntologyResponse(BaseModel):
    request_id: str
    status: Status
    confidence: float = 1.0
    result: Optional[Dict[str, Any]] = None
    missing_info: Optional[Dict[str, Any]] = None
    follow_up: Optional[Dict[str, Any]] = None
```

### 8-2. FastAPI 라우터

`backend/modeling/ontology/api/ontology_router.py`:

```python
from fastapi import APIRouter
from backend.shared.contracts.ontology import OntologyRequest, OntologyResponse
from ..queries import impact_queries, test_data_queries, locator_queries

router = APIRouter(prefix="/api/modeling/ontology", tags=["modeling-ontology"])

@router.post("/query", response_model=OntologyResponse)
async def query_ontology(req: OntologyRequest):
    """3개 Agent 모두의 진입점"""
    # intent에 따라 분기
    handlers = {
        "impact_analysis": impact_queries.analyze,
        "explain": locator_queries.locate,
        # ... Agent 2는 별도 엔드포인트
    }
    handler = handlers.get(req.intent)
    if not handler:
        return OntologyResponse(
            request_id=req.request_id,
            status="unsupported",
            result={"message": f"Intent {req.intent} not supported"}
        )
    return await handler(req)


@router.get("/graph/stats")
async def graph_stats():
    """온톨로지 통계 (디버깅/모니터링용)"""
    from ..client import get_client
    return get_client().get_stats()


@router.get("/term/search")
async def search_terms(q: str, limit: int = 10):
    """Term 검색 (자동완성용)"""
    from ..client import get_client
    return get_client().query("""
        MATCH (t:Term)
        WHERE t.korean_name CONTAINS $q 
           OR t.english_name CONTAINS $q
           OR ANY(alias IN t.aliases WHERE alias CONTAINS $q)
        RETURN t.id AS id, t.korean_name AS name, 
               t.english_name AS english, t.category AS category
        LIMIT $limit
    """, q=q, limit=limit)
```

### 8-3. main.py에 등록

```python
from backend.modeling.ontology.api.ontology_router import router as ontology_router
app.include_router(ontology_router)
```

---

## 9. 검증 시나리오 (필수 통과)

빌드 완료 후 다음 시나리오가 모두 동작해야 한다.

### 9-1. Layer 1 검증
```cypher
// 1. 19개 Term 생성됐는가
MATCH (t:Term) RETURN count(t)
// 기대: 19

// 2. 'Edging'이 검색되는가
MATCH (t:Term)
WHERE 'Edging' IN [t.korean_name, t.english_name] OR 'Edging' IN t.aliases
RETURN t.id
// 기대: 'term_edging'
```

### 9-2. Layer 2 검증
```cypher
// 3. SC070을 사용하는 Step
MATCH (s:Step)-[:USES_STANDARD]->(std:Standard {code: 'SC070'})
RETURN s.step_number, s.korean_name
// 기대: Step 2 (1차 폭범위), Step 13 (Target폭 재계산)
```

### 9-3. Bridge 검증
```cypher
// 4. 'Edging' 키워드 → 어느 Step?
MATCH (t:Term {korean_name: 'Edging'})-[:REFERS_TO_PROCESS]->(s:Step)
RETURN s.step_number, s.korean_name
// 기대: Step 2, Step 13
```

### 9-4. Layer 3 검증 (jQAssistant 실행 후)
```cypher
// 5. com.ontong.scm 패키지의 클래스 수
MATCH (c:Class) WHERE c.fqn STARTS WITH 'com.ontong.scm'
RETURN count(c)
// 기대: 1개 이상
```

### 9-5. 3-Layer 통합 쿼리 (최종 검증)
```cypher
// 6. 'Edging' 키워드 → 소스 위치까지
MATCH (t:Term {korean_name: 'Edging'})
      -[:REFERS_TO_PROCESS]->(s:Step)
      <-[:CALCULATES]-(m:Method)
      <-[:CONTAINS]-(c:Class)
RETURN c.name, m.name, s.step_number
// 기대: 1개 이상의 결과
```

이 6개 쿼리가 모두 결과를 내야 온톨로지 구축이 완료된 것으로 간주한다.

---

## 10. 작업 진행 순서

### Day 1: 인프라
1. docker-compose.yml에 Neo4j 추가
2. .env / .env.example 환경변수 추가
3. pyproject.toml에 neo4j 의존성 추가
4. `backend/modeling/ontology/` 폴더 구조 생성
5. `client.py` 작성 + 연결 테스트

### Day 2: Layer 1
1. `data/terms.json` 입력 (시드 문서 참고)
2. `builders/layer1_business.py` 작성
3. 빌드 실행 + Neo4j Browser에서 시각 확인
4. 검증 쿼리 1, 2 통과

### Day 3: Layer 2 (1)
1. `data/steps.json` 입력
2. `data/standards.json` 입력
3. `data/variables.json` 입력
4. `builders/layer2_process.py` 작성
5. 빌드 실행 + 검증 쿼리 3 통과

### Day 4: Layer 2 (2) + Bridge
1. `data/error_codes.json` 입력
2. `data/bridges.json` 입력
3. `builders/bridges.py` 작성 (Layer 1 → 2)
4. 검증 쿼리 4 통과

### Day 5: Layer 3 (1)
1. `sample-repos/scm-demo/pom.xml` 수정
2. `mvn jqassistant:scan` 실행
3. Neo4j Browser에서 자동 추출 결과 확인
4. `builders/layer3_code.py` 작성 (정규화)

### Day 6: Layer 3 (2) — Method ↔ Step 매핑
1. Naming Convention 패턴 매칭 (Stage 1)
2. LLM 보조 매핑 (Stage 2)
3. 수동 검증 (Stage 3)
4. 검증 쿼리 5 통과

### Day 7: API + 최종 검증
1. `shared/contracts/ontology.py` 작성
2. `api/ontology_router.py` 작성
3. `main.py`에 라우터 등록
4. curl로 API 동작 확인
5. 검증 쿼리 6 통과 → **온톨로지 구축 완료**

---

## 11. 산출물 체크리스트

이 명세서대로 구현하면 다음이 만들어져야 한다:

- [ ] Neo4j 컨테이너 동작
- [ ] `backend/modeling/ontology/` 모듈 전체
- [ ] Layer 1: 19 Term, 5 Category, 9 관계
- [ ] Layer 2: 12 Step, 14 Standard, 10 Variable, 1 ErrorCode
- [ ] Layer 1↔2 Bridge: 14 REFERS_TO_PROCESS 관계
- [ ] Layer 3: jQAssistant 자동 추출 + 정규화 완료
- [ ] Layer 2↔3 Bridge: Method ↔ Step 매핑
- [ ] `shared/contracts/ontology.py`
- [ ] `POST /api/modeling/ontology/query` 엔드포인트
- [ ] `GET /api/modeling/ontology/graph/stats` 엔드포인트
- [ ] `GET /api/modeling/ontology/term/search` 엔드포인트
- [ ] 검증 쿼리 6개 모두 통과

---

## 12. 주의사항

- **기존 Section 2 코드는 건드리지 말 것**. `backend/modeling/`의 기존 분석 콘솔, 매핑 워크벤치, 시뮬레이션 패널은 그대로 유지.
- **`backend/shared/contracts/ontology.py` 추가**는 다른 섹션에 영향을 주므로 신중하게.
- **Neo4j 비밀번호**는 반드시 환경변수에서 받을 것. 하드코딩 금지.
- **시드 데이터(JSON)는 별도 파일**로 관리. Python 코드 안에 데이터 박지 말 것.
- **모든 빌더는 멱등성 보장**: 두 번 실행해도 같은 결과가 나와야 함.
