# 03 — Simulation API Spec

> **목적**: 시뮬레이션 라이프사이클 (ChangeSpec 입력 → 실행 → SimResult 출력 → 판정) 을 위한 신규 router `/api/simulation/*` 명세.
>
> **위치**: `backend/simulation/api/router.py` (실 폴더 구조). **modeling 폴더가 아닌 별도 simulation 영역**. 사용자 강조 + 실제 backend 구조 (`backend/simulation/{api,tools,mock,client}/` 폴더가 이미 존재, 현재 빈 상태) 기반. 자세한 단방향 의존성은 `00-README.md` 의 "섹션 경계" 절 + `05-runner-interface.md` Section 7 참조.
>
> **결정 근거**: Phase D Q4 = **B** (별 router 로 분리). 이유 — Ontology Query 는 read-only state 이고 Simulation 은 mutate state (run/result/anchor invalidation) 이므로 cohesion 분리.
>
> **의존**: `01-schema-extensions.md` (DesignGap / SimulationScenario 등) + `02-ontology-api-additions.md` (BR / delegates-to-tree).
>
> **관련**: ChangeSpec 입력 + SimResult 출력 schema 의 정밀 정의는 `04-changespec-simresult-schema.md` (D.3 산출물, 후속).

---

## 0. 카탈로그

| 분류 | 신규 endpoint | 수 |
|---|---|---|
| Scenario 실행 | runs (POST/GET/list) | 3 |
| 결과 조회 | sim-result / changespec / artifacts | 3 |
| 비교 | runs/diff | 1 |
| Anchor 라이프사이클 | anchor-invalidate | 1 |
| Verification 진급 | verification/promote | 1 |
| 메타 | health / capabilities | 2 |
| **합계** | | **약 11** |

---

## 1. Run 시작 / 조회

### 1.1 POST `/api/simulation/runs`

새 시뮬 실행 등록 + 비동기 시작.

**Request body**:
```python
class CreateRunRequest(BaseModel):
    change_spec: ChangeSpec
    """변경 명세 — `04-changespec-simresult-schema.md` 의 schema.
    핵심 필드:
      action_fqn: str                     # 실행할 PRIMARY Action
      atomic_overrides: dict[str, Any]    # atomic_path → 변경 값
      scenario_fixture: dict[str, Any]    # 시나리오 fixture 입력
    """
    scenario_id: str | None = None
    """미리 등록된 SimulationScenario 사용 시.
    scenario_id 와 change_spec 둘 다 주면 scenario_fixture 가 base 가 되고
    atomic_overrides 가 위에 덮어씀."""
    run_options: RunOptions | None = None
    """실행 옵션 — timeout / retry / verbose 등."""
    requested_by: str | None = None
    """사용자 / agent name (감사 추적용)."""


class RunOptions(BaseModel):
    timeout_sec: int = 30
    capture_traces: bool = True             # AnchorBinding marker hit 추적
    capture_br_evidence: bool = True        # BR 위반 증거 수집
    dry_run: bool = False                   # 코드 실행 없이 plan 만 반환
```

**Response**: `RunHandle`
```python
class RunHandle(BaseModel):
    run_id: str                # uuid
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    created_at: str            # ISO datetime
    plan: RunPlan | None       # dry_run=True 면 채워짐, false 면 None (poll 후 받음)


class RunPlan(BaseModel):
    """ChangeSpec → 실제 실행 계획의 미리보기."""
    target_action_fqn: str
    delegates_to_tree: list[str]  # transitive Action fqn 목록 (실행 순서)
    expected_brs: list[str]
    expected_anchors: list[str]
    estimated_steps: int
    warnings: list[str]           # design-gap 영향 경고
```

**상태 머신**:
- `pending` → `running` (sandbox 가 받아 시작)
- `running` → `completed` | `failed` | `cancelled`
- `completed` 의 SimResult 는 1.3 endpoint 로 조회

**용도**:
- 시뮬 에이전트의 핵심 진입점 — ChangeSpec 한 번 보내고 run_id 받음

### 1.2 GET `/api/simulation/runs/{run_id}`

```
GET /api/simulation/runs/{run_id}
```

**Response**: `RunHandle` (상태 polling)

### 1.3 GET `/api/simulation/runs`

```
GET /api/simulation/runs
  ?status={pending|running|completed|failed|cancelled}  # optional
  &target_action_fqn={str}                              # optional
  &requested_by={str}                                   # optional
  &since={ISO datetime}                                 # optional
  &limit=50                                             # default 50, le 200
```

**Response**: `list[RunHandle]` — 최근 run 목록.

**용도**:
- 시뮬 UI 의 history 패널
- VerificationLevel 진급 시 "이전에 이 Action 의 SIM 통과한 run 있는가" 조회

---

## 2. 결과 조회

### 2.1 GET `/api/simulation/runs/{run_id}/sim-result`

