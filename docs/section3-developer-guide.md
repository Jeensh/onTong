# Section 3 (Simulation) 개발 가이드

> **담당 영역**: Section 3 — 비즈니스 시뮬레이션 (시나리오 설계 / 실행 / 시각화)
> **대상 사용자**: SCM 현업 담당자
> **현재 상태**: 스캐폴딩 완료, Mock 서버 동작 중, 독립 개발 가능

---

## 1. 프로젝트 개요

onTong은 3개 섹션으로 구성된 플랫폼입니다:

| 섹션 | 용도 | 상태 |
|------|------|------|
| **Section 1 (Wiki)** | 문서 관리 + AI Q&A | 완성 (운영 중) |
| **Section 2 (Modeling)** | 코드매핑 / 온톨로지 / 영향분석 | (개발 예정) |
| **Section 3 (Simulation)** | 시뮬레이션 시나리오 설계 / 시각화 | **← 여기를 개발** |

세 섹션이 하나의 애플리케이션에서 함께 동작합니다. Wiki 기능은 이미 완성되어 있으므로 Simulation 개발 중에도 Wiki를 동시에 사용할 수 있습니다.

---

## 2. 환경 세팅 및 애플리케이션 실행

### 2-1. 사전 요구사항

- **Python 3.10+** (venv 사용, 프로젝트 venv에는 Python 3.13 설치됨)
- **Node.js 20** (`nvm use 20`)
- **Docker** (ChromaDB 실행용)

### 2-2. 최초 설정

```bash
# 1. 프로젝트 클론
git clone <repo-url>
cd onTong

# 2. Python 가상환경 + 의존성
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
# 또는: poetry install

# 3. 프론트엔드 의존성
cd frontend
npm install
cd ..

# 4. 환경변수 확인
# .env 파일이 루트에 있어야 합니다. 없으면 팀 리더에게 요청하세요.
# 최소 필요 항목:
#   LITELLM_MODEL=openai/gpt-4o (또는 사용 중인 LLM)
#   CHROMADB_HOST=localhost
#   CHROMADB_PORT=8000
#   ENVIRONMENT=development
```

### 2-3. 서비스 실행 순서

총 3개의 서비스를 실행해야 합니다:

```bash
# 터미널 1: ChromaDB (벡터 DB — Wiki 검색에 필요)
docker compose up -d chroma
# 정상 확인: curl http://localhost:8000/api/v1/heartbeat

# 터미널 2: 백엔드 (포트 8001)
source venv/bin/activate
python -m backend.main
# 정상 확인: curl http://localhost:8001/health

# 터미널 3: 프론트엔드 (포트 3000)
cd frontend
npm run dev
# 정상 확인: 브라우저에서 http://localhost:3000 접속
```

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
│   └── simulation.py              ← API 라우터 (엔드포인트 추가/수정 자유)
├── agent/                         ← SimAgent (AI 채팅 에이전트) 구현 위치
├── visualization/                 ← 결과 포맷 변환 유틸
├── storage/                       ← 시나리오 버전 관리 / 결과 저장
├── mock/
│   ├── parametric_mock.py         ← Mock 서버 (파라미터 기반 동적 생성)
│   └── scenarios/                 ← 시나리오 mock 데이터
└── client/
    ├── modeling_client.py         ← Section 2 API 클라이언트 (Protocol 기반)
    └── config.py                  ← SIMULATION_USE_MOCK 설정
```

### 3-2. Section 3 프론트엔드

백엔드와 동일하게, 프론트엔드에서도 Section 3 전용 폴더가 분리되어 있습니다. 이 두 디렉토리 아래에서 자유롭게 작업하시면 됩니다.

```
frontend/src/
├── components/
│   └── simulation/                ← Section 3 컴포넌트 전체 (자유 영역)
│       ├── SimulationSection.tsx  ← 메인 레이아웃 (수정 자유)
│       ├── SimCopilot.tsx         ← AI 채팅 어시스턴트
│       ├── ScenarioDashboard.tsx  ← 결과 시각화 (차트/테이블/Gantt)
│       ├── ParameterForm.tsx      ← 시나리오 파라미터 입력 폼
│       └── CompareView.tsx        ← 시나리오 A vs B 비교
└── lib/
    └── simulation/                ← Section 3 훅 / API 클라이언트 / 스토어 (자유 영역)
        ├── useSimulationStore.ts  ← Zustand 상태 관리
        ├── api.ts                 ← Simulation API 호출 함수
        └── types.ts               ← TypeScript 타입 정의
```

### 3-3. 건드리지 않는 영역

| 경로 | 소유자 | 설명 |
|------|--------|------|
| `backend/application/` | Wiki (Section 1) | 기존 완성된 Wiki 코드 |
| `backend/modeling/` | 팀 리더 (Section 2) | Section 2 영역 |
| `backend/shared/contracts/` | **공유** | Section 2↔3 타입 계약. **수정 시 팀 리더와 합의 필수** |
| `frontend/src/components/sections/` | 공유 | SectionNav 등 공통 UI |
| `frontend/src/components/` (simulation 제외) | Wiki / 공통 | 기존 Wiki 프론트엔드 |
| `backend/core/`, `backend/infrastructure/` | 공유 인프라 | 수정 필요 시 팀 리더와 상의 |

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

## 10. 참고 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| 아키텍처 총정리 | `toClaude/reports/platform_architecture_v2.md` | 전체 플랫폼 설계 (16개 섹션) |
| 타입 계약 | `backend/shared/contracts/simulation.py` | Section 2↔3 API 계약 |
| 기술스택 | `docs/tech-stack.md` | 사용 기술 목록 및 선정 이유 |
| 기존 채팅 UI | `frontend/src/components/AICopilot.tsx` | AI 채팅 구현 패턴 참고 |
| SSE 스트리밍 | `backend/api/agent.py` | 백엔드 SSE 이벤트 스트리밍 패턴 |
