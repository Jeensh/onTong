# onTong 3-Section Platform Architecture v2

> 2026-04-01 | 아키텍처 설계 + 3관점 리뷰 반영 총정리
> 리뷰어: Systems Architect, Developer C (Section 3), Domain Expert (Manufacturing SCM)

---

## 1. 플랫폼 비전

Wiki 기반 AI 에이전트 플랫폼(onTong)을 **제조 SCM 준자동화 플랫폼**으로 확장.
3개 섹션으로 구성하되, 각 섹션은 독립 에이전트 + 독립 UI + 독립 데이터 소스를 가짐.

```
┌──────────────────────────────────────────────────────────────┐
│                         사용자                                │
│         Wiki 관리자 / IT 담당자 / SCM 현업 사용자              │
└──────┬──────────────────┬──────────────────┬─────────────────┘
       │                  │                  │
  ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
  │ Section1│       │ Section2│       │ Section3│
  │  Wiki   │       │Modeling │       │  Sim    │
  │ (문서)   │       │(코드/도메인)│    │(비즈니스)│
  └────┬────┘       └────┬────┘       └────┬────┘
       │                  │                  │
  WikiAgent          ModelingAgent      SimAgent
  (문서 RAG,          (코드추적,         (시나리오설계,
   충돌감지)           영향분석,          결과해석,
                      매핑관리)          What-if)
       │                  │                  │
  ChromaDB            Neo4j              섹션2 API
  (문서 벡터)          (온톨로지+코드)      호출
```

---

## 2. 섹션 역할 정의

### Section 1: Wiki (기존, 안정)
- **사용자**: 문서 관리자, 전 직원
- **기능**: 문서 CRUD, AI Q&A, 충돌 감지/해결, 메타데이터 태깅
- **에이전트**: WikiAgent — 문서 RAG, conflict_check, search 스킬
- **데이터**: ChromaDB (문서 벡터), 파일시스템 (마크다운)
- **상태**: 177 tests, TypeScript 빌드 정상, 운영 가능

### Section 2: Source-Domain Modeling (팀 리더 담당)
- **사용자**: IT 담당자
- **기능**:
  - 레거시 코드 분석 및 온톨로지 매핑 관리
  - 코드 변경 영향 분석 (온톨로지 그래프 순회)
  - 비즈니스 시뮬레이션 실행 엔진 (파라메트릭 모델)
  - 샌드박스 코드 실행 (제한된 범위)
- **에이전트**: ModelingAgent — ontology_query, code_trace, impact_analysis 스킬
- **데이터**: Neo4j (온톨로지 + 코드 엔티티 + 매핑)
- **외부 도구**: tree-sitter, ast-grep, Zoekt

### Section 3: Simulation UI (개발자 C 담당)
- **사용자**: SCM 현업 사용자 (비기술)
- **기능**:
  - 도메인 용어로 시뮬레이션 시나리오 설계
  - 섹션 2 API를 호출하여 시뮬레이션 실행
  - 결과를 다양한 형태로 동적 시각화
  - 시나리오 비교, 이력 관리
- **에이전트**: SimAgent — scenario_design, result_explain, what_if 스킬
- **데이터**: 섹션 2 API 호출 (자체 실행 엔진 없음) + 결과 저장소
- **UI**: 채팅 + 대시보드 하이브리드 (Chat-only 아님)

### 섹션 간 관계
```
Section 3 ──(API 호출)──▶ Section 2 ──(실행+결과)──▶ Section 3
Section 1 ◀──(간접 참조)──▶ Section 2  (shared contract 통해)
Section 1 ◀────(없음)────▶ Section 3  (직접 통신 없음)
```

---

## 3. "시뮬레이션"의 정의 — 2종 분리

리뷰에서 가장 중요하게 지적된 점: 모든 시뮬레이션 ≠ 코드 실행.

