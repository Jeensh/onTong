# Section 3 — Simulation TODO

Single Source of Truth for task status. Use `[x]` (done) / `[ ]` (pending).

## STEP 3 — Section 3 boilerplate (06-developer-onboarding.md)

### 3.0 폴더 신설 — 기존 simulation 코드 (sandbox/agents/jvm_bridge) 와 병존
- [x] `backend/simulation/` 디렉토리 (이미 존재 — 옛 simulation 작업물)
- [x] `tests/simulation/` 폴더 + conftest 구조 (이미 존재)

### 3.1 신설 파일 7개 (spec 따른 ChangeSpec/SimResult 흐름)
- [x] `backend/shared/contracts/simulation.py` — ChangeSpec/SimResult 모델 (STEP 3a, 2026-05-10)
- [x] `tests/simulation/test_changespec_schema.py` — 19 test 통과
- [ ] `backend/simulation/runner/` 폴더 (mkdir + __init__.py)
- [ ] `backend/simulation/runner/lookup_source.py` — spec 05 §3 (fixture 모드만)
- [ ] `backend/simulation/runner/python_generator.py` — spec 05 §1 (echo-stub)
- [ ] `backend/simulation/runner/java_sandbox.py` — spec 05 §2 (stub_dispatch tier)
- [ ] `backend/simulation/runner/orchestrator.py` — spec 05 §4.5 (entry)
- [ ] `backend/simulation/api/run_handle.py` — spec 03 (run lifecycle state machine)
- [ ] `backend/simulation/api/spec_router.py` — spec 03 (POST /runs / GET /runs/{id}/sim-result)

### 3.2 main.py wiring
- [x] simulation router 9개 이미 등록됨 (commit `4ddf170`)
- [ ] spec_router 추가 등록 (3.1 의 spec_router.py 작성 후)

## STEP 4 — 첫 ChangeSpec → SimResult 흐름

- [ ] 4.1 시나리오 선정 — `action.scm.std.match_customer_limit_for_order` (DB 검증)
- [ ] 4.2 ChangeSpec 작성 (spec 04 + 05 정합) — Phase E #41 lookups 형식 결정 필요
- [ ] 4.3 흐름 통과: POST /runs → orchestrator → python_generator → java_sandbox → SimResult verdict=sim_verified
- [ ] 4.5 verdict 6 조건 (a~f) unit test
- [ ] 4.6 anchor invalidation manual trigger (POST /api/simulation/anchor-invalidate)

## 통합 작업 backlog (Section 2 ↔ Section 3)

- [ ] `sample-repos/slab-design-real_v2/` 와 우리 simulation 의 jvm_bridge HTTP endpoint 매핑 결정 (slab-design 폴더 제거 후 endpoint 재포팅 필요)
- [ ] `tests/simulation/test_agent3.py` / `test_demo_e2e.py` 3 failure 해결 — fixture 경로를 새 sample-repos 위치로
- [ ] frontend `JavaPythonComparePanel.tsx` 의 `SLAB_DESIGN_BASE` URL 매핑

## Phase E backlog (modeling 측 미결정 11건)

- [ ] #41 lookups schema 형식 — STEP 4.2 첫 시나리오 작성 시 굳히기
- [ ] #49 atomic ↔ method-arg broadcast 매핑 — STEP 4.2 검증
- [ ] #37~#47 나머지 — STEP 4 진행 중 부딪힐 때 결정

## Bug Fixes / 옛 작업

- [x] `/api/simulation/slab/ontology` 500 (`ModuleNotFoundError: networkx`) — 2026-04-17
- [x] 샌드박스 timeout 7s → 308ms (psycopg pool join hang 해결) — 2026-05-10
- [x] slab-design SLAB_RESULT 0 → 13 (kg 단위 시드 보정) — 2026-05-10

## UI

- [x] 상단 Section 탭에서 Simulation의 "soon" 배지 제거 (status → `active`) — 2026-04-17
- [x] SandboxConsole 케이스 펼침 + 한국어 라벨 + case_type stat — 2026-05-10
- [x] RunHistoryPanel ▶ 상세 토글 (input/output JSON) — 2026-05-10
- [x] RegressionPanel ▶ 원본 JSON 보기 — 2026-05-10
- [x] JavaPythonComparePanel H2 시드 chip 프리셋 + 📋 복사 — 2026-05-10
- [x] slab-design.html 한글 라벨 (FIELD_LABELS 47개) + 📋 JSON copy — 2026-05-10
- [x] section3.html 한글 보강 + §11-5/§11-6 (Section 2 통합 5 지점) — 2026-05-10

## Backlog

- 사용자 지시 대기 (STEP 3b 진입할지, 또는 통합 backlog 우선 처리할지)
