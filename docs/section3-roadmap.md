# Section 3 로드맵 — 완료 이력 & 고도화 계획

> **최종 수정일**: 2026-04-16  
> **범위**: Section 3 (시뮬레이션) 지금까지의 개발 이력 + 앞으로의 고도화 계획 + Section 2 연결 전략  
> **현재 상태**: Phase 1 + Phase 1.5 완료 (Mock 데이터 기반), Section 2는 스캐폴딩만 존재

---

## 1. 지금까지 완료된 작업 이력

### Phase 0 — 3-Section 플랫폼 스캐폴딩 (2026-04-02)

| 완료 항목 | 세부 내용 |
|-----------|----------|
| **3-Section 아키텍처 설계** | Wiki / Modeling / Simulation 3섹션 분리, SCOR+ISA-95 하이브리드 온톨로지 설계 |
| **백엔드 스캐폴딩** | `backend/simulation/` — API 라우터, Mock 서버, ModelingClient Protocol, Agent 모듈 |
| **프론트엔드 스캐폴딩** | SectionNav 상단 탭, SimulationSection 3-pane 레이아웃, SimulationSidebar |
| **Section 2↔3 타입 계약** | `shared/contracts/simulation.py` — Pydantic 모델 (SimulationRequest, SimulationJob 등) |
| **MockModelingClient** | 파라미터 기반 동적 결과 생성 (수요예측/재고최적화/리드타임분석 3개 시나리오) |
| **main.py 라우터 등록** | modeling_api, simulation_api, slab_agent_api, custom_agent_api |

### Phase 1 — 시나리오 Agent + Slab 시뮬레이터 (2026-04-04)

| 완료 항목 | 세부 내용 |
|-----------|----------|
| **시나리오 A Agent** | DG320 에러 진단 — 주문 조회 → Edging 기준 확인 → 폭 조정 제안 |
| **시나리오 B Agent** | Edging 파급효과 분석 — 변경 파라미터 파싱 → 전체 주문 영향 병렬 스캔 |
| **시나리오 C Agent** | 단중·분할수 최적화 — 분할수 1~N 조합별 만족률 계산 + 최적 추천 |
| **SimulationToolExecutor** | Anthropic tool_use 기반 ReAct 루프 실행기 (모든 Agent 공통) |
| **Slab 설계 도구 10개** | get_order_info, simulate_width_range, suggest_adjusted_width, find_edging_specs_for_order, simulate_width_impact, batch_simulate_width_impact, find_orders_by_rolling_line, simulate_split_combinations, get_equipment_spec, slab_calculate |
| **Tool Registry** | SimulationToolRegistry — 중앙 등록, Anthropic 스키마 조회, 실행 |
| **Parallel Executor** | asyncio.gather 기반 병렬 주문 영향 분석 (시나리오 B용) |
| **Mock 온톨로지 그래프** | NetworkX 기반 — 13개 노드, 12개 엣지 (Order, CC, HR, EdgeSpec, Slab) |
| **SEQ 1~16 설계 계산 엔진** | calculate_slab_design() — 두께 결정, 폭범위, 길이범위, 단중범위, 분할수, 매수, 2차 폭범위, Target폭/길이 |
| **Slab 에이전트 API** | POST /run (SSE), GET /orders, /ontology, /equipment, /constraints, /tools, POST /calculate |
| **SlabSizeSimulator** | 3-pane 레이아웃 (파라미터 컨트롤러 + 3D 뷰어 + 영향도 패널) |
| **SlabParamController** | 6개 파라미터 슬라이더 + 숫자 입력 + 상태 인디케이터 (🟢🟡🔴) + 주문 드롭다운 |
| **SlabViewer3D** | Three.js 3D Slab 렌더링 — OrbitControls, 치수 라벨, 상태별 색상 코딩 |
| **SlabDesignViewer3D** | 고급 3D 뷰어 — 분할 애니메이션 (1→N개), 시나리오 C 딥링크용 |
| **SlabImpactPanel** | SEQ 2~16 단계별 통과 여부 실시간 판정 트리 + 연쇄 실패 감지 |
| **SlabCompareTable** | 변경 전/후 파라미터 비교 테이블 |
| **ChatPanel** | SSE 스트리밍 + 마크다운 렌더링 + 추론 과정/도구 호출 표시 |
| **OntologyGraph** | vis-network 기반 그래프 시각화 — 노드 타입별 색상, Agent 탐색 경로 하이라이팅 |
| **딥 링킹 (시나리오 A)** | 완료 → "Slab 설계 3D로 확인" 버튼 → 조정 폭 파라미터로 시뮬레이터 이동 |
| **딥 링킹 (시나리오 C)** | 완료 → "최적 분할수 N개를 3D로 확인" 버튼 → 분할 애니메이션 |
| **딥 링킹 (시나리오 B)** | 완료 → "영향받은 슬랩 Slab 설계 3D로 확인" 버튼 |
| **온톨로지 → 시뮬레이터 연동** | Order 노드 클릭 → 해당 주문 파라미터로 시뮬레이터 자동 이동 |
| **Zustand 상태 관리** | useSimulationStore (activeView, graphData, customAgents, orders) |
| **API 클라이언트 + SSE 파서** | api.ts — fetchOntologyGraph, runAgent, runCustomAgent 등 |
| **TypeScript 타입 시스템** | types.ts — CustomAgent, ActiveView, SLAB_TOOLS, SCENARIO_META |
| **Mock 데이터 4종** | mock_orders.json (5건), mock_equipment_spec.json, mock_edging_spec.json, mock_ontology.json |