### 종류 1: 코드 영향 분석 (Impact Analysis)
- **대상**: IT 담당자
- **방법**: 온톨로지 그래프 순회 (BFS), 결정론적
- **실행 위치**: 섹션 2 내부
- **데이터 필요**: 코드 + 온톨로지만 (외부 데이터 불필요)
- **예시**: "이 메서드를 바꾸면 어떤 도메인 기능이 영향받나?"

### 종류 2: 비즈니스 시뮬레이션 (Parametric Simulation)
- **대상**: SCM 현업 사용자
- **방법**: 수학적/통계적 모델 (Monte Carlo 등), 코드 실행이 아님
- **실행 위치**: 섹션 2 실행 엔진 → 섹션 3이 요청
- **데이터 필요**: 시뮬레이션 모델 + 운영 데이터 (ERP/MES)
- **예시**: "안전재고 공식을 바꾸면 결품률이 어떻게 되나?"

### 코드 샌드박스 실행 (제한적)
- **범위**: 독립 실행 가능한 코드 조각만 (전체 시스템이 아닌 함수/모듈 단위)
- **용도**: 영향 분석의 보조 수단
- **보안**: gVisor 또는 Kata Containers, 네트워크 격리, 리소스 제한 필수

---

## 4. 온톨로지 아키텍처

### 4-1. SCOR + ISA-95 하이브리드 (ISA-95 단독 X)

ISA-95는 공장 내부(Make)만 커버. SCM 전체 범위에는 SCOR 필요.

```
SCOR (SCM 전체)
├── Plan: 수요 예측, 공급 계획, 재고 정책
├── Source: 공급업체 관리, 구매, 입고
├── Make: 생산 (← ISA-95가 여기를 상세화)
│   ├── Production Order, Work Order
│   ├── Equipment, Material Consumption
│   └── Quality (IQC, PQC, OQC)
├── Deliver: 물류, 배송, 납기 관리
└── Return: 반품, 리콜
```

### 4-2. 3-Layer 구조 (유지)

```
Layer 1: 도메인 온톨로지 (SCOR + ISA-95)
  - 수동 설계, 도메인 전문가 검증
  - LLM이 건드리지 않음

Layer 2: 코드 엔티티 그래프
  - tree-sitter + AST 자동 생성, 100% 정확
  - 함수, 클래스, DB 테이블, API 엔드포인트

Layer 3: 매핑 레이어 (도메인 ↔ 코드)
  - 각 매핑에 confidence score + 승인 상태
  - LLM이 제안, 전문가가 승인
```

### 4-3. 누락 도메인 개념 보완

현재 계획에 빠진 제조 SCM 필수 개념:

| 개념 | SCOR 영역 | 시뮬레이션 필요도 |
|------|----------|----------------|
| 품질 관리 (수율, 불량률) | Make | 높음 — 수율이 재고/생산계획에 직접 영향 |
| 규제 준수 (GMP, IATF) | 전체 | 중간 — 공정 변경 시 재인증 비용/기간 |
| 다공장 조율 | Plan, Make | 높음 — 공장 간 생산 분배 시나리오 |
| 계절 수요 패턴 | Plan | 높음 — 가장 빈번한 what-if |
| 공급업체 리스크 | Source | 높음 — C-level 최대 관심사 |

---

## 5. Dual-Path 쿼리 (유지, 임계값 수정)

```
사용자 질의
  ├── Path A: 그래프 직접 순회 (결정론적, 항상 동일 결과)
  │   승인된 매핑만 사용 (confidence ≥ 0.95)
  │
  └── Path B: LLM 추론 (유연, 검증 필요)
      confidence 계산 후 표시

결과: Path A 우선 표시, Path B는 보조
```

### 매핑 신뢰도 임계값 (제조업 수정)

| 범위 | 처리 | 근거 |
|------|------|------|
| ≥ 0.95 | 자동 승인 | 거의 동일 명칭/패턴 |
| 0.80-0.95 | IT 전문가 리뷰 | 코드 구조 이해 필요 |
| 0.60-0.80 | IT + 비즈니스 합동 리뷰 | 도메인 의미 확인 필요 |
| < 0.60 | 자동 거부 | 수동 매핑 요청 |

