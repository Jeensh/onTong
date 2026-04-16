# SimCopilot + Custom Agent System — Step Summary

> 작성일: 2026-04-08 | 해당 세션: 2026-04-07

---

## 개요

Section 3 (Simulation) 프론트엔드 전체 통합 완료.
SlabSizeSimulator, 시나리오 A/B/C 에이전트, Custom Agent 빌더/실행 시스템까지
백엔드-프론트엔드 end-to-end 연결 완료.

---

## 완료된 핵심 작업

### 1. 백엔드 — Simulation Agent 시스템

| 파일 | 역할 |
|------|------|
| `backend/simulation/agent/scenario_a_agent.py` | Scenario A SSE 스트리밍 에이전트 |
| `backend/simulation/agent/scenario_b_agent.py` | Scenario B SSE 스트리밍 에이전트 |
| `backend/simulation/agent/scenario_c_agent.py` | Scenario C SSE 스트리밍 에이전트 |
| `backend/simulation/agent/custom_agent_runner.py` | 등록된 Custom Agent 실행 (LLM + 도구) |
| `backend/simulation/agent/agent_builder_agent.py` | 대화형 Custom Agent 빌더 SSE 에이전트 |
| `backend/simulation/agent/llm_tool_executor.py` | LLM → 도구 호출 루프 (423줄, 핵심 실행 엔진) |
| `backend/simulation/api/custom_agent.py` | Custom Agent CRUD + 빌더 + 실행 REST API |
| `backend/simulation/api/slab_agent.py` | Slab 설계 에이전트 API (SlabSizeSimulator 연동) |
| `backend/simulation/api/simulation.py` | Simulation 시나리오 API |
| `backend/simulation/tools/` | tool_definitions, tool_registry, mock_simulator, ontology_graph, parallel_executor |
| `backend/simulation/data/` | Custom Agent JSON 영속 저장소 |
| `backend/simulation/mock/scenarios/` | 시나리오별 Mock 응답 데이터 |
| `backend/shared/contracts/simulation.py` | Pydantic typed 계약 (파라미터 모델) |

### 2. 프론트엔드 — Simulation 컴포넌트

| 파일 | 역할 |
|------|------|
| `SimulationSection.tsx` | 최상위 컨테이너, `activeView` 기반 뷰 라우팅, 앱 시작 시 에이전트 자동 로드 |
| `SimulationSidebar.tsx` | 시나리오 A/B/C + SLAB_DESIGN + custom_hub 네비게이션 |
| `ChatPanel.tsx` | 시나리오 채팅 공통 패널 (SSE 스트리밍) |
| `AgentBuilderChat.tsx` | 대화형 Custom Agent 빌더 채팅 UI |
| `CustomAgentHub.tsx` | 등록된 Custom Agent 목록 뷰 |
| `CustomAgentRunner.tsx` | 에이전트별 독립 채팅 실행 UI |
| `CustomAgentFormBuilder.tsx` | 양식 기반 에이전트 생성 (아이콘/색상/도구/프롬프트) |
| `SlabSizeSimulator.tsx` | Slab 크기 시뮬레이터 (파라미터 입력 + 결과) |
| `SlabViewer3D.tsx` | Three.js 기반 3D Slab 뷰어 |
| `SlabDesignViewer3D.tsx` | 설계 단계별 3D 뷰어 |
| `SlabParamController.tsx` | Slab 파라미터 컨트롤러 |
| `SlabImpactPanel.tsx` | Slab 변경 영향 패널 |
| `SlabCompareTable.tsx` | 시나리오 비교 테이블 |
| `OntologyGraph.tsx` | SCOR+ISA-95 온톨로지 그래프 시각화 |
| `ScenarioTabs.tsx` | 시나리오 탭 컴포넌트 |

### 3. 상태 관리 — Zustand Store

| 파일 | 주요 추가 상태 |
|------|--------------|
| `lib/simulation/useSimulationStore.ts` | `activeView`, `customAgents`, `setCustomAgents`, `fetchCustomAgents` |
| `lib/simulation/api.ts` | `fetchCustomAgents()`, `createCustomAgent()`, `deleteCustomAgent()`, `runCustomAgent()` |
| `lib/simulation/types.ts` | `CustomAgent`, `SlabSizeParams`, `SimulationScenario` 타입 |

### 4. 문서 업데이트

- `docs/section3-user-guide.md` — 사이드바 레이아웃, Custom Agent 섹션(7-1~7-6), FAQ, 로드맵
- `docs/section3-developer-guide.md` — 파일 구조 현행화, Custom Agent API 상세, 도구 추가 가이드, 뷰 라우팅

---

## 핵심 아키텍처 패턴

### activeView 기반 뷰 라우팅
```typescript
type ActiveView =
  | { kind: "scenario"; id: "A" | "B" | "C" | "SLAB_DESIGN" }
  | { kind: "custom_hub" }
  | { kind: "custom_agent_builder" }
  | { kind: "custom_agent_runner"; agentId: string }
  | { kind: "custom_agent_form" }
```

### Custom Agent API 엔드포인트
```
GET    /api/simulation/custom-agents              → 목록 조회
POST   /api/simulation/custom-agents              → 에이전트 등록
DELETE /api/simulation/custom-agents/{id}         → 에이전트 삭제
POST   /api/simulation/custom-agents/build/chat   → 채팅 빌더 (SSE)
POST   /api/simulation/custom-agents/{id}/run     → 에이전트 실행 (SSE)
```

---

## 에러 수정 (2026-04-08)

- `pydantic-ai-slim` 패키지 미설치로 `ModuleNotFoundError` 발생
  - 원인: pyproject.toml에 의존성 명시되어 있으나 venv에 미설치
  - 수정: `venv/bin/pip install "pydantic-ai-slim[litellm]>=1.0"` 실행
  - 결과: 177/177 테스트 전수 통과

---

## 검증 결과

- 백엔드 pytest: ✅ **177/177 통과**
- 프론트엔드 빌드: ✅ **성공** (경고만, 에러 없음)
- 백엔드 임포트: ✅ `backend.main` 정상 로드
