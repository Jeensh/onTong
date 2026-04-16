# 변경/추가 요청

> 세션 사이에 요구사항이 바뀌거나 추가되면 여기에 메모.
> Claude는 매 세션 시작 시 이 파일의 `[ ]` 항목을 확인하고 우선 처리.
> 처리 완료 시 `[x]`로 체크하고 TODO.md/master_plan.md에 반영.

---

## 2026-04-16 (docs 정리)

- [x] **Section 3 고도화 + Section 2 연결 로드맵 문서 작성**
  - `docs/section3-roadmap.md` 신규 생성
  - Phase A: Section 2 최소 API 4개 구현 (주문/설비/온톨로지/시뮬레이션 실행)
  - Phase B: 섹션 3 코어 고도화 (그래프 시각화, 역계산, 멀티셋 비교, Wiki SEQ 연동)
  - Phase C: 플랫폼 통합 (섹션 1→3 연결, 실시간 동기화, 팀 에이전트 라이브러리)
  - Phase D: 해커톤 차별화 (Extended Thinking, MCP 서버, Graph RAG, Observability)
  - 통합 후 아키텍처 및 데이터 플로우 다이어그램 포함

- [x] **section3-developer-guide.md 업데이트**
  - 상태 정보 현행화 (Phase 1+1.5 완료 반영)
  - 참고 문서 경로 업데이트 (section3-* 접두어 반영)

- [x] **section3-user-guide.md 업데이트**
  - 로드맵 테이블 현행화 (Phase A/B/C/D 구조로 변경)

---

## 2026-04-09 (외부 접속 + 개발 가이드 보완)

- [x] **SSE 스트리밍 프록시 추가** (`12cb42a`)
  - ngrok/LAN 환경에서 SSE 이벤트 스트리밍 정상 동작하도록 프록시 설정
  - Next.js rewrite 규칙에 SSE 엔드포인트 buffering off 적용

- [x] **section3-developer-guide.md 업데이트** (`181546d`)
  - 실제 실행 환경 기반 세팅 가이드 전면 재작성
  - Section 10 추가: 현재 구현된 아키텍처 전체 문서화
    - Slab 에이전트 API (SSE 이벤트 상세)
    - Custom Agent API (CRUD + 빌더 + 실행)
    - SimulationToolExecutor ReAct 루프 아키텍처
    - Tool Registry 자기 기술 시스템
    - Parallel Executor (asyncio.gather)
    - 온톨로지 그래프 구조
    - ActiveView 프론트엔드 뷰 라우팅

- [x] **의존성 누락 수정** (`5c1e46d`)
  - fresh install 시 빌드 실패하던 문제 해결
  - package.json / pyproject.toml 의존성 정리

---

## 2026-04-07 (Phase 1.5 Custom Agent Hub 완성)

- [x] **Custom Agent 시스템 전체 구현 (백엔드)**
  - `custom_agent.py` — Custom Agent CRUD API + 채팅 빌더 + 실행 API
  - `agent_builder_agent.py` — LLM 기반 에이전트 정의 수집 채팅 빌더
  - `custom_agent_runner.py` — 등록된 Custom Agent 실행기
  - `custom_agents.json` — 파일 기반 영구 저장소
  - SSE 이벤트: `agent_ready` (정의 완성 시) + 기존 `thinking/tool_call/tool_result/content_delta/done`

- [x] **Custom Agent 시스템 전체 구현 (프론트엔드)**
  - `CustomAgentHub.tsx` — 에이전트 카드 목록 + 채팅/양식 생성 버튼
  - `AgentBuilderChat.tsx` — AI와 대화하며 에이전트 설계 + 미리보기 카드 + 등록 버튼
  - `CustomAgentFormBuilder.tsx` — 구조화된 폼 기반 에이전트 생성 (아이콘/색상/도구/프롬프트)
  - `CustomAgentRunner.tsx` — 등록된 에이전트 실행 채팅 (에이전트별 독립 대화)
  - `SimulationSidebar.tsx` — Custom Agent 섹션 통합 (헤더 클릭→허브, 채팅/양식 빌더, 에이전트 목록)
  - `SimulationSection.tsx` — `activeView` 기반 뷰 라우팅 확장 (custom_hub/custom_chat_builder/custom_form_builder/custom_agent)

- [x] **Phase 1 연동 기능 완성**
  - Scenario A 딥링크: `done` 이벤트 + `suggested_width` → "이 주문을 Slab 설계 3D로 확인" 버튼
  - Scenario C 딥링크: `done` 이벤트 + `recommended_split_count` → "최적 분할수 N개를 3D로 확인" 버튼
  - Scenario B 딥링크: 영향받은 슬랩 Slab 설계 3D 연결 버튼
  - 온톨로지 그래프 Order 노드 클릭 → 시뮬레이터 자동 이동 + 파라미터 로딩
  - 주문 선택 드롭다운 (`GET /api/simulation/slab/orders` → SlabParamController 상단)

- [x] **Tool Registry 시스템 구축**
  - `tool_registry.py` — SimulationToolRegistry: 중앙 등록, Anthropic 스키마 조회, 실행
  - `tool_definitions.py` — 10개 도구 Anthropic tool_use 형식 JSON 스키마 선언
  - 시나리오별 도구 묶음: SCENARIO_A_TOOLS, SCENARIO_B_TOOLS, SCENARIO_C_TOOLS, ALL_TOOLS
  - `GET /api/simulation/slab/tools` — Custom Agent 빌더 UI용 도구 목록

- [x] **사용자 가이드 + 개발자 가이드 전면 작성**
  - `section3-user-guide.md` — 800줄 사용자 매뉴얼 (화면 구성, 시나리오 사용법, FAQ, 연동 흐름 5가지)
  - `section3-developer-guide.md` — Custom Agent API 상세 + 도구 추가 가이드 + 뷰 라우팅 설명 추가

---

## 2026-04-04 (Phase 1 시나리오 에이전트 + Slab 시뮬레이터 구축)

- [x] **시나리오 A/B/C AI 에이전트 구현**
  - `scenario_a_agent.py` — DG320 에러 진단 (주문 조회 → Edging 기준 확인 → 폭 조정 제안)
  - `scenario_b_agent.py` — Edging 파급효과 분석 (변경 파라미터 파싱 → 전체 주문 영향 스캔)
  - `scenario_c_agent.py` — 단중·분할수 최적화 (분할수 1~N 조합별 만족률 계산)
  - `llm_tool_executor.py` — Anthropic tool_use 기반 ReAct 루프 실행기 (모든 에이전트 공통)

- [x] **Slab 설계 도구 함수 7개 구현**
  - `mock_simulator.py` — get_order_info, simulate_width_range, suggest_adjusted_width, find_edging_specs_for_order, simulate_width_impact, batch_simulate_width_impact, find_orders_by_rolling_line, simulate_split_combinations, get_equipment_spec
  - `parallel_executor.py` — asyncio.gather 기반 병렬 주문 영향 분석 (시나리오 B용)
  - `ontology_graph.py` — NetworkX 기반 Mock 온톨로지 그래프 (build_mock_graph, find_edging_specs_for_order, find_orders_by_rolling_line)

- [x] **Slab Size Simulator 프론트엔드 구현**
  - `SlabSizeSimulator.tsx` — 3-pane 레이아웃 컨테이너
  - `SlabParamController.tsx` — 6개 파라미터 슬라이더 + 숫자 입력 + 상태 인디케이터 (🟢🟡🔴)
  - `SlabViewer3D.tsx` — Three.js 3D Slab 렌더링 (OrbitControls, 치수 라벨, 상태별 색상 코딩)
  - `SlabDesignViewer3D.tsx` — 고급 3D 뷰어 (분할 애니메이션, 시나리오 C 딥링크용)
  - `SlabImpactPanel.tsx` — SEQ 2~16 단계별 통과 여부 실시간 판정 트리
  - `SlabCompareTable.tsx` — 변경 전/후 파라미터 비교 테이블

