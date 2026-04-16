# Section 3 (Simulation) 개발 가이드

> **담당 영역**: Section 3 — 비즈니스 시뮬레이션 (시나리오 설계 / 실행 / 시각화)  
> **대상 사용자**: SCM 현업 담당자  
> **현재 상태**: Phase 1 + Phase 1.5 완료. Mock 데이터 기반 동작 중. Section 2 연동 대기.  
> **최종 업데이트**: 2026-04-16

---

## 1. 프로젝트 개요

onTong은 3개 섹션으로 구성된 플랫폼입니다:

| 섹션 | 용도 | 상태 |
|------|------|------|
| **Section 1 (Wiki)** | 문서 관리 + AI Q&A | 완성 (운영 중) |
| **Section 2 (Modeling)** | 코드매핑 / 온톨로지 / 영향분석 | (개발 예정) |
| **Section 3 (Simulation)** | 시뮬레이션 시나리오 설계 / 시각화 | **Phase 1+1.5 완료 (Mock 기반)** |

세 섹션이 하나의 애플리케이션에서 함께 동작합니다. Wiki 기능은 이미 완성되어 있으므로 Simulation 개발 중에도 Wiki를 동시에 사용할 수 있습니다.

---

## 2. 환경 세팅 및 애플리케이션 실행

### 2-1. 사전 요구사항

| 구분 | 버전 | 확인 명령어 |
|------|------|-------------|
| **Python** | 3.10+ | `python3 --version` |
| **Node.js** | 20+ | `node --version` |
| **Docker Desktop** | 최신 | `docker --version` |
| **Poetry** | 2.x | `poetry --version` (없으면 `pip install poetry`) |

> **주의**: macOS 기본 Python(3.9)으로는 설치가 안 됩니다. `python3.13`이나 `python3.12` 경로를 확인해서 venv를 만드세요.

### 2-2. 최초 설정

```bash
# 1. 프로젝트 클론
git clone https://github.com/Jeensh/onTong.git
cd onTong

# 2. Python 가상환경 생성 (반드시 3.10 이상 경로 지정)
python3.13 -m venv venv          # 또는: python3.12 -m venv venv
source venv/bin/activate
python --version                  # 3.10+ 확인

# 3. Python 의존성 설치
pip install poetry
poetry install                    # pyproject.toml 기반 전체 설치

# 4. 프론트엔드 의존성 설치
cd frontend
npm install
cd ..

# 5. 환경변수 설정
cp .env.example .env
# 필요 시 .env를 편집하여 LLM 키 등 설정 (없어도 Wiki/Simulation Mock은 동작)
```

### 2-3. 서비스 실행 순서

Docker Desktop을 먼저 실행한 뒤, 아래 순서대로 진행합니다:

```bash
# 1. 인프라 (ChromaDB + Redis)
docker compose up -d chroma redis
# 정상 확인: curl http://localhost:8000/api/v1/heartbeat

# 2. 백엔드 (포트 8001)
source venv/bin/activate
python -m backend.main
# 정상 확인: curl http://localhost:8001/health

# 3. 프론트엔드 (포트 3000, 새 터미널에서)
cd frontend
npm run dev
# 정상 확인: 브라우저에서 http://localhost:3000 접속
```

> **포트 충돌 시**: 3000 포트를 다른 서비스가 사용 중이면 `PORT=3001 npm run dev`로 실행하세요.

### 2-4. 정상 동작 확인 체크리스트

```bash
# 1. 백엔드 헬스
curl http://localhost:8001/health
# → "status": "healthy" 확인

# 2. Section 3 헬스
curl http://localhost:8001/api/simulation/health
# → "section": "simulation", "mock_mode": true 확인

# 3. 시나리오 목록
curl http://localhost:8001/api/simulation/scenarios
# → 3개 시나리오 (수요 예측, 재고 최적화, 리드타임 분석) 확인

# 4. 시뮬레이션 실행 테스트
curl -X POST http://localhost:8001/api/simulation/scenario \
  -H "Content-Type: application/json" \
  -d '{"scenario_type":"demand_forecast","parameters":{"scenario_type":"demand_forecast","product_id":"PROD-001"},"output_formats":["chart_line","table"]}'
# → job_id, status=completed, result.outputs 확인

# 5. 브라우저 확인
# http://localhost:3000 → 상단 [Simulation] 탭 클릭 → 좌측에 시나리오 목록 표시
# [Wiki] 탭도 클릭해서 기존 Wiki 기능이 정상 동작하는지 확인
```

---

## 3. 작업 폴더 구조

### 3-1. Section 3 백엔드 (`backend/simulation/`)

이 디렉토리 아래에서 자유롭게 작업하시면 됩니다. API 추가, 구조 변경, 새 모듈 생성 모두 자유입니다.