### Phase 1.5 — Custom Agent Hub (2026-04-07)

| 완료 항목 | 세부 내용 |
|-----------|----------|
| **Custom Agent API** | CRUD (GET/POST/DELETE) + 채팅 빌더 (SSE) + 실행 (SSE) |
| **AgentBuilderAgent** | LLM 기반 에이전트 정의 수집 — 이름/도구/프롬프트를 대화로 수집 |
| **CustomAgentRunner** | 등록된 Custom Agent 실행기 — 에이전트별 독립 대화 |
| **CustomAgentHub** | 에이전트 카드 목록 + "채팅으로 만들기" / "양식으로 만들기" 버튼 |
| **AgentBuilderChat** | AI와 대화하며 에이전트 설계 → 미리보기 카드 → 등록 버튼 |
| **CustomAgentFormBuilder** | 구조화된 폼 기반 에이전트 생성 (아이콘/색상/도구/프롬프트/예시) |
| **CustomAgentRunner UI** | 등록된 에이전트 실행 채팅 (에이전트별 독립 대화 이력) |
| **사이드바 통합** | Custom Agent 섹션 — 헤더 클릭→허브, 빌더 2종, 에이전트 목록 + 삭제 |
| **영구 저장** | custom_agents.json 파일 기반 — 서버 재시작 시에도 에이전트 유지 |
| **뷰 라우팅 확장** | activeView에 custom_hub / custom_chat_builder / custom_form_builder / custom_agent 추가 |

### 부가 작업 (2026-04-09 ~ 2026-04-16)

| 완료 항목 | 세부 내용 |
|-----------|----------|
| **SSE 스트리밍 프록시** | ngrok/LAN 외부 접속 환경에서 SSE 정상 동작하도록 프록시 설정 |
| **개발자 가이드 대규모 업데이트** | 아키텍처 전체 문서화 (Section 10 — API, ReAct 루프, Tool Registry 등) |
| **의존성 누락 수정** | fresh install 시 빌드 실패하던 문제 해결 |
| **docs/ 폴더 정리** | section3-* 접두어 표준화, 요구사항 통합(section3-requirements.md), 로드맵 작성 |

---

## 2. 현재 아키텍처 연결 구조

### Section 2 ↔ 3 Protocol 추상화 (이미 구현됨)

```
Section 3 (시뮬레이션)
    |
ModelingClient (Protocol - 덕 타이핑)
    |
현재:    MockModelingClient (Mock JSON 파일)
미래:    RealModelingClient (Section 2 실제 API)
```

