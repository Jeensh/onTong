# STEP 3d-E — 운영화 layer 4종 (TimeoutBudget + FailurePolicy + artifact 디스크 + promote/downgrade hook)

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**범위**: E3 (TimeoutBudget + FailurePolicy) / E4 (promote/downgrade hook) / E5 (artifact 디스크 저장)

## 목표

STEP 3c 종결 후 남은 운영화 backlog 4건 일괄 처리. 모두 spec 명세에 있던 항목으로, echo-stub iter 의 단순화 표에서 미구현이었던 것들.

## E3-1 — TimeoutBudget (spec 05 §4.7) + RunOptions 확장

### `RunOptions` 6 필드 추가 (`backend/shared/contracts/simulation.py`)

```python
class RunOptions(BaseModel):
    # 기존
    sandbox_tier: Literal[...] = "stub_dispatch"
    dry_run: bool = False
    # 신규 (spec 03 §1.1)
    timeout_sec: int = Field(30, ge=1, le=600)
    capture_traces: bool = True
    capture_br_evidence: bool = True
    # 신규 (spec 05 §4.8 FailurePolicy)
    on_dispatch_error: Literal["fail_fast", "continue", "abort_after_n"] = "fail_fast"
    on_br_violation: Literal["continue", "fail_fast"] = "continue"
    on_anchor_miss: Literal["continue", "fail_fast"] = "continue"
    on_dispatch_inconsistent: Literal["continue", "fail_fast"] = "continue"
    max_dispatch_errors: int = Field(3, ge=1, le=20)
```

### `backend/simulation/runner/timeout_budget.py` 신설 (+50 lines)

`TimeoutBudget(total_sec, plan)`:
- `for_dispatch()` — 다음 dispatch 의 fair-share budget. 0 이하 시 TimeoutError raise
- `budget_remaining()` / `is_exhausted()`
- 분배: `total / estimated_steps` 기본 + 임의 dispatch 가 fair-share × 2 를 못 넘음 (한 frame 폭발 방지)

## E3-2 — FailurePolicy 4가지 정책 적용 (spec 05 §4.8)

`Orchestrator.run()` 의 dispatch loop 가 RunOptions 의 4 정책을 따라 분기:

| 정책 | continue | fail_fast | abort_after_n |
|---|---|---|---|
| `on_dispatch_error` | frame.error 채우고 다음 | 즉시 break + status=failed | max_dispatch_errors 누적 시 abort |
| `on_br_violation` | violation 도 capture, dispatch 계속 (verdict=sim_violation) | 즉시 break | — |
| `on_dispatch_inconsistent` | trace 끝까지 수집 (verdict=inconclusive) | 즉시 break | — |
| `on_anchor_miss` | (verdict 단계서 처리) | (현재 미사용 — 후속) | — |

추가로: dispatch 시작 전 `budget.is_exhausted()` 체크 — total run timeout 초과 시 sandbox_error.

### Test (`tests/test_timeout_and_failure_policy.py` +250 lines, 10 test):
- TimeoutBudget unit (2): for_dispatch positive / exhausted raises
- RunOptions defaults / Literal validation (2)
- on_dispatch_error continue / abort_after_n (2)
- on_br_violation fail_fast / default continue (2)
- on_dispatch_inconsistent fail_fast (1)
- timeout_sec exhausted → status=failed (1)

## E5 — artifact 디스크 저장 (spec 05 §6.2)

### `RunHandleStore` 가 in-memory + 디스크 dual:

- `__init__(artifact_root: Optional[Path])` — 기본 `data/simulation/artifacts/` 또는 `$ONTONG_ARTIFACT_ROOT` 환경변수
- `store_artifact(run_id, kind, content)` — in-memory cache + 디스크 write (`{root}/{run_id}/{kind}.{ext}`)
- `get_artifact(run_id, kind)` — in-memory 우선, 미존재 시 디스크 fallback (재시작 후 / process 간)
- `list_artifact_kinds(run_id)` — in-memory + 디스크 file 목록 union
- `artifact_path(run_id, kind)` — file path 반환 (다운로드용)

### 확장자 매핑

| kind | extension |
|---|---|
| generated_python | .py |
| jvm_log | .log |
| trace | .jsonl |
| input_fixture | .json |
| output_dump | .json |

### Graceful failure

디스크 write 실패 (read-only / permission / disk full) → warning log + in-memory 만 유지. read 는 in-memory 우선이므로 동작 영향 없음.

### Test (`tests/test_artifact_disk_storage.py` +180 lines, 12 test):
- store_artifact 디스크 파일 생성 / 디렉터리 자동 생성 / 확장자 매핑 (3)
- get_artifact in-memory 우선 / 디스크 fallback / 둘 다 없음 → None (3)
- list_artifact_kinds 디스크 포함 / memory+disk union (2)
- artifact_path / None (2)
- ONTONG_ARTIFACT_ROOT env (1)
- 디스크 write 실패 graceful (1)

