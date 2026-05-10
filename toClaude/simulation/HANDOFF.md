# Section 3 — Simulation HANDOFF

섹션 담당: 시뮬레이션 Claude 세션
쓰기 영역: `toClaude/simulation/`, `backend/simulation/`, `backend/shared/contracts/{ontology,simulation}.py`
읽기 전용: `toClaude/wiki/`, `toClaude/modeling/`, `toClaude/_shared/`, `backend/modeling/api/{ontology_query, ontology_router}` (DTO + facade 만)

## 현재 상태 (2026-05-10)

**브랜치**: `section3-integration` — origin/main + simulation 7 commit + STEP 3a 진행 중

**완료**:
- jyu 브랜치 push 완료 (오늘 작업 모두 origin/jyu)
- main 기준 새 브랜치 `section3-integration` 생성 + simulation 6 commit cherry-pick
- `sample-repos/` main 100% 정렬 (slab-design 폴더 제거 + scm-demo 복원, commit `2a346e3`)
- 인계 검증 9/9 통과 (06 onboarding STEP 2)
- **STEP 3a 완료** (2026-05-10)
  - `backend/shared/contracts/simulation.py` 신설 — ChangeSpec / SimResult / BREvidence / AnchorEvidence / DelegationTraceFrame 등 7 Pydantic 모델 (spec 04 §1~§2 1:1)
  - `tests/simulation/test_changespec_schema.py` 19/19 ✅
  - 회귀: 195 passed, 17 skipped (3 failure 는 `sample-repos/slab-design/` 부재 영향, STEP 3a 무관)

**기존 작업 (jyu 시점)**:
- 백엔드 simulation 패키지 (sandbox / agents / transpile / jvm_bridge) — 이미 동작 중
- 프론트엔드 27 패널 + 9 lib API — 오늘 변경 모두 살아있음
- 랜딩 페이지 (section3.html 2094줄) + slab-design 콘솔 (slab-design.html 952줄)

## 다음 세션 첫 작업

**STEP 3b 후보** (사용자 승인 후 결정):

1. `backend/simulation/runner/` 폴더 신설 + 4 파일 (lookup_source / python_generator / java_sandbox / orchestrator)
2. `backend/simulation/api/run_handle.py` + `spec_router.py` (POST /runs / GET /runs/{id}/sim-result)
3. STEP 4.1 첫 시나리오 — `action.scm.std.match_customer_limit_for_order` ChangeSpec 작성

## 환경 설정 메모

- 백엔드 실행: `venv/` (`.venv/`가 아님). uvicorn `backend.main:app --host 0.0.0.0 --port 8001`
- 프론트엔드: port 3000, Next.js rewrite `/api/*` → `http://localhost:8001/api/*`
- slab-design (Java legacy 데모): port 8080, `--spring.profiles.active=h2` (단, **`sample-repos/slab-design/` 폴더 제거됨** — 통합 작업 시 `slab-design-real_v2/` 와 매핑 결정 필요)
- ontology 데이터: `data/ontology.db` (read-only ground truth, 80MB SQLite, 9/9 검증 통과)
- 시뮬 결과 저장: `backend/simulation/data/storage.db` 또는 신설 (modeling DB 와 분리)

## Section 2 통합 인터페이스

| 통합 지점 | 사용할 API |
|---|---|
| ontology Core query | `from backend.modeling.api.ontology_query import OntologyQueryClientImpl` (Python facade, DTO 만) |
| 또는 HTTP | `GET http://localhost:8001/api/ontology/{terms,actions,business-rules,anchor-bindings,...}` |
| 금지 (CI 차단) | `backend.modeling.{mapping_layer,domain_layer,code_layer,persistence}.*` — `tools/check_agent_isolation.py` 가 검사 |

## 환경 의존성 (main 통합 시 추가 설치된 것)

```
sqlalchemy, alembic, anthropic, sqlglot, hypothesis, fakeredis, pytest-postgresql, locust,
pydantic-ai-slim[anthropic]
+ frontend: elkjs, @xyflow/react
```
