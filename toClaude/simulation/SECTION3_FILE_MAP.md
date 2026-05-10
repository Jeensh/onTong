# Section 3 파일 맵 + Section 2 통합 준비

> **대상**: 5/10 통합 미팅 — Section 2 (코드 기반 온톨로지 모델링) 담당자와 공유
> **목적**: Section 3가 onTong 루트의 어디에 있는지, Section 2와 어디서 어떻게 만나야 하는지 한눈에 정리
> **연관 문서**: [`SECTION3_LANDING.md`](SECTION3_LANDING.md) · [`SLAB_DESIGN_API_GUIDE.md`](SLAB_DESIGN_API_GUIDE.md)

---

## 1. onTong 루트 — Section 별 소유권 한눈에

```
/Users/jiyoon/claude/onTong/
├── backend/
│   ├── api/                          [모두 섹션 무관 / 공통]
│   ├── application/
│   │   ├── wiki/                     🟡 Section 1 (Wiki)
│   │   ├── conflict/                 🟡 Section 1 (Wiki)
│   │   ├── agent/                    🟡 Section 1 (Wiki)
│   │   ├── trust/                    🟡 Section 1 (Wiki)
│   │   ├── image/                    🟡 Section 1 (Wiki)
│   │   └── graph/                    🟡 Section 1 (Wiki)
│   ├── modeling/                     🟢 Section 2 (Modeling) ← 통합 대상
│   ├── simulation/                   🔵 ★ Section 3 (Simulation) — 본 세션 소유
│   ├── shared/contracts/             🔄 공유 — 변경 시 양 섹션 협의
│   │   ├── ontology.py               🔄 ★ Section 2 ↔ 3 인터페이스
│   │   └── simulation.py             🔵 Section 3 입출력 schema
│   ├── core/, infrastructure/        [공통]
│   └── main.py                       [공통 — router 등록]
│
├── frontend/src/
│   ├── components/
│   │   ├── wiki/                     🟡 Section 1
│   │   ├── modeling/                 🟢 Section 2
│   │   ├── simulation/               🔵 ★ Section 3
│   │   └── sections/SectionNav.tsx   [공통 네비]
│   ├── lib/
│   │   ├── wiki/, modeling/          [각 섹션]
│   │   └── simulation/               🔵 ★ Section 3
│   └── app/                          [Next.js routes]
│
├── sample-repos/
│   └── slab-design/                  🔵 Section 3 데모 fixture (자바, 무수정)
│
├── tests/
│   ├── wiki/                         🟡
│   ├── modeling/                     🟢
│   └── simulation/                   🔵 ★ Section 3 (189 통과)
│
├── toClaude/
│   ├── _shared/                      🔄 공용 (사용자 승인 시만 수정)
│   ├── wiki/                         🟡
│   ├── modeling/                     🟢
│   └── simulation/                   🔵 ★ 본 세션 쓰기 영역
│
├── docs/                             [공통 문서]
├── wiki/                             🟡 위키 콘텐츠 (예외: 세션 격리 대상 아님)
├── docker-compose.yml                [공통]
└── pyproject.toml, package.json      [공통 — 의존성 추가 시 협의]
```

**범례**: 🔵 Section 3 / 🟢 Section 2 / 🟡 Section 1 / 🔄 공유

---

## 2. Section 3 본체 — 디렉터리 상세

### 2-1. 백엔드 (`backend/simulation/`)

