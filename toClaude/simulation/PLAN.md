# Section 3 — Simulation 고도화 PLAN

작성일: 2026-05-04
대상 데모 코드베이스: `sample-repos/slab-design` (Java 21 / Spring Boot 3.4, 21-step Slab 설계 알고리즘)

---

## 0. 핵심 가치 명제 (1줄)

> **"레거시 자바를 안 돌리고도, 룰 1줄을 바꾸면 결과가 어떻게 변하는지 그 자리에서 Python 샌드박스로 실제 실행해서 보여준다."**

심사위원 한방 임팩트:
- IntelliJ Call Hierarchy = 정적, "어디서 호출되는지"만 보여줌
- 우리 도구 = **동적**, "값이 얼마나 변하는지" 실행해서 보여줌
- 비즈니스 룰 1개 변경의 fan-out을 **숫자**로 시각화

---

## 1. 아키텍처

### 1.1 Section 간 책임 분리

```
┌────────────────┐   ontology query    ┌─────────────────┐
│  Section 3     │ ───────────────────▶│  Section 2      │
│  (Simulation)  │   (in-process)      │  (Modeling)     │
│                │ ◀───────────────────│                 │
│  - Agents 1/2/3│   ontology graph    │  - Tree-sitter  │
│  - Sandbox     │                     │  - Neo4j        │
│  - Test gen    │                     │  - Source viewer│
│  - Viz         │                     └─────────────────┘
└────────────────┘
       │
       │  RAG (wiki)
       ▼
┌────────────────┐
│  Section 1     │
│  (Wiki — RAG)  │
└────────────────┘
```

**불변 규칙**: Section 3는 Section 2의 `ontology_client` 인터페이스만 사용. Section 2의 내부 구현은 건드리지 않음. Sandbox/testgen은 Section 3 단독.

### 1.2 Section 3 내부 모듈

```
backend/simulation/
├── api/
│   └── agents_router.py          (재작성: SSE 스트리밍 추가)
├── agents/
│   ├── agent1_impact.py          (재작성: sandbox 비교 실행 추가)
│   ├── agent2_test_data.py       (재작성: Hypothesis + sandbox + SSE)
│   └── agent3_locator.py         (재작성: preview + handoff)
├── client/
│   └── ontology_client.py        (유지)
├── sandbox/                      ← 신규
│   ├── runner.py                 (subprocess 격리 실행)
│   ├── transpiler.py             (Java→Python LLM 변환, Phase 2 후반)
│   └── fixtures/                 (slab-design 사전 수작업 Python 모델)
│       ├── __init__.py
│       ├── domain.py             (SDOrder, CastSpec, HrSpec 등 dataclass)
│       ├── steps/
│       │   ├── validator.py      (DG001~005)
│       │   ├── productivity.py   (누적 실수율)
│       │   ├── thickness.py      (step 1)
│       │   ├── split_range.py    (step 8)
│       │   ├── slab_count.py     (step 9)
│       │   ├── slab_weight.py    (step 10/12/13)
│       │   └── final_range.py    (step 16~19)
│       └── fixtures.py           (mock orders + std rows)
├── testgen/                      ← 신규
│   ├── hypothesis_strategies.py  (도메인 strategy: order, slab, …)
│   ├── llm_seed.py               (LLM이 boundary case 힌트 생성)
│   └── case_builder.py           (Hypothesis + LLM 결합)
├── visualization/                ← 신규 (백엔드는 데이터만; 프론트가 그림)
│   └── diff_summary.py           (전후 비교 통계 요약)
└── data/
    └── slab-design-rules.json    (수정 가능한 룰 마스터 — 시나리오 5/8용)

frontend/src/components/simulation/
├── SimulationSection.tsx         (재구성)
├── AgentSidebar.tsx              (유지/조정)
├── Agent1ImpactPanel.tsx         (영향도 + 전후 비교 시각화)
├── Agent2RunPanel.tsx            (★ 메인 — 사용자 본인 담당)
├── Agent3LocatorPanel.tsx        (위치 + Monaco preview)
├── SandboxConsole.tsx            (실시간 SSE 콘솔)
├── ResultChart.tsx               (Plotly 막대/산점도)
└── index.ts
```

### 1.3 데이터 흐름 — Agent 2 (메인)

```
User input
  ├─ target: step 9 (SdSlabCountAction)
  ├─ case_types: [normal, boundary, error, performance]
  └─ test_count: 1000

  ↓
[testgen]
  Hypothesis strategy + LLM seed → 1000 SDOrder fixture
  ↓
[sandbox/runner]
  subprocess Python (resource limited)
    → for each fixture: import slab-design-fixtures, run step 9
    → JSON 결과 stream (case_id, input, output, error?)
  ↓
[SSE]
  case_id 1, 2, 3, … → 프론트 실시간 표시
  ↓
[visualization]
  fail count, value distribution histogram, edge cases
  ↓
User
  Plotly 차트 + 실패 케이스 테이블 + 코드 스켈레톤 (pytest 호환)
```