### Confidence 계산 (4-factor)
```
score = 0.3 × self_consistency    (5회 샘플링 합의율)
      + 0.3 × ast_verification    (AST 존재+관련성 확인)
      + 0.2 × embedding_sim       (도메인 용어↔코드 유사도)
      + 0.2 × body_relevance      (함수 내용 관련성)
```

---

## 6. 모듈 구조

### 6-1. 백엔드

```
backend/
├── shared/
│   ├── agent_framework/          # 에이전트 공통 뼈대
│   │   ├── base_agent.py         # 인터페이스(Protocol) 정의
│   │   ├── sse_protocol.py       # SSE 와이어 포맷만 정의
│   │   └── session.py            # 세션 관리 최소 구현
│   │   # ※ 구현이 아닌 인터페이스 중심. 삭제 후 50줄로 대체 가능해야 함
│   │
│   ├── contracts/                # 섹션 간 API 계약
│   │   ├── simulation.py         # 섹션 2↔3 시뮬레이션 계약 (typed)
│   │   └── README.md             # 계약 변경 규칙
│   │
│   ├── schemas.py                # 공통 Pydantic 모델
│   ├── auth.py, config.py, db.py
│   └── observability.py          # 공통 request_id, 구조화 로깅
│
├── wiki/                         # Section 1
│   ├── api/
│   ├── agent/                    # WikiAgent (현재 rag_agent 이동)
│   ├── application/
│   └── infrastructure/           # ChromaDB
│
├── modeling/                     # Section 2
│   ├── api/
│   │   ├── router.py
│   │   ├── agent.py              # POST /agent/chat
│   │   ├── ontology.py           # 온톨로지 CRUD
│   │   ├── code_graph.py         # 코드 그래프 조회
│   │   ├── mapping.py            # 매핑 관리 + 승인
│   │   └── simulation.py         # 비동기 job 엔드포인트
│   │
│   ├── agent/
│   │   ├── modeling_agent.py
│   │   └── skills/
│   │       ├── ontology_query.py
│   │       ├── code_trace.py
│   │       ├── impact_analysis.py
│   │       └── mapping_suggest.py
│   │
│   ├── ontology/                 # SCOR + ISA-95 스키마
│   │   ├── schema.py
│   │   ├── repository.py
│   │   └── validators.py
│   │
│   ├── code_analysis/
│   │   ├── parser.py             # tree-sitter
│   │   ├── graph_builder.py      # 코드 → Neo4j
│   │   ├── ast_diff.py           # Git diff → 매핑 재검증
│   │   └── indexer.py            # Zoekt 연동
│   │
│   ├── mapping/
│   │   ├── engine.py             # 매핑 생성 (LLM + 검증)
│   │   ├── confidence.py         # 4-factor scoring
│   │   ├── validator.py          # AST 기반 자동 검증
│   │   └── review_queue.py       # 전문가 리뷰 큐
│   │
│   ├── simulation/               # 비즈니스 시뮬레이션 엔진
│   │   ├── executor.py           # 파라메트릭 모델 실행
│   │   ├── job_queue.py          # 비동기 job 관리
│   │   ├── formatter.py          # OutputFormat별 결과 가공
│   │   ├── sandbox.py            # 코드 샌드박스 (제한적)
│   │   └── templates/            # SCM 시뮬레이션 모델
│   │
│   ├── infrastructure/
│   │   ├── neo4j_client.py
│   │   ├── zoekt_client.py
│   │   └── docker_client.py
│   │
│   └── data/                     # 데이터 통합 (Phase 3)
│       ├── connectors/           # ERP/MES/WMS 커넥터
│       ├── catalog.py            # 데이터 카탈로그
│       └── snapshot.py           # 시뮬레이션용 데이터 스냅샷
│
├── simulation/                   # Section 3
│   ├── api/
│   │   ├── router.py
│   │   ├── agent.py              # POST /agent/chat
│   │   └── scenarios.py          # 시나리오 CRUD + 이력
│   │
│   ├── agent/
│   │   ├── sim_agent.py
│   │   └── skills/
│   │       ├── scenario_design.py
│   │       ├── result_explain.py
│   │       └── what_if.py
│   │
│   ├── visualization/            # 결과 시각화 어댑터
│   │   ├── chart_adapter.py
│   │   ├── table_adapter.py
│   │   └── gantt_adapter.py
│   │
│   ├── storage/                  # 시뮬레이션 결과 저장소
│   │   ├── result_store.py       # 결과 persist
│   │   └── scenario_store.py     # 시나리오 버전 관리
│   │
│   ├── mock/                     # 섹션 2 연동 전 독립 개발용
│   │   ├── parametric_mock.py    # 파라미터 기반 동적 mock (정적 JSON X)
│   │   └── scenarios/
│   │
│   └── client/
│       ├── modeling_client.py    # Protocol 기반 (mock/real 공통 인터페이스)
│       └── config.py
│
└── main.py                       # 3개 라우터 통합
```