| 경로 | 책임 | 주요 파일 |
|---|---|---|
| `agents/` | Agent 1~4 핸들러 | `agent1_impact.py` (영향도) / `agent2_test_data.py` (Hypothesis) / `agent3_locator.py` (위치 추적) / `agent4_explorer.py` (탐색) / `scenario_assistant.py` (LLM 시나리오) |
| `api/` | FastAPI 라우터 | `agents_router.py` / `auto_pr_router.py` / `bridge_router.py` / `differential_router.py` / `jobs_router.py` / `scenarios_router.py` / `seed_router.py` / `slab_agent.py` / `transpile_router.py` |
| `auto_pr/` | LLM 자바 패치 제안 | `suggester.py` (PatchSuggestion) |
| `client/` | 외부 호출 어댑터 | `ontology_client.py` 🔄 **Section 2 호출 진입점** |
| `data/` | 시드 / 픽스처 | `scenarios/*.yaml` (8건 시나리오) |
| `jobs/` | AsyncJobQueue | `queue.py` (Semaphore N=4) |
| `jvm_bridge/` | Java 무수정 호출 | `runner.py` (subprocess) / `differential.py` (양측 diff) / `java_bridge/` (Spring Boot CLI) |
| `mock/scenarios/` | 3D Slab 보존 | `slab_size_simulator.py` |
| `ontology_bridge/` | 도메인 용어 → step 매핑 | `bridge.py` (16 용어 정규화) |
| `sandbox/` | Python step 격리 실행 | `runner.py` (subprocess+setrlimit) / `registry.py` (step → 함수) / `fixtures/` (steps + domain + repository) |
| `storage/` | SQLite 영구 저장소 | `db.py` / `runs.py` / `scenarios.py` / `postgres/` (선택) |
| `testgen/` | Hypothesis 케이스 생성 | `hypothesis_strategies.py` / `case_builder.py` |
| `transpile/` | Java→Python 자동 변환 | `parser.py` (tree-sitter) / `llm_transpile.py` (Pydantic AI) / `equivalence.py` (shadow_compare / structural) |
| `visualization/` | 차트 데이터 | `heatmap.py` (line-level) / `diff_summary.py` (stage_transitions 4셀) |

### 2-2. 프론트엔드 (`frontend/src/components/simulation/` + `lib/simulation/`)

#### 페이지 / 패널 (Phase 7-E 기준)

| 컴포넌트 | 역할 |
|---|---|
| `SimulationSection.tsx` | 라우트 entry |
| `AgentSidebar.tsx` / `AgentHub.tsx` | 좌측 네비 |
| `HomeDashboardPanel.tsx` | 🏠 홈 |
| `SandboxPanel.tsx` + `SandboxConsole.tsx` | ⚙️ 샌드박스 시뮬 |
| `TimelineScrubber.tsx` | Time-travel 스크러버 (Phase 7-E) |
| `ScenarioLibraryPanel.tsx` | 📚 시나리오 라이브러리 |
| `ImpactPanel.tsx` + `Agent1ImpactPanel.tsx` + `Agent1ImpactForm.tsx` | 📊 변경 영향 분석 + What-if 슬라이더 (Phase 7-E) |
| `RegressionPanel.tsx` | ✅ 회귀 검증 |
| `RunHistoryPanel.tsx` | 🕐 실행 이력 |
| `OntologyBridgePanel.tsx` | 🌐 OntologyBridge |
| `NavigatorPanel.tsx` + `Agent3LocatorPanel.tsx` + `Agent3LocatorForm.tsx` | 룰/코드 위치 |
| `Agent4ExplorerForm.tsx` | 탐색 |
| `Agent2RunPanel.tsx` + `Agent2TestDataForm.tsx` | Hypothesis 실행 |
| `RiskHeatmap.tsx` | 라인 히트맵 |
| `ResultChart.tsx` | Plotly 차트 |
| `MigrationDiffCard.tsx` | 마이그 Before/After |
| `AutoPRCard.tsx` | 자바 패치 제안 (Phase 7-E) |
| `JsonTable.tsx` | failures / inputs 표 (Phase 7-E) |
| `JavaPythonComparePanel.tsx` | Java↔Python 비교 (placeholder) |
| `TranspilePanel.tsx` | Java→Python 변환 미리보기 |
| `SlabViewer3D.tsx` + `SlabParamController.tsx` + `SlabDesignViewer3D.tsx` | 3D 뷰어 (보존) |
| `DbSeedCard.tsx` | PG 시드 |
| `OnboardingBanner.tsx` + `HelpPopover.tsx` | 온보딩 |

#### lib (`frontend/src/lib/simulation/`)

