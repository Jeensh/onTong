"""Simulation 입출력 contract — Section 3 (시뮬레이션) 의 entry-level 모델.

spec 04 (`toClaude/modeling/handoff-spec/04-changespec-simresult-schema.md`) 의 schema 를
Pydantic v2 로 1:1 옮긴 모듈. 외부 (frontend / Section 2) 가 의존하는 표준 DTO.

핵심 모델:
- ChangeSpec      — 시뮬 입력 (action_fqn / atomic_overrides / scenario_fixture)
- CreateRunRequest — POST /api/simulation/runs body
- BREvidence      — 시뮬 도중 BR 호출 + outcome
- AnchorEvidence  — anchor marker 의 hit / miss / deferred
- DelegationTraceFrame — workflow 의 sub-action 호출 trace (depth, dispatch_consistent 등)
- SimResult       — 시뮬 출력 + verdict (sim_verified / sim_violation / inconclusive)

호환:
- 기존 simulation 코드 (sandbox / agents / jvm_bridge) 와 병존. ChangeSpec 흐름은 별도 router/runner 로
  도입되며, 본 모듈은 그 표준 contract.
- ontology_query 의 DTO (TermDTO/ActionDTO 등) 와 cross-ref 안 함 — 본 모듈은 시뮬 흐름 전용.

작성 시점: 2026-05-10 STEP 3a (06-developer-onboarding.md).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── ChangeSpec — 시뮬 입력 (spec 04 §1) ────────────────────────────


class ChangeSpec(BaseModel):
    """시뮬 입력. action_fqn 만 필수, 나머지는 점진 합쳐짐 (spec 04 §1.1).

    필드:
    - action_fqn       : 실행 대상 PRIMARY Action FQN (workflow / pure_function 모두 가능)
    - atomic_overrides : atomic_path 형식 키 → 새 값 dict (spec 04 §1.2 path 해석)
    - scenario_fixture : DB lookup row + metadata (spec 04 §1.1 구조)
    """

    model_config = ConfigDict(extra="forbid")

    action_fqn: str
    atomic_overrides: dict[str, Any] = Field(default_factory=dict)
    scenario_fixture: dict[str, Any] = Field(default_factory=dict)


class RunOptions(BaseModel):
    """시뮬 실행 옵션 (spec 03/04 — 03 의 RunOptions 확정 후 보강 예정).

    현재는 minimal — sandbox tier / dry_run 만. spec 03 endpoint 정의 시 확장.
    """

    model_config = ConfigDict(extra="forbid")

    sandbox_tier: Literal["stub_dispatch", "jvm_subprocess", "graalvm"] = "stub_dispatch"
    """spec 05 §2 의 3-tier — 첫 iteration 은 stub_dispatch 만 의미 있음."""

    dry_run: bool = False
    """True 면 RunPlan 생성까지만 (실제 sandbox 실행 skip)."""


class CreateRunRequest(BaseModel):
    """POST /api/simulation/runs body (spec 03 + 04 §1.1).

    scenario_id + change_spec 동시 제공 시 우선순위 — spec 04 §1.3:
        final_lookups = scenario.inputs.lookups | change_spec.scenario_fixture.lookups
        atomic_overrides 는 change_spec 가 단독.
    """

    model_config = ConfigDict(extra="forbid")

    change_spec: ChangeSpec
    scenario_id: Optional[str] = None
    run_options: Optional[RunOptions] = None
    requested_by: Optional[str] = None


# ─── Evidence — 시뮬 출력의 핵심 (spec 04 §2.1) ─────────────────────


class BREvidence(BaseModel):
    """시뮬 도중 발견된 BR (Business Rule) evidence.

    outcome:
    - passed   : guard 가 정상 동작 + 입력이 BR 위반 안 함
    - violated : BR 가 violate 됨
    - skipped  : guard 가 호출되지 않음 (delegation_trace 에 없음)
    """

    model_config = ConfigDict(extra="forbid")

    br_fqn: str
    severity: Literal["error", "warning", "info"]
    enforcer_method_fqn: Optional[str]
    outcome: Literal["passed", "violated", "skipped"]
    violation_path: Optional[str] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    operational_history_refs: list[str] = Field(default_factory=list)


class AnchorEvidence(BaseModel):
    """anchor binding 의 marker 가 시뮬 도중 hit 되었는지 evidence.

    outcome:
    - hit      : marker 인식 + expected anchor fired
    - miss     : marker 인식 안 됨 (코드 변경 / 다른 분기)
    - deferred : anchor 가 stale 마킹됨 (Section 4 invalidation)
    """

    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    marker: str
    method_fqn: str
    line: int
    outcome: Literal["hit", "miss", "deferred"]
    captured_value: Optional[Any] = None


class DelegationTraceFrame(BaseModel):
    """workflow 가 호출한 sub-action 의 동적 실행 기록.

    delegates_to (ontology 의 정적 그래프) 와 대비되는 actual runtime trace.
    spec 04 §2.1 + §3.2 의 (f) 조건 (모든 frame dispatch_consistent=True) 와 연결.
    """

    model_config = ConfigDict(extra="forbid")

    seq: int
    """호출 순서 (1부터)."""

    depth: int
    """호출 깊이 (root workflow = 0)."""

    action_fqn: str
    realized_method_fqn: Optional[str]
    """실제 dispatch 된 method (Action.realizations 중 하나)."""

    dispatch_consistent: bool
    """input runtime CodeType 이 Action.realizes 의 input_type 과 일치하는가.
    sandbox 가 dispatch 시 검증 — 미달 시 False. spec 04 §3.2 (f) 조건."""

    dispatch_mismatch_reason: Optional[str] = None
    inputs_summary: dict[str, Any] = Field(default_factory=dict)
    outputs_summary: Optional[dict[str, Any]] = None
    duration_ms: int = 0
    in_loop_iter: Optional[int] = None
    """루프 안에서 호출된 경우 회차 (1부터). 루프 외부면 None."""

    error: Optional[str] = None


# ─── SimResult — 시뮬 출력 (spec 04 §2.1) ──────────────────────────


class SimResult(BaseModel):
    """시뮬 실행 출력.

    verdict 산정 — spec 04 §2.2:
        sim_verified  := all(br.passed) ∧ all(anchor.hit) ∧ all(expected_brs ⊆ br_evidence)
                          ∧ status=completed ∧ all(frame.dispatch_consistent=True)
        sim_violation := exists(br.violated AND severity=error) ∧ status=completed
        inconclusive  := else
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: Literal["completed", "failed"]
    verdict: Literal["sim_verified", "sim_violation", "inconclusive"]

    # ── 증거 ─────────────────────────────────────────────
    br_evidence: list[BREvidence] = Field(default_factory=list)
    anchor_evidence: list[AnchorEvidence] = Field(default_factory=list)
    output_values: dict[str, Any] = Field(default_factory=dict)
    """action_fqn 의 outputs 슬롯 path → 실측값."""

    delegation_trace: list[DelegationTraceFrame] = Field(default_factory=list)

    # ── 컨텍스트 ─────────────────────────────────────────
    affected_design_gaps: list[int] = Field(default_factory=list)
    failure_reason: Optional[str] = None

    # ── 시간 ─────────────────────────────────────────────
    started_at: str
    completed_at: str
    duration_ms: int

    # ── 입력 참조 ────────────────────────────────────────
    change_spec_ref: str
    """ChangeSpec 의 hash — 재현 시 동일 입력 검증용."""


__all__ = [
    "ChangeSpec",
    "RunOptions",
    "CreateRunRequest",
    "BREvidence",
    "AnchorEvidence",
    "DelegationTraceFrame",
    "SimResult",
]
