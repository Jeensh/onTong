# STEP 3b-5 — RunHandle state machine + RunHandleStore

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**의존**: `toClaude/modeling/handoff-spec/03-simulation-api-spec.md` (§1, §2) + `05-runner-interface.md` (§4.1~4.4)

## 목표

06-developer-onboarding.md 의 STEP 3.1 7개 신설 파일 중 6번째 — **RunHandle 상태 머신** 과 in-memory store 구현. spec 03 §1.1 의 POST /runs 응답 형태 + spec 05 §4.1 의 5 상태 전환 매트릭스. async queue 는 후속 step (운영 v2 / Redis 도입 시).

## 작업 내용 (TDD)

### 1. 테스트 먼저 (`tests/simulation/test_run_handle.py` +250 lines)

20 test 작성:

| 영역 | 검증 |
|---|---|
| RunHandle 모델 (2) | 필수 필드 / status Literal 거부 |
| store register/get/list (5) | pending 등록 / 고유 run_id / get / unknown=None / list filter status |
| change_spec 보존 (1) | spec 03 §2.2 GET /changespec source |
| 상태 전환 (6) | pending→running→completed / pending→cancelled / running→failed / terminal→raise / unknown_id→KeyError |
| submit lifecycle (5) | orchestrator 동기 실행 / 예외→failed / sim_result 저장 + run_id 정규화 / pending→None / unknown→None |
| sanity end-to-end | RunHandleStore + Orchestrator + Phase C P-2018-0098 → completed/sim_verified |

→ TDD red phase 20/20 fail, green phase 20/20 pass.

### 2. 코드 작성

#### `backend/shared/contracts/simulation.py` — RunHandle 모델 추가 (+15 lines)

```python
class RunHandle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    created_at: str
    plan: Optional[RunPlan] = None
```

`__all__` 에 `RunHandle` 추가.

#### `backend/simulation/api/run_handle.py` 신설 (+200 lines)

**상태 전환 매트릭스** (spec 05 §4.1):
```python
_VALID_TRANSITIONS = {
    "pending":   {"running", "cancelled"},
    "running":   {"completed", "failed", "cancelled"},
    "completed": set(),  # terminal
    "failed":    set(),  # terminal
    "cancelled": set(),  # terminal
}
```

**클래스 — `RunHandleStore`** (thread-safe, RLock 보호):

| 영역 | 메서드 | 책임 |
|---|---|---|
| 등록 | `register(request)` | run_id 발급 + pending 상태 + ChangeSpec 보존 |
| 조회 | `get(run_id)` | RunHandle 또는 None |
| 조회 | `list(status=None)` | 전체 또는 status 필터 |
| 조회 | `get_change_spec(run_id)` | spec 03 §2.2 source |
| 조회 | `get_sim_result(run_id)` | 완료 후만 (그 외 None) |
| 전이 | `transition(run_id, new_status)` | 매트릭스 검증 — invalid 시 ValueError |
| 전이 | `cancel(run_id)` | 편의 메서드 (pending/running → cancelled) |
| **lifecycle** | `submit(request, orchestrator, run_plan)` | register → running → orchestrator.run() → completed/failed (sync) |

**`submit()` 흐름**:
1. `register` → pending
2. `transition` pending → running
3. `orchestrator.run(change_spec, run_plan, run_options)` 동기 호출
4. 결과 분기:
   - 정상 + sim_result.status='completed' → store + transition running → completed
   - 정상 + sim_result.status='failed' → store + transition running → failed
   - 예외 → transition running → failed (sim_result 미저장)
5. SimResult.run_id 를 RunHandle.run_id 로 정규화 (orchestrator 가 placeholder 썼을 가능성)

**echo-stub iter 합의**: sync 실행 (asyncio queue 미구현). 운영 v2 에서 Redis + RQ 도입 시 본 메서드를 worker 에서 호출하면 v2 가 됨 — 상태 전이 매트릭스는 동일.

### 3. 회귀 검증

| 검증 | 결과 |
|---|---|
| `test_run_handle.py` | **20/20 GREEN** |
| 전체 `tests/simulation/` | **282 passed** (이전 262 → +20), 17 skipped |
| 3 failure | sample-repos/slab-design 부재 (STEP 3b-5 무관) |
| Section isolation | ✅ modeling internal layer import 0건 |
| **e2e RunHandleStore + Orchestrator** | ✅ submit → RunHandle.completed + SimResult.sim_verified + filter 동작 |

## 주요 결정

- **sync orchestrator 실행** — async queue (asyncio.Queue) 는 후속 (3b-6 또는 별도 step). 첫 iter 의 단일 process 환경에서는 sync 가 충분 + 테스트 단순화.
- **RLock 사용** — multi-thread 안전 (FastAPI worker 환경 가정). multi-process 는 v2 (Redis) 에서 보강.
- **state machine 매트릭스 명시** — 5 상태 + transition dict 로 invalid 검출. terminal 상태에서 다른 상태로 못 감 (audit log 일관성).
- **SimResult.run_id 정규화** — orchestrator 가 placeholder 를 사용해도 store 가 RunHandle.run_id 로 강제 덮어씀. orchestrator 가 run_id 를 모르고도 SimResult 빌드 가능.
- **submit 의 사용자 예외 처리** — orchestrator 가 raise → failed 전이 + sim_result 미저장. failure_reason 은 SimResult 가 없으니 별도 보관 미구현 (후속에서 RunHandle 또는 별도 audit log 에 기록).
- **`request.run_options or RunOptions()`** — None 인 경우 default 사용 (spec 03 §1.1 의 옵션 필드).
- **`api/__init__.py` 미생성** — 기존 `backend/simulation/api/` 도 `__init__.py` 없이 namespace package 로 작동 중. 일관성 유지 위해 새 파일도 동일 패턴.

## 호환성

- 기존 simulation 코드 (sandbox / agents / jvm_bridge) 와 병존. `run_handle.py` 는 신규 모듈, 기존 import 영향 없음.
- 3b-1~3b-4 의 runner core 4 컴포넌트와 묶여 e2e 통과 — 다음 step (3b-6 spec_router) 이 본 store 를 의존성 주입 받아 wiring.

## Diff stat

- `backend/shared/contracts/simulation.py` — +15 lines (RunHandle 모델 + __all__ 항목)
- `backend/simulation/api/run_handle.py` — 신규 +200 lines
- `tests/simulation/test_run_handle.py` — 신규 +250 lines

## 다음 sub-step

| step | 내용 |
|---|---|
| **3b-6** | `api/spec_router.py` — POST /api/simulation/runs / GET /runs/{id} / GET /runs/{id}/sim-result / GET /runs/{id}/changespec 등 spec 03 §1, §2 endpoints + main.py 등록 |
| (future) | async queue (asyncio.Queue / Redis-RQ) 도입 — submit 을 worker thread/process 로 |