### 1.4 데이터 흐름 — Agent 1 (영향도 + 전후 실행)

```
User input
  ├─ target: HR 실수율 (값) 또는 column rename (스키마)
  └─ new_value: 0.92

  ↓
[ontology_client]
  Section 2 → 영향받는 step/method/table 식별
  ↓
[sandbox/runner] × 2회
  case 1: 변경 전 룰 + 표본 100 주문 → 결과 A
  case 2: 변경 후 룰 + 동일 100 주문 → 결과 B
  ↓
[diff_summary]
  주문별 결과 차이: Slab 매수, 단중, 폭, 길이 변동
  ↓
User
  영향도 트리 + Plotly diff 차트 + "이 변경으로 N건 주문 결과 변동" 카드
```

### 1.5 데이터 흐름 — Agent 3 (용어 → 위치 → 실행)

```
User: "단중상한이 어디서 결정돼?"

  ↓
[ontology_client + RAG]
  matched_terms: secondWgtHigh
  source_locations: [SdSecondWgtHighAction.java:42]
  process_locations: [step 6]
  data_locations: [SDSlabEntity.secondWgtHigh, SD_PRODUCTIVITY_STD]
  ↓
User UI
  Monaco preview + "이 step을 시뮬레이션" 버튼
  ↓ (클릭)
Agent 2 패널로 jump (target=step:6 사전 채움)
```

---

## 2. 기술 선정 (2026 트렌드)

| 영역 | 선택 | 이유 |
|---|---|---|
| Agent framework | **Pydantic AI 1.x** | 프로젝트 표준, 구조화 tool-use, type-safe |
| LLM | **Claude Opus 4.7 / Sonnet 4.6** (env switchable) | tool-use 정확도, prompt cache로 반복 cost↓ |
| Test gen | **Hypothesis 6.x** (property-based) | boundary 자동 발견, shrink로 minimal fail case |
| Sandbox | **subprocess + resource module** (1차) → **nsjail/docker** (Phase 5+) | Phase 4 데모는 subprocess로 충분; 보안 강화는 차후 |
| Streaming | **SSE (Server-Sent Events)** | FastAPI + EventSource 단순. 1000건 케이스 실시간 |
| 시각화 | **Plotly.js** (frontend) | 인터랙티브 zoom/hover, 빠른 구현 |
| Code preview | **Monaco** (이미 modeling에 있음) | read-only Java 하이라이팅 |
| 트레이스 | **자체 trace_id + Pydantic AI agent steps** | OpenTelemetry는 오버킬 — 단순 JSON 로그 |

---

## 3. 단계별 실행 계획

### Phase 0 — 셋업 (오늘, 0.5h)
- [x] toClaude/simulation/ 폴더 신설
- [x] PLAN.md (본 문서)
- [ ] TODO.md / HANDOFF.md / CHANGES.md / CHECKLIST.md / demo_guide.md 초안

### Phase 1 — Sandbox + slab-design Python fixture (1.5d)
**목표**: subprocess 격리 + 5~7개 핵심 step의 Python 변환본 작성. JSON I/O 표준화.

**산출물**:
- `backend/simulation/sandbox/runner.py` — `run(fixture_module, step_id, inputs) → result`
- `backend/simulation/sandbox/fixtures/domain.py` — 도메인 dataclass 7~8개
- `backend/simulation/sandbox/fixtures/steps/*.py` — validator, productivity, thickness, split_range, slab_count, slab_weight, final_range
- `backend/simulation/sandbox/fixtures/fixtures.py` — mock data
- `tests/simulation/test_sandbox_phase1.py` — 각 step 1건 이상 PASS

**검증**:
- `pytest tests/simulation/test_sandbox_phase1.py` 전수 통과
- subprocess 메모리/CPU 한도 동작 확인 (resource.setrlimit)

### Phase 2 — Agent 2 재작성 (2d) ★ 핵심
**목표**: Hypothesis 통합, SSE 스트리밍, 프론트 Agent2RunPanel + SandboxConsole + ResultChart.

**산출물**:
- `backend/simulation/testgen/*.py` — Hypothesis strategies + LLM seed
- `backend/simulation/agents/agent2_test_data.py` — 재작성. SSE 이벤트: `case_started / case_done / case_failed / summary`
- `backend/simulation/api/agents_router.py` — SSE 엔드포인트 `POST /api/simulation/agents/test-data/stream`
- `frontend/src/components/simulation/Agent2RunPanel.tsx`
- `frontend/src/components/simulation/SandboxConsole.tsx`
- `frontend/src/components/simulation/ResultChart.tsx` (Plotly)
- `tests/simulation/test_agent2.py`

**검증**:
- pytest 통과, tsc clean
- 브라우저에서 step 9 / count=100 실행 → 실시간 진행 + 차트 렌더 확인

