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


# ─── Runner-side 모델 (spec 05 §1, §2, §3, §4.6, §4.8) ──────────────


class TypedValue(BaseModel):
    """slot 값의 type-tagged 표현 — JSON 직렬화 시 _type 식별자 보존 (spec 05 §5.5).

    `type_` 명명: Pydantic v2 가 `_type` 으로 underscore-prefix 을 private 로 처리하므로
    public 필드는 `type_` 사용. 직렬화 시 alias `_type` 으로 노출.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type_: str = Field(alias="_type")
    """CodeType FQN — 예: 'scm.order.Order'."""

    value: Any
    """primitive / dict / list."""


class RunPlan(BaseModel):
    """시뮬 입력의 plan — orchestrator 가 expected_brs / expected_anchors 계산 (spec 04 §3.3).

    minimal — POST /runs 가 plan 을 즉시 빌드하거나 (spec 03), runner 가 주입 받음.
    """

    model_config = ConfigDict(extra="forbid")

    delegates_to_tree: list[dict[str, Any]] = Field(default_factory=list)
    """flatten 된 delegation tree — 각 element 는 {action_fqn, depth, is_in_loop?, optional?, ...}.
    구체 schema 는 spec 02 의 delegates-to-tree endpoint 응답과 동일."""

    expected_brs: dict[str, list[str]] = Field(default_factory=dict)
    """spec 04 §3.3 — {"direct": [...], "transitive": [...], "scenario": [...]} 형식."""

    expected_anchors: list[str] = Field(default_factory=list)
    estimated_steps: int = 0
    warnings: list[str] = Field(default_factory=list)


class RunInputs(BaseModel):
    """orchestrator → python_generator → java_sandbox 일관 사용되는 입력 (spec 05 §4.6).

    `fixture` 는 LookupDataSource 인스턴스 (Pydantic 외 type) — model_config 로 허용.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    slots: dict[str, TypedValue] = Field(default_factory=dict)
    """Action.inputs 의 slot_name → TypedValue."""

    fixture: Optional[Any] = None
    """LookupDataSource 인스턴스. orchestrator 가 빌드 후 주입.
    type 으로 명시 안 하는 이유: LookupDataSource 는 backend.simulation.runner 안에 있어
    상위 contracts 에서 import 시 순환. duck-typed."""

    overrides: dict[str, Any] = Field(default_factory=dict)
    """ChangeSpec.atomic_overrides 의 그대로 — atomic_path → 값 (spec 04 §1.2)."""

    primary_input_slot: Optional[str] = None
    """다형성 dispatch 가 참조할 슬롯 이름 (spec 05 §4.6)."""


class GeneratedScript(BaseModel):
    """PythonGenerator 의 산출 (spec 05 §1.2)."""

    model_config = ConfigDict(extra="forbid")

    source_code: str
    """실행 가능한 Python 코드 (utf-8)."""

    entrypoint: str = "run"
    """실행할 함수 이름."""

    imports: list[str] = Field(default_factory=list)
    """필요 import 문 — sandbox 가 화이트리스트 검증 (spec 05 §1.4)."""

    estimated_steps: int = 0
    java_dispatch_calls: list[str] = Field(default_factory=list)
    """본 코드가 호출할 Java method_fqn 목록 — 사전 검증 용."""

    fixture_keys_used: list[str] = Field(default_factory=list)


# ─── Java sandbox dispatch (spec 05 §2.2) ──────────────────────────


class AnchorHit(BaseModel):
    """JVM agent 가 instrumentation 으로 capture 한 anchor hit (spec 05 §2.2)."""

    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    marker: str
    line: int
    captured_value: Optional[Any] = None


class BRTrigger(BaseModel):
    """JVM 도중 호출된 BR enforcer 메서드 trace (spec 05 §2.2)."""

    model_config = ConfigDict(extra="forbid")

    br_fqn: str
    enforcer_method_fqn: Optional[str]
    outcome: Literal["passed", "violated", "skipped"]
    violation_path: Optional[str] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None