### 6-2. 프론트엔드

```
frontend/src/
├── app/
│   ├── (wiki)/                   # Section 1 페이지
│   ├── (modeling)/               # Section 2 페이지
│   └── (simulation)/             # Section 3 페이지
│       └── simulation/
│           └── page.tsx          # 하이브리드 레이아웃:
│                                 # 좌측 시나리오목록 + 중앙 대시보드 + 우측 채팅
│
├── components/
│   ├── shared/
│   │   ├── ChatShell.tsx         # 채팅 UI 껍데기 (AICopilot에서 추출)
│   │   ├── MessageBubble.tsx
│   │   └── StreamingHandler.tsx
│   ├── wiki/
│   │   └── WikiCopilot.tsx       # ChatShell + wiki 확장
│   ├── modeling/
│   │   └── ModelingCopilot.tsx   # ChatShell + 코드뷰어 + 그래프뷰
│   └── simulation/
│       ├── SimCopilot.tsx        # ChatShell + 결과해석
│       ├── ScenarioDashboard.tsx # 결과 대시보드 (차트/테이블/Gantt)
│       ├── ParameterForm.tsx     # 시나리오 파라미터 입력 폼
│       └── CompareView.tsx       # 시나리오 A vs B 비교
│
└── lib/
    ├── shared/                   # SSE 클라이언트, 공통 훅
    ├── wiki/
    ├── modeling/
    └── simulation/
```

---

## 7. 섹션 2↔3 API 계약 (Typed)

### 7-1. 시나리오별 타입 파라미터

```python
# shared/contracts/simulation.py

class OutputFormat(str, Enum):
    TABLE = "table"
    CHART_LINE = "chart_line"
    CHART_BAR = "chart_bar"
    GANTT = "gantt"
    GRAPH = "graph"
    RAW_JSON = "raw_json"

# 시나리오별 typed 파라미터
class DemandForecastParams(BaseModel):
    product_id: str
    forecast_horizon_days: int = 90
    confidence_level: float = 0.95
    include_seasonality: bool = True

class InventoryOptimizeParams(BaseModel):
    warehouse_id: str
    target_service_level: float = 0.98
    safety_stock_method: Literal["fixed", "dynamic", "demand_driven"]
    holding_cost_per_unit: float

class LeadTimeAnalysisParams(BaseModel):
    supplier_id: str
    delay_days: int
    affected_materials: list[str] = []

# Discriminated union
ScenarioParams = Annotated[
    DemandForecastParams | InventoryOptimizeParams | LeadTimeAnalysisParams,
    Field(discriminator="scenario_type")
]
```

### 7-2. 비동기 Job 라이프사이클