- [x] **SEQ 1~16 설계 계산 엔진 구현**
  - `slab_size_simulator.py` — calculate_slab_design() 함수
  - SEQ2 두께 결정, SEQ3 1차 폭범위, SEQ4 길이범위, SEQ5 단중범위, SEQ8 분할수, SEQ9 매수, SEQ12 2차 폭범위, SEQ14 Target폭, SEQ16 Target길이
  - 설비 제약 기반 상태 판정 (ok/warning/error)

- [x] **Slab 에이전트 API 구축**
  - `slab_agent.py` — Slab 전용 API 라우터
  - `POST /api/simulation/slab/run` — 시나리오 A/B/C 에이전트 실행 (SSE 스트리밍)
  - `GET /api/simulation/slab/orders` — Mock 주문 목록
  - `GET /api/simulation/slab/ontology` — 온톨로지 그래프 JSON
  - `POST /api/simulation/slab/calculate` — Slab 설계 파라미터 계산
  - `GET /api/simulation/slab/constraints` — 슬라이더 min/max 범위용 설비 제약
  - `GET /api/simulation/slab/equipment` — 설비 스펙 데이터

- [x] **채팅 패널 + 온톨로지 그래프 구현**
  - `ChatPanel.tsx` — SSE 스트리밍 + 마크다운 렌더링 + 추론 과정/도구 호출 표시
  - `OntologyGraph.tsx` — vis-network 기반 그래프 시각화 (노드 타입별 색상, 에이전트 탐색 경로 하이라이트)

- [x] **프론트엔드 상태 관리 + API 클라이언트**
  - `useSimulationStore.ts` — Zustand 전역 상태 (activeView, graphData, customAgents, orders)
  - `useSlabSimulator.ts` — Slab 시뮬레이터 전용 훅 (파라미터 상태 + API 호출)
  - `api.ts` — API 클라이언트 + SSE 파서 (fetchOntologyGraph, runAgent, runCustomAgent, etc.)
  - `types.ts` — TypeScript 타입 정의 (CustomAgent, ActiveView, SLAB_TOOLS, SCENARIO_META)

- [x] **Mock 데이터 생성**
  - `mock_orders.json` — 5개 주문 (DG320 에러 1건 포함)
  - `mock_equipment_spec.json` — 연주설비 2대 + 열연설비 2대
  - `mock_edging_spec.json` — Edging 기준 3건 (HR-A 2구간 + HR-B 1구간)
  - `mock_ontology.json` — 13노드 12엣지 온톨로지 그래프

---

## 2026-04-02 (3-Section 플랫폼 스캐폴딩)

- [x] **3-Section 플랫폼 아키텍처 구현** (`00e81f2`)
  - `backend/simulation/` 스캐폴딩 — API 라우터, mock 서버, client Protocol, agent 빈 모듈
  - `backend/modeling/` 스캐폴딩 — API 라우터(health), 빈 모듈
  - `backend/shared/contracts/simulation.py` — Section 2↔3 typed 계약 (Pydantic 모델)
  - `main.py` 라우터 등록 — modeling_api, simulation_api, slab_agent_api, custom_agent_api
  - 프론트엔드 SectionNav 상단 탭 (Wiki/Modeling/Simulation)
  - SimulationSection 3-pane 레이아웃 + SimulationSidebar
  - ModelingSection placeholder 카드
  - MockModelingClient — 파라미터 기반 동적 결과 생성 (수요예측/재고최적화/리드타임분석)

---

## 2026-04-07 (세션 — SimCopilot 프론트엔드 통합 완료)

- [x] **Custom Agent 시스템 프론트엔드 통합**
  - `CustomAgentRunner.tsx` — 등록된 커스텀 에이전트 실행 채팅 UI (에이전트별 독립 대화)
  - `CustomAgentFormBuilder.tsx` — 양식 기반 에이전트 생성 UI (아이콘/색상/도구/프롬프트)
  - `SimulationSection.tsx` — 사이드바 통합 + `activeView` 기반 뷰 라우팅
  - `SimulationSidebar.tsx` — "Custom Agent" 헤더 → `custom_hub` 뷰 링크 추가
  - 앱 시작 시 `fetchCustomAgents()` 호출, 기존 에이전트 자동 로드
  - `api.ts` TypeScript 타입 캐스팅 수정 (`unknown` → 구체 타입)

- [x] **문서 업데이트 (`docs/`)**
  - `section3-user-guide.md` — 사이드바 레이아웃 설명 + Custom Agent 섹션(7-1~7-6) + FAQ + 로드맵
  - `section3-developer-guide.md` — 파일 구조 현행화 + Custom Agent API 상세 + 도구 추가 가이드 + 뷰 라우팅 설명

---

## 2026-04-01 (세션 27 — Phase 0 스캐폴딩 + 개발자 C 환경 구축)

- [x] **shared/contracts/ 생성** — `simulation.py` typed 계약 (DemandForecastParams, InventoryOptimizeParams, LeadTimeAnalysisParams, SimulationJob 등)
- [x] **shared/agent_framework/ 생성** — AgentPlugin Protocol re-export
- [x] **backend/simulation/ 스캐폴딩** — API 라우터, mock 서버(파라미터 기반), client Protocol, agent/visualization/storage 빈 모듈
- [x] **backend/modeling/ 스캐폴딩** — API 라우터(health), agent/ontology/code_analysis/mapping/simulation/data 빈 모듈
- [x] **main.py 라우터 등록** — modeling_api, simulation_api 등록 + MockModelingClient 초기화
- [x] **프론트엔드 Section 네비게이션** — SectionNav 상단 탭 (Wiki/Modeling/Simulation), useWorkspaceStore에 activeSection 상태 추가
- [x] **SimulationSection 3-pane 레이아웃** — 시나리오 목록(API 연동) + 대시보드 영역 + SimCopilot placeholder
- [x] **ModelingSection stub** — Phase 1 로드맵 카드 + ModelingCopilot placeholder
- [x] **개발자 C 가이드 문서** — `docs/section3-developer-guide.md` (실행법, 디렉토리, API 계약, mock 사용법, 규칙)
- [x] **전체 테스트 통과** — 177/177 pass + TypeScript 빌드 성공

---

## 2026-04-01 (세션 26 — 3-Section Platform 아키텍처 v2)

- [x] **3-Section 플랫폼 아키텍처 설계** — Wiki / Source-Domain Modeling / Simulation 3섹션 분리
- [x] **3관점 리뷰 수행** — Systems Architect, Developer C, Domain Expert 관점 검토 (26건 이슈 도출)
- [x] **리뷰 반영 아키텍처 v2 확정** — 시뮬레이션 2종 분리, SCOR+ISA-95, typed 계약, 비동기 job, 매핑 임계값 상향
- [x] **아키텍처 문서 작성** — `toClaude/reports/platform_architecture_v2.md` (16개 섹션)
- [x] **TODO.md 업데이트** — V2 Phase 0~3 태스크 44건 추가
- [x] **메모리 업데이트** — project_status, architecture_v2, user_role
- [x] **Phase 0 실행 시작** — 세션 27에서 스캐폴딩 + 개발자 C 환경 구축 완료

### 핵심 아키텍처 결정 (합의 완료)
- 에이전트 섹션별 독립 (공유 금지, Protocol만 공유)
- ISA-95 단독 X → SCOR + ISA-95 하이브리드 온톨로지
- 시뮬레이션 2종: 코드 영향분석(그래프 BFS) + 비즈니스시뮬(파라메트릭 모델)
- 매핑 자동승인 임계값 0.95 (제조업 기준 상향)
- 비동기 Job queue 필수 (동기 HTTP X)
- Typed 계약 (dict X → 시나리오별 Pydantic 모델)
- Chat + Dashboard 하이브리드 UI (섹션 3)
- 모노리스 솔직하게 인정 (Python Protocol → 나중에 HTTP 분리)
- MVP 순서: Phase 1은 코드 영향분석 (데이터 없이 가치 제공 가능)
- Neo4j Community (그래프 DB)

---