### Phase 3 — Agent 1/3 재작성 (1d)
**목표**: A1 sandbox diff, A3 preview + handoff.

**산출물**:
- `backend/simulation/agents/agent1_impact.py` — 재작성. sandbox 2회 실행 + diff
- `backend/simulation/agents/agent3_locator.py` — 재작성. preview payload 추가
- `frontend/src/components/simulation/Agent1ImpactPanel.tsx`
- `frontend/src/components/simulation/Agent3LocatorPanel.tsx`
- `tests/simulation/test_agent1.py`, `test_agent3.py`

### Phase 4 — 데모 시나리오 3종 + verify.sh (1d)
**목표**: 시나리오 5 / 8 / 1 시연 스크립트 작성, 자동 검증 추가.

**산출물**:
- `toClaude/simulation/demo_guide.md` 갱신 — 3 시나리오 step-by-step
- `toClaude/_shared/verify.sh` 항목 추가 (사용자 승인 필요 — `_shared` 수정이므로)
- `tests/simulation/test_demo_e2e.py` — 3 시나리오 e2e

### Phase 5 (옵션 — 시간 남으면) — Java→Python 자동 transpile
**목표**: LLM이 slab-design Java step 1개를 Python으로 자동 변환 → "다른 레거시 코드도 적용 가능" 어필.

LLM tool-use chain:
1. Tree-sitter parse `SdSplitRangeAction.java`
2. 변수/연산 → Python 의도 trees
3. 단위 검증 (Hypothesis로 Java 결과 vs Python 결과 일치성 검증)
4. 사용자 승인 → fixtures/steps에 저장

이건 데모에서 "확장성" 카드. 실제 시연은 Phase 4까지로 충분.

---

## 4. 데모 시나리오 우선순위 (영상 5분 기준)

| 시간 | 시나리오 | Agent | 시연 포인트 |
|---|---|---|---|
| 0:00–1:00 | **#5 누적 실수율 변경** | A1 | "HR 0.95→0.92 → 1000건 주문 Slab 매수 +12% 변동" 막대그래프 |
| 1:00–2:30 | **#8 A-a 루프 분기** ★ | A2 | step 9 boundary 케이스 1000건 자동 생성 + 실시간 SSE + 실패 케이스 minimize |
| 2:30–3:30 | **#1 컬럼 통합** | A3 | "단중" 검색 → 4개 컬럼/2개 step + Monaco preview + 즉시 시뮬 |
| 3:30–4:30 | A2 fail 케이스 deep-dive | A2 | Hypothesis가 찾은 minimal fail input + 코드 위치 + fix 제안 |
| 4:30–5:00 | (옵션) Phase 5 transpile 어필 | — | "이 도구는 slab-design 외 다른 레거시도 동일 흐름" |

---

## 5. 리스크 & 대응

| 리스크 | 가능성 | 대응 |
|---|---|---|
| LLM 변환 신뢰성 부족 | 高 | Phase 1은 100% 수작업 변환. Phase 5는 옵션. |
| subprocess 1000건 너무 느림 | 中 | concurrent.futures.ProcessPoolExecutor 풀 + Hypothesis @settings(max_examples=N) |
| Section 2 ontology API 변경 | 中 | ontology_client만 유지. 호출 응답 schema에 의존하므로 modeling 세션과 contracts 버전 핀 필요 |
| 프론트 Plotly 번들 사이즈 | 低 | dynamic import |
| 브라우저 CORS / SSE proxy | 低 | Next.js api route proxy 또는 Nginx 설정 (이미 nginx.conf 있음) |
| 시간 부족 (5분 영상까지 D-?) | 中 | Phase 4까지가 MVP. Phase 5는 시간 보너스. |

---

## 6. 비-목표 (이번 사이클에서 안 함)

- 실제 Java 런타임 실행 (`mvn spring-boot:run`)
- Oracle DB 연결
- Kafka / 외부 서비스 통합
- 자동 transpile **production-grade** 정확도 보장
- nsjail/docker 강격리 (Phase 5+ 운영 단계에서)
- Bloop 통합 (이미 modeling이 tree-sitter 사용 중)

---

## 7. 완료 정의 (DoD)

### Phase별
각 Phase는 다음 7항목 완료 시 종료 (CLAUDE.md Step Completion Protocol):
1. 코드 구현
2. CHECKLIST.md 검증 통과
3. log/step{N}_summary.md 작성 → archive/ 이동
4. demo_guide.md 시나리오 추가
5. TODO.md `[x]` 마킹
6. memory/project_status.md 갱신
7. 사용자에게 보고

### 전체 (해커톤 데모 가능 상태)
- pytest 전수 통과 (177개 + 신규 추가 ≥ 30개)
- TypeScript 빌드 clean
- 데모 시나리오 3종 브라우저에서 e2e 동작
- 데모 영상 5분 내 시연 가능
- toClaude/_shared/verify.sh PASS