```python
class SimulationJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SimulationError(BaseModel):
    code: str             # "AMBIGUOUS_PARAMETER", "SANDBOX_LIMIT", etc.
    message: str
    details: dict | None = None
    retryable: bool = False

class SimulationRequest(BaseModel):
    scenario_type: str
    parameters: ScenarioParams
    output_formats: list[OutputFormat]
    timeout_sec: int = 120

class SimulationResult(BaseModel):
    outputs: dict[OutputFormat, ChartOutput | TableOutput | GanttOutput]  # typed
    execution_time_ms: int
    uncertainty_range: dict | None = None    # 불확실성 범위
    metadata: dict = {}

class SimulationJob(BaseModel):
    job_id: str
    status: SimulationJobStatus
    created_at: datetime
    estimated_duration_sec: int | None = None
    progress_pct: float | None = None
    result: SimulationResult | None = None
    error: SimulationError | None = None
```

### 7-3. 비동기 엔드포인트

```
POST   /api/modeling/simulation/scenario     → SimulationJob (즉시 반환)
GET    /api/modeling/simulation/job/{id}      → SimulationJob (폴링)
SSE    /api/modeling/simulation/job/{id}/stream → 진행률 스트리밍
DELETE /api/modeling/simulation/job/{id}      → 취소
GET    /api/modeling/simulation/scenarios     → 사용 가능한 시나리오 타입 목록
```

### 7-4. 출력 타입도 명시

```python
class ChartSeries(BaseModel):
    name: str
    data: list[float]

class ChartOutput(BaseModel):
    chart_type: Literal["line", "bar", "scatter"]
    x_label: str
    y_label: str
    x_data: list[str | float]
    series: list[ChartSeries]

class ColumnDef(BaseModel):
    key: str
    label: str
    type: Literal["string", "number", "date", "percent"]

class TableOutput(BaseModel):
    columns: list[ColumnDef]
    rows: list[dict]

class GanttTask(BaseModel):
    id: str
    name: str
    start: datetime
    end: datetime
    progress: float = 0.0
    dependencies: list[str] = []

class GanttOutput(BaseModel):
    tasks: list[GanttTask]
```

---

## 8. 협업 구조

### 8-1. 브랜치 전략: Trunk-Based Development

```
main (항상 배포 가능, 보호됨)
├── feat/wiki-xxx          (수명 1-2일, 머지 후 삭제)
├── feat/modeling-xxx
└── feat/simulation-xxx
```

- 하루 1회 이상 main에서 rebase
- PR 머지 전 CI 통과 + 최소 1명 리뷰
- shared/ 변경 시 3명 전원 리뷰

### 8-2. 모듈 경계 강제

```toml
# pyproject.toml
[tool.importlinter]
root_packages = ["backend"]

[[tool.importlinter.contracts]]
name = "Section independence"
type = "independence"
modules = ["backend.wiki", "backend.modeling", "backend.simulation"]

[[tool.importlinter.contracts]]
name = "Sections depend on shared only"
type = "layers"
layers = [
    "backend.wiki | backend.modeling | backend.simulation",
    "backend.shared",
]
```

### 8-3. CODEOWNERS

```
# .github/CODEOWNERS
/backend/wiki/              @team-lead
/backend/modeling/          @team-lead
/backend/simulation/        @developer-c
/backend/shared/            @team-lead @developer-c
/frontend/src/components/shared/  @team-lead @developer-c
```

### 8-4. 섹션 간 통신 방식

- 현재: 같은 프로세스 내 Python Protocol (모듈러 모노리스)
- 미래: 필요 시 HTTP 분리 (서비스 분리)
- 솔직하게 인정: 지금은 서비스가 아닌 모노리스. 계약은 Python Protocol로 정의하되, 나중에 HTTP로 전환 가능하도록 설계

```python
# shared/contracts/simulation.py
class SimulationExecutor(Protocol):
    async def submit_job(self, request: SimulationRequest) -> SimulationJob: ...
    async def get_job(self, job_id: str) -> SimulationJob: ...
    async def cancel_job(self, job_id: str) -> bool: ...
    async def stream_progress(self, job_id: str) -> AsyncGenerator[SimulationStreamEvent, None]: ...

# Section 3 uses this Protocol — mock or real, same interface
```