## 2026-04-01 (세션 23 — GitHub 배포 + 방법론 + 기술스택 + 에이전트 논의)

- [x] **README.md 한국어 가이드** — 주요 기능, 아키텍처, 실행법, API, 스킬 작성법, 배포 가이드
- [x] **GitHub 공개 배포** — Jeensh/onTong, v1.0.0 태그, 프론트엔드 서브모듈 fix
- [x] **위키 콘텐츠 교체** — IT 시스템 운영 데모용 21개 문서 (장애대응/인프라/보안/업무절차/개발운영 + 스킬 3개)
- [x] **Agentic Workflow 방법론** — agentic-workflow/ 폴더 (가이드 + 템플릿 5개 + CLAUDE.md 프리셋 3개 + 6-Layer 스킬 2개)
- [x] **Mermaid 다이어그램** — ASCII → Mermaid 전환, 서브에이전트 검토 반영
- [x] **기술스택 상세 문서** — docs/tech-stack.md 작성 완료 (2회 검토, 로컬에 있음, 미커밋)
- [x] **Pydantic AI 프레임워크 도입** — Hybrid 접근: 구조화된 출력(cognitive reflect, classify, edit, write, conflict) + ReAct 루프 + 스트리밍을 Pydantic AI로 전환. litellm 직접 호출을 llm_generate.py 1곳으로 격리. 신규 7파일, 수정 12파일, 테스트 174/174 PASS
- [x] **SIMULATION/DEBUG_TRACE 에이전트** — 스캐폴딩 완료. 본격 구현은 동료가 별도 진행 (본 TODO 범위 밖)

## 2026-04-01 (세션 25 — 충돌 문서 비교 해결 기능)

- [x] **ConflictPair 모델** — `schemas.py`에 `ConflictPair(file_a, file_b, similarity, summary)` 추가, `ConflictWarningEvent`에 `conflict_pairs` 필드 추가
- [x] **충돌 페어 빌드** — `rag_agent.py`에서 충돌 감지 시 문서 쌍별 similarity 계산 + 명시적 ConflictPair 목록 생성
- [x] **ConflictStore 연동** — `AgentContext`에 `conflict_store` 추가, 채팅에서 감지된 충돌을 ConflictStore에 등록하여 ConflictDashboard와 동기화
- [x] **채팅 충돌 배너 개선** — 페어별 유사도 표시 + "나란히 비교" 버튼 → 기존 DiffViewer에서 "A가 최신/B가 최신" 선택으로 해결
- [x] **해결 상태 반영** — DiffViewer에서 deprecation 완료 시 채팅 배너에 "해결됨" 표시 (`resolvedConflicts` 상태 관리)
- [x] **하위 호환** — `conflict_pairs`가 없는 기존 이벤트에서도 레거시 배너 정상 표시
- [x] **충돌 감지 오탐 수정** — 2차 conflict_check 조건을 관련도 60% 이상 문서 2개 이상으로 강화, 일반적 질문에서 불필요한 충돌 경고 방지
- [x] **충돌 요약 품질 개선** — conflict_details[:200] 단순 자르기 → 문서명 기반 문장 추출 (`_extract_pair_summary`)

## 2026-04-01 (세션 24 — Pydantic AI 데모 테스트 버그 수정)

- [x] **스킬 참조문서 wikilink 해석 버그** — `[[장애등급-분류기준]]` 등 하위 디렉토리 문서를 파일명만으로 찾지 못하던 문제. skill_loader에 파일명→전체경로 인덱스 추가
- [x] **Pydantic AI LiteLLMProvider API 키 버그** — LiteLLMProvider가 OPENAI_API_KEY를 무시하고 placeholder 키를 사용하던 문제. OpenAIProvider로 직접 교체하여 올바른 API 키 전달
- [x] **Write intent 패턴 확장** — "체크리스트/가이드/매뉴얼/절차서 만들어줘" 패턴 추가 (기존은 "문서/위키" 키워드 필수)
- [x] **LLM Provider 추상화** — llm_factory.py를 레지스트리 패턴으로 재설계. OpenAI/Anthropic/Ollama/Google/Azure/Groq/DeepSeek 7개 프로바이더 지원. .env의 LITELLM_MODEL만 변경하면 전환 가능
- [x] **LLM 모델 업그레이드** — gpt-4o-mini → gpt-4o로 변경
- [x] **키워드 라우팅 → LLM 통합 분류** — router.py의 40+ regex 규칙과 rag_agent.py의 edit/write regex를 제거. 단일 LLM 호출(UserIntent 모델)로 agent + action을 동시에 판단. 키워드 누락 문제 근본 해결
- [x] **문서 업데이트** — README.md (AI Copilot 설명, LLM 설정 7개 프로바이더, 환경 변수 테이블, 테스트 수 177), docs/tech-stack.md (LiteLLM→Pydantic AI 섹션 재작성, Ollama 연동 방식 업데이트)
- [x] **충돌 감지 버그 수정** — (1) context[:3000]→[:6000] 확장 (2) zip() 불일치 수정: relevant_docs/metas/dists 동기화 (3) cognitive reflection이 놓친 충돌을 conflict_check 스킬로 2차 감지
- [x] **Lineage 동기화 버그 수정** — status를 미설정으로 변경 시 supersedes/superseded_by 자동 정리 + 상대 문서의 역참조도 연동 삭제
- [x] **충돌 설명 한국어화** — cognitive reflection + conflict_check 스킬 프롬프트에서 conflict_details를 한국어로 출력하도록 변경
- [x] **채팅 입력 히스토리** — 위/아래 방향키로 이전 질문 재입력 기능 (세션 내 히스토리)
- [x] **문서 생성/수정 워크스페이스 직접 작업** — 채팅에서 승인 버튼 제거, workspace에서 바로 미리보기+승인/취소/편집. 생성: 렌더링된 미리보기+상단바(저장/직접편집/취소). 수정: DiffView에서 hunk별 선택+전체적용/되돌리기/직접편집. 채팅은 상태 메시지만 표시.

## 2026-04-01 (세션 22 — Skill 시스템 테스트 추가)

- [x] **skill_loader Unit 테스트** — frontmatter 파싱, 카테고리 추출, 6-Layer 섹션, 캐시, wikilink 참조 (39 tests)
- [x] **skill_matcher Unit 테스트** — substring/Jaccard 매칭, threshold, priority 가중치, 한국어 토큰화 (18 tests)
- [x] **Skill API Integration 테스트** — CRUD, toggle, move, match, context 엔드포인트 (20 tests)

## 2026-04-01 (세션 21 — 스킬 관리 편의 기능)

- [x] **스킬 우클릭 컨텍스트 메뉴** — 편집/복제/토글/삭제 메뉴 (SkillContextMenu 컴포넌트)
- [x] **스킬 삭제 기능** — confirm 확인 후 deleteSkill API 호출
- [x] **스킬 드래그앤드롭** — 카테고리 간 이동 (PATCH /api/skills/{path}/move + 네이티브 DnD)
- [x] **BE move API** — 카테고리 변경 시 파일 이동 + frontmatter 업데이트

## 2026-03-31 (세션 21 — FE 고급 설정 UI)

- [x] **SkillCreateDialog 모달** — 6-Layer 필드(역할/워크플로우/체크리스트/출력형식/제한사항) + 참조문서 피커 포함 스킬 생성 다이얼로그
- [x] **ReferencedDocsPicker** — /api/search/quick 기반 문서 검색/선택 컴포넌트
- [x] **GET /api/skills/{path}/context** — 스킬 6-Layer 컨텍스트 조회 API
- [x] **스킬 복제 6-Layer 복사** — handleDuplicate에서 context API로 전체 내용 복사
- [x] **SkillContext TypeScript 타입** — FE 타입 추가

## 2026-03-31 (세션 20 — 6-Layer Skill Architecture)