```
GET /api/simulation/runs/{run_id}/sim-result
```

**Response**: `SimResult` (`04-changespec-simresult-schema.md` 의 schema)

핵심 필드 미리보기:
```python
class SimResult(BaseModel):
    run_id: str
    status: Literal["completed", "failed"]
    verdict: Literal["sim_verified", "sim_violation", "inconclusive"]
    """sim_verified — 모든 BR 통과 + anchor marker 모두 hit
    sim_violation — BR 위반 1건 이상
    inconclusive — design-gap 영향으로 판정 불가
    """
    br_evidence: list[BREvidence]
    anchor_evidence: list[AnchorEvidence]
    output_values: dict[str, Any]      # action_fqn 의 output 슬롯 → 실측값
    delegation_trace: list[DelegationTraceFrame]   # 실제 호출 순서
    affected_design_gaps: list[int]    # gap_id 목록
    duration_ms: int
    started_at: str
    completed_at: str
```

### 2.2 GET `/api/simulation/runs/{run_id}/changespec`

```
GET /api/simulation/runs/{run_id}/changespec
```

**Response**: `ChangeSpec` — 이 run 의 입력 ChangeSpec.

**용도**: 재현 / 디버깅 / explanation panel.

### 2.3 GET `/api/simulation/runs/{run_id}/artifacts`

```
GET /api/simulation/runs/{run_id}/artifacts
  ?kind={generated_python|jvm_log|trace|all}  # default all
```

**Response**:
```python
class ArtifactBundle(BaseModel):
    run_id: str
    artifacts: list[Artifact]


class Artifact(BaseModel):
    kind: Literal["generated_python", "jvm_log", "trace", "input_fixture", "output_dump"]
    name: str
    content_type: str   # "text/x-python", "text/plain", "application/json" 등
    size_bytes: int
    download_url: str   # 별도 GET 으로 raw download
    summary: str        # 1~2 줄 요약 (head / tail / 핵심 라인)
```

**용도**:
- PythonGenerator 가 생성한 Python 코드 다운로드
- Java sandbox 의 stdout / stderr 로그
- AnchorBinding marker hit trace

---

## 3. Run 비교

### 3.1 POST `/api/simulation/runs/diff`

```python
class DiffRequest(BaseModel):
    base_run_id: str
    head_run_id: str
    aspects: list[Literal[
        "outputs", "br_evidence", "anchor_evidence",
        "delegation_trace", "duration"
    ]] = ["outputs", "br_evidence", "anchor_evidence"]
```

**Response**:
```python
class DiffResult(BaseModel):
    base_run_id: str
    head_run_id: str
    output_diffs: list[FieldDiff]
    br_diffs: list[BRDiff]
    anchor_diffs: list[AnchorDiff]
    summary: str
```

**용도**:
- ChangeSpec 의 atomic_override 효과를 base 와 비교
- regression — "P-2018-0098 시나리오에서 코드 변경 전/후 차이" 시각화

---

## 4. Anchor 라이프사이클

### 4.1 POST `/api/simulation/anchor-invalidate`

> design-gap #2 (Anchor invalidation) 의 1차 결정. 코드가 변경되면 stale anchor 가 발생하므로 명시적으로 invalidate 처리.

**Request**:
```python
class AnchorInvalidateRequest(BaseModel):
    repo_id: str
    method_fqn: str | None = None       # 변경된 메서드 — None 이면 전체 repo
    commit_sha_before: str | None = None
    commit_sha_after: str | None = None
    reason: Literal["code_change", "manual_edit", "auto_detect"]
```

**Response**:
```python
class AnchorInvalidateResult(BaseModel):
    invalidated_anchor_ids: list[str]
    affected_actions: list[str]         # action_fqn 목록 (verification_level 다운그레이드 대상)
    downgrade_count: int                # SIM_VERIFIED → BODY_ANCHORED 등 다운그레이드 수
    suggested_resimulate_runs: list[str]  # 재실행 추천 run_id (이전 run 중 재현 가능한 것)
```

**용도**:
- 코드 PR merge 후 호출 — stale anchor 일괄 다운그레이드
- 시뮬 에이전트가 "이 action 은 코드 변경 후 재시뮬 필요" 알림

---

## 5. Verification 진급

### 5.1 POST `/api/simulation/verification/promote`

**Request**:
```python
class PromoteRequest(BaseModel):
    action_fqn: str
    target_level: VerificationLevel    # DRAFT → SIGNATURE_LOCKED → BODY_ANCHORED → SIM_VERIFIED → PR_PROVEN
    evidence_run_ids: list[str] = []   # SIM_VERIFIED 진급 시 통과 run 증거
    approver: str                      # 사람 ID (audit)
    note: str | None = None
```

