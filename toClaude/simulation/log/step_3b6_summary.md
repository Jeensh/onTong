# STEP 3b-6 — spec 03 Run lifecycle FastAPI router + main.py wiring (★ STEP 3.1 종결)

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**의존**: `toClaude/modeling/handoff-spec/03-simulation-api-spec.md` (§1, §2)

## 목표

06-developer-onboarding.md 의 STEP 3.1 7개 신설 파일 중 마지막 — spec 03 §1, §2 의 Run lifecycle REST endpoints 를 FastAPI router 로 노출 + `main.py` 에 등록. 외부 (curl / frontend / agent) 에서 `POST /api/simulation/runs` 호출 가능.

## 작업 내용 (TDD)

### 1. 테스트 먼저 (`tests/simulation/test_spec_router.py` +210 lines)

13 test 작성 (FastAPI TestClient + 의존성 override):

| 영역 | 검증 |
|---|---|
| POST /runs (3) | RunHandle 반환 / ChangeSpec 보존 / 422 invalid body |
| GET /runs/{id} (2) | RunHandle polling / 404 unknown |
| GET /runs/{id}/sim-result (2) | completed 후 SimResult / 404 unknown |
| GET /runs/{id}/changespec (2) | atomic_overrides 보존 / 404 unknown |
| GET /runs?status=... (2) | list 반환 / status filter |
| e2e chain (1) | POST → GET handle → GET sim-result → GET changespec |
| import sanity (1) | router 가 APIRouter 인스턴스 + prefix=/api/simulation |

→ TDD red phase 13/13 fail/error, green phase 13/13 pass.

### 2. 코드 작성

#### `backend/simulation/api/spec_router.py` 신설 (+135 lines)

**Module singleton + FastAPI Depends**:
- `_store: Optional[RunHandleStore]` — lazy init
- `_orchestrator: Optional[Orchestrator]` — lazy init (NullOntologyClient 기반 stub backend)
- `get_store() -> RunHandleStore` — Depends getter (test 시 override 가능)
- `get_orchestrator() -> Orchestrator` — Depends getter
- `_NullOntologyClient` — modeling 미가용 환경 동작용 4-method duck stub
- `_build_minimal_run_plan(change_spec)` — change_spec.action_fqn 1 frame RunPlan (echo-stub iter; 실제 delegates_to_tree 추출은 STEP 4.1+)

**5 Endpoints** (모두 `/api/simulation` prefix, tags=`["simulation-runs"]`):

| 메서드 | 경로 | 책임 | 응답 |
|---|---|---|---|
| `POST` | `/runs` | spec 03 §1.1 — RunHandleStore.submit() 호출 | `RunHandle` |
| `GET` | `/runs` | spec 03 §1.3 — list (status filter) | `list[RunHandle]` |
| `GET` | `/runs/{run_id}` | spec 03 §1.2 — RunHandle polling | `RunHandle` (404 if 미등록) |
| `GET` | `/runs/{run_id}/sim-result` | spec 03 §2.1 — completed 후 SimResult | `SimResult` (404 if 미등록 / 미완료) |
| `GET` | `/runs/{run_id}/changespec` | spec 03 §2.2 — 재현 / 디버깅 | `ChangeSpec` (404 if 미등록) |

**미구현 (후속 step)**: §2.3 `/artifacts`, §3.1 `/runs/diff`, §4.1 `/anchor-invalidate`, §5.1 `/verification/promote`, §6.1 `/health` confidence, §6.2 `/capabilities`.

#### `backend/main.py` wiring (2 hunk 수정)

**Import 순서 변경** — `spec_router` 를 simulation routers 묶음 맨 처음에 import (path 충돌 시 우선 등록):
```python
# spec_router 먼저 import — /api/simulation/runs 의 spec 03 우선권
from backend.simulation.api.spec_router import router as spec_router
from backend.simulation.api.slab_agent import router as slab_agent_router
...
```

**`include_router` 순서** — 동일 이유로 spec_router 먼저:
```python
app.include_router(spec_router)        # ← 첫 등록 = 매칭 우선권
app.include_router(slab_agent_router)
app.include_router(scenarios_router)   # ← 옛 /runs/{id} (simulation-storage) 와 path 충돌 — spec_router 가 win
...
```

### 3. Path 충돌 해결 — spec_router 우선권

`scenarios_router` (옛 simulation-storage tag) 가 같은 prefix `/api/simulation` + `/runs`, `/runs/{run_id}`, `/runs/{run_id}/lineage` 핸들러를 들고 있음. FastAPI 는 등록 순서대로 매칭하므로 **spec_router 를 먼저 등록**해 spec 03 가 canonical owner.

**검증**:
- 프론트엔드 (`/Users/jiyoon/claude/onTong/frontend/src/`) 에 `/api/simulation/runs` 직접 사용 0건
- 다른 백엔드 모듈에서 호출 0건
- `/runs/{id}/lineage` 는 spec_router 미정의 → fall through 로 scenarios_router 가 처리 (호환)

**부작용**: 옛 scenarios_router 의 `/runs/{run_id}` 는 본 변경 후 호출 불가 (spec_router 에 가려짐). 통합 작업 backlog 에 추가 — 별도 prefix (`/api/simulation/scenario-runs/{id}`) 로 마이그레이션.

### 4. 회귀 검증

