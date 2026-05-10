# 04 — ChangeSpec + SimResult Schema + Critical Gap #1/#2

> **목적**: 시뮬레이션의 입력 (`ChangeSpec`) 과 출력 (`SimResult`) 의 정밀 스키마, 그리고 두 critical 갭 (#1 SIM_VERIFIED 자동 판정 / #2 Anchor invalidation 흐름) 의 명세.
>
> **결정 근거**:
> - Q2=B — ChangeSpec format = `{action_fqn, atomic_overrides, scenario_fixture}`
> - Q3=A — D.3 에서 #1/#2 일괄 명세 (#4/#5 는 D.4 runner interface)
>
> **위치**: 본 파일이 `handoff-spec/04-changespec-simresult-schema.md`. 적용 코드는 `backend/shared/contracts/simulation.py` (신규).
>
> **의존**: `01-schema-extensions.md` (DesignGap / SimulationScenario / BR 보강) + `03-simulation-api-spec.md` (runs/sim-result 라이프사이클).

---

## 0. 개관

| 섹션 | 내용 |
|---|---|
| 1 | ChangeSpec 입력 스키마 — action_fqn / atomic_overrides / scenario_fixture |
| 2 | SimResult 출력 스키마 — verdict / br_evidence / anchor_evidence / output_values / delegation_trace |
| 3 | Critical 갭 #1 — SIM_VERIFIED 자동 판정 정책 |
| 4 | Critical 갭 #2 — Anchor invalidation 흐름 |
| 5 | 종합 라이프사이클 (시퀀스) |
| 6 | 검증 예시 — Phase A/B/C 실데이터 기반 |

---

## 1. ChangeSpec 입력 스키마

### 1.1 결정 형태 (Q2=B)

```python
class ChangeSpec(BaseModel):
    """시뮬 입력. action_fqn 만이 필수, 나머지는 optional 로 점진 합쳐짐."""

    # ── 1) 무엇을 시뮬할 것인가 ───────────────────────────
    action_fqn: str
    """실행 대상 PRIMARY Action.
    예: 'scm.workflow.SDSlabEntity_step_1_to_8'.
    workflow / pure_function 모두 가능. effectful 은 sandbox 정책 (D.4) 에 따라 결정."""

    # ── 2) 무엇을 변경할 것인가 ───────────────────────────
    atomic_overrides: dict[str, Any] = {}
    """atomic_path 형식의 키 → 새 값.
    
    atomic_path 문법:
      "{atomic_fqn}"                — 단순 atomic 값
      "{composite_fqn}.{slot}"      — composite term 의 슬롯
      "{action_fqn}.inputs[{i}]<{TypeFqn}>.{path}"
                                    — Action 인자의 atomic 경로 (Phase A 합의 path)
    
    예:
      "scm.shared.atomic.thickness": 230,
      "scm.spec.HrSpec.range_min": 200,
      "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.thickness": 240
    
    값 type 은 atomic.facets 에 따라 자동 검증:
      facets.unit / range_min / range_max / enum / default_value (01-...에서 추가).
    위반 시 RunPlan.warnings 에 명시."""

    # ── 3) 어떤 컨텍스트로 ──────────────────────────────────
    scenario_fixture: dict[str, Any] = {}
    """시나리오 fixture — DB lookup 가능한 데이터 + 비-atomic 컨텍스트.
    
    구조:
      {
        "lookups": {
          "Customer:7": { ... CustomerStd full row ... },
          "HrSpec:HR-23-A": { ... HrSpec row ... }
        },
        "metadata": {
          "scenario_origin": "P-2018-0098",  # IncidentRef 인 경우
          "snapshot_at": "2018-04-23T03:14",
          "operator_note": "정XX 슬래브 폭 미달 사고 재현"
        }
      }
    
    참고: scenario_id 가 같이 주어지면 SimulationScenario.inputs 가 base 가 되고
    여기서 lookups + metadata 추가/덮어씀 가능. 단순 fixture override 만 한다면
    scenario_id 없이 본 필드만 채워도 OK."""


class CreateRunRequest(BaseModel):
    """03-simulation-api-spec.md POST /runs 의 body 와 일치."""
    change_spec: ChangeSpec
    scenario_id: str | None = None
    run_options: RunOptions | None = None
    requested_by: str | None = None
```

### 1.2 atomic_overrides 의 path 해석 알고리즘

```
1. path 에 '<...>' 가 있으면 → Action input/output 슬롯 path
   — `OntologyQuery.resolve_path(action_fqn, slot_path)` 를 호출 (기존 endpoint 사용)
   — 결과 last_term_fqn 이 atomic 인지 확인 (atomic 만 override 가능)

2. path 가 'atomic_fqn' 단일 토큰이면 → atomic 직접 override
   — fixture/lookups 의 모든 row 중 본 atomic 슬롯 가진 곳에 적용 (broadcast)
   — 다중 row 영향 시 RunPlan.warnings 에 broadcast 안내

3. path 가 'composite_fqn.slot' 형이면 → composite 내 atomic 슬롯
   — `OntologyQuery.effective_parts(composite_fqn)` 결과에서 slot 검증
   — fixture/lookups 의 해당 composite 인스턴스에 대해 적용

4. path 가 인식 안 되면 → ValueError + 'invalid path: {path}' 에러
```

### 1.3 scenario_id + change_spec 동시 제공 시 우선순위

```
final_lookups = {**scenario.inputs.lookups, **change_spec.scenario_fixture.lookups}
final_metadata = {**scenario.inputs.metadata, **change_spec.scenario_fixture.metadata}
final_atomic_overrides = change_spec.atomic_overrides   # scenario 는 override 안 가짐
```

원칙: scenario 가 base, change_spec 가 위에 덮어씀. metadata 도 머지.

### 1.4 atomic_overrides 예시 (Phase A/B/C 실데이터)

```python
# Case A: Phase A — Customer 의 capability multiplier 조정 (drama DNA 시연)
ChangeSpec(
    action_fqn="scm.action.CalcCapability",
    atomic_overrides={
        "scm.shared.atomic.capabilityMultiplier": 1.05
    },
    scenario_fixture={
        "lookups": {"Customer:7": {...}}, 
        "metadata": {"origin": "drama-multiplier-tweak"}
    }
)

# Case B: Phase B — HrSpec proc[1] 자리 'HR' 검출 시연
ChangeSpec(
    action_fqn="scm.action.SdWidthRangeAction",
    atomic_overrides={
        "scm.spec.HrSpec.proc": "0HR23456"  # 자리 1 = HR
    }
)

# Case C: Phase C — Order/Slab 조정 (P-2018-0098 회귀)
ChangeSpec(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    atomic_overrides={
        "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.width": 1180,
        "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.thickness": 220
    },
    scenario_fixture={
        "lookups": {"Customer:7": {...}, "HrSpec:HR-23-A": {...}},
        "metadata": {"scenario_origin": "P-2018-0098", "snapshot_at": "2018-04-23T03:14"}
    }
)
```

---

## 2. SimResult 출력 스키마

### 2.1 메인 모델

```python
class SimResult(BaseModel):
    run_id: str
    status: Literal["completed", "failed"]
    verdict: Literal["sim_verified", "sim_violation", "inconclusive"]
    """sim_verified — 모든 BR 통과 + anchor marker 모두 hit + output 정합
    sim_violation — BR 위반 1건 이상 (severity=error)
    inconclusive — design-gap 영향 / sandbox 실행 실패 / anchor 미달 등 (Section 3 정책)"""

    # ── 증거 ─────────────────────────────────────────────
    br_evidence: list[BREvidence] = []
    anchor_evidence: list[AnchorEvidence] = []
    output_values: dict[str, Any] = {}
    """action_fqn 의 outputs 슬롯 path → 실측값.
    예: {"scm.workflow.SDSlabEntity_step_1_to_8.outputs[0]<scm.slab.SlabResult>": {...}}"""

    delegation_trace: list[DelegationTraceFrame] = []
    """workflow 가 호출한 sub-action 의 실제 호출 순서/시점/결과.
    delegates_to (스키마) 가 정적 그래프라면 본 trace 는 동적 실행 기록."""

    # ── 컨텍스트 ─────────────────────────────────────────
    affected_design_gaps: list[int] = []
    """이 run 의 결과 해석에 영향 주는 design-gap id 목록.
    예: [#1, #4] = SIM_VERIFIED 판정 + 시뮬 fixture 영향."""

    failure_reason: str | None = None
    """status=failed 의 1줄 사유. inconclusive 는 verdict 가 inconclusive 로,
    failure_reason 은 별개 (sandbox 충돌 등 시스템 사유)."""

    # ── 시간 ─────────────────────────────────────────────
    started_at: str       # ISO datetime
    completed_at: str
    duration_ms: int

    # ── 입력 참조 ────────────────────────────────────────
    change_spec_ref: str  # ChangeSpec 의 hash — 재현 시 동일 입력 검증용


class BREvidence(BaseModel):
    br_fqn: str
    severity: Literal["error", "warning", "info"]
    enforcer_method_fqn: str | None
    """BR.enforced_by 중 실제 실행 동안 호출된 메서드 (있다면)."""
    outcome: Literal["passed", "violated", "skipped"]
    """passed — guard 가 정상 동작 + 입력이 BR 위반 안함
    violated — BR 가 violate 됨
    skipped — guard 가 호출되지 않음 (delegation_trace 에 없음)"""
    violation_path: str | None
    """위반 시 atomic_path 형식의 위반 슬롯.
    예: 'scm.slab.SlabResult.thickness' (실측값 < range_min)."""
    expected: Any | None
    actual: Any | None
    operational_history_refs: list[str] = []
    """BR.operational_history 의 IncidentRef.incident_id 목록 (참고용)."""


class AnchorEvidence(BaseModel):
    anchor_id: str
    marker: str            # 예: '자리 1 = HR'
    method_fqn: str        # 어떤 메서드의 anchor 가 hit 됐는지
    line: int
    outcome: Literal["hit", "miss", "deferred"]
    """hit — marker 가 인식되어 expected anchor 가 fired
    miss — marker 가 인식 안 됨 (코드 변경 / 다른 분기 등)
    deferred — anchor 가 stale 마킹됨 (Section 4 invalidation)"""
    captured_value: Any | None
    """marker 가 capture 한 runtime 값 (있다면). 예: charAt(1) 결과."""


class DelegationTraceFrame(BaseModel):
    seq: int                # 호출 순서 (1부터)
    depth: int              # 호출 깊이 (root workflow = 0)
    action_fqn: str
    realized_method_fqn: str | None
    """실제 dispatch 된 method (Action.realizations 중 하나)."""
    dispatch_consistent: bool
    """input runtime CodeType 이 Action.realizes 의 input_type 과 일치하는가.
    sandbox 가 dispatch 시 검증 — 미달 시 False.
    Section 3.2 verdict 의 (f) 조건."""
    dispatch_mismatch_reason: str | None
    """dispatch_consistent=False 인 경우의 사유 (예: 'expected scm.order.Order, got scm.order.OrderArchive')."""
    inputs_summary: dict[str, Any]
    """dump 된 인자 요약 (큰 객체는 truncate)."""
    outputs_summary: dict[str, Any] | None
    duration_ms: int
    """이 frame 안에서 child frame 들도 포함한 누적 시간."""
    in_loop_iter: int | None
    """루프 안에서 호출된 경우 루프 회차 (1부터). 루프 외부면 None."""
    error: str | None
    """이 frame 에서 발생한 예외 (있다면)."""
```

### 2.2 verdict 판정 로직 (Section 3 의 핵심)

```
sim_verified  := all(br.outcome=passed) ∧ all(anchor.outcome=hit) ∧
                 all(expected_brs ⊆ br_evidence) ∧
                 status=completed

sim_violation := exists(br.outcome=violated AND severity=error) ∧
                 status=completed

inconclusive  := else (anchor miss / deferred / status=failed / 
                       expected_br 미수집 / design-gap 영향 등)
```

상세는 Section 3 참조.

---

## 3. Critical 갭 #1 — SIM_VERIFIED 자동 판정 정책

### 3.1 문제 정의 (design-gap #1)

기존: 시뮬을 돌렸을 때 "통과" 의 기준이 명세되지 않음. VerificationLevel 의 `SIM_VERIFIED` 진급에 어떤 조건이 충분한지 합의 필요.

### 3.2 결정 — 3-tier verdict + 진급 조건

| verdict | 조건 (모두 만족) | VerificationLevel 진급 |
|---|---|---|
| `sim_verified` | (a) `status=completed` <br>(b) 기대된 모든 직접 BR (`expected_brs.direct`) 가 evidence 에 포함 + 모두 `passed` <br>(c) transitive BR (`expected_brs.transitive`) 누락은 warning 으로 처리 (verdict 엔 영향 없음) <br>(d) 모든 expected_anchors 가 `outcome=hit` <br>(e) `output_values` 가 scenario.expected_outputs 와 일치 (있는 경우) <br>(f) **모든 frame `dispatch_consistent=True`** — input runtime type 이 Action.realizes 의 input_type 과 일치 | `BODY_ANCHORED → SIM_VERIFIED` 가능 (단, scenario.kind ∈ {regression, boundary, integration} 1건 이상 필요) |
| `sim_violation` | `status=completed` ∧ ∃ `BREvidence(outcome=violated, severity=error)` | 다운그레이드 — 기존이 SIM_VERIFIED 라면 BODY_ANCHORED 로 |
| `inconclusive` | 위 둘 외 — anchor miss / deferred / status=failed / expected_br 미수집 | 변동 없음 (SIM_VERIFIED 진급 불가, 다운그레이드도 안 함) |

### 3.3 expected_brs / expected_anchors 의 출처

```
expected_brs.direct     = GET /api/ontology/actions/{action_fqn}/business-rules
                          (02-... Section 1.3, declared_on_term==target_action 만)
expected_brs.transitive = GET /api/ontology/actions/{action_fqn}/business-rules
                          (02-... Section 1.3, include_transitive=True)
                          MINUS expected_brs.direct
expected_brs.scenario   = scenario.expected_brs (있다면)

expected_anchors = ⋃ for action in delegates_to_tree:
                       GET /api/ontology/actions/{action_fqn}/anchor-bindings
                       (기존 endpoint, ontology_router.py:120)
                   ∪ scenario.expected_anchors

# 합집합. fold-up 시 같은 anchor_id 는 한 번만.
```

**direct vs transitive 분리 이유** — A3 검수자 합의에 따른 보강. transitive BR (60+ 개 가능) 의 evidence 누락은 false-negative 폭발 위험. Section 3.2 의 (b)/(c) 처럼 direct 만 verdict 에 영향, transitive 누락은 warning 으로.

### 3.4 진급 자동화 정책

```
on POST /api/simulation/runs result available:
  if verdict == sim_verified:
    if scenario.kind in {regression, boundary, integration}:
      auto-suggest promote BODY_ANCHORED → SIM_VERIFIED
      (사람 confirm 또는 Authoring agent confirm 후 5.1 promote endpoint 호출)
    else (drama / br_violation):
      no auto-promote. 시뮬 결과만 표시.

  if verdict == sim_violation:
    if action.verification_level == SIM_VERIFIED:
      auto-downgrade SIM_VERIFIED → BODY_ANCHORED
      (즉시 + audit log)
    
  if verdict == inconclusive:
    no level change. inconclusive 사유 explanation panel 에 표시.
```

### 3.5 affected_design_gaps 산출

```
affected_design_gaps = OntologyQuery.actions/{action_fqn}/design-gaps
                       (02-...-Section 4.3, include_transitive=True)
                       ∪ {gap | gap.related_action_fqns ∩ delegation_trace.action_fqn ≠ ∅}
```

inconclusive 인 경우 본 list 가 길어지면 explanation panel 의 "현재 결과는 갭 #X / #Y 의 잠정 가정 위에 만들어졌다" 노출.

### 3.6 실수 / 보수적 결정

- **anchor miss 1개라도 있으면 sim_verified 아님** — 코드 분기를 뒤짚는 변화일 수 있음. 보수적으로 inconclusive.
- **direct expected_br 가 evidence 에 없으면** → inconclusive. passed 로 가정 안함.
- **transitive expected_br 가 evidence 에 없으면** → SimResult.warnings 에 기록, verdict 엔 영향 없음 (3.2 (c)).
- **scenario.expected_outputs 가 None 인 경우** → output 일치는 무시 (a~d 만 검사).
- **dispatch 정합성 미달** — 1 frame 이라도 `dispatch_consistent=False` 면 verdict=inconclusive (sim_verified 의 (f) 미달). 이유 — Java 다형성 환경에서 input runtime type 이 Action.realizes 와 다르면 시뮬 결과가 의도와 어긋날 수 있음 (D.4 sandbox runner 가 dispatch 시 자동 설정).

---

## 4. Critical 갭 #2 — Anchor invalidation 흐름

### 4.1 문제 정의 (design-gap #2)

기존: 코드가 변경되면 (refactor / line shift / 분기 추가) anchor 의 line 정보가 stale 해질 수 있음. 어떤 시점에 anchor 를 invalidate 해야 하는지 + 영향 받는 Action 의 verification_level 처리가 명세되지 않음.

### 4.2 결정 — 3-trigger invalidation

| Trigger | 시점 | 액션 |
|---|---|---|
| (T1) 코드 PR merge | git webhook | `POST /api/simulation/anchor-invalidate` (4.3) |
| (T2) 수동 anchor 편집 | Authoring agent 가 anchor binding 수정 | 같은 endpoint 호출 (`reason=manual_edit`) |
| (T3) 자동 stale detection | Authoring agent 의 sanity check (line 번호의 코드 텍스트가 anchor.expected_text 와 다름) | 같은 endpoint 호출 (`reason=auto_detect`) |

### 4.3 invalidation 알고리즘

```
input: AnchorInvalidateRequest{repo_id, method_fqn?, commit_sha_before?, commit_sha_after?, reason}

1. 영향 anchor 수집:
   if method_fqn given:
     anchors = AnchorBinding.list_for_method(method_fqn)
   else:
     anchors = AnchorBinding.list_for_repo(repo_id)

2. anchor 마킹:
   for a in anchors:
     a.status = "stale"
     a.invalidated_at = now()
     a.invalidated_reason = reason
     a.last_known_commit = commit_sha_before

3. 영향 Action 수집:
   affected_actions = { action.fqn 
                        | action.anchor_bindings ∋ any(anchors) }

4. VerificationLevel 부분 다운그레이드 (B2 검수 합의 — 일률 아님):
   for action in affected_actions:
     total_anchors    = count(action.anchor_bindings)
     stale_anchors    = count(action.anchor_bindings ∩ anchors)
     stale_ratio      = stale_anchors / total_anchors

     match (action.verification_level, stale_ratio):
       (SIM_VERIFIED, 0)              → no change
       (SIM_VERIFIED, 0 < r < 0.30)   → BODY_ANCHORED   # 일부 stale, 부분 보전
       (SIM_VERIFIED, r >= 0.30)      → SIGNATURE_LOCKED  # 다수 stale, 전체 후퇴
       (BODY_ANCHORED, 0 < r < 0.30)  → BODY_ANCHORED   # 변동 없음
       (BODY_ANCHORED, r >= 0.30)     → SIGNATURE_LOCKED
       (SIGNATURE_LOCKED, *)          → no change       # 더 이상 후퇴 없음
     audit: "downgraded ratio=R% due to anchor invalidation"

   # 0.30 임계값 — 운영 사고 추적성 (소수 anchor 만 stale 일 때 SIM_VERIFIED 유지) + 
   # 안전성 (다수 stale 일 때 보수적 후퇴) 절충.

5. 재시뮬 추천:
   suggested_resimulate_runs = [
     run.id for run in recent_runs(target_action ∈ affected_actions)
     if run.verdict == sim_verified
   ]

6. return AnchorInvalidateResult
```

### 4.4 invalidation 이후의 흐름

```
T0: anchor X1 (action A1 의 marker) hit, action.level = SIM_VERIFIED
T1: 코드 PR merge — anchor-invalidate 호출
    X1.status = stale, A1.level = SIGNATURE_LOCKED (다운그레이드)
T2: Authoring agent 가 A1 의 anchor 재바인딩 (line 갱신)
    X1.status = active, A1.level 은 그대로 SIGNATURE_LOCKED (anchor hit 만으로는 BODY_ANCHORED 진급 별개)
T3: 사용자 / agent 가 시뮬 재실행 (POST /runs with same ChangeSpec)
    new SimResult → verdict = sim_verified 면 promote → SIM_VERIFIED 복귀
```

### 4.5 stale anchor 의 SimResult 영향

- 시뮬 도중 anchor 가 stale 인 경우 (T1~T2 사이 실행) → AnchorEvidence.outcome = `deferred`.
- deferred 1건이라도 있으면 verdict = `inconclusive`.
- 실행 자체는 막지 않음 (best-effort) — sandbox 가 코드를 돌리고 결과를 채우되, anchor 검증만 미정 처리.

### 4.6 합의 — invalidation 의 책임 영역

| 영역 | 누가 |
|---|---|
| anchor 의 stale 마킹 | 본 endpoint (자동) |
| anchor 의 line 재바인딩 | Authoring agent (별도 흐름, 본 명세 외) |
| Action level 다운그레이드 | 본 endpoint (자동, 부분 다운그레이드 정책 — 4.3 step 4) |
| Action level 재진급 (SIGNATURE_LOCKED → SIM_VERIFIED) | 시뮬 재실행 + 5.1 promote (수동/agent) |

### 4.7 verdict=sim_violation 시 operational_history 자동 추가 (B5 검수 보강)

> **동기**: anchor invalidation 정책의 핵심은 코드 변화에 따른 stale 처리이지만, 변화의 결과가 운영 사고로 이어졌을 때 추적성이 끊기는 위험이 검수에서 지적됨. 본 절은 **시뮬 결과가 violation** 일 때 자동으로 BR.operational_history 에 기록을 남기는 흐름을 명세.

#### 흐름

```
on POST /api/simulation/runs result available:
  if verdict == sim_violation:
    for evidence in br_evidence where outcome == "violated":
      candidate_incident = IncidentRef(
        incident_id     = "AUTO-{run_id}-{br_fqn}",
        occurred_at     = now(),
        summary         = "SIM violation in {evidence.br_fqn} via run {run_id}",
        triggered_by    = change_spec.action_fqn,
        fixed_at_commit = None
      )
      
      # 정책 1 — 자동 등록 (origin=incident scenario 일 때만)
      if scenario.origin == "incident" and scenario.incident_ref:
        # scenario 가 이미 알려진 사고와 매칭됨 — 자동 추가
        BR(evidence.br_fqn).operational_history.append(scenario.incident_ref)
        audit: "auto-linked to {scenario.incident_ref.incident_id}"
      
      # 정책 2 — confirm 큐 등록 (그 외 모든 경우)
      else:
        IncidentReview.queue.append({
          run_id, evidence, candidate_incident,
          status: "pending_review"
        })
        notify: "사고 후보 검토 필요 — IncidentReview queue {N}건"
```

#### 정책 분리

| 시나리오 origin | 처리 |
|---|---|
| `incident` (scenario.incident_ref 가 P-2018-0098 등) | **자동 추가** — 이미 검증된 사고와 BR 가 매칭됨 |
| `interview` / `synthetic` | **confirm 큐** — 사람 / Authoring agent 가 검토 후 BR.operational_history 추가 결정 |

#### 위험 통제

- 자동 추가 모드만 audit log 에 기록 — 누가 / 언제 / 어떤 run 으로 추가됐는지 항상 추적 가능
- confirm 큐의 timeout (예: 7일) 후에도 처리 안 되면 alert (B4 검수 합의)

#### 관련

- design-gap #18 (BR enforcement 추적) 의 후속 — enforcement 뿐 아니라 violation 도 history 와 연결
- IncidentReview 큐 자체의 storage / endpoint 는 D.4 또는 Phase E 에서 명세

---

## 5. 종합 라이프사이클 (시퀀스)

```
사용자 / 시뮬 에이전트            /api/simulation/*           sandbox runner          OntologyQuery
─────────────────────────────────────────────────────────────────────────────────────────────────
 (a) ChangeSpec 작성
     POST /runs(change_spec) ──▶
                                 ┌── plan 생성 ─────────────────────────────▶ delegates-to-tree
                                 │   (expected_brs / anchors) ◀──────────────── actions/.../business-rules
                                 │   warnings 검사 (atomic.facets)
                                 └── runner queue
                                                ──────────▶ generate Python (D.4)
                                                            sandbox exec
                                                            collect br_evidence
                                                            collect anchor_evidence
                                                            collect delegation_trace
                                 ◀────────────── result writeback
 (b) GET /runs/{id}/sim-result ─▶
                                 ◀── SimResult(verdict + evidence + traces)

 (c) verdict=sim_verified 이면:
     POST /verification/promote ▶
                                 ┌── scenario.kind 확인
                                 └── BODY_ANCHORED → SIM_VERIFIED

 (d) verdict=sim_violation 이면:
     auto-downgrade
                                 SIM_VERIFIED → BODY_ANCHORED

 (e) (코드 PR merge — 별 흐름)
     POST /anchor-invalidate ──▶
                                 ┌── anchor stale 마킹
                                 ├── action level 다운그레이드
                                 └── 재시뮬 추천 run_id 반환

 (f) 사용자 / agent 가 (a) 부터 다시
```

---

## 6. 검증 예시 (Phase A/B/C 실데이터)

### 6.1 Phase A — Customer 시연 (drama)

```python
# Input
change_spec = ChangeSpec(
    action_fqn="scm.action.CalcCapability",
    atomic_overrides={"scm.shared.atomic.capabilityMultiplier": 1.05}
)

# Expected SimResult (예상)
{
    "verdict": "sim_verified",  # 단, scenario.kind=drama 이므로 자동 진급 안함
    "br_evidence": [],          # CalcCapability 는 BR 없음 (Phase A archive)
    "anchor_evidence": [
        {"anchor_id": "a1", "outcome": "hit", "captured_value": 1.05}
    ],
    "output_values": {"capability": 1050.5},  # 1000 * 1.05 + epsilon
    "affected_design_gaps": []
}
```

### 6.2 Phase B — HrSpec proc[1] 자리 'HR' (drama DNA 시연)

```python
change_spec = ChangeSpec(
    action_fqn="scm.action.SdWidthRangeAction",
    atomic_overrides={"scm.spec.HrSpec.proc": "0HR23456"}
)

# Expected
{
    "verdict": "sim_verified",
    "anchor_evidence": [
        {"anchor_id": "a1_proc_pos1", "marker": "자리 1 = HR",
         "outcome": "hit", "captured_value": "HR"}
    ],
    "output_values": {"width_range": {"min": 1100, "max": 1300}}
}
```

### 6.3 Phase C — P-2018-0098 회귀 (regression)

```python
change_spec = ChangeSpec(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    atomic_overrides={
        "...inputs[0]<scm.order.Order>.width": 1180,
        "...inputs[0]<scm.order.Order>.thickness": 220
    },
    scenario_fixture={
        "lookups": {"Customer:7": {...}, "HrSpec:HR-23-A": {...}},
        "metadata": {"scenario_origin": "P-2018-0098"}
    }
)

# Expected (P-2018-0098 가 폭 미달 사고였으므로 BR 위반 기대)
{
    "verdict": "sim_violation",
    "br_evidence": [
        {"br_fqn": "br.scm.slab.DG003.WidthMin", "outcome": "violated",
         "severity": "error",
         "violation_path": "scm.slab.SlabResult.width",
         "expected": ">=1200", "actual": 1180,
         "operational_history_refs": ["P-2018-0098"]}
    ],
    "delegation_trace": [...],   # 21-step 의 step-3 (width range) 에서 violation
    "affected_design_gaps": [3]  # DG003 영향
}
# 결과: 기존 SIM_VERIFIED 였다면 BODY_ANCHORED 로 자동 다운그레이드
```

---

## 7. 호환성

- `ChangeSpec` / `SimResult` / `BREvidence` / `AnchorEvidence` / `DelegationTraceFrame` 모두 신규 모델 — 기존 DTO 영향 없음.
- `03-simulation-api-spec.md` 의 endpoint 가 본 스키마를 그대로 사용 (cross-ref).
- VerificationLevel enum 은 기존 6 stage 그대로 (`UNMAPPED → DRAFT → SIGNATURE_LOCKED → BODY_ANCHORED → SIM_VERIFIED → PR_PROVEN`).

---

## 8. 구현 단계 권장

| # | 단계 | 의존 |
|---|---|---|
| 1 | ChangeSpec / SimResult 모델 정의 (`backend/shared/contracts/simulation.py`) | `01-...` 스키마 보강 |
| 2 | `03-...` 의 POST /runs / GET /runs/{id}/sim-result endpoint 가 본 모델 사용 | 1 |
| 3 | RunPlan 생성 로직 — expected_brs / expected_anchors 계산 | `02-...` 의 BR / delegates-to-tree endpoint |
| 4 | verdict 판정 로직 (Section 3) | 2 |
| 5 | anchor-invalidate 흐름 (Section 4) | `03-...` 4.1 + storage 의 anchor.status 컬럼 |
| 6 | auto-promote / auto-downgrade hook (Section 3.4 / 4.4) | 4 + 5 |

---

## 9. design-gaps 와의 매핑

| design-gap # | 본 명세 가 해소 |
|---|---|
| #1 SIM_VERIFIED 자동 결정 | Section 3 (3-tier verdict + 진급 정책) |
| #2 Anchor invalidation 흐름 | Section 4 (3-trigger + 다운그레이드 정책) |
| #4 시뮬 input fixture | 부분 — ChangeSpec.scenario_fixture 형식까지. DB lookup 의 sandbox 데이터 source 는 D.4 |
| #5 Java dispatch sandbox | 부분 — DelegationTraceFrame.realized_method_fqn 자리만. 실제 dispatch 전략은 D.4 |

---

마지막 업데이트: 2026-05-10