| 파일 | 역할 |
|---|---|
| `agentApi.ts` | Agent 1~4 호출 |
| `autoPrApi.ts` | Auto-PR API |
| `differentialApi.ts` | Java↔Python diff API |
| `seedApi.ts` | DB 시드 |
| `storageApi.ts` | scenarios / runs |
| `transpileApi.ts` | 변환 미리보기/저장 |
| `useAgent2Stream.ts` | SSE 스트림 hook (casesDetailed 전체 보존 — Phase 7-E) |
| `useSlabSimulator.ts` | 3D 시뮬 hook |
| `stepLabels.ts` | step 한국어 라벨 매핑 (Phase 7-E) |
| `plotTheme.ts` | Plotly 공통 테마 (Phase 7-E) |
| `types.ts` | 공통 타입 |

### 2-3. 테스트 (`tests/simulation/`)

| 파일 | 검증 대상 |
|---|---|
| `test_sandbox_phase1.py` (16) / `test_sandbox_phase6a.py` (10) / `test_sandbox_subprocess.py` (5) | 격리 실행 / step 정확성 |
| `test_agent1.py` (8) / `test_agent2.py` (12) / `test_agent3.py` (15) | Agent 동작 |
| `test_assistant.py` (4) | LLM 시나리오 어시스턴트 |
| `test_auto_pr.py` (6) | Auto-PR 패치 제안 |
| `test_bridge.py` (8) | OntologyBridge |
| `test_demo_e2e.py` (4) | 시나리오 전체 흐름 |
| `test_jobs.py` (12) | AsyncJobQueue |
| `test_postgres_repo.py` (10) | PG 저장소 |
| `test_storage.py` (15) | SQLite + lineage |
| `test_testgen.py` (12) | Hypothesis strategy |
| `test_transpile.py` (14) | AST 파싱 + LLM 변환 + 동치성 |

> 합계: **189 통과** / 7 skipped (모두 LLM 미가용 시 skip).

### 2-4. fixture 코드 (`sample-repos/slab-design/`)

CLAUDE.md 가 말하는 "drama DNA" 자바 코드. **Section 3가 분석 대상으로 사용**.

| 모듈 | 역할 |
|---|---|
| `slab-design-boot/` | Spring Boot 진입점 |
| `slab-design-facade/` | REST 컨트롤러 (`SdWorkingController`) |
| `slab-design-feature/` | 비즈니스 로직 (`SdDesigner`, `SdDriver`, `SdThicknessAction` ...) |
| `slab-design-store/` | JPA/MyBatis (entity / jpo / repository / logic) |

### 2-5. Section 3 작업 / 계획 문서 (`toClaude/simulation/`)

| 파일 | 내용 |
|---|---|
| `HANDOFF.md` | 다음 세션 진입점 |
| `PLAN.md` | 마스터 플랜 |
| `TODO.md` | 단일 task 추적 |
| `CHANGES.md` | ad-hoc 변경 이력 |
| `CHECKLIST.md` | 테스트 매뉴얼 |
| `FEATURES.md` | 기능 종합 |
| `VERIFY_SCENARIOS.md` | 시나리오 검증 |
| `demo_guide.md` | 데모 가이드 |
| `verify_section3.sh` | 검증 스크립트 |
| `archive/` + `log/` | step별 누적 |
| **★ `SECTION3_LANDING.md`** | 본 통합 미팅용 랜딩 |
| **★ `SLAB_DESIGN_API_GUIDE.md`** | 자바 기동 + 비교 가이드 |
| **★ `SECTION3_FILE_MAP.md`** | 본 파일 |

---

## 3. Section 2 ↔ Section 3 통합 — 어떻게 연결하나

### 3-1. 현재 인터페이스 — 한 군데만 만난다

```
backend/simulation/client/ontology_client.py
                ↓ (호출)
backend/modeling/ontology/api/ontology_router.py
                ↑ (구현)
backend/shared/contracts/ontology.py  ← 양 섹션이 공유하는 schema
```