```
backend/simulation/                ← 여기가 Section 3 백엔드 전체 영역
├── api/
│   ├── simulation.py              ← 일반 시뮬레이션 API (수요예측/재고 등)
│   ├── slab_agent.py              ← Slab 에이전트 API (시나리오 A/B/C, SSE)
│   └── custom_agent.py            ← Custom Agent CRUD + 빌더 + 실행 API
├── agent/
│   ├── scenario_a_agent.py        ← 시나리오 A: DG320 에러 진단
│   ├── scenario_b_agent.py        ← 시나리오 B: Edging 파급효과 분석
│   ├── scenario_c_agent.py        ← 시나리오 C: 단중·분할수 최적화
│   ├── agent_builder_agent.py     ← Custom Agent 채팅 빌더
│   ├── custom_agent_runner.py     ← Custom Agent 실행기
│   └── llm_tool_executor.py       ← Anthropic tool_use 기반 ReAct 루프 실행기 (모든 에이전트 공통)
├── tools/
│   ├── mock_simulator.py          ← Slab 설계 도구 함수 구현체 (Python 함수)
│   ├── tool_definitions.py        ← Anthropic tool_use 형식 JSON 스키마 전체 선언
│   ├── tool_registry.py           ← SimulationToolRegistry — 툴 자기 기술 + 조회 레지스트리
│   ├── parallel_executor.py       ← asyncio.gather 기반 병렬 툴 실행 (시나리오 B용)
│   └── ontology_graph.py          ← NetworkX 기반 온톨로지 Mock 그래프
├── mock/
│   └── scenarios/
│       └── slab_size_simulator.py ← SEQ 1~16 설계 계산 엔진
├── data/                          ← Mock 데이터 + Custom Agent 저장소
│   ├── custom_agents.json         ← 등록된 Custom Agent 영구 저장
│   ├── mock_orders.json
│   ├── mock_equipment_spec.json
│   ├── mock_edging_spec.json
│   └── mock_ontology.json         ← 온톨로지 그래프 노드·엣지 데이터
└── client/
    ├── modeling_client.py         ← Section 2 API 클라이언트 (Protocol 기반)
    └── config.py                  ← SIMULATION_USE_MOCK 설정
```

> **Section 10**에서 현재 구현된 아키텍처 전체를 더 자세히 다룹니다.

### 3-2. Section 3 프론트엔드

백엔드와 동일하게, 프론트엔드에서도 Section 3 전용 폴더가 분리되어 있습니다.

```
frontend/src/
├── components/
│   └── simulation/                ← Section 3 컴포넌트 전체 (자유 영역)
│       ├── SimulationSection.tsx  ← 메인 레이아웃 + 뷰 라우팅
│       ├── SimulationSidebar.tsx  ← 좌측 네비게이션 사이드바
│       ├── ChatPanel.tsx          ← 빌트인 시나리오 채팅 패널
│       ├── OntologyGraph.tsx      ← 온톨로지 그래프 (vis-network)
│       ├── SlabSizeSimulator.tsx  ← Slab 설계 시뮬레이터 (3-pane 컨테이너)
│       ├── SlabParamController.tsx ← 파라미터 슬라이더 (폭/두께/길이/단중/분할수)
│       ├── SlabViewer3D.tsx       ← Three.js 기본 3D Slab 뷰어
│       ├── SlabDesignViewer3D.tsx ← Three.js 고급 3D 뷰어 (분할 애니메이션, 시나리오 C용)
│       ├── SlabImpactPanel.tsx    ← SEQ별 영향도 분석 패널
│       ├── SlabCompareTable.tsx   ← 변경 전/후 비교 테이블
│       ├── ScenarioTabs.tsx       ← ⚠️ 레거시 (사이드바로 대체. 신규 개발 시 사용하지 않음)
│       ├── CustomAgentHub.tsx     ← Custom Agent 허브 (카드 목록 + 생성 버튼)
│       ├── AgentBuilderChat.tsx   ← 채팅 기반 에이전트 빌더
│       ├── CustomAgentFormBuilder.tsx ← 양식 기반 에이전트 빌더
│       └── CustomAgentRunner.tsx  ← 등록된 에이전트 실행 채팅
└── lib/
    └── simulation/                ← Section 3 훅 / API / 스토어
        ├── types.ts               ← TypeScript 타입 + SLAB_TOOLS + SCENARIO_META
        ├── api.ts                 ← API 클라이언트 + SSE 파서
        ├── useSimulationStore.ts  ← Zustand 전역 상태 관리
        └── useSlabSimulator.ts    ← Slab 시뮬레이터 전용 훅
```

### 3-3. 건드리지 않는 영역

| 경로 | 소유자 | 설명 |
|------|--------|------|
| `backend/application/` | Wiki (Section 1) | 기존 완성된 Wiki 코드 |
| `backend/modeling/` | 팀 리더 (Section 2) | Section 2 영역 |
| `backend/shared/contracts/` | **공유** | Section 2↔3 타입 계약. **수정 시 팀원과 합의 필수** |
| `frontend/src/components/sections/` | 공유 | SectionNav 등 공통 UI |
| `frontend/src/components/` (simulation 제외) | Wiki / 공통 | 기존 Wiki 프론트엔드 |
| `backend/core/`, `backend/infrastructure/` | 공유 인프라 | 수정 필요 시 팀원과 상의 |

---

## 4. 현재 동작하는 API

