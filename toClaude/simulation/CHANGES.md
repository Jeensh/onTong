# Section 3 — Simulation CHANGES

Ad-hoc change log. `[x]` = done, `[ ]` = deferred/pending.

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