## E4 — promote/downgrade hook (spec 04 §3.4)

### `SimResult` 2 필드 추가:
```python
suggested_promotion: Optional[str] = None
suggested_downgrade: Optional[str] = None
```

### Orchestrator `_derive_promotion_hook(verdict, change_spec)`:

| verdict | scenario_kind | suggestion |
|---|---|---|
| `sim_verified` | regression / boundary / integration | `"BODY_ANCHORED → SIM_VERIFIED"` |
| `sim_verified` | drama / br_violation / 미명시 | (둘 다 None — 보수적) |
| `sim_violation` | * | suggested_downgrade = `"SIM_VERIFIED → BODY_ANCHORED"` |
| `inconclusive` | * | (둘 다 None) |

scenario_kind 는 `change_spec.scenario_fixture.metadata.scenario_kind` 에서 추출.

**Hook 의 역할**: SimResult 응답에 권장 action 만 포함. 실 storage update (verification level 변경) 는:
- 사람 또는 agent 가 `POST /api/simulation/verification/promote` 호출 책임
- 또는 별도 hook 으로 modeling 측 수동 update

### Test (`tests/test_promote_hook.py` +150 lines, 7 test):
- sim_verified + regression → promote (1)
- sim_verified + boundary / integration → promote (2)
- sim_verified + drama / 미명시 → promote 안 함 (2)
- sim_violation → downgrade (1)
- inconclusive → 둘 다 None (1)

## 회귀

| | |
|---|---|
| `test_timeout_and_failure_policy.py` | 10 test |
| `test_artifact_disk_storage.py` | 12 test |
| `test_promote_hook.py` | 7 test |
| 전체 `tests/simulation/` | **374 passed** (이전 345 → **+29**), 17 skipped, 3 failed (sample-repos — 무관) |
| Section isolation | ✅ |

## 주요 결정

- **TimeoutBudget 정책**: `total / estimated_steps` 기본 fair-share + dynamic 흡수 (남은 시간 기반). 임의 dispatch 가 fair-share × 2 초과 시 강제 timeout.
- **on_anchor_miss 미적용**: anchor miss 는 dispatch 단계가 아닌 verdict 판정 단계에서 처리됨 — RunOptions 필드는 계약상 추가, 실 동작은 후속 (verdict 정합성 보강 시).
- **artifact 디스크 root**: env `ONTONG_ARTIFACT_ROOT` 또는 default `data/simulation/artifacts/`. test 시 `tmp_path` 로 격리.
- **promote hook 의 권장만**: spec 04 §3.4 의 "auto-promote/downgrade" 는 시스템이 verification level 을 자동 변경하는 게 아닌, **권장을 SimResult 에 노출** 하는 것. 실 변경은 별도 endpoint 호출 (사람/agent confirm).
- **scenario_kind metadata**: ChangeSpec.scenario_fixture.metadata.scenario_kind — 사용자가 명시 안 하면 promote 권장 안 함 (보수적).
- **graceful failure**: 디스크 write 실패해도 in-memory 동작 / OntologyClient 인스턴스화 실패해도 NullOntologyClient fallback. 어떤 운영 환경에서도 router 자체는 부팅.

## Section 3 의 ontology + 운영화 도달 수준 (3d 종결)

| 영역 | 상태 |
|---|---|
| ontology 데이터 흐름 | ✅ (3c) |
| atomic_overrides 4-rule | ✅ (3c-A) |
| spec 03 endpoints (POST/GET 11종) | ✅ (3b-6 / 3c-C) |
| artifact storage in-memory | ✅ (3c-C) |
| **artifact storage 디스크** | **✅ (3d-E5)** |
| **TimeoutBudget** | **✅ (3d-E3-1)** |
| **FailurePolicy 4가지** | **✅ (3d-E3-2)** |
| **promote/downgrade hook** | **✅ (3d-E4)** |
| 실 Java 코드 실행 | ❌ stub (E1: jvm_subprocess 후속) |
| async queue | ❌ sync (E2: Redis-RQ 후속) |
| Neo4j ↔ SQLite ontology 통합 | ❌ (E6) |

## Diff stat

- `runner/timeout_budget.py` — 신규 +50 lines
- `runner/orchestrator.py` — TimeoutBudget + FailurePolicy + promote_hook +120 lines
- `api/run_handle.py` — artifact 디스크 storage +60 lines
- `shared/contracts/simulation.py` — RunOptions 확장 +30 lines / SimResult promote fields +10 lines
- 테스트 3개 신규 (29 test 추가)

## 다음 작업 후보 (사용자 결정)

- **E1** — spec 05 §2.5 `jvm_subprocess` tier (실 Java 코드 실행). 큰 작업 (JNI / 직렬화 / instrumentation jar).
- **E2** — async queue (asyncio.Queue / Redis-RQ) v2.
- **E6** — Neo4j ↔ SQLite ontology source 통합 (agents_router 가 다른 client).
- **F** — 실 시나리오 추가 (drama / boundary / br_violation 변형).