- **계약 파일**: `backend/shared/contracts/simulation.py` (Pydantic 모델)
- **클라이언트 팩토리**: `backend/simulation/client/modeling_client.py` (`use_mock` 플래그)
- **전환 방법**: `use_mock=false`로 변경 + `RealModelingClient` 구현 → 프론트엔드 변경 불필요

### Section 2 현재 상태 (스캐폴딩만 존재)

```
backend/modeling/
├── api/modeling.py       -> health 엔드포인트만 (46줄)
├── code_analysis/        -> 비어 있음
├── ontology/             -> 비어 있음
├── mapping/              -> 비어 있음
└── agent/                -> 비어 있음
```

---

## 3. 고도화 계획 — Section 2 연결

### 원칙: Section 2 전체 완성을 기다리지 않는다

Section 3이 실제로 소비하는 **4개의 API만** 먼저 구현하면 Mock → 실제 전환이 가능하다.

### Phase A: 데이터 연결 (낮은 노력, 높은 효과)

| 순서 | API 엔드포인트 | 용도 | 대체 대상 | 작업량 |
|------|-------------|---------|----------|--------|
| A-1 | `GET /api/modeling/orders` | 주문 목록 | `mock_orders.json` | 낮음 |
| A-2 | `GET /api/modeling/equipment` | 설비 제약 조건 | `mock_equipment_spec.json` | 낮음 |
| A-3 | `GET /api/modeling/ontology/graph` | 온톨로지 노드/엣지 | `mock_ontology.json` | 중간 |
| A-4 | `POST /api/modeling/simulation/scenario` | 시뮬레이션 실행 위임 | `MockModelingClient` | 중간 |

**구현 단계:**

1. `docker-compose.yml`에 Neo4j Docker 서비스 추가
2. 기존 Mock JSON 데이터를 Neo4j 초기 그래프로 시드
3. `backend/simulation/client/modeling_client.py`에 `RealModelingClient` 구현
4. `backend/simulation/client/config.py`에서 `use_mock` 플래그를 `false`로 전환
5. 프론트엔드 변경 불필요 — Protocol 인터페이스가 안정적으로 유지됨

**통합 지점 상세:**

```
주문 (A-1):
  현재 → mock_orders.json (정적 5건)
  미래 → Neo4j: MATCH (o:Order) RETURN o
  영향 → SlabParamController 드롭다운, Agent 시나리오 입력

설비 제약 (A-2):
  현재 → mock_equipment_spec.json (CC-01, CC-02, HR-A, HR-B 하드코딩)
  미래 → Neo4j: MATCH (e:Equipment) RETURN e
  영향 → 슬라이더 min/max 범위가 실제 설비 기준으로 자동 조정

온톨로지 (A-3):
  현재 → mock_ontology.json → NetworkX 인메모리 (13노드, 12엣지)
  미래 → Neo4j: MATCH (n)-[r]->(m) RETURN n,r,m
  영향 → OntologyGraph.tsx 시각화, Agent 탐색 도구

시뮬레이션 실행 (A-4):
  현재 → MockModelingClient.run_simulation() → parametric_mock.py
  미래 → RealModelingClient → POST /api/modeling/simulation/scenario
  영향 → 3개 시나리오 유형 전체
```

---

## 4. 고도화 계획 — Section 3 기능 확장

### Phase B: 핵심 기능 고도화