### 4-1. Simulation 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/simulation/health` | 헬스 체크 |
| `GET` | `/api/simulation/scenarios` | 사용 가능한 시나리오 타입 목록 |
| `POST` | `/api/simulation/scenario` | 시나리오 실행 요청 (SimulationJob 반환) |
| `GET` | `/api/simulation/job/{job_id}` | Job 상태 폴링 |
| `DELETE` | `/api/simulation/job/{job_id}` | Job 취소 |

**Slab 에이전트 엔드포인트** (`backend/simulation/api/slab_agent.py`):

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/simulation/slab/run` | 시나리오 A/B/C 에이전트 실행 (SSE 스트리밍) |
| `GET` | `/api/simulation/slab/orders` | Mock 주문 목록 |
| `GET` | `/api/simulation/slab/ontology` | 온톨로지 그래프 JSON (프론트엔드 시각화용) |
| `GET` | `/api/simulation/slab/equipment` | 설비 스펙 데이터 (Mock) |
| `POST` | `/api/simulation/slab/calculate` | Slab 설계 파라미터 계산 (SEQ 전체) |
| `GET` | `/api/simulation/slab/constraints` | 슬라이더 min/max 범위용 설비 제약 기준 |
| `GET` | `/api/simulation/slab/tools` | 등록된 Slab 도구 목록 (Custom Agent 빌더 UI용) |

**Custom Agent 엔드포인트** (`backend/simulation/api/custom_agent.py`):

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/simulation/custom-agents` | 등록된 에이전트 목록 |
| `POST` | `/api/simulation/custom-agents` | 새 에이전트 등록 |
| `DELETE` | `/api/simulation/custom-agents/{id}` | 에이전트 삭제 |
| `POST` | `/api/simulation/custom-agents/build/chat` | 채팅 빌더 (SSE) |
| `POST` | `/api/simulation/custom-agents/{id}/run` | 에이전트 실행 (SSE) |

API는 `backend/simulation/api/simulation.py`에 정의되어 있으며, 필요에 따라 엔드포인트를 추가하거나 수정해도 됩니다. `main.py`에 라우터가 이미 등록되어 있어서 `backend/simulation/api/` 아래에 새 라우터 파일을 만들면 `main.py`에도 등록하면 됩니다.

### 4-2. API 테스트 예시

```bash
# 수요 예측
curl -X POST http://localhost:8001/api/simulation/scenario \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "demand_forecast",
    "parameters": {
      "scenario_type": "demand_forecast",
      "product_id": "PROD-001",
      "forecast_horizon_days": 30,
      "confidence_level": 0.95,
      "include_seasonality": true
    },
    "output_formats": ["chart_line", "table"]
  }'

# 재고 최적화
curl -X POST http://localhost:8001/api/simulation/scenario \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "inventory_optimize",
    "parameters": {
      "scenario_type": "inventory_optimize",
      "warehouse_id": "WH-001",
      "target_service_level": 0.98,
      "safety_stock_method": "dynamic",
      "holding_cost_per_unit": 2.5
    },
    "output_formats": ["table", "chart_bar"]
  }'

# 리드타임 영향 분석
curl -X POST http://localhost:8001/api/simulation/scenario \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "lead_time_analysis",
    "parameters": {
      "scenario_type": "lead_time_analysis",
      "supplier_id": "SUP-KOREA-01",
      "delay_days": 7,
      "affected_materials": ["MAT-100", "MAT-200", "MAT-300"]
    },
    "output_formats": ["gantt", "table"]
  }'
```

### 4-3. Wiki API (참고 — 이미 동작 중)