- [x] **SkillContext 구조체** — 6개 레이어(role, workflow, checklist, output_format, self_regulation + instructions) 독립 필드
- [x] **skill_loader 업그레이드** — load_skill_context()가 SkillContext 반환, 참조문서 누락 추적
- [x] **Preamble 런타임 주입** — 날짜, 사용자 이름, 참조문서 현황을 코드가 자동 수집
- [x] **6-Layer 프롬프트 빌더** — _handle_skill_qa()에서 레이어별 조건부 조립 (빈 레이어 skip → 하위호환)
- [x] **스킬 생성 템플릿 확장** — 역할/워크플로우/체크리스트/출력형식/제한사항 가이드 추가
- [x] **SkillCreateRequest 확장** — role, workflow, checklist, output_format, self_regulation 필드 (BE+FE)
- [x] **데모 스킬 업그레이드** — 신규입사자-온보딩.md를 6-layer 형식으로 전환
- [x] **후속 질문 스킬 유지** — sessionSkill state로 세션 내 스킬 자동 유지, X 버튼/세션 전환 시만 해제
- [x] **자동 매칭 스킬 유지** — onSkillMatch SSE에서도 sessionSkill 저장
- [x] **스킬 유지 UI** — pill에 "(유지 중)" 라벨, Zap 버튼 하이라이트
- [x] **테스트 회귀 확인** — 68/68 PASSED

## 2026-03-31 (세션 19 — Skill System 고도화)

- [x] **스킬 생성 템플릿** — 지시사항/배경/제약조건/질문예시/참조문서 가이드 자동 채움
- [x] **스킬 CRUD 직접 파일 쓰기** — create/update도 storage.write() 우회 (frontmatter 보존)
- [x] **참조 문서 탐색 시각화** — thinking step에서 각 참조 문서를 개별 표시 (📄 문서명 1/N)
- [x] **스킬 목록 API 비활성 포함** — list_skills(include_disabled=True)로 사이드바에서 재활성화 가능
- [x] **Copilot 피커 실시간 갱신** — 피커 열 때마다 refreshSkillList() 호출
- [x] **HR 스킬 파일 복원** — storage.write()로 frontmatter 손상된 파일 복구
- [x] **토글 API 직접 파일 쓰기** — storage.write() 우회하여 스킬 frontmatter 보존
- [x] **SE-1~12: Skill System 고도화** (카테고리 + 우선순위 + 무시 관리)
  - BE: SkillMeta에 category/priority/pinned 필드 추가
  - skill_loader: 폴더 경로 기반 카테고리 자동 추출 (_skills/HR/file.md → "HR")
  - skill_matcher: priority 곱셈 가중치 (score * (0.8 + p*0.04)) + tiebreaker 확장
  - PATCH toggle API: enabled 필드 flip
  - FE 사이드바: 카테고리 접이식 그룹, 검색, 토글(활성/비활성), 복제 버튼, pinned 표시
  - FE 생성 폼: 카테고리(combobox) + 우선순위 입력 추가
  - Copilot 피커: 카테고리별 그룹핑 + 스킬 검색
  - localStorage: dismissed skills 영속화
  - 데모 스킬 카테고리 폴더 이동: HR/신규입사자, Finance/출장비, @개발자/SCM/구매발주

---

## 2026-03-31 (세션 18 — User-Facing Skill System)

- [x] **US-1~15: User-Facing Skill System 전체 구현** (6 phases)
  - Phase 1: 스키마(SkillMeta, SkillListResponse, SkillCreateRequest) + skill_loader + skill_matcher
  - Phase 2: AgentContext 확장 + api/agent.py 스킬 해석 + RAGAgent._handle_skill_qa
  - Phase 3: Skill CRUD API + main.py 와이어링
  - Phase 4: 사이드바 ⚡ 스킬 탭 + 인라인 생성 폼
  - Phase 5: Copilot 스킬 피커 + 자동 제안 + SSE skill_match 이벤트
  - Phase 6: 그래프 스킬 노드 (보라색 다이아몬드)
- [x] **데모용 샘플 스킬 3개 생성**
  - `_skills/출장비-정산-도우미.md` (공용, trigger: 출장비/출장 정산)
  - `_skills/신규입사자-온보딩.md` (공용, trigger: 신규입사/온보딩)
  - `_skills/@개발자/구매발주-안내.md` (개인, trigger: 구매발주/납품 검수)

---

## 2026-03-30 (세션 16 — 문서 관계 그래프 리디자인)

- [x] **P3-AH5: 그래프 검색 우선 UX** — 전체 그래프 대신 검색 우선 UI로 전환. 중심 문서 선택 후 BFS 관계만 표시
  - `DocumentGraph.tsx`: 검색 랜딩 페이지 + `/api/search/quick` 디바운스(200ms) + 인라인 문서 전환 검색
  - `search.py`: `center_path` 필수 파라미터로 변경, 유사도 엣지 conflict store에서 읽기 (broken import 수정)

---

## 2026-03-30 (세션 15 — 충돌 감지 리팩토링)

- [x] **CR-1: ChromaDB 네이티브 유사도 검색** — `get_file_embeddings()`, `query_by_embedding()` 추가
- [x] **CR-2: ConflictStore 신규** — Redis/InMemory 이중 백엔드, SHA256 해시 키, `replace_for_file`/`remove_for_file`
- [x] **CR-3: ConflictService 리라이트** — `check_file()` 증분 감지, `full_scan()`, `get_pairs()`, `update_metadata()`
- [x] **CR-4: API 수정** — `/duplicates` store 읽기, `/full-scan` + `/scan-status` 신규
- [x] **CR-5: WikiService 훅** — `_bg_index()`, `delete_file()`, `move_file()`, `move_folder()`에 충돌 감지 연결
- [x] **CR-6: 프론트엔드** — 즉시 로드 + "전체 스캔" 버튼 + 프로그레스 바
- [x] **CR-7: 테스트** — conflict_store, conflict_service, API, E2E (23 tests 통과)

---

## 2026-03-30 (세션 14 — Phase 5 구현)

- [x] P5A-1: 트리 Lazy Loading — depth=1 초기 로드 + subtree API, `has_children` 플래그
- [x] P5A-2: 서버 사이드 검색 — MiniSearch 제거, `/api/search/quick` + `/api/search/resolve-link`
- [x] P5A-3: 트리 증분 업데이트 — CRUD 후 낙관적 로컬 업데이트 (fetchTree 제거)
- [x] P5A-4: 프론트엔드 ETag 활용 — `fetchWithETag()` 유틸리티, 304 캐시
- [x] P5B-1: Uvicorn 멀티 워커 — `--workers 4` + Docker 리소스 제한
- [x] P5B-2: 비동기 인덱싱 — save 즉시 반환 + IndexStatus 추적
- [x] P5B-2a: 인덱싱 상태 UI — 에디터 "검색 반영 대기 중" 배너
- [x] P5B-3: BM25 주기적 리빌드 — 10초 데몬 스레드
- [x] P5B-4: 하이브리드 검색 병렬화 — vector + BM25 병렬 실행
- [x] P5B-5: 시작 시 백그라운드 인덱싱 — 앱 즉시 가용
- [x] P5B-6: list_all_files() 최적화 — asyncio.to_thread + list_file_paths()
- [x] P5C-1: Redis 도입 + Lock 이관 — SET NX EX, LockBackend ABC, 자동 폴백
- [x] P5C-2: Redis 기반 쿼리 캐시 — RedisQueryCache, file→key 인덱스
- [x] P5C-3: Lock Refresh 배치화 — lockManager 중앙 매니저 + batchRefreshLock API
- [x] P5C-4: ACL 캐싱 + 핫 리로드 — check_permission LRU 캐시(60s TTL), 30s 파일 변경 감지
- [x] P5D-1: Nginx 리버스 프록시 — nginx.conf + docker-compose nginx 서비스
- [x] P5D-2: Docker 리소스 제한 — 이전 세션에서 완료 (backend 4C/4G, frontend 1C/1G 등)
- [x] P5D-3: ChromaDB 커넥션 풀링 — chromadb.Settings 설정
- [x] P5D-4: get_all_embeddings 페이지네이션 — offset/limit 1000건 배치 조회
- [x] P5D-5: SSE 실시간 이벤트 — EventBus + /api/events SSE endpoint + TreeNav 구독
- [x] P5E-1: RAG LLM 파이프라인 최적화 — reflection 캐시로 반복 쿼리 LLM 호출 스킵
- [x] P5E-2: LLM 응답 캐싱 — cognitive_reflect 인메모리 LRU (256개, TTL 10분)
- [x] P5E-3: Ollama 동시 처리 — OLLAMA_NUM_PARALLEL=4, asyncio.Semaphore(8)
- [x] P5E-4: 검색 인덱스 캐싱 — backlinks/tags 엔드포인트 60s TTL 캐시
- [x] P5E-5: 메타데이터 엔드포인트 최적화 — `list_all_metadata()` (frontmatter 4KB만 읽기) + 60s TTL 캐시
- [x] **충돌 감지 성능 개선 + 500 에러 수정** — numpy 벡터화 코사인 유사도, asyncio.to_thread() 래핑, threshold 0.95로 상향, 결과 200건 제한, 120s TTL 캐시. ChromaDB get_all_embeddings 79초 병목은 캐싱으로 완화.