### 3-2. 호출 패턴 (in-process / HTTP 양쪽 지원)

```python
from backend.simulation.client.ontology_client import OntologyClient
from backend.shared.contracts.ontology import OntologyRequest, Intent

client = OntologyClient(in_process=True)        # 단일 프로세스
# client = OntologyClient(base_url="http://...")  # 분리 배포

resp = await client.query(OntologyRequest(
    intent=Intent.IMPACT_ANALYSIS,
    parameters={"target_id": "HRF_PRODUCTIVITY", "change_kind": "data"},
))
```

### 3-3. Intent (5종) — Section 2가 어떤 핸들러로 분기할지

| Intent | Section 3 사용 위치 |
|---|---|
| `QUERY` | (예약) 일반 그래프 조회 |
| `SIMULATE` | Agent 2 — 실행은 Section 3 sandbox이지만 scope 결정에 ontology 사용 |
| `IMPACT_ANALYSIS` | Agent 1 — 룰 변경 영향 step 후보 결정 |
| `OPTIMIZE` | (예약) 룰 추천 |
| `EXPLAIN` | Agent 3 — 룰/메서드 위치 설명 |

### 3-4. 파서 공유 — 의존성 측면 통합

| 영역 | Section 2 | Section 3 |
|---|---|---|
| tree-sitter Java 파서 | `backend/modeling/code_analysis/java_parser.py` | `backend/simulation/transpile/parser.py` |
| Language 객체 | `tsjava.language()` 1회 로드 | **동일 인스턴스 재사용** (모듈 간 직접 import 가능) |
| 추출 결과 | `CodeEntity / CodeRelation` (그래프) | `JavaMethodInfo` (메서드 단위 + body) |

> 두 파서는 **같은 tree-sitter 백엔드를 공유**. Section 2가 코드 그래프를 만들고 Section 3가 메서드 본문을 변환 — **상호 보완**.

### 3-5. 환경변수 — fallback 정책

| 변수 | 기본값 | 의미 |
|---|---|---|
| `SIMULATION_SKIP_ONTOLOGY` | `1` (skip) | Section 2 호출 우회 — Section 2 미가동 시 Section 3 단독 동작 |
| `MODELING_API_URL` | `http://localhost:8001` | HTTP 모드 시 Section 2 baseURL |
| `SIMULATION_JAVA_BRIDGE_JAR` | (자동 탐색) | java-bridge JAR 경로 override |

---

## 4. 통합 미팅 (5/10) 체크리스트

### 4-1. 사전 공유

- [ ] `SECTION3_LANDING.md` 사전 회독 요청
- [ ] `SLAB_DESIGN_API_GUIDE.md` §9 (빠른 검증) 사전 시도
- [ ] `backend/shared/contracts/ontology.py` 양측 동의 확인

### 4-2. 미팅 의제

| 분 | 의제 | 산출 |
|---|---|---|
| 0~10 | Section 3 5분 시연 (`SECTION3_LANDING.md` §8-3) | — |
| 10~20 | Java↔Python 비교 라이브 (`SLAB_DESIGN_API_GUIDE.md` §5-3) | — |
| 20~30 | Section 2 ontology 데이터 상태 점검 | Neo4j seed 현황 |
| 30~45 | `OntologyRequest/Response` schema 동기화 | 변경 합의 |
| 45~60 | Phase 8 통합 후보 결정 | TODO 추가 |

### 4-3. 통합 후 검증 (`SIMULATION_SKIP_ONTOLOGY=0`)

```bash
# 1) Section 2 ontology API 가용성
curl -s http://localhost:8001/api/modeling/ontology/graph/stats

# 2) Section 3 → Section 2 in-process 호출 통합 테스트
SIMULATION_SKIP_ONTOLOGY=0 ./venv/bin/pytest tests/simulation/test_demo_e2e.py -v

# 3) Agent 1 ontology trace 채워지는지 확인
curl -X POST http://localhost:8001/api/simulation/agents/impact \
  -d '{"change_kind":"data","target_type":"column","target_id":"HRF_PRODUCTIVITY",
       "modification_type":"value_change","new_value":"0.50","sample_size":5,"run_sandbox":true}' \
  | jq '.ontology_trace'   # ← null 이 아니라 값이 들어와야 함
```