Wiki 섹션의 API도 같은 서버에서 동작합니다. Section 3에서 Wiki 문서를 참조해야 할 경우 사용할 수 있습니다:

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/wiki/tree` | Wiki 문서 트리 |
| `GET` | `/api/wiki/file/{path}` | 문서 내용 조회 |
| `POST` | `/api/agent/chat` | AI 에이전트 채팅 (SSE 스트리밍) |

---

## 5. Mock 서버

Section 2(Modeling)가 아직 구현 전이므로, Mock 서버가 Section 2 API를 대신합니다.

### 5-1. 동작 원리

- **정적 JSON이 아닙니다** — 파라미터에 따라 동적으로 결과를 생성합니다
- 같은 파라미터 → 같은 결과 (deterministic seed)
- 파라미터 변경 → 결과도 달라짐 (예: `forecast_horizon_days=30` vs `90`)
- 현재 3개 시나리오: 수요 예측, 재고 최적화, 리드타임 분석

### 5-2. Mock ↔ Real 전환

```bash
# .env 파일에서 (기본값: true)
SIMULATION_USE_MOCK=true    # Mock 모드 (독립 개발용)
SIMULATION_USE_MOCK=false   # Real 모드 (Section 2 연동 시 — 아직 사용 불가)
```

### 5-3. 새 시나리오 추가

Mock에 새 시나리오를 추가하는 것도 자유입니다:

1. `backend/simulation/mock/parametric_mock.py`에 generator 함수 추가
2. `MockModelingClient.list_scenarios()`에 ScenarioInfo 추가
3. 필요하면 `backend/shared/contracts/simulation.py`에 파라미터 모델 추가 (**이 경우 팀 리더에게 알려주세요**)

---

## 6. 프론트엔드 개발

### 6-1. 현재 레이아웃

`SimulationSection.tsx`에 3-pane 하이브리드 레이아웃이 준비되어 있습니다:

```
┌───────────────────────────────────────────────────────┐
│ onTong  [Wiki] [Modeling] [Simulation]                │  ← SectionNav (상단 탭)
├────────────┬────────────────────┬─────────────────────┤
│ 시나리오    │ 대시보드            │ SimCopilot          │
│ 목록       │ (파라미터 입력     │ (AI 채팅)           │
│ (API 연동) │  + 결과 시각화)    │                     │
│            │                    │                     │
└────────────┴────────────────────┴─────────────────────┘
```

이 레이아웃도 변경해도 됩니다. 더 나은 구조가 있으면 자유롭게 수정하세요.

### 6-2. 기존 프론트엔드 패턴 참고

| 패턴 | 참고 파일 | 설명 |
|------|-----------|------|
| AI 채팅 UI | `frontend/src/components/AICopilot.tsx` | SSE 스트리밍 채팅, 세션 관리, 메시지 렌더링 |
| SSE 클라이언트 | `frontend/src/lib/api/sseClient.ts` | 백엔드 SSE 이벤트 처리 |
| 상태 관리 | `frontend/src/lib/workspace/useWorkspaceStore.ts` | Zustand store 패턴 |
| UI 컴포넌트 | `frontend/src/components/ui/` | shadcn/ui 기반 공통 컴포넌트 |

### 6-3. API 호출 패턴

프론트엔드에서 `/api/*`로 요청하면 `next.config.ts`의 rewrite 규칙에 따라 백엔드(`localhost:8001`)로 자동 프록시됩니다.

```typescript
// 시나리오 목록
const res = await fetch("/api/simulation/scenarios");
const scenarios = await res.json();

// 시뮬레이션 실행
const res = await fetch("/api/simulation/scenario", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    scenario_type: "demand_forecast",
    parameters: {
      scenario_type: "demand_forecast",
      product_id: "PROD-001",
      forecast_horizon_days: 90,
    },
    output_formats: ["chart_line", "table"],
  }),
});
const job = await res.json();
// job.result.outputs 에서 chart_line, table 등을 꺼내서 렌더링
```

### 6-4. 추천 라이브러리

자유롭게 선택하셔도 되지만, 참고용으로:

- 차트: `recharts` (React 친화적, TypeScript 지원)
- 테이블: shadcn/ui Table 또는 `@tanstack/react-table`
- Gantt: `gantt-task-react` 또는 직접 구현

---

## 7. 타입 계약 (`shared/contracts/simulation.py`)

Section 2↔3 사이의 공식 계약입니다. 이 파일에 정의된 타입 기준으로 나중에 실제 Section 2와 연동합니다.

### 주요 모델

| 모델 | 용도 |
|------|------|
| `SimulationRequest` | 시뮬레이션 실행 요청 |
| `SimulationJob` | Job 상태 + 결과 (비동기) |
| `DemandForecastParams` | 수요 예측 시나리오 파라미터 |
| `InventoryOptimizeParams` | 재고 최적화 시나리오 파라미터 |
| `LeadTimeAnalysisParams` | 리드타임 분석 시나리오 파라미터 |
| `ChartOutput` | 차트 결과 (line/bar/scatter) |
| `TableOutput` | 테이블 결과 (columns + rows) |
| `GanttOutput` | Gantt 차트 결과 (tasks) |
| `ScenarioInfo` | 시나리오 메타데이터 (이름, 설명, 지원 출력 형식) |

### 규칙

- `dict`를 시나리오 파라미터로 사용하지 않습니다. 반드시 typed Pydantic 모델을 정의합니다.
- 시뮬레이션은 항상 비동기(Job)로 반환합니다. 동기 실행은 하지 않습니다.
- 이 파일을 수정해야 할 경우 팀 리더에게 먼저 알려주세요.

---

## 8. 테스트 방법

```bash
# 백엔드 전체 테스트 (177개 — 기존 Wiki 포함)
source venv/bin/activate
pytest tests/ -v

# 프론트엔드 타입 체크
cd frontend
npx tsc --noEmit

# 프론트엔드 빌드 확인
npm run build
```

---

## 9. 브랜치 규칙

```bash
# 새 기능 시작
git checkout -b feat/sim-parameter-form

# 작업 완료 후
git push -u origin feat/sim-parameter-form
# → main 브랜치로 PR 생성
```

- main 브랜치에 직접 push하지 않습니다
- `backend/shared/contracts/` 수정이 포함된 PR은 팀 리더 리뷰가 필요합니다

---

## 10. 현재 구현된 아키텍처 (Phase 1 + Custom Agent)

> 스캐폴딩 당시 문서와 실제 구현이 다를 수 있으므로, 현재 구현 상태를 기준으로 업데이트합니다.

### 10-1. 실제 파일 구조

```
backend/simulation/
├── api/
│   ├── simulation.py          ← 일반 시뮬레이션 API (수요예측/재고/리드타임)
│   ├── slab_agent.py          ← Slab 에이전트 API (SSE 스트리밍)
│   └── custom_agent.py        ← Custom Agent CRUD + 빌더 + 실행 API
├── agent/
│   ├── scenario_a_agent.py    ← 시나리오 A: DG320 에러 진단 에이전트
│   ├── scenario_b_agent.py    ← 시나리오 B: Edging 파급효과 에이전트
│   ├── scenario_c_agent.py    ← 시나리오 C: 단중·분할수 최적화 에이전트
│   ├── agent_builder_agent.py ← Custom Agent 채팅 빌더 (LLM 기반 수집)
│   └── custom_agent_runner.py ← 등록된 Custom Agent 실행기
├── tools/
│   └── mock_simulator.py      ← Slab 설계 도구 함수 7개
├── mock/
│   ├── ontology_graph.py      ← NetworkX 기반 온톨로지 Mock 그래프
│   └── scenarios/
│       └── slab_size_simulator.py  ← SEQ 1~16 설계 계산 엔진
└── data/
    ├── custom_agents.json     ← 등록된 Custom Agent 영구 저장소
    ├── mock_orders.json       ← 주문 Mock 데이터
    ├── mock_equipment_spec.json ← 설비 기준 Mock 데이터
    └── mock_edging_spec.json  ← Edging 기준 Mock 데이터

frontend/src/
├── components/simulation/
│   ├── SimulationSection.tsx  ← 최상위 레이아웃 (사이드바 + 뷰 라우팅)
│   ├── SimulationSidebar.tsx  ← 좌측 네비게이션 사이드바
│   ├── ChatPanel.tsx          ← 빌트인 시나리오 A/B/C 채팅 패널
│   ├── OntologyGraph.tsx      ← 온톨로지 그래프 (vis-network)
│   ├── ScenarioTabs.tsx       ← 시나리오 탭 (레거시 — 사이드바로 대체됨)
│   ├── SlabSizeSimulator.tsx  ← Slab 설계 시뮬레이터 레이아웃
│   ├── SlabParamController.tsx ← 파라미터 슬라이더 컨트롤러
│   ├── SlabViewer3D.tsx       ← Three.js 3D Slab 뷰어
│   ├── SlabImpactPanel.tsx    ← SEQ별 영향도 분석 패널
│   ├── SlabCompareTable.tsx   ← 변경 전/후 비교 테이블
│   ├── SlabDesignViewer3D.tsx ← 3D 뷰어 고급 버전
│   ├── CustomAgentHub.tsx     ← Custom Agent 허브 (생성 카드 + 목록)
│   ├── AgentBuilderChat.tsx   ← 채팅 기반 에이전트 빌더
│   ├── CustomAgentFormBuilder.tsx ← 양식 기반 에이전트 빌더
│   └── CustomAgentRunner.tsx  ← 등록된 에이전트 실행 채팅
└── lib/simulation/
    ├── types.ts               ← TypeScript 타입 정의 (CustomAgent, ActiveView 등)
    ├── api.ts                 ← API 클라이언트 + SSE 파서
    ├── useSimulationStore.ts  ← Zustand 전역 상태 (뷰 라우팅 포함)
    └── useSlabSimulator.ts    ← Slab 시뮬레이터 전용 훅
```

---

### 10-2. Slab 에이전트 API

Slab 전용 AI 에이전트 엔드포인트입니다. 모두 SSE 스트리밍으로 응답합니다.

```
GET  /api/simulation/slab/orders      → 주문 목록 (JSON)
GET  /api/simulation/slab/ontology    → 온톨로지 그래프 (JSON)
GET  /api/simulation/slab/constraints → Slab 파라미터 제약 기준 (JSON)
POST /api/simulation/slab/calculate   → Slab 설계 계산 (JSON)
POST /api/simulation/slab/run         → 시나리오 A/B/C 에이전트 실행 (SSE)
```

**SSE 이벤트 스트림 (`/api/simulation/slab/run`)**:

```bash
curl -X POST http://localhost:8001/api/simulation/slab/run \
  -H "Content-Type: application/json" \
  -d '{"scenario": "A", "message": "ORD-2024-0042 DG320 에러 원인 찾아줘"}'
```

```
event: thinking
data: {"message": "주문 정보를 조회하겠습니다"}

event: tool_call
data: {"tool": "get_order_info", "args": {"order_id": "ORD-2024-0042"}}

event: tool_result
data: {"tool": "get_order_info", "result": {"order_id": "ORD-2024-0042", ...}}

event: graph_state
data: {"traversal": ["ORD-2024-0042", "HR-A"], "highlighted_edges": [...]}

event: content_delta
data: {"delta": "분석 결과: 목표폭 1,850mm가 "}

event: slab_state
data: {"slabs": [{"id": "s1", "status": "error", "width": 1850, ...}]}

event: done
data: {"result": {"suggested_width": 1570, "order_id": "ORD-2024-0042"}}
```

---

### 10-3. Custom Agent API

Custom Agent 생성·실행·삭제 전용 엔드포인트입니다.

```
GET    /api/simulation/custom-agents              → 등록된 에이전트 목록
POST   /api/simulation/custom-agents              → 새 에이전트 등록
DELETE /api/simulation/custom-agents/{id}         → 에이전트 삭제
POST   /api/simulation/custom-agents/build/chat   → 채팅 빌더 (SSE)
POST   /api/simulation/custom-agents/{id}/run     → 에이전트 실행 (SSE)
```

**에이전트 등록 예시**:

```bash
curl -X POST http://localhost:8001/api/simulation/custom-agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DG320 진단기",
    "description": "DG320 에러 주문을 자동으로 진단합니다",
    "icon": "🔍",
    "color": "#ef4444",
    "system_prompt": "당신은 DG320 에러 전문가입니다. 주문 정보를 조회하고 폭 조정 방안을 제시하세요.",
    "available_tools": ["get_order_info", "simulate_width_range", "suggest_adjusted_width"],
    "example_prompt": "ORD-2024-0042의 DG320 에러를 분석해줘",
    "created_by": "form"
  }'
```

**에이전트 실행 (SSE)**:

```bash
curl -X POST http://localhost:8001/api/simulation/custom-agents/{id}/run \
  -H "Content-Type: application/json" \
  -d '{"message": "ORD-2024-0042 DG320 에러 분석해줘"}'
```

응답 이벤트: `thinking`, `tool_call`, `tool_result`, `content_delta`, `done`, `error`

**채팅 빌더 (SSE)**:

```bash
curl -X POST http://localhost:8001/api/simulation/custom-agents/build/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "DG320 에러를 자동으로 진단하는 에이전트를 만들고 싶어",
    "history": []
  }'
```

추가 이벤트: `agent_ready` — 에이전트 정의가 완성되면 발생

```
event: agent_ready
data: {"agent": {"name": "DG320 진단기", "icon": "🔍", "color": "#ef4444",
       "system_prompt": "...", "available_tools": [...], "example_prompt": "..."}}
```

---

### 10-4. Custom Agent 데이터 저장소

에이전트 정의는 `backend/simulation/data/custom_agents.json`에 파일로 저장됩니다.

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "DG320 진단기",
    "description": "DG320 에러 주문을 자동으로 진단합니다",
    "icon": "🔍",
    "color": "#ef4444",
    "system_prompt": "당신은...",
    "available_tools": ["get_order_info", "simulate_width_range"],
    "example_prompt": "ORD-2024-0042의 DG320 에러를 분석해줘",
    "created_at": "2026-04-07T15:30:00",
    "created_by": "chat"
  }
]
```

서버를 재시작해도 에이전트가 유지됩니다. 운영 환경에서는 데이터베이스로 교체를 고려하세요.

---

### 10-5. Slab 설계 도구 추가 방법

새 도구를 Custom Agent에서 사용 가능하게 만들려면 3곳을 수정합니다.

> **중요**: 이전에는 `custom_agent_runner.py`에 직접 추가했지만, 현재는 **`tool_registry.py`를 통해 중앙 등록**합니다.

**Step 1 — 도구 함수 구현** (`backend/simulation/tools/mock_simulator.py`):

```python
def my_new_tool(param1: str, param2: int) -> dict:
    """새 도구 설명."""
    return {"result": "..."}
```

**Step 2 — Anthropic 스키마 선언** (`backend/simulation/tools/tool_definitions.py`):

```python
MY_NEW_TOOL: dict = {
    "name": "my_new_tool",
    "description": "새 도구 설명 (LLM이 언제 호출할지 판단하는 기준)",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "파라미터 설명"},
            "param2": {"type": "integer", "description": "파라미터 설명"},
        },
        "required": ["param1"],
    },
}

# 시나리오 도구 묶음에도 추가 (해당하는 시나리오에)
SCENARIO_A_TOOLS: list[dict] = [
    ...
    MY_NEW_TOOL,  # 추가
]
ALL_TOOLS: list[dict] = [
    ...
    MY_NEW_TOOL,  # 추가
]
```

**Step 3 — Tool Registry에 등록** (`backend/simulation/tools/tool_registry.py`의 `_register_all_tools()` 함수):

```python
from backend.simulation.tools.tool_definitions import MY_NEW_TOOL
from backend.simulation.tools.mock_simulator import my_new_tool

registry.register(SimulationTool(
    name=MY_NEW_TOOL["name"],
    description=MY_NEW_TOOL["description"],
    input_schema=MY_NEW_TOOL["input_schema"],
    python_fn=my_new_tool,
    domain_tags=["scenario_a"],   # 해당 시나리오 태그
))
```

**Step 4 — 프론트엔드 타입에 추가** (`frontend/src/lib/simulation/types.ts`):

```typescript
export const SLAB_TOOLS = [
  ...
  { id: "my_new_tool", label: "새 도구 이름", icon: "🆕" },
] as const;
```

---

### 10-6. SimulationToolExecutor — ReAct 루프 아키텍처

> **파일**: `backend/simulation/agent/llm_tool_executor.py`

모든 시나리오 에이전트(A/B/C)와 Custom Agent 실행기는 `SimulationToolExecutor`에 실행을 위임합니다. LLM(claude-sonnet-4-6)이 **어떤 툴을 언제 호출할지 스스로 결정**하는 진짜 ReAct 루프입니다.

```
[사용자 메시지]
      ↓
 LLM (Anthropic tool_use API)
      ↓
 stop_reason == "tool_use" ?
    → tool_call 이벤트 발행 → 툴 실행 → tool_result 이벤트 발행 → LLM에 결과 전달 → 반복
    → stop_reason == "end_turn" → content_delta 스트리밍 → done 이벤트 발행
```

**SSE 이벤트 흐름**:

| 이벤트 | 발생 시점 | data 구조 |
|--------|----------|-----------|
| `thinking` | 에이전트 시작 직후 | `{"message": "분석을 시작합니다..."}` |
| `tool_call` | LLM이 툴 호출 결정 | `{"tool": "get_order_info", "args": {...}}` |
| `tool_result` | 툴 실행 완료 | `{"tool": "get_order_info", "result": {...}}` |
| `graph_state` | 온톨로지 탐색 툴 실행 후 | `{"traversal": [...], "highlighted_edges": [...]}` |
| `slab_state` | Slab 상태 변경 툴 실행 후 | `{"slabs": [{...}]}` |
| `content_delta` | LLM 최종 답변 토큰 스트리밍 | `{"delta": "텍스트 조각"}` |
| `done` | 전체 완료 | `{"result": {...}}` |
| `error` | 예외 발생 | `{"message": "에러 메시지"}` |

**에이전트 생성 패턴** (시나리오 에이전트에서 공통 사용):

```python
from backend.simulation.agent.llm_tool_executor import SimulationToolExecutor

async def run_scenario_a(message: str):
    executor = SimulationToolExecutor(
        tool_names=SCENARIO_A_TOOL_NAMES,   # 이 에이전트가 사용 가능한 툴 이름 목록
        system_prompt=SCENARIO_A_SYSTEM_PROMPT,
        scenario="A",                        # graph_state/slab_state 이벤트 생성 여부 결정
        initial_context={"order_id": "ORD-2024-0042"},  # 첫 LLM 호출에 추가할 컨텍스트
    )
    async for evt in executor.run(message):
        yield evt
```

**최대 반복 횟수**: 툴 호출 루프는 `MAX_ITERATIONS = 10`으로 제한됩니다.

---

### 10-7. Tool Registry — 도구 자기 기술 시스템

> **파일**: `backend/simulation/tools/tool_registry.py`  
> **스키마 파일**: `backend/simulation/tools/tool_definitions.py`

`SimulationToolRegistry`는 Slab 설계 툴을 중앙에서 등록·조회합니다.

```python
from backend.simulation.tools.tool_registry import get_registry

registry = get_registry()

# Anthropic API에 넘길 tool 스키마 조회
schemas = registry.get_anthropic_schemas(["get_order_info", "simulate_width_range"])

# 툴 실행
result = registry.execute("get_order_info", {"order_id": "ORD-2024-0042"})

# 전체 툴 목록 (Custom Agent 빌더 UI에서 사용)
all_tools = registry.list_tools()
```

`tool_definitions.py`에는 **Anthropic tool_use 형식** JSON 스키마가 선언되어 있습니다:

```python
# tool_definitions.py 구조
GET_ORDER_INFO: dict = {
    "name": "get_order_info",
    "description": "주문 ID로 Slab 설계 주문 상세 정보를 조회합니다...",
    "input_schema": { "type": "object", "properties": {...}, "required": [...] }
}

# 시나리오별 툴 묶음
SCENARIO_A_TOOLS: list[dict] = [GET_ORDER_INFO, SIMULATE_WIDTH_RANGE, ...]
SCENARIO_B_TOOLS: list[dict] = [FIND_ORDERS_BY_ROLLING_LINE, SIMULATE_WIDTH_IMPACT, ...]
SCENARIO_C_TOOLS: list[dict] = [GET_ORDER_INFO, SIMULATE_SPLIT_COMBINATIONS]
ALL_TOOLS: list[dict] = [...]   # 전체 10개
```

**전체 Slab 도구 목록**:

| 도구 이름 | 시나리오 | 설명 |
|----------|---------|------|
| `get_order_info` | A, B, C | 주문 ID로 Slab 설계 주문 상세 조회 |
| `simulate_width_range` | A | 목표폭·열연라인 기준 폭 범위 산정 가부 확인 (DG320) |
| `suggest_adjusted_width` | A | DG320 에러 시 실현 가능한 최대 목표폭 제안 |
| `find_edging_specs_for_order` | A | 온톨로지 탐색: 주문 → 열연라인 → Edging 기준 |
| `simulate_width_impact` | B | Edging 능력 변경이 단일 주문에 미치는 영향 평가 |
| `batch_simulate_width_impact` | B | 여러 주문에 대한 Edging 변경 영향 병렬 평가 |
| `analyze_edging_change_ripple` | B | 열연라인 전체 주문 파급 효과 분석 |
| `find_orders_by_rolling_line` | B | 온톨로지 탐색: 열연라인 배정 주문 목록 |
| `simulate_split_combinations` | C | 분할수 1~N별 단중 만족률 계산 + 최적 분할수 추천 |
| `get_equipment_spec` | Custom | 연주기·열연 설비 기준 데이터 전체 조회 |

---

### 10-8. Parallel Executor — 병렬 툴 실행

> **파일**: `backend/simulation/tools/parallel_executor.py`

시나리오 B에서 다수 주문의 파급 효과를 동시에 분석할 때 `asyncio.gather`로 병렬 실행합니다.

```python
from backend.simulation.tools.parallel_executor import parallel_simulate_width_impact

result = await parallel_simulate_width_impact(
    order_ids=["ORD-2024-0042", "ORD-2024-0055", "ORD-2024-0061"],
    new_edging_max=160,
)
# result:
# {
#     "new_edging_max": 160,
#     "total_orders": 3,
#     "orders_affected": 2,
#     "orders_safe": 1,
#     "impact_rate": "66.7%",
#     "details": [{"order_id": "ORD-2024-0042", "affected": True, ...}, ...]
# }
```

`batch_simulate_width_impact` 도구가 내부적으로 이 함수를 호출합니다. LLM이 단일 툴 호출로 다수 주문을 병렬 처리할 수 있습니다.

---

### 10-9. 온톨로지 그래프 구조

> **백엔드**: `backend/simulation/tools/ontology_graph.py`  
> **데이터**: `backend/simulation/data/mock_ontology.json`  
> **프론트엔드**: `frontend/src/components/simulation/OntologyGraph.tsx`

`GET /api/simulation/slab/ontology` 엔드포인트가 반환하는 그래프 구조:

```json
{
  "nodes": [
    {"id": "ORD-2024-0042", "type": "Order", "label": "주문 ORD-2024-0042", "...": ""},
    {"id": "HR-A", "type": "HotRollingMill", "label": "열연 A라인", "...": ""},
    {"id": "EDGE-HR-A-1", "type": "EdgeSpec", "label": "Edging 기준 HR-A", "...": ""}
  ],
  "edges": [
    {"from": "ORD-2024-0042", "to": "HR-A", "relation": "ROLLED_BY"},
    {"from": "HR-A", "to": "EDGE-HR-A-1", "relation": "HAS_EDGING_SPEC"}
  ]
}
```

**노드 타입**: `Order`, `HotRollingMill`, `ContinuousCaster`, `EdgeSpec`  
**엣지 관계**: `ROLLED_BY`, `CAST_BY`, `HAS_EDGING_SPEC`

Section 2 연동 시 `build_mock_graph()` 함수만 `build_graph_from_section2()`로 교체하면 됩니다.

---

### 10-10. 프론트엔드 뷰 라우팅 (ActiveView)

`SimulationSection.tsx`는 `activeView` 상태에 따라 메인 콘텐츠를 전환합니다.

```typescript
// types.ts
type ActiveView =
  | { kind: "scenario"; id: ScenarioType }       // A/B/C/SLAB_DESIGN
  | { kind: "custom_hub" }                        // Custom Agent 허브
  | { kind: "custom_chat_builder" }               // 채팅 에이전트 빌더
  | { kind: "custom_form_builder" }               // 양식 에이전트 빌더
  | { kind: "custom_agent"; agentId: string };    // 특정 에이전트 실행
```

뷰 전환은 항상 `useSimulationStore`의 `setActiveView()`를 통해 이루어집니다:

```typescript
const { setActiveView } = useSimulationStore();

// 시나리오 B로 이동
setActiveView({ kind: "scenario", id: "B" });

// 특정 Custom Agent 실행 화면으로 이동
setActiveView({ kind: "custom_agent", agentId: "550e8400-..." });
```

---

## 11. 참고 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| 아키텍처 총정리 | `toClaude/reports/platform_architecture_v2.md` | 전체 플랫폼 설계 (16개 섹션) |
| 타입 계약 | `backend/shared/contracts/simulation.py` | Section 2↔3 API 계약 |
| 기술스택 | `docs/tech-stack.md` | 사용 기술 목록 및 선정 이유 |
| Slab 에이전트 설계 | `docs/section3-slab-agent-dev-guide.md` | Slab 시나리오 A/B/C 상세 설계 |
| 시각화 요구사항 | `docs/section3-slab-viz-requirements.md` | 3D 시각화 스펙 |
| 도메인 검증 질문 | `docs/section3-domain-review.md` | 현업 도메인 정합성 확인 사항 |
| 기획 검토 질문 | `docs/section3-planner-questions.md` | 기획자용 UX/기능 검증 질문지 |
| 고도화 로드맵 | `docs/section3-roadmap.md` | Section 3 고도화 + Section 2 연결 계획 |
| 기존 채팅 UI | `frontend/src/components/AICopilot.tsx` | Wiki AI 채팅 구현 패턴 참고 |
| SSE 스트리밍 | `backend/api/agent.py` | 백엔드 SSE 이벤트 스트리밍 패턴 |