---

## 2026-03-30 (세션 13)

- [x] Phase 4 프로덕션 작업 리포트 작성 → `toClaude/reports/phase4_production_readiness.md`
- [x] Phase 4 검토/테스트 플랜 작성 → `toClaude/reports/phase4_review_test_plan.md`
- [x] 대규모 대응 규모 분석 (컴포넌트별 병목, 커버 가능 규모 판정)
- [x] 스트레스 테스트 스크립트 3종 포함 (파일 규모, 동시 사용자, 잠금 동시성)
- [x] 스트레스 테스트 실행 + 결과 리포트 → `toClaude/reports/phase4_stress_test_results.md`
- [x] Phase 5 엔터프라이즈 스케일링 플랜 수립 (23 tasks, 5 sub-phase)
- [x] TODO.md에 Phase 5 태스크 추가 (P5A~P5E)

---

## 2026-03-29 (세션 12 — Phase 4 프로덕션 준비)

- [x] P4A-1: PDF.js worker 로컬 번들링 (unpkg CDN → public/)
- [x] P4A-2: Google Fonts 제거 → 시스템 폰트 스택
- [x] P4A-3: LLM 설정 추상화 (Ollama 기본값, OpenAI 옵션)
- [x] P4A-4: 임베딩 로컬 전환 (설정 기반, ChromaDB 기본 embedding)
- [x] P4A-5: 외부 의존성 점검 스크립트
- [x] P4B-1: Backend Dockerfile (Python 3.10-slim 멀티스테이지)
- [x] P4B-2: Frontend Dockerfile (Node 20-alpine 멀티스테이지 + standalone)
- [x] P4B-3: docker-compose.yml 통합 (backend+frontend+chroma, monitoring profile)
- [x] P4B-4: 환경 변수 분리 (.env.example + .env.production.example)
- [x] P4B-5: 헬스체크 + 시작 순서 + .dockerignore
- [x] P4C-3: NASBackend 구현 (LocalFSAdapter 서브클래스, 마운트 경로 검증)
- [x] P4C-4: 스토리지 팩토리 설정 기반 전환 (STORAGE_BACKEND=local/nas)
- [x] next.config.ts: standalone 출력 모드 + BACKEND_URL 환경변수 지원
- [x] P4D-1: Lock 서비스 (인메모리, TTL 5분, 자동 만료)
- [x] P4D-2: Lock API (POST /lock, DELETE, GET /status, POST /refresh)
- [x] P4D-3: 에디터 잠금 UI (잠금 획득, 읽기전용 배너, 세션 사용자 ID)
- [x] P4D-4: 자동 해제 (탭 닫기 → releaseLock, 2분 주기 TTL 리프레시)
- [x] P4F-1: .gitignore 강화 (.pem, .key, credentials.json 추가)
- [x] P4F-2: CORS 강화 (와일드카드 → 명시적 메서드/헤더 화이트리스트)
- [x] P4F-3: 구조화 로깅 (JSON 포맷 + request_id 미들웨어)
- [x] P4F-4: 입력 검증 (path traversal 차단, content 10MB 제한)
- [x] P4F-5: 전역 에러 핸들러 (500 → JSON 응답, ValueError → 400)
- [x] P4E-1~2: ACL 저장소 (JSON 기반, 폴더 상속, document 오버라이드)
- [x] P4E-3: require_read/require_write 의존성
- [x] P4E-4: Wiki API에 읽기/쓰기 권한 체크 적용
- [x] P4E-5: RAG 검색 결과에 ACL 기반 필터 추가
- [x] P4E-7: ACL 관리 API + PermissionEditor UI + TreeNav 메뉴
- [x] P4G-1: 검색 인덱스 API에 offset/limit 페이지네이션
- [x] P4G-2: 트리 API depth 파라미터 + subtree lazy load API
- [x] P4G-3: ChromaDB upsert 100건 단위 배치 처리
- [x] P4G-4: 트리 API ETag/304 캐싱

---

## 2026-03-29 (세션 11)

- [x] **Phase 3-A: 문서 검색 (커맨드 팔레트)** (7 tasks)
  - MiniSearch 클라이언트 사이드 검색 (즉시 결과, prefix+fuzzy, 한글 토크나이저)
  - 서버 사이드 하이브리드 검색 API (`GET /api/search/hybrid` — BM25+벡터 RRF)
  - Ctrl+K / Cmd+K 커맨드 팔레트 UI (cmdk CommandDialog 기반)
  - 키워드/의미 검색 모드 전환, 결과 하이라이트, 태그 뱃지, 스니펫 미리보기
  - TreeNav 사이드바 헤더에 검색 아이콘 추가

- [x] **Phase 3 고도화** (4 tasks)
  - 문서 열기 시 연결 문서 패널 (lineage + wiki-link 백링크, 참조/역참조, 접이식)
  - 그래프 내 문서 검색 (검색→노드 센터링+줌)
  - 문서 링크 복사 — 사이드바 우클릭 "문서 링크 복사" (md→`[[문서명]]`, 기타→경로)
  - WikiLink 인라인 노드: `[[문서명]]` 타이핑/붙여넣기 시 클릭 가능한 링크로 자동 변환, 클릭 시 openTab

- [x] **Phase 3-B: 문서 관계 그래프** (13 tasks)
  - react-force-graph-2d 기반 force-directed 그래프 시각화
  - 그래프 데이터 API (`GET /api/search/graph` — 백링크+lineage+related+similarity 집계, BFS)
  - 4가지 연결 타입: wiki-link(gray), supersedes(orange), related(blue/dashed), similar(red/dotted)
  - 노드: status별 색상, degree 기반 크기, 라벨, 호버 툴팁
  - 노드 클릭→문서 열기, 우클릭→컨텍스트 메뉴, 현재 문서 중심 보기
  - center_path + depth BFS로 대규모 위키 성능 보장
  - Virtual Tab (`"document-graph"`), 관리 섹션 메뉴 진입점

---

## 2026-03-29 (세션 10)

- [x] **P2B-6: RAG deprecated 문서 필터링 + 최신 문서 자동 대체** (3 tasks)
  - 검색 시 deprecated 문서 제외 (ChromaDB where + BM25 필터)
  - deprecated만 검색 시 superseded_by 체인 추적 → 최신 문서 자동 대체
  - 기존 +0.3 패널티 로직 제거

- [x] **P2B-7: 충돌 대시보드 해결 상태 관리** (3 tasks)
  - DuplicatePair에 resolved 필드 + 양방향 lineage 자동 해결 판정
  - API filter 파라미터 (unresolved/resolved/all)
  - 프론트엔드 탭 필터 (미해결/해결됨/전체), 기본값 "미해결"