| 검증 | 결과 |
|---|---|
| `test_spec_router.py` | **13/13 GREEN** |
| 전체 `tests/simulation/` | **295 passed** (이전 282 → +13), 17 skipped |
| 3 failure | sample-repos/slab-design 부재 (STEP 3b-6 무관) |
| Section isolation | ✅ modeling internal layer import 0건 |
| **서버 sanity (curl)** | ✅ POST /runs → run_id 발급 → GET /runs/{id} 정상 → sim-result/changespec 조회 → list filter 동작 → 404 unknown |

curl smoke 출력 (재현):
```
POST → run_id: run-8a67b9ca8178
GET /runs/{id} → {"run_id":"run-...","status":"completed",...}
GET /runs/{id}/sim-result → verdict: inconclusive / status: completed
GET /runs/{id}/changespec → action_fqn: action.scm.demo
GET /runs (list) → list / count: 1
GET /runs/unknown → HTTP 404
```

## 주요 결정

- **Module singleton + Depends override** — pytest 에선 `app.dependency_overrides[get_store]` 으로 fresh store 주입, 운영에선 default singleton. FastAPI 의 표준 testing 패턴.
- **NullOntologyClient default** — modeling facade 미연결 환경 (single-process dev) 에서도 router 동작. 통합 작업 시 `_build_default_orchestrator()` 만 교체하면 실 ontology 연결.
- **echo-stub RunPlan 1 frame** — `_build_minimal_run_plan` 이 `change_spec.action_fqn` 만 delegation tree 에 넣음. `primary_input_type="scm.order.Order"` default. 실제 delegates_to_tree 추출은 STEP 4.1+ (modeling 의 `/api/ontology/actions/{fqn}/delegates-to-tree` HTTP 호출).
- **spec 03 의 `/runs/{id}/artifacts` 미구현** — Section 6 (artifact collection) 의 storage 가 아직 없음. 후속 step.
- **spec_router 우선 등록** — 충돌하는 옛 scenarios_router 의 `/runs/{id}` 보다 우선. spec 03 protocol 준수가 우선 (CLAUDE.md "두 섹션간 규약").
- **`HTTPException(404, detail=...)`** — spec 03 명시 안 됐지만 FastAPI 표준 + 기존 simulation routers 와 동일.
- **`response_model=...`** 명시 — Pydantic 자동 직렬화 + OpenAPI 스키마 생성 (FastAPI /docs 의 자동 문서화).

## ★ STEP 3.1 종결 — Section 3 의 spec 03/04/05 구현 7/7 완료

| 파일 | step | LOC | test |
|---|---|---|---|
| `backend/shared/contracts/simulation.py` | 3a + 3b-1 + 3b-5 | +220+15 = +455 cumulative | 19 + ... |
| `backend/simulation/runner/__init__.py` | 3b-1 | +12 | — |
| `backend/simulation/runner/lookup_source.py` | 3b-1 | +165 | 9 |
| `backend/simulation/runner/java_sandbox.py` | 3b-2 | +200 | 13 |
| `backend/simulation/runner/python_generator.py` | 3b-3 | +165 | 14 |
| `backend/simulation/runner/orchestrator.py` | 3b-4 | +260 | 16 |
| `backend/simulation/api/run_handle.py` | 3b-5 | +200 | 20 |
| **`backend/simulation/api/spec_router.py`** | **3b-6** | **+135** | **13** |

총 **8 신규 파일 + 1 contracts 확장 + main.py 1 hunk wiring**, **295 test (이전 base 175 → +120)**.

## 호환성

- 기존 simulation routers 8종 그대로 등록 (slab_agent / agents / scenarios / jobs / bridge / transpile / auto_pr / seed / differential).
- 기존 사용 예 (frontend, sample-repos) 영향 없음 — 0건 검증.
- 옛 scenarios_router `/runs/{id}` 만 spec_router 에 가려짐 (마이그레이션 backlog).

## Diff stat

- `backend/simulation/api/spec_router.py` — 신규 +135 lines
- `backend/main.py` — 2 hunk (import 순서 + include 순서)
- `tests/simulation/test_spec_router.py` — 신규 +210 lines

## 다음 작업

| 영역 | 내용 |
|---|---|
| **STEP 4.1+** | 첫 시나리오 ChangeSpec → SimResult 흐름 (`action.scm.std.match_customer_limit_for_order`) — Phase E #41 lookups schema 확정 |
| 통합 backlog | scenarios_router `/runs/{id}` → `/scenario-runs/{id}` 마이그레이션 |
| 통합 backlog | `_build_default_orchestrator()` 의 NullOntologyClient → 실 OntologyQueryClient 연결 |
| 통합 backlog | `_build_minimal_run_plan` 의 1-frame → 실 `delegates-to-tree` HTTP 호출 |
| 통합 backlog | `sample-repos/slab-design-real_v2/` ↔ jvm_bridge endpoint 매핑 |

## 마일스톤 의의

★ STEP 3.1 의 모든 신설 파일 완료 = **Section 3 의 spec 03 (REST API) + spec 04 (ChangeSpec/SimResult schema) + spec 05 (runner interface) 1차 통합 완료**. POST `/api/simulation/runs` 한 번 호출로 ChangeSpec → SimResult round-trip 동작. 외부 agent / frontend / curl 에서 spec-compliant 호출 가능.