**Response**:
```python
class PromoteResult(BaseModel):
    action_fqn: str
    previous_level: VerificationLevel
    new_level: VerificationLevel
    promoted_at: str
    blocked_reason: str | None  # 진급 실패 시 이유
```

**규칙**:
- `SIM_VERIFIED` 진급 — `evidence_run_ids` 중 verdict=sim_verified 1건 이상 + scenario.kind 가 regression / boundary / integration 중 하나여야 함
- `PR_PROVEN` 진급 — 코드 PR merge + run 결과 정상 (별도 PR webhook 으로 자동화 가능)
- 다운그레이드 (높은 → 낮은) — 본 endpoint 가 아닌 4.1 anchor-invalidate 가 자동 처리

**용도**:
- 시뮬 에이전트가 자동 진급 / 사람 검수자 수동 진급 모두 사용

---

## 6. 메타 endpoints

### 6.1 GET `/api/simulation/health`

```
GET /api/simulation/health
```

**Response**:
```python
class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "down"]
    sandbox_available: bool        # Python sandbox 가능?
    jvm_available: bool            # Java sandbox 가능?
    queue_depth: int               # pending run 수
    last_run_at: str | None
```

**용도**: 시뮬 UI 의 시스템 상태 패널.

### 6.2 GET `/api/simulation/capabilities`

```
GET /api/simulation/capabilities
```

**Response**:
```python
class Capabilities(BaseModel):
    supported_action_kinds: list[str]   # ["pure_function", "workflow"]
    supported_scenario_kinds: list[str]
    supported_verdicts: list[str]
    runner_version: str
    java_sandbox_version: str | None
    max_timeout_sec: int
    max_atomic_overrides: int
```

**용도**: 클라이언트가 어떤 기능까지 지원되는지 사전 조회 (capability negotiation).

---

## 7. 인증 / 인가 (메모)

> 본 명세는 인증을 명시하지 않음. 기존 onTong backend 의 ACL 관행에 따름.

기본 가정:
- POST 계열 (runs / anchor-invalidate / verification/promote) — 인증된 user/agent 만
- GET 계열 — 같은 repo 권한 있는 user 만

---

## 8. 흐름 (시퀀스)

```
시뮬 에이전트                    /api/simulation/*               sandbox runner
────────────────────────────────────────────────────────────────────────────
  (1) POST /runs (change_spec) ──▶                       
                                  ┌──── pending ──▶ runner queue
  (2) GET /runs/{id} (poll) ────▶
                                  ◀── status: running
                                                  ──▶ runner picks up
                                                       generates Python code
                                                       executes in sandbox
                                                       collects evidence
                                  ◀────────── result writeback
  (3) GET /runs/{id}/sim-result ─▶
                                  ◀── SimResult (verdict + evidence)
  (4) (verdict=sim_verified) 
      POST /verification/promote ▶
                                  ◀── promoted: BODY_ANCHORED → SIM_VERIFIED
  (5) (코드 PR merge 후)
      POST /anchor-invalidate ──▶
                                  ◀── invalidated_anchor_ids + downgrade
```

---

## 9. design-gaps 와의 매핑

| design-gap # | 본 명세 endpoint 가 해소 |
|---|---|
| #1 SIM_VERIFIED 자동 결정 | 1.1 + 5.1 (verdict + promote 정책) |
| #2 Anchor invalidation 흐름 | 4.1 |
| #4 시뮬 input fixture | 1.1 (scenario_fixture + atomic_overrides) |
| #5 Java dispatch sandbox | 2.3 (artifacts) + 결과 SimResult.delegation_trace |
| #34 SimulationScenario 카탈로그 | `02-ontology-api-additions.md` 5.x 와 본 1.1 의 scenario_id 연결 |

---

## 10. 호환성

기존 router 와 path prefix 가 다름 (`/api/simulation/*` 신규) — **충돌 없음**.

기존 router 와 cross-call:
- `01-schema-extensions.md` 의 BR / Action / DesignGap / Scenario 스키마 사용
- `02-ontology-api-additions.md` 의 `delegates-to-tree` / `actions/.../business-rules` 호출 (run plan 작성 시)

---

## 11. 구현 순서 권장

| # | 단계 | 의존 |
|---|---|---|
| 1 | 1.1~1.3 runs (sandbox 없이 dry_run 만 먼저) | `01-schema-extensions.md` 모두 |
| 2 | sandbox runner 연결 (`05-runner-interface.md`, D.4 산출 후) | D.4 |
| 3 | 2.1~2.3 결과 조회 | run 1 동작 후 |
| 4 | 5.1 verification/promote | 2.1 의 verdict 정상 동작 |
| 5 | 4.1 anchor-invalidate | repo 변경 webhook 연결 |
| 6 | 3.1 runs/diff | 다수 run 누적 후 |
| 7 | 6.1~6.2 health / capabilities | 마지막 |

---

마지막 업데이트: 2026-05-10