---

## 5. Phase 8 — 통합 후 가능한 시너지

### 5-1. OntologyBridge에 Section 2 그래프 연결

**현재**: 16 용어 hardcoded alias 매핑 → step 추천.

**통합 후**: Section 2 Neo4j BFS 결과를 받아 동적 매핑 + 영향 step 자동 확장.
```
사용자: "실수율 변경 시 영향 받는 코드는?"
→ Section 2: BFS depth=2로 productivity → SdProductivityService → SdSecondWgtAction → ... 추적
→ Section 3 OntologyBridge: 추적 결과 step ID로 변환 + 시나리오 추천
→ 자동으로 What-if 슬라이더 + Auto-PR 카드 표시
```

### 5-2. Java↔Python diff에 fixture 자동 시드

**현재**: java-bridge에 빈 fixtures → java_ok=false (입력 정합성 부족).

**통합 후**: Section 2가 분석한 자바 entity 컬럼 매핑을 fixture mock 데이터로 자동 생성.
```
Section 2: SDOrderEntity → 컬럼/타입 추출 (이미 구현)
   ↓ (fixture 자동 생성)
java-bridge: MockConfig가 동일 fixture 사용
   ↓
differential/run: 양측 동일 입력 + 동일 mock data → 의미 있는 diff
```

### 5-3. Auto-PR에 Section 2 코드 위치 정확도 향상

**현재**: `STEP_TO_TARGET` hardcoded (step → 자바 메서드 매핑).

**통합 후**: Section 2 `CodeEntity` 그래프에서 step 관련 메서드 자동 추적.
```
Section 3 step → Section 2 ontology query → 정확한 자바 메서드 위치
   ↓
Auto-PR이 더 좁고 정확한 패치 후보 메서드 식별
```

### 5-4. Transpile에 Section 2 컨텍스트 주입

**현재**: 메서드 단위 변환 (parser.py) — 클래스 fields / imports 만 LLM에 전달.

**통합 후**: Section 2 그래프에서 호출 체인 + 도메인 의미 요약을 함께 전달 → LLM 변환 정확도 향상.
```
Java method "execute()" 에서 호출하는 SdProductivityService.cumulativeProductivity()
   → Section 2: 해당 메서드 시그니처 + 도메인 의미 ("활성 공정 실수율 곱")
   → Section 3 LLM transpile: rationale + line_origins에 도메인 의미 반영
```

---

## 6. 변경 시 주의 — 양측 협의 필요한 파일

| 파일 | 변경 영향 |
|---|---|
| `backend/shared/contracts/ontology.py` | 양 섹션 schema 동시 수정 필요 |
| `backend/shared/contracts/simulation.py` | Section 3 단독이지만 frontend도 같이 수정 |
| `pyproject.toml` (의존성) | tree_sitter / pydantic_ai 버전 양측 영향 |
| `frontend/package.json` (의존성) | next/turbopack 등 |
| `backend/main.py` | 모든 router 등록 — 충돌 방지 |
| `frontend/src/components/sections/SectionNav.tsx` | 네비 — 다른 섹션 메뉴 이름 변경 시 영향 |

> 본 세션 (Section 3) 은 위 파일을 **읽기 전용**으로 취급하며, 변경 시 협의 후 진행.

---

## 7. 빠른 진단 명령

```bash
# Section 3 백엔드 가용성
curl -s http://localhost:8001/api/simulation/scenarios | head -c 200
curl -s http://localhost:8001/api/simulation/bridge/terms | head -c 200
curl -s http://localhost:8001/api/simulation/differential/status

# Section 2 가용성 (통합 후)
curl -s http://localhost:8001/api/modeling/ontology/graph/stats

# 자동화 회귀
./venv/bin/pytest tests/simulation/ -q
cd frontend && npx tsc --noEmit
```

---