---

## 9. 보안 (Section 2 샌드박스)

Section 2는 사실상 **원격 코드 실행 서비스**. 보안 설계 필수.

| 항목 | 요구사항 |
|------|---------|
| 컨테이너 격리 | gVisor 또는 Kata Containers (Docker 단독 X) |
| 네트워크 | 샌드박스에서 외부 접근 차단 (Neo4j, 프로덕션 서비스 포함) |
| 리소스 제한 | CPU/Memory/PID/Disk cgroup 제한 |
| 실행 시간 | hard kill 타임아웃 (기본 120초) |
| 출력 크기 | 결과 크기 상한 (OOM 방지) |
| 패치 허용 범위 | 수정 가능 파일/모듈 allowlist |
| 감사 로그 | 누가, 언제, 무엇을 실행했는지 기록 |
| 컨테이너 수명 | 요청 완료 시 즉시 삭제 (상태 잔류 방지) |
| 프롬프트 인젝션 | Section 3 → Section 2 패치 요청 독립 검증 |

---

## 10. 옵저빌리티

```
모든 섹션 공통:
├── 구조화 로깅 (JSON, request_id 포함)
├── OpenTelemetry 트레이싱 (Section 3 → Section 2 → Neo4j 추적)
├── 메트릭 (요청 지연, job queue 깊이, 샌드박스 사용률)
└── 알림 (실패율 임계값 초과 시)
```

request_id는 `shared/observability.py`에서 미들웨어로 주입.
3명 팀이므로 Datadog 수준은 불필요 — 구조화 로그 + 트레이스 ID면 충분.

---

## 11. 위키 마이그레이션 전략

현재 `backend/application/` → `backend/wiki/` 이동 시:

1. **독립 커밋**: 로직 변경 없이 `git mv`만 수행
2. **import 호환 shim**: `backend/application/__init__.py`에서 re-export + deprecation warning
3. **테스트 전수 실행**: 177개 테스트 전체 통과 확인
4. **CI/CD 경로 업데이트**: 테스트 수집, 커버리지, 린트 경로
5. **shim 제거**: 1스프린트 후 호환 shim 삭제

---

## 12. 데이터 통합 (Phase 3 범위)

현재 아키텍처에서 가장 큰 구조적 결함: **운영 데이터 연결 부재**.

Phase 3에서 추가할 `modeling/data/`:

| 컴포넌트 | 역할 |
|---------|------|
| ERP/MES/WMS 커넥터 | 읽기 전용 데이터 추출 |
| 데이터 카탈로그 | 어떤 데이터가 어디에, 얼마나 신선한지 |
| 데이터 익명화 | 시뮬레이션용 프로덕션 데이터 마스킹 |
| 스냅샷 관리 | 시뮬레이션 시점 데이터 상태 고정 |

코드 + 온톨로지만으로는 껍데기. 시뮬레이션의 가치는 데이터 현실성에서 나옴.

---

## 13. 실행 순서 (Phase 계획)

