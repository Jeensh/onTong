"""Orchestrator (spec 05 §4.5) — running 단계 entry.

ChangeSpec + RunPlan 을 받아 LookupDataSource + PythonGenerator + JavaSandbox 를
묶어 SimResult 를 빌드하는 단일 entry point.

echo-stub iteration (첫 iter):
- generated source_code 는 artifact (실제 dispatch 는 본 모듈이 직접)
- atomic_overrides 적용 미구현 (4-rule algorithm 은 후속)
- failure policy fail_fast (sandbox 예외 → status=failed)
- verdict 판정 (spec 04 §3.2 6 조건 단순화):
  * sim_verified : status=completed + 모든 BR passed + 모든 anchor hit + 모든 dispatch consistent
  * sim_violation: status=completed + BR (outcome=violated, severity=error) 1건 이상
  * inconclusive : 위 둘 외

후속 step (3b-5+) 보강:
- generated source_code 의 ast 기반 안전 실행 (현재는 직접 dispatch)
- timeout budget 분배 (spec 05 §4.7)
- failure policy 4가지 정책 (spec 05 §4.8)
- promote/downgrade hook (spec 04 §3.4)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol

from backend.shared.contracts.simulation import (
    AnchorEvidence,
    AnchorHit,
    BREvidence,
    BRTrigger,
    ChangeSpec,
    DelegationTraceFrame,
    DispatchResult,
    GeneratedScript,
    RunInputs,
    RunOptions,
    RunPlan,
    SimResult,
    TypedValue,
)

logger = logging.getLogger(__name__)


# ─── 의존성 — duck-typed Protocol ───────────────────────────────────


class _PythonGeneratorProtocol(Protocol):
    def generate(self, change_spec: ChangeSpec, run_plan: RunPlan) -> GeneratedScript: ...


class _JavaSandboxProtocol(Protocol):
    def dispatch(
        self, action_fqn: str, inputs: RunInputs, run_options: RunOptions
    ) -> DispatchResult: ...


class _LookupDataSourceProtocol(Protocol):
    def get(self, table_spec_fqn: str, pk: Any) -> Any: ...
    def list(self, table_spec_fqn: str) -> list[Any]: ...
    def validate(self) -> list[str]: ...


# ─── Orchestrator ───────────────────────────────────────────────────


class Orchestrator:
    """spec 05 §4.5 — running 단계 entry point.

    Constructor:
        python_generator       : PythonGenerator (또는 동일 Protocol 구현체)
        java_sandbox           : JavaSandbox 구현체 (StubJavaSandbox / 후속 jvm_subprocess)
        lookup_source_factory  : Callable[[fixture dict], LookupDataSource]
    """

    def __init__(
        self,
        python_generator: _PythonGeneratorProtocol,
        java_sandbox: _JavaSandboxProtocol,
        lookup_source_factory: Callable[[dict[str, Any]], _LookupDataSourceProtocol],
    ):
        self._gen = python_generator
        self._sandbox = java_sandbox
        self._lookup_factory = lookup_source_factory

    # ─── Public — run() entry ───────────────────────────────────

    def run(
        self,
        change_spec: ChangeSpec,
        run_plan: RunPlan,
        run_options: RunOptions,
    ) -> SimResult:
        """spec 05 §4.5 의 8 step 단순화 (echo-stub iter).

        Returns: SimResult — verdict / br_evidence / anchor_evidence / delegation_trace.
        """
        run_id = self._make_run_id()
        started_at = datetime.now(timezone.utc).isoformat()
        t_start = time.monotonic()

        # 1. lookup_source 생성
        lookup_source = self._lookup_factory(change_spec.scenario_fixture)

        # 2. generated script (artifact 용 — 직접 실행은 안 함)
        try:
            self._gen.generate(change_spec, run_plan)
        except Exception as exc:
            logger.warning("PythonGenerator.generate() 실패 — %s", exc)

        # 3. RunInputs 빌드 — echo-stub: empty slots, fixture 만 주입
        inputs = self._build_run_inputs(change_spec, run_plan, lookup_source)

        # 4. dispatch loop
        trace: list[DelegationTraceFrame] = []
        all_anchors: list[tuple[str, AnchorHit]] = []  # (action_fqn, hit)
        all_brs: list[BRTrigger] = []
        sandbox_error: Optional[str] = None

        for i, edge in enumerate(run_plan.delegates_to_tree, start=1):
            action_fqn = edge.get("action_fqn") if isinstance(edge, dict) else None
            depth = edge.get("depth", 0) if isinstance(edge, dict) else 0
            if action_fqn is None:
                logger.debug("delegation edge without action_fqn — skip")
                continue
            try:
                dr = self._sandbox.dispatch(action_fqn, inputs, run_options)
            except Exception as exc:
                logger.warning(
                    "JavaSandbox.dispatch(%s) raised — failure policy fail_fast",
                    action_fqn,
                )
                sandbox_error = f"sandbox crashed on {action_fqn}: {exc}"
                break

            trace.append(DelegationTraceFrame(
                seq=i,
                depth=depth,
                action_fqn=action_fqn,
                realized_method_fqn=dr.realized_method_fqn,
                dispatch_consistent=dr.dispatch_consistent,
                dispatch_mismatch_reason=dr.dispatch_mismatch_reason,
                duration_ms=dr.duration_ms,
            ))
            all_anchors.extend((action_fqn, h, dr.realized_method_fqn) for h in dr.captured_anchors)
            all_brs.extend(dr.captured_brs)
            # echo-stub: outputs={} 이므로 merge 의미 없음 — 후속 iter 보강

        # 5. evidence 매핑
        br_evidence = [self._br_trigger_to_evidence(t) for t in all_brs]
        anchor_evidence = [
            self._anchor_hit_to_evidence(action_fqn, hit, realized)
            for (action_fqn, hit, realized) in all_anchors
        ]

        # 6. verdict 판정 (spec 04 §3.2 단순화)
        if sandbox_error:
            status = "failed"
            verdict = "inconclusive"
            failure_reason = sandbox_error
        else:
            status = "completed"
            verdict = self._decide_verdict(trace, br_evidence, anchor_evidence)
            failure_reason = None

        completed_at = datetime.now(timezone.utc).isoformat()
        duration_ms = int((time.monotonic() - t_start) * 1000)

        return SimResult(
            run_id=run_id,
            status=status,
            verdict=verdict,
            br_evidence=br_evidence,
            anchor_evidence=anchor_evidence,
            output_values={},
            delegation_trace=trace,
            affected_design_gaps=[],
            failure_reason=failure_reason,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            change_spec_ref=self._compute_change_spec_ref(change_spec),
        )

    # ─── 내부 — 보조 메서드 ───────────────────────────────────────

    @staticmethod
    def _make_run_id() -> str:
        return f"run-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _compute_change_spec_ref(change_spec: ChangeSpec) -> str:
        """ChangeSpec hash — 재현 시 동일 입력 검증."""
        canonical = json.dumps(
            change_spec.model_dump(),
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"sha256:{digest[:16]}"

    @staticmethod
    def _build_run_inputs(
        change_spec: ChangeSpec,
        run_plan: RunPlan,
        lookup_source: _LookupDataSourceProtocol,
    ) -> RunInputs:
        """echo-stub 빌드 — primary_input_slot 은 첫 frame 의 primary_input_type 으로 추정.

        spec 05 §4.6 의 build_slots 알고리즘은 후속 iter (Action.params 분석 필요).
        본 iter 는 dispatch 자체가 stub 이므로 slots 비어있어도 OK.
        """
        primary_type: Optional[str] = None
        for edge in run_plan.delegates_to_tree:
            if isinstance(edge, dict):
                primary_type = edge.get("primary_input_type")
                if primary_type:
                    break

        slots: dict[str, TypedValue] = {}
        primary_slot: Optional[str] = None
        if primary_type:
            primary_slot = "primary"
            slots[primary_slot] = TypedValue(_type=primary_type, value={})

        return RunInputs(
            slots=slots,
            fixture=lookup_source,
            overrides=dict(change_spec.atomic_overrides),
            primary_input_slot=primary_slot,
        )

    @staticmethod
    def _br_trigger_to_evidence(trigger: BRTrigger) -> BREvidence:
        """BRTrigger → BREvidence 매핑 (severity 는 violated 만 'error', 그 외 'info')."""
        severity = "error" if trigger.outcome == "violated" else "info"
        return BREvidence(
            br_fqn=trigger.br_fqn,
            severity=severity,
            enforcer_method_fqn=trigger.enforcer_method_fqn,
            outcome=trigger.outcome,
            violation_path=trigger.violation_path,
            expected=trigger.expected,
            actual=trigger.actual,
            operational_history_refs=[],
        )

    @staticmethod
    def _anchor_hit_to_evidence(
        action_fqn: str,
        hit: AnchorHit,
        realized_method_fqn: Optional[str],
    ) -> AnchorEvidence:
        """AnchorHit → AnchorEvidence (method_fqn 은 realized 우선, 없으면 빈 문자열)."""
        return AnchorEvidence(
            anchor_id=hit.anchor_id,
            marker=hit.marker,
            method_fqn=realized_method_fqn or "",
            line=hit.line,
            outcome="hit",
            captured_value=hit.captured_value,
        )

    @staticmethod
    def _decide_verdict(
        trace: list[DelegationTraceFrame],
        br_evidence: list[BREvidence],
        anchor_evidence: list[AnchorEvidence],
    ) -> str:
        """spec 04 §3.2 6 조건 단순화 (echo-stub iter).

        - sim_violation: BR (outcome=violated, severity=error) 1건 이상
        - sim_verified : 모든 BR passed + 모든 anchor hit + 모든 frame dispatch_consistent
                        (vacuously true 도 OK — BR 0 + anchor 0 + consistent → sim_verified)
        - inconclusive : 위 둘 외
        """
        has_violation = any(
            b.outcome == "violated" and b.severity == "error" for b in br_evidence
        )
        if has_violation:
            return "sim_violation"

        all_brs_passed = all(b.outcome == "passed" for b in br_evidence)
        all_anchors_hit = all(a.outcome == "hit" for a in anchor_evidence)
        all_consistent = all(f.dispatch_consistent for f in trace)

        if all_brs_passed and all_anchors_hit and all_consistent:
            return "sim_verified"
        return "inconclusive"


__all__ = ["Orchestrator"]