| 순서 | 기능 | 설명 | 작업량 | 구현 방안 |
|------|------|------|--------|----------|
| B-1 | **온톨로지 그래프 시각화 개선** | vis-network 렌더링 품질 향상 + Agent 탐색 경로 하이라이팅 강화 + 레이아웃 알고리즘 개선 | 중간 | `OntologyGraph.tsx` 리팩토링, 노드 클러스터링, 줌/패닝 UX 개선 |
| B-2 | **역산 계산** | "목표 단중 X일 때 가능한 폭×길이 조합은?" → 격자 히트맵 시각화 | 중간 | `POST /api/simulation/slab/reverse-calculate` 신규 + 히트맵 컴포넌트 |
| B-3 | **다중 세트 비교** | 최대 3개 설계 파라미터 세트를 테이블/차트로 나란히 비교 | 중간 | `SlabCompareTable` 확장 — 현재 1개 스냅샷 → 3개 세트 |
| B-4 | **Wiki SEQ 연동** | SEQ 체크 트리에서 각 단계 클릭 시 Section 1 Wiki 설계 규칙 문서로 연결 | 낮음 | SEQ별 wiki_path 필드 추가 + `SlabImpactPanel`에 📄 아이콘 링크 |
| B-5 | **세션 영속성** | Custom Agent 대화 기록이 페이지 새로고침 시에도 유지 | 낮음 | Zustand persist 옵션 + localStorage 또는 Redis 세션 |
| B-6 | **강종 프리셋** | 강종 드롭다운 (일반강/STS/고장력강/극후강) → 파라미터 + 비중(DENSITY) 자동 설정 | 낮음 | `SlabParamController`에 강종 셀렉터 + 프리셋 JSON |
| B-7 | **에러 자동 수정 버튼** | SEQ 에러 발생 시 우측 패널에 "자동 수정" 버튼 → 권장값 즉시 적용 | 낮음 | `SlabImpactPanel`에 "권장값 적용" 클릭 핸들러 |
| B-8 | **시뮬레이터 → Agent 역방향 연동** | 시뮬레이터에서 파라미터 설정 후 "이 파라미터로 분석해 줘" 버튼 → Agent 채팅 자동 전달 | 중간 | `SlabSizeSimulator`에 "Agent에게 분석 요청" 버튼 + 시나리오 A로 컨텍스트 전달 |

### Phase C: 플랫폼 통합

| 순서 | 기능 | 설명 | 작업량 | 구현 방안 |
|------|------|------|--------|----------|
| C-1 | **Section 1 → 3 연결** | Wiki에서 "시뮬레이션 실행" 버튼 → 컨텍스트를 Section 3으로 전달 | 중간 | Wiki 문서의 에러코드/주문번호 자동 감지 → Section 3 딥링크 |
| C-2 | **Section 2 → 3 실시간 동기화** | 온톨로지 변경 시 시뮬레이터 제약 조건 자동 업데이트 | 높음 | Neo4j 변경 감지 → WebSocket 이벤트 → 프론트엔드 상태 갱신 |
| C-3 | **팀 Agent 라이브러리** | Custom Agent를 팀원과 공유 | 중간 | custom_agents.json → DB 마이그레이션 + 공유/비공개 플래그 |
| C-4 | **Agent 메모리 (단기)** | 시나리오 간 컨텍스트 유지 | 낮음 | 세션 내 분석 결과를 공유 컨텍스트로 저장 + 타 시나리오에서 참조 |

### Phase D: 고급 기능 (해커톤 차별화)

| 순서 | 기능 | 설명 | 작업량 | 데모 임팩트 |
|------|------|------|--------|-----------|
| D-1 | **Extended Thinking** | 시나리오 B 같은 복잡한 분석에 Anthropic Extended Thinking 활성화 → AI 사고 과정을 투명하게 표시 | 낮음 | 높음 |
| D-2 | **MCP Server 노출** | tool_registry의 10개 도구를 MCP Server로 노출 → Claude Desktop에서 바로 호출 가능 | 낮음 | 높음 |
| D-3 | **Graph RAG** | 온톨로지 그래프 탐색 + Wiki 벡터 검색 결합 → 엔티티 간 관계 기반 멀티홉 추론 | 중간 | 높음 |
| D-4 | **Agent 관측성** | 트레이스 저장 + 정확도/도구 호출 횟수 대시보드 → "에이전트 정확도 92%" 정량 데이터 제시 | 중간 | 중간 |
| D-5 | **멀티모달 입력** | 설계 결과 스크린샷 드래그 앤 드롭 → Claude Vision이 파라미터 추출 → 자동 분석 | 중간 | 높음 |
| D-6 | **Human-in-the-Loop 게이트** | 시뮬레이션 결과에 승인 워크플로 추가 → "이 변경을 설계 시스템에 반영하시겠습니까?" | 중간 | 높음 |