```
Phase 0: 공유 인프라 구축
  ├── shared/ 추출 (agent_framework Protocol, contracts, observability)
  ├── backend/wiki/ 마이그레이션 (기존 코드 이동, 테스트 유지)
  ├── import-linter + CODEOWNERS 설정
  ├── simulation_contract.py typed 계약 합의 (Day 1 산출물)
  ├── modeling/ 스캐폴딩 + simulation/ 스캐폴딩
  └── Neo4j docker-compose 추가

Phase 1: 코드 영향 분석 MVP (Section 2 코어) ★ 데이터 없이 가능
  ├── tree-sitter 파싱 → 코드 엔티티 그래프 (Neo4j)
  ├── SCOR + ISA-95 하이브리드 온톨로지 스키마 설계
  ├── 코드 ↔ 도메인 매핑 엔진 (LLM 제안 + AST 검증 + 전문가 리뷰)
  ├── "이 메서드 바꾸면 어떤 도메인 기능이 영향?" 질의
  ├── Wiki 런북 자동 링크
  └── IT 팀이 매핑 검증 → Phase 2 신뢰 기반 확보

Phase 2: 비즈니스 시뮬레이션 연동 (Section 2 + 3)
  ├── 파라메트릭 시뮬레이션 엔진 (비동기 job queue)
  ├── Section 3 UI (시나리오 설계 + 대시보드 + 채팅)
  ├── Parametric mock → 실제 연동 전환
  ├── 시나리오 버전 관리 + 결과 저장소
  └── 시뮬레이션 결과에 불확실성 범위 포함

Phase 3: 데이터 통합 + 운영 연동
  ├── ERP/MES/WMS 커넥터 (읽기 전용)
  ├── 데이터 카탈로그 + 익명화 파이프라인
  ├── 모니터링 연동 (장애 대응 진입점)
  ├── 변경 이력 상관분석 (배포↔장애 매칭)
  └── 장애 이력 DB + 에스컬레이션 경로
```

---

## 14. Day 1 체크리스트

Phase 0 시작 전 반드시 확정할 것:

- [ ] SCOR + ISA-95 하이브리드 온톨로지 초안 스키마 (Neo4j 노드/관계 타입)
- [ ] simulation_contract.py typed 계약 (첫 시나리오: demand_forecast)
- [ ] BaseAgent → Protocol 기반 인터페이스 확정 (기존 AgentPlugin 참고)
- [ ] ChatShell 추출 범위 확정 (기존 AICopilot.tsx에서 어디까지)
- [ ] 비동기 job queue 기술 선택 (Celery vs Dramatiq vs asyncio Queue)
- [ ] 샌드박스 격리 수준 확정 (gVisor vs Kata vs Docker+seccomp)
- [ ] 디렉토리 구조 + 네이밍 규칙 + import 규칙 3명 합의 문서

---

## 15. 리스크 매트릭스

| 우선순위 | 리스크 | 영향 | 완화 |
|---------|--------|------|------|
| P0 | 데이터 통합 없는 시뮬레이션 = 빈 껍데기 | 사용 불가 | Phase 순서로 완화: 먼저 영향분석(데이터 불필요) |
| P0 | 타입 없는 계약 → 통합 시 전면 재작업 | 개발 기간 2배 | Day 1 typed 계약 |
| P0 | 동기 시뮬레이션 → 시스템 먹통 | 운영 불가 | 비동기 job queue Day 1 |
| P1 | 온톨로지 스키마 미확정 → Neo4j 코드 계속 변경 | 개발 지연 | Phase 1 시작 전 스키마 리뷰 |
| P1 | Neo4j SPOF | 전체 장애 | 읽기 캐시 + degraded mode |
| P1 | shared/ 블랙홀 | 아키텍처 부식 | Protocol 중심 + 파일 수 상한 CI 체크 |
| P2 | 마이그레이션 시 177 테스트 깨짐 | 1-2일 낭비 | 독립 커밋 + shim |
| P2 | 매핑 부실화 (코드 변경 후 미업데이트) | 오진단 | CI에 매핑 재검증 단계 |

---

## 16. 핵심 설계 원칙 요약

1. **시뮬레이션 ≠ 코드 실행**. 영향분석(그래프)과 비즈니스시뮬(수학모델)은 별개.
2. **에이전트는 섹션별 독립**. 공유하는 것은 프레임워크(Protocol)뿐.
3. **결정론적 경로 우선, LLM은 보조**. 같은 질문에 항상 같은 핵심 답변.
4. **타입 있는 계약 먼저, 코드는 나중**. dict 계약은 계약이 아님.
5. **모노리스를 솔직하게**. 지금은 같은 프로세스, 나중에 분리.
6. **데이터 없이 가치 주는 것부터** (Phase 1: 코드 영향 분석).
7. **코드 분석은 실마리 제공, 확정은 인간 전문가**. Human-in-the-loop 필수.