class DispatchResult(BaseModel):
    """JavaSandbox.dispatch() 의 산출 (spec 05 §2.2)."""

    model_config = ConfigDict(extra="forbid")

    outputs: dict[str, Any] = Field(default_factory=dict)
    realized_method_fqn: Optional[str] = None
    dispatch_consistent: bool = True
    dispatch_mismatch_reason: Optional[str] = None
    duration_ms: int = 0
    jvm_log: str = ""
    captured_anchors: list[AnchorHit] = Field(default_factory=list)
    captured_brs: list[BRTrigger] = Field(default_factory=list)


class SandboxCapabilities(BaseModel):
    """JavaSandbox 구현체 capabilities (spec 05 §2.4)."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["jvm_subprocess", "graalvm_polyglot", "stub"] = "stub"
    java_version: Optional[str] = None
    classpath_roots: list[str] = Field(default_factory=list)
    instrumentation_jar: Optional[str] = None
    max_heap_mb: int = 512
    max_concurrent_dispatches: int = 4


# ─── Lookup data source (spec 05 §3.2) ─────────────────────────────


class TableSpec(BaseModel):
    """lookup 가능한 CodeType 의 메타 (spec 05 §3.2).

    LookupDataSource 가 modeling 측 OntologyClient 의 list_code_types 결과로 derive.
    """

    model_config = ConfigDict(extra="forbid")

    code_type_fqn: str
    pk_atom_fqn: str
    columns: dict[str, str] = Field(default_factory=dict)
    """slot_name → atomic_fqn 매핑."""

    drama_dna_columns: list[str] = Field(default_factory=list)


class LookupRow(BaseModel):
    """scenario_fixture.lookups 의 한 row — atomic 슬롯 dict (spec 05 §3.2)."""

    model_config = ConfigDict(extra="forbid")

    pk: Any
    table_spec_fqn: str
    columns: dict[str, Any] = Field(default_factory=dict)


# ─── Failure policy (spec 05 §4.8) ─────────────────────────────────


class FailurePolicy(BaseModel):
    """dispatch loop 실패 시 정책 (spec 05 §4.8).

    21-step 회귀 / drama 시연 vs 운영 빠른 ping 의 정책 분리.
    """

    model_config = ConfigDict(extra="forbid")

    on_dispatch_error: Literal["fail_fast", "continue", "abort_after_n"] = "fail_fast"
    on_br_violation: Literal["continue", "fail_fast"] = "continue"
    on_anchor_miss: Literal["continue", "fail_fast"] = "continue"
    on_dispatch_inconsistent: Literal["continue", "fail_fast"] = "continue"


# ─── Run lifecycle (spec 03 §1.1) ─────────────────────────────────


class RunHandle(BaseModel):
    """spec 03 §1.1 — POST /api/simulation/runs 의 응답 + 상태 polling.

    상태 머신 (spec 05 §4.1):
        pending → running → {completed, failed, cancelled}
        pending → cancelled (시작 전 취소 허용)
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    created_at: str
    plan: Optional[RunPlan] = None
    """dry_run=True 면 채워짐 (코드 생성만, sandbox 안 부름). 그 외 None."""


__all__ = [
    "ChangeSpec",
    "RunOptions",
    "CreateRunRequest",
    "BREvidence",
    "AnchorEvidence",
    "DelegationTraceFrame",
    "SimResult",
    # Runner-side (STEP 3b)
    "TypedValue",
    "RunPlan",
    "RunInputs",
    "GeneratedScript",
    "AnchorHit",
    "BRTrigger",
    "DispatchResult",
    "SandboxCapabilities",
    "TableSpec",
    "LookupRow",
    "FailurePolicy",
    # Run lifecycle (STEP 3b-5)
    "RunHandle",
]