- [x] **증분 인덱싱 해시 비교 버그 수정** — frontmatter만 변경 시 인덱싱 스킵되던 문제
- [x] **conflict_service numpy array 비교 버그** — ChromaDB embeddings가 numpy array → len() 체크로 변경
- [x] **deprecate API 500 에러 수정** — storage.save → _serialize_frontmatter + save_file로 변경
- [x] **DiffViewer React key 경고 수정** — Fragment key 추가
- [x] **CONFLICT_CHECK 프롬프트 강화** — 다른 팀/부서의 다른 수치도 충돌로 판정
- [x] **ChromaDB 메타데이터 동기화 버그 수정** — `_metadata_to_chroma()`에 `superseded_by`/`supersedes` 누락 → 추가
- [x] **deprecate API force reindex** — 상태 변경 후 ChromaDB 즉시 동기화 보장
- [x] **메타데이터 완전성 가드 테스트** — `DocumentMetadata` 스칼라 필드 누락 시 테스트 실패
- [x] **`_metadata_to_chroma()` 자동생성 전환** — 수동 필드 나열 → `DocumentMetadata.model_fields` 순회 방식으로 변경. 새 필드 추가 시 자동 반영
- [x] **재고관리 샘플 데이터 lineage 누락 수정** — v1에 `superseded_by`, v2에 `supersedes` 추가

---

## 2026-03-28 (세션 9)

- [x] **증분 인덱싱 해시 비교 버그 수정** — frontmatter만 변경 시 인덱싱 스킵되던 문제
  - `wiki_indexer.py`: `has_changed()` 비교 대상을 `wiki_file.content` → `wiki_file.raw_content`로 변경
  - `sseClient.ts`: `onSources` 콜백 타입에 `status`, `updated`, `updated_by` 필드 추가

- [x] **P2B-5: 문서 계보(Lineage) 시스템** (5 tasks)
  - `schemas.py`: `DocumentMetadata`에 `supersedes`, `superseded_by`, `related` 필드 추가
  - `local_fs.py`: frontmatter 파싱/직렬화에 lineage 필드 반영
  - `rag_agent.py`: superseded 문서 +0.3 거리 패널티 + "폐기됨" 경고 삽입
  - `api/wiki.py`: `GET /api/wiki/lineage/{path}` — 계보 트리 반환 (supersedes/superseded_by/related 해석)
  - `LineageWidget.tsx`: 에디터 상단 lineage 배너 (이전/새 버전 링크, 관련 문서)
  - `DiffViewer.tsx`: "A가 최신"/"B가 최신" 버튼 → bidirectional lineage 자동 설정
  - `tests/test_p2b5_lineage.py`: 10 tests (lineage 필드, frontmatter roundtrip, 패널티) ✅

- [x] **P2B-4: 인라인 비교 뷰** (5 tasks)
  - `api/wiki.py`: `GET /api/wiki/compare?path_a=&path_b=` — 두 문서 body+메타데이터 반환
  - `DiffViewer.tsx`: side-by-side diff (추가=녹색, 삭제=빨강, 변경=amber), 라인 번호
  - `workspace.ts`: `document-compare` VirtualTabType
  - `useWorkspaceStore.ts`: `openCompareTab(pathA, pathB)` 메서드 + 타이틀 자동 생성
  - `FileRouter.tsx`: compare 탭 라우팅 (filePath에서 경로 파싱)
  - `DiffViewer.tsx`: "A가 최신"/"B가 최신" 버튼 → deprecated 자동 설정
  - `ConflictDashboard.tsx`: "나란히 비교" 버튼 → openCompareTab 연동

- [x] **P2B-3: 문서 중복/충돌 감지 대시보드** (5 tasks)
  - `chroma.py`: `get_all_embeddings()` — 전체 임베딩/문서/메타데이터 조회
  - `conflict/conflict_service.py`: `ConflictDetectionService` — 파일별 평균 임베딩 + 코사인 유사도 쌍 탐지
  - `api/conflict.py`: `GET /duplicates` (유사 문서 쌍) + `POST /deprecate` (deprecated 설정)
  - `main.py`: conflict_api 라우터 등록
  - `workspace.ts`: `conflict-dashboard` VirtualTabType 추가
  - `useWorkspaceStore.ts`: 탭 타이틀 추가
  - `FileRouter.tsx`: ConflictDashboard 라우팅
  - `TreeNav.tsx`: 관리 섹션에 "문서 충돌 감지" 메뉴 (AlertTriangle 아이콘)
  - `ConflictDashboard.tsx`: 유사도 임계값 조절 + 유사 문서 쌍 테이블 + 파일 열기/폐기 액션
  - `tests/test_p2b3_conflict_dashboard.py`: 11 tests (코사인유사도, 평균임베딩, 서비스 통합)

- [x] **P2B-2: 메타데이터 기반 신뢰도 표시** (5 tasks)
  - `schemas.py`: `DocumentMetadata.status` 필드 추가 (draft/review/approved/deprecated)
  - `local_fs.py`: frontmatter 파싱/직렬화에 status 반영
  - `wiki_indexer.py`: ChromaDB metadata에 status 포함
  - `schemas.py`: `SourceRef`에 `updated`, `updated_by`, `status` 필드 확장
  - `rag_agent.py`: `_build_sources()`에서 메타데이터 주입
  - `agent.ts`: SourceRef 타입 확장
  - `AICopilot.tsx`: 소스 패널에 status 아이콘/색상 + 날짜 배지 + 상세 tooltip
  - `wiki.ts`: `DocumentStatus` 타입 + `DocumentMetadata.status`
  - `MetadataTagBar.tsx`: status 드롭다운 + collapsed 뱃지
  - `frontmatterSync.ts`: status 파싱/직렬화
  - `tests/test_p2b2_status_field.py`: 10 tests (스키마, SourceRef, frontmatter roundtrip)

- [x] **P2B-1: RAG 답변 충돌 감지 프롬프트** (4 tasks)
  - `rag_agent.py`: `_build_context_with_metadata()` — 각 청크에 [출처/작성자/최종수정/도메인/관련도] 헤더 삽입, 중복 파일 표시
  - `rag_agent.py`: `FINAL_ANSWER_SYSTEM_PROMPT`에 문서 충돌 감지 규칙 추가 (모순 시 ⚠️ 경고 + 최신 문서 권고)
  - `rag_agent.py`: `COGNITIVE_REFLECT_PROMPT`에 CONFLICT_CHECK 항목 + `has_conflict`/`conflict_details` JSON 필드
  - `schemas.py`: `ConflictWarningEvent` 스키마 신규 (details + conflicting_docs)
  - `agent.ts`: `ConflictWarningEvent` 타입 추가
  - `sseClient.ts`: `onConflictWarning` 콜백 + dispatch 처리
  - `AICopilot.tsx`: `ConflictWarning` 인터페이스, ChatMessage에 필드 추가, amber 경고 배너 UI
  - `tests/test_p2b1_conflict_detection.py`: 8 tests (메타데이터 헤더, 스키마, 프롬프트 검증)

---

## 2026-03-28 (세션 8)

- [x] **P2A-1: LLM 호출 병렬화 + 제거** (4 tasks)
  - `router.py`: 키워드 규칙 확대 — 기업/도메인 용어 + 한글 catch-all 패턴 추가 (11/12 키워드 적중)
  - `rag_agent.py`: `_check_clarity` LLM 호출 → `_check_clarity_rule_based` 규칙 기반으로 전환 (0ms)
  - `agent.py` + `rag_agent.py`: 라우팅 + 쿼리보강 `asyncio.gather` 병렬화, `augmented_query` 파라미터 전달
  - `tests/bench_rag_latency.py`: 파이프라인 지연시간 벤치마크 스크립트 (키워드 적중률, 순차/병렬 비교)

- [x] **메타데이터 템플릿 한글 IME 버그 수정**
  - `MetadataTemplateEditor.tsx`: `onKeyDown`에 `isComposing` 체크 추가 — 한글 조합 중 Enter 이중 등록 방지

- [x] **샘플 PDF/PPTX 파일 재생성**
  - 이전 세션에서 깨진 파일(8B/70B) → reportlab/python-pptx로 정상 재생성

