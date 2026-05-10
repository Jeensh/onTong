# Section 3 — Simulation CHANGES

Ad-hoc change log. `[x]` = done, `[ ]` = deferred/pending.

## 2026-05-10 (★ STEP 3f-2 — 랜딩 페이지 재개편 + 모든 패널에 ontology evidence UI)

사용자 피드백: "section3.html 눈에 안 들어오고 내용 빠짐. ontology 근거 어디서 보냐 — 모든 시뮬 기능에 적용 근거 보여야"

- [x] **OntologyEvidencePanel.tsx 신설** (재사용 컴포넌트)
  - props: { runId?, actionFqn?, autoOpen?, variant }
  - 4 evidence kind 색상 구분 (Action / Realization / BR / AnchorBinding)
  - summary chips + per-kind 그룹 expand
  - `OntologyEvidenceToggle` — 다른 panel 에 임베드용 토글

- [x] **OntologyEvidenceView.tsx 신설** (메인 진입점 view)
  - 자주 쓰는 action_fqn preset 2종 (match_customer_limit / 슬랩설계_실행)
  - free input + ontology actions 검색 (autocomplete)
  - OntologyEvidencePanel 임베드

- [x] **SimulationSection.tsx — 좌측 메뉴에 "온톨로지 근거 보기" view 추가**
  - 탐색 그룹의 첫 번째 항목으로 등장
  - URL: `?section=simulation&view=evidence`

- [x] **4 핵심 panel 에 OntologyEvidenceToggle 통합**
  - `RunHistoryPanel` — 각 run 의 detail 영역. step_id → action_fqn 매핑 (STEP_TO_ACTION 테이블)
  - `SandboxPanel` — 샌드박스 결과 영역 (15 step → action 매핑)
  - `RegressionPanel` — 비교 결과 옆
  - `JavaPythonComparePanel` — 헤더 영역 ("Java/Python 모두 같은 ontology Action 기반")

- [x] **backend `/api/simulation/ontology-evidence/by-action` 신설**
  - run_id 없이 action_fqn 만으로 evidence 조회 (lightweight)
  - SandboxPanel / Differential / NavigatorPanel 같은 곳에서 spec 03 run 트리거 없이 즉시 조회 가능

- [x] **frontend/public/section3.html 전면 재개편 (745 → ~880 lines)**
  - 9 panel 카탈로그 grid (3x3) — 한 눈에 모든 기능 + endpoint + ontology 매핑 명시
  - hero 통계 4 stats (9 패널 / 58 endpoints / 4 evidence kind / 423 회귀)
  - WHY 4가지 한계 (정적 분석 / 도메인 용어 / Java↔Python / 근거 추적)
  - 4 evidence kind 시각 도식 (색상 구분 + facade call + data 필드 명시)
  - 5 컴포넌트 flow (RunPlanBuilder → PythonGenerator → JavaSandbox → Orchestrator → RunHandleStore)
  - 5 카테고리 differential 표 (matched / mismatched / java_only / python_only / both_null)
  - spec 03 핵심 12 endpoint 표 (method + path + 설명)
  - Section 2 통합 5 지점 카드 (delegates_to_tree / Realization / TableSpec / AtomicOverridePatcher / OntologyEvidence)
  - 운영화 6 reveal (TimeoutBudget / artifact disk / JvmSubprocess / async queue / promote / dual ontology)

- [x] 회귀: by-action endpoint test 2종 추가 → **425 passed** (이전 423 → +2: by-action 2종)
- [x] TypeScript 빌드 통과 (npx tsc --noEmit)

## 2026-05-10 (★ STEP 3f — 사용자 3 요구사항 + 통신 검증)

- [x] **0번 — Section 2 ↔ Section 3 통신 방식 검증**
  - `06-developer-onboarding.md` Q4 (line 501-506) + line 78 → HTTP / Python facade 둘 다 명시 허용
  - 결정: in-process facade 유지 (사용자 "규약대로 진행")
  - landing page chapter 03 reveal 에 명시 결정 기록

- [x] **요구사항 1 — Java↔Python differential 정합성**
  - `backend/simulation/jvm_bridge/differential.py` — 5 카테고리 분류 (matched/mismatched/java_only/python_only/both_null)
  - `_normalize_payload()` helper — null/빈값 재귀 제거
  - `_classify_diff()` helper — (java_value, python_value) → (category, is_close)
  - `DifferentialResult` 신규 필드 — matched_count / mismatched_count / java_only_count / python_only_count / both_null_count / summary / java_payload_normalized / python_payload_normalized
  - 16 test 통과 (`tests/simulation/test_differential_classification.py`)

- [x] **요구사항 2 — Ontology evidence endpoint**
  - `backend/simulation/api/ontology_evidence_router.py` 신설 (+250 lines)
  - `GET /api/simulation/runs/{run_id}/ontology-evidence`
  - 4 evidence kind — action / realized_method / br / anchor
  - 각 trace: evidence_kind / evidence_id / ontology_source / ontology_facade_call / ontology_data / explanation
  - `backend/main.py` — router 등록
  - 7 test 통과 (`tests/simulation/test_ontology_evidence.py`)

- [x] **요구사항 3-A — 랜딩 페이지 전면 재작성**
  - `frontend/public/section3.html` — Apple SD Gothic Neo + Claude warm cream(#faf9f5) + accent orange(#d97757)
  - 6 chapter 스토리라인 (왜/무엇을/어떻게/근거/Java↔Python/운영화)
  - 8 `<details class="reveal">` 블록 — 호기심 유발 클릭 expand
  - hero + stats grid + flow steps grid + CTA band

- [x] **요구사항 3-B — 좌측 toc → 상단 sticky nav**
  - 이전: `<nav class="toc">` 좌측 250px 고정 (12 항목)
  - 새: 상단 sticky nav + chapter scroll + scroll spy (현재 chapter accent 색)
  - `frontend/public/section3.legacy.html` — 이전 버전 보존 (사용자 지시 "지우진말고")

- [x] 회귀: **423 passed** (이전 400 → +23: differential 16 + ontology evidence 7), 17 skipped, 3 failed (sample-repos — 무관)
- [x] `toClaude/simulation/log/step_3f_summary.md` 작성

## 2026-04-17
- [x] 상단 SectionNav에서 Simulation 탭의 "soon" 배지 제거
  - `frontend/src/components/sections/SectionNav.tsx` Simulation entry `status: "scaffolding"` → `"active"`
  - 이유: Section 3 엔드포인트 동작 확인됨, 더 이상 예정 상태 아님
- [x] `networkx` 의존성 추가 및 설치
  - `pyproject.toml`: `[tool.poetry.dependencies]`에 `networkx = "^3.2"` 선언 (Graph Database neo4j 섹션 아래)
  - `venv/`에 `networkx 3.6.1` 설치 (`venv/bin/pip install "networkx>=3.2,<4"`)
  - 이유: `backend/simulation/tools/ontology_graph.py:13`의 top-level `import networkx`로 인해 `/api/simulation/slab/ontology` + scenario A/B tool 500 에러 발생 중
  - 검증: `curl http://localhost:8001/api/simulation/slab/ontology` → HTTP 200, proxy `http://localhost:3000/...` → HTTP 200