---

## 5. 권장 실행 순서

```
1단계 (즉시 실행 가능 — 프론트엔드 개선):
    B-6 (강종 프리셋) + B-7 (에러 자동 수정) + B-5 (세션 영속성)

2단계 (데이터 연결):
    A-1 (주문 API) + A-2 (설비 API) → Mock 탈출 시작

3단계 (시각화 + 역산):
    B-1 (그래프 시각화 개선) + B-2 (역산 계산)

4단계 (온톨로지 연결):
    A-3 (Neo4j 온톨로지) → 실제 그래프 데이터로 전환

5단계 (해커톤 차별화 — 낮은 노력/높은 임팩트):
    D-1 (Extended Thinking) + D-2 (MCP Server)

6단계 (기능 확장):
    B-3 (다중 세트 비교) + B-4 (Wiki SEQ 연동) + B-8 (역방향 연동)

7단계 (플랫폼 통합):
    C-1, C-2, C-3, C-4

8단계 (고급 기능):
    D-3, D-4, D-5, D-6 + A-4 (시뮬레이션 실행 위임)
```

**핵심 원칙**: Section 2의 완전한 완성을 기다리지 않는다. 1~3단계는 Section 2 없이 즉시 진행 가능하다. Protocol 추상화가 이미 갖춰져 있으므로 데이터 연결 시 프론트엔드 코드 변경은 불필요하다.

---

## 6. 통합 후 아키텍처

```
                    +------------------+
                    |   프론트엔드      |
                    |   (React/Next)   |
                    +--------+---------+
                             |
                    +--------+---------+
                    |   FastAPI        |
                    |   백엔드          |
                    +--------+---------+
                             |
            +----------------+----------------+
            |                |                |
    +-------+-------+ +-----+------+ +-------+-------+
    | Section 1     | | Section 2  | | Section 3     |
    | Wiki          | | 모델링      | | 시뮬레이션     |
    | (ChromaDB +   | | (Neo4j +   | | (Agent +      |
    |  BM25 + LLM)  | |  온톨로지)  | |  도구 + 3D)   |
    +---------------+ +-----+------+ +-------+-------+
                             |                |
                             +--- Protocol ---+
                             ModelingClient
                             (Mock / 실제)
```

### 통합 후 데이터 흐름

```
1. 사용자가 Slab 시뮬레이터에서 주문 선택
   → GET /api/modeling/orders (Section 2 Neo4j)
   → SlabParamController 자동 입력

2. Agent가 시나리오 A 실행 (DG320 진단)
   → 도구: get_order_info → Section 2 Neo4j
   → 도구: find_edging_specs_for_order → Section 2 Neo4j 그래프 탐색
   → 도구: simulate_width_range → Section 3 mock_simulator (로컬 계산)
   → SSE 스트리밍으로 프론트엔드 전송

3. 온톨로지 그래프 시각화
   → GET /api/modeling/ontology/graph (Section 2 Neo4j)
   → OntologyGraph.tsx에서 노드/엣지 렌더링
   → Agent 탐색 경로를 실시간 하이라이팅
```

---

## 7. 위험 요소 및 완화 방안

| 위험 요소 | 영향 | 완화 방안 |
|----------|------|----------|
| Section 2 개발 지연 | Section 3이 Mock 데이터에 머무름 | Mock 데이터가 완전히 기능하므로 데모에 지장 없음 |
| 대규모 그래프에서 Neo4j 성능 저하 | 온톨로지 시각화 속도 저하 | 페이지네이션 + 서브그래프 쿼리; 현재 Mock은 13개 노드에 불과 |
| shared/contracts 계약 변경 | Section 2와 3 모두 업데이트 필요 | Pydantic 모델이 타입 안전성 보장; 변경 시 팀 합의 필수 |
| Mock 데이터 ↔ 실제 데이터 형식 불일치 | 전환 시 통합 문제 | 동일한 JSON 인터페이스(`{nodes, edges}`) 유지 중 |

---

*문서 버전: 2026-04-16 · Section 3 완료 이력 & 고도화 로드맵*