- [x] **P2A-2: 하이브리드 검색 (벡터 + BM25)** (5 tasks)
  - `infrastructure/search/bm25.py`: BM25Okapi 인덱스 + 한글/영어 토크나이저
  - `infrastructure/search/hybrid.py`: RRF(Reciprocal Rank Fusion) 병합
  - `rag_agent.py`: 하이브리드 검색 적용, thinking step에 검색 모드 표시
  - `wiki_indexer.py`: BM25 인덱스 자동 동기화 (추가/삭제/전체 재인덱싱)
  - `tests/test_hybrid_search.py`: 검색 품질 비교 테스트

- [x] **P2A-3: 증분 인덱싱** (4 tasks)
  - `infrastructure/storage/file_hash.py`: SHA256 해시 기반 변경 감지
  - `wiki_indexer.py`: 해시 비교 → 미변경 파일 스킵 (15파일 0초 완료)
  - `wiki.py`: `POST /api/wiki/reindex?force=true` 파라미터 추가

- [x] **P2A-4: 임베딩/검색 캐싱** (4 tasks)
  - `infrastructure/cache/query_cache.py`: LRU 캐시 (TTL 5분, 128 entries)
  - `rag_agent.py`: 캐시 히트 시 검색 스킵 ("캐시" 모드 표시)
  - `wiki_indexer.py`: 문서 변경 시 해당 파일 관련 캐시 자동 무효화
  - 캐시 히트율 모니터링 로그 내장

- [x] **P2A-5: 메타데이터 사전 필터링** (4 tasks)
  - `application/agent/filter_extractor.py`: domain/process 키워드 자동 추출
  - `rag_agent.py`: 추출 필터 → ChromaDB where 절 적용 + 0건 시 필터 제거 fallback

- [x] **P2A-6: Cross-encoder 리랭킹** (4 tasks)
  - `infrastructure/search/reranker.py`: LLM 기반 리랭킹 (기존 LiteLLM 활용)
  - `rag_agent.py`: 검색 후 리랭킹 단계 추가
  - `config.py`: `enable_reranker` 설정 (on/off), 지연 시간 로깅
  - `tests/test_reranker.py`: A/B 비교 테스트

- [x] **Phase 2-B: 문서 충돌 감지 & 해소 계획 수립** (5 Steps, 24 Tasks)
  - `master_plan.md`에 Phase 2-B 섹션 추가 (배경, 5단계 상세 설계, 타임라인)
  - `TODO.md`에 P2B-1 ~ P2B-5 태스크 테이블 추가 + 진행 요약 갱신
  - 항목: RAG 충돌 감지 프롬프트, 메타데이터 신뢰도, 중복 감지 대시보드, 인라인 비교 뷰, 문서 계보

---

## 2026-03-28 (세션 7)

- [x] **Phase 1.5: PDF Viewer 구현**
  - `react-pdf` 패키지 설치
  - `PdfViewer.tsx`: 페이지 네비게이션, 6단계 줌(50%~200%), 50페이지 이상 페이지 그룹 페이지네이션
  - 키보드 화살표 네비게이션, 페이지 번호 직접 입력
  - `FileRouter.tsx`: dynamic import (ssr: false)

- [x] **Phase 1.5: Presentation Viewer 구현**
  - 백엔드: `GET /api/files/pptx-data/{path}` — python-pptx로 슬라이드 JSON 추출 (텍스트/이미지/서식)
  - `PresentationViewer.tsx`: 백엔드 JSON → HTML/CSS 렌더링, 슬라이드 네비게이션, 키보드 조작
  - pptx-viewer 패키지는 Turbopack 호환 문제로 제거, 백엔드 파싱 방식으로 전환

---

## 2026-03-26 (세션 5)

- [x] **에이전트 라우팅/RAG 고도화 — 일반 질문 WIKI_QA 미라우팅 수정**
  - `router.py`: KEYWORD_RULES 확장 — 일반 검색(찾아줘, 누구, 어떻게 등) 패턴 WIKI_QA 매칭
  - `router.py`: LLM classifier 프롬프트 개선 — UNKNOWN 대신 WIKI_QA를 기본 폴백으로 설정
  - `rag_agent.py`: 시스템 프롬프트 범용화 ("제조 SCM 도메인" → "사내 Wiki", 인사/조직 등 포함)
  - `rag_agent.py`: Clarity check 조건 완화 — `len(query) < 10` 제거, 관련성 기반으로만 판단
  - `rag_agent.py`: Clarity check 프롬프트 개선 — 구체적 키워드 있으면 CLEAR 처리

- [x] **RAG 검색 품질 고도화 — 구조화 데이터(인사정보) 미검색 수정**
  - `rag_agent.py`: 대화 히스토리 기반 쿼리 보강 (`_augment_query`) — 후속 질문에 이전 맥락 반영
  - `rag_agent.py`: 시스템 프롬프트 강화 — 구조화 데이터(키:값) 추출, 인사정보 이름/소속 명시 규칙
  - `rag_agent.py`: 검색 범위 확대 (n_results 5→8) + MIN_SOURCE_RELEVANCE 0.4→0.3
  - `wiki_indexer.py`: 짧은 문서에 파일 경로 컨텍스트 프리픽스 추가 → 임베딩 품질 향상

- [x] **RAG 탐색 과정 시각화 (하이브리드 방식)**
  - Backend: `ThinkingStepEvent` 스키마 추가, RAG 파이프라인 각 단계에서 `thinking_step` SSE 이벤트 방출
  - 단계: 쿼리 보강 → 문서 검색 → 명확성 확인 → 답변 생성 (각각 start/done 상태)
  - Frontend: `ThinkingStepsDisplay` 컴포넌트 — 진행 중 애니메이션 + 완료 후 접이식 로그
  - SSE client에 `onThinkingStep` 콜백 추가

- [x] **Self-Reflective Cognitive Pipeline (Option A: Two-Step Run)**
  - `rag_agent.py`: `_cognitive_reflect()` — 숨겨진 LLM 호출로 의도분석/초안/자기검토 수행, 백엔드 콘솔에만 로깅
  - `rag_agent.py`: 최종 답변 생성 시 critique 피드백을 시스템 프롬프트로 주입 → 품질 향상
  - `rag_agent.py`: `FINAL_ANSWER_SYSTEM_PROMPT` — 공감 IT 파트너 페르소나, Minto Pyramid, 실행 가능 다음 단계
  - `rag_agent.py`: `COGNITIVE_REFLECT_PROMPT` — 3단계 인지 분석 (thought/draft/critique)
  - `AICopilot.tsx`: `cognitive_reflect` thinking step + Brain 아이콘 추가
  - **SSE 파이프라인 무변경**: content_delta에는 최종 답변만 전송, 내부 사고 절대 미노출

- [x] **Phase 2-A: RAG 성능 고도화 계획 수립** (6 Steps, 25 Tasks)
  - `master_plan.md`에 Phase 2-A 섹션 추가 (배경, 6단계 상세 설계, 타임라인)
  - `TODO.md`에 P2A-1 ~ P2A-6 태스크 테이블 추가 + 진행 요약 갱신
  - 항목: LLM 병렬화, 하이브리드 검색, 증분 인덱싱, 캐싱, 메타데이터 필터링, 리랭킹

---

## 2026-03-26 (세션 4)

- [x] **문서 메타데이터 이력 관리 (생성일/수정일/생성자/수정자)**
  - `DocumentMetadata`에 `updated`, `created_by`, `updated_by` 필드 추가 (기존 `author` → `created_by` 마이그레이션)
  - Backend Storage Layer: 저장 시 자동 타임스탬프/작성자 주입 (`created`/`created_by`는 최초만, `updated`/`updated_by`는 매번)
  - WikiService + Wiki API에 `user_name` 전달 경로 연결 (인증 레이어 활용)
  - ChromaDB indexer에 새 필드 반영 → RAG 검색에서 활용 가능
  - Frontend: 타입/파서/시리얼라이저 업데이트, MetadataTagBar에 읽기전용 이력 표시

- [x] **AI Copilot 마크다운 렌더링 + 저장 후 메타데이터 갱신 버그 수정**
  - `react-markdown` + `remark-gfm` 설치, AssistantBubble에 마크다운 렌더링 적용
  - prose 스타일링 (볼드, 이탤릭, 코드, 리스트, 테이블, 헤딩 등)
  - `handleSave` 후 서버 응답의 metadata를 로컬 상태에 반영 (updated/updated_by 갱신)

- [x] **사이드바 빈 공간 우클릭 컨텍스트 메뉴**
  - 빈 공간 우클릭 시 "새 문서" / "새 폴더" 메뉴 표시 (루트 레벨)
  - ContextMenuState.node를 nullable로 변경, RootDropZone에 onContextMenu 핸들러 추가

- [x] **인증 추상화 레이어 (Auth Abstraction Layer)**
  - Backend: `backend/core/auth/` — User 모델, AuthProvider ABC, NoOpProvider, FastAPI Depends
  - Backend: 전체 API 라우터에 `dependencies=[Depends(get_current_user)]` 적용
  - Backend: `config.py`에 `auth_provider` 설정, `factory.py`로 provider 선택
  - Frontend: `lib/auth/` — AuthProvider 인터페이스, AuthContext, useAuth hook, DevAuthProvider
  - Frontend: `Providers.tsx` → `layout.tsx` 연결, `useAuthFetch` 유틸
  - 추후 SSO/LDAP/OIDC 등으로 교체 시 Provider만 구현하면 됨

---

## 2026-03-26 (세션 3)

- [x] **TreeNav 활성 파일 강조 + 폴더 기본 접힘**
  - 현재 열린 탭의 파일이 사이드바에 `bg-primary/15` 강조 표시
  - 폴더 기본값 접힘 (`useState(false)`), 활성 파일 포함 폴더만 자동 펼침
  - `activeFilePath` prop을 DraggableTreeItem에 전달

- [x] **Context Engineering 시스템 업그레이드**
  - `toClaude/archive/` 생성, 기존 요약/이슈 파일 8개 아카이브 이동
  - CHECKLIST.md → 테스트 매뉴얼로 전환 (모든 체크박스 제거)
  - `agent_tools_schema.md` 스켈레톤 생성 (PydanticAI tool SSOT)
  - CLAUDE.md에 Smart TDD Rule + Archive Rule 추가
  - TODO.md = 상태 추적 SSOT 확립

---

## 2026-03-26 (세션 2)

- [x] **RAG 에이전트 명확화 질문 기능** (Step 1-F 고도화)
  - 모호한 질문 시 바로 답변하지 않고 검색 결과 기반 명확화 질문
  - 검색 결과를 보여주면서 선택지 제시 ("이런 문서를 찾았는데 어떤 걸 원하시나요?")
  - 대화 히스토리 활용 (세션 내 멀티턴 맥락 유지)

- [x] **RAG 출처 참조 고도화** (Step 1-F 고도화)
  - 관련도 필터링: MIN_SOURCE_RELEVANCE(0.4) 미만 출처 제외
  - 명확화 질문 시 낮은 threshold(0.2)로 참조 문서 표시
  - 구체적 답변 시 높은 threshold(0.4)로 관련 문서만 표시

- [x] **UI 라벨 변경**
  - AI Copilot → On-Tong Agent
  - 사이드바 Wiki → On-Tong

- [x] **에이전트 세션 관리** (Step 1-F 고도화)
  - 새 대화 시작 / 세션 목록 / 세션 전환 / 세션 삭제
  - 첫 메시지 기반 세션 제목 자동 생성
  - 세션별 독립된 대화 히스토리

- [x] **드래그앤드롭 + 이름 변경** (Step 1-A 고도화)
  - @dnd-kit DndContext + DragOverlay + PointerSensor(distance:8)
  - DraggableTreeItem: useDraggable + useDroppable(폴더만)
  - RootDropZone: 루트 레벨 드롭 지원
  - 이름 변경: 우클릭 → InlineInput 인라인 편집 → PATCH API
  - 열린 탭 경로 자동 업데이트 (updateTabPath 스토어 메서드 추가)
  - 백엔드: PATCH /api/wiki/file/{path}, PATCH /api/wiki/folder/{path}

- [x] **사이드바 파일/폴더 관리** (Step 1-A 고도화)
  - 새 문서 생성 (+ 버튼 → 파일명 입력 → .md 자동 생성)
  - 파일 삭제 (우클릭 → 컨텍스트 메뉴 → 삭제 + 탭 자동 닫기)
  - 새 폴더 생성 (헤더 버튼 + 폴더 우클릭 → 새 폴더)
  - 폴더 삭제 (우클릭 → 삭제, 빈 폴더만 가능)
  - 폴더 내 파일/하위폴더 생성 (폴더 우클릭 컨텍스트 메뉴)
  - 트리 새로고침 버튼
  - 백엔드: POST/DELETE /api/wiki/folder API 추가

---

## 2026-03-26 (세션 1)

- [x] **메타데이터 템플릿 관리 기능** (Phase 2)
  - 백엔드: `GET/PUT/POST /api/metadata/templates` — JSON 파일 기반 CRUD (`wiki/.ontong/metadata_templates.json`)
  - 프론트엔드: `MetadataTemplateEditor` — Workspace 가상 탭으로 열림, Domain/Process/Tags 추가·삭제 UI
  - MetadataTagBar의 하드코딩된 DEFAULT_DOMAINS/DEFAULT_PROCESSES → 템플릿 API에서 동적 로드로 대체

- [x] **메타데이터 태깅 고도화** (Phase 2)
  - 에러코드 자동 추출: 저장 시 본문에서 정규식(`DG320`, `ERR-001` 등) 자동 감지 → frontmatter에 주입
  - 태그 정규화: `GET /api/metadata/tag-merge-suggestions` — 유사 태그 감지 (캐시/캐쉬/cache → 통합 제안)
  - 태그 기반 사이드바: Domain > Process > Tags 계층 브라우저, 클릭 시 문서 목록 표시
  - 미태깅 문서 대시보드: `UntaggedDashboard` — 미태깅 목록 + 일괄 자동 태깅 + 태그 사용 통계
  - `GET /api/metadata/files-by-tag` — 필드·값 기반 문서 필터링 API
  - `GET /api/metadata/untagged` — 미태깅 문서 목록 API

- [x] **3-Pane UI 고도화** (Phase 2)
  - 탭 시스템 확장: `TabType = FileType | VirtualTabType`, `openVirtualTab()` 스토어 메서드 추가
  - 사이드바 3-섹션 전환: 파일 트리(FolderTree) / 태그 브라우저(Tags) / 관리(Settings) 아이콘 탭
  - Workspace: 가상 탭(메타데이터 템플릿, 미태깅 대시보드) 지원, FileRouter에서 TabType 기반 라우팅

---

## 2026-03-30 (세션 17 — Skill System 기반 구축)

- [x] **Skill System Phase 1-5 구현**
  - Skill Protocol + SkillResult + SkillRegistry (`backend/application/agent/skill.py`)
  - AgentContext: per-request context with `run_skill()`, `emit_thinking()`, `sse()` (`backend/application/agent/context.py`)
  - 7개 스킬 추출: query_augment, wiki_search, wiki_read, wiki_write, wiki_edit, llm_generate, conflict_check (`backend/application/agent/skills/`)
  - ReAct loop + tool executor for LLM tool-use agents (`backend/application/agent/tool_executor.py`)
  - RAGAgent refactoring: skill 호출로 전환, backward compatibility 유지 (ctx 없을 때 inline fallback)
  - main.py: `register_all_skills()` 호출 + `agent_api.init(wiki_service, chroma, storage)` 업데이트
  - api/agent.py: AgentContext 생성 + `ctx=ctx` kwarg으로 agent에 전달
  - 68개 기존 테스트 전부 통과 (regression 없음)
