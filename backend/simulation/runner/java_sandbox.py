"""JavaSandbox Protocol + StubJavaSandbox (spec 05 §2 + §3.4.5).

스시뮬 dispatch loop 가 호출하는 Java sandbox 의 추상 인터페이스 (Protocol) 와
3-tier 중 가장 가벼운 stub 구현체.

stub backend 합의 (spec 05 §3.4.5):
- 모든 expected_anchors 가 자동 hit (verdict=sim_verified 가능)
- 모든 BR (Action.preconditions + postconditions) 자동 passed
- outputs={} (scenario.expected_outputs echo 는 후속 iteration)
- duration_ms=0, jvm_log='[stub mode]\\n'

stub 의 검증 한계 — Java code 호출 안 함. 코드 변경의 실제 효과 검증 불가.
운영 promote 결정에는 jvm_subprocess / graalvm tier 필요.

본 모듈은 modeling internal layer 직접 import 금지 — duck-typed Protocol 만 사용.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol, runtime_checkable

from backend.shared.contracts.simulation import (
    AnchorHit,
    BRTrigger,
    DispatchResult,
    RunInputs,
    RunOptions,
    SandboxCapabilities,
)

logger = logging.getLogger(__name__)


# ─── 의존성 — modeling facade duck-typed Protocol ───────────────────


class _OntologyClientProtocol(Protocol):
    """StubJavaSandbox 가 의존하는 ontology facade 의 최소 인터페이스.

    실제 구현은 modeling 측 OntologyQueryClientImpl. 본 Protocol 은 duck-typed —
    아래 3 메서드만 사용 (spec 05 §7.1).
    """

    def get_action(self, fqn: str) -> Any: ...

    def get_realizations_for_input_type(
        self, action_fqn: str, code_type_fqn: str
    ) -> list[Any]: ...

    def get_anchor_bindings_for_action(self, action_fqn: str) -> list[Any]: ...


# ─── JavaSandbox Protocol (spec 05 §2.2) ──────────────────────────


@runtime_checkable
class JavaSandbox(Protocol):
    """Java dispatch sandbox 의 추상 인터페이스 (spec 05 §2.2).

    3-tier 구현체: StubJavaSandbox / JvmSubprocessSandbox / GraalvmSandbox.
    공통 dispatch() 시그니처를 통해 swap 가능.
    """

    def dispatch(
        self,
        action_fqn: str,
        inputs: RunInputs,
        run_options: RunOptions,
    ) -> DispatchResult: ...


# ─── StubJavaSandbox (spec 05 §2.5 + §3.4.5) ──────────────────────


class StubJavaSandbox:
    """Java code 실행 없이 dispatch 결과를 합성하는 stub backend.

    용도:
    - 단위 test (orchestrator / verdict 판정 회로 검증)
    - dev 시연 (UI 동작 확인)
    - regression 의 sim_verified 빠른 확인

    검증 한계:
    - 실제 Java method 호출 안 함 → 코드 변경 효과 검증 불가
    - BR violation 회귀 (P-2018-0098) 는 jvm_subprocess / graalvm 으로만
    """

    _STUB_LOG = "[stub mode]\n"

    def __init__(
        self,
        capabilities: SandboxCapabilities,
        ontology_client: _OntologyClientProtocol,
    ):
        if capabilities.backend != "stub":
            raise ValueError(
                f"StubJavaSandbox 는 SandboxCapabilities.backend='stub' 만 받음 — "
                f"got {capabilities.backend!r}. jvm_subprocess / graalvm tier 는 "
                f"별도 클래스 (spec 05 §2.5)."
            )
        self._cap = capabilities
        self._ont = ontology_client

    def dispatch(
        self,
        action_fqn: str,
        inputs: RunInputs,
        run_options: RunOptions,
    ) -> DispatchResult:
        """spec 05 §3.4.5 stub 정책에 따라 합성 결과 반환.

        Step:
          1. primary_input slot 의 _type 으로 realization 조회
          2. dispatch_consistent / realized_method 결정
          3. anchor binding 모두 자동 hit
          4. Action.preconditions+postconditions 모두 BR passed
          5. outputs={} (echo 는 후속 iteration)
        """
        realized_method, consistent, mismatch_reason = self._select_realization(
            action_fqn, inputs
        )
        captured_anchors = self._capture_anchors(action_fqn)
        captured_brs = self._capture_brs(action_fqn)

        return DispatchResult(
            outputs={},
            realized_method_fqn=realized_method,
            dispatch_consistent=consistent,
            dispatch_mismatch_reason=mismatch_reason,
            duration_ms=0,
            jvm_log=self._STUB_LOG,
            captured_anchors=captured_anchors,
            captured_brs=captured_brs,
        )

    # ─── 내부 — realization 선택 (spec 05 §2.3 step 1~3 단순화) ──

    def _select_realization(
        self, action_fqn: str, inputs: RunInputs
    ) -> tuple[Optional[str], bool, Optional[str]]:
        """Returns (realized_method_fqn, dispatch_consistent, mismatch_reason).

        stub 단순화 (실 ontology 호환 fallback 포함):
        - primary_input_slot 있음 + realizations 매칭 → consistent=True, 첫 번째 선택
        - primary_input_slot 있음 + realizations 0건 → action.realizations[0] fallback
          (modeling 의 applies_to=None base 처리. fallback 시 consistent=True 유지)
        - primary_input_slot 없음 → action.realizations[0] fallback (object_ref 미참조 action)
        - 모든 fallback 실패 → consistent=False, mismatch_reason 채움
        """
        slot = inputs.primary_input_slot
        primary_type: Optional[str] = None

        if slot is not None:
            typed_value = inputs.slots.get(slot)
            if typed_value is None:
                return (
                    None,
                    False,
                    f"primary_input slot '{slot}' not present in RunInputs.slots",
                )
            primary_type = typed_value.type_

            try:
                realizations = self._ont.get_realizations_for_input_type(
                    action_fqn, primary_type
                )
            except Exception as exc:
                logger.warning(
                    "get_realizations_for_input_type(%s, %s) 실패 — %s",
                    action_fqn, primary_type, exc,
                )
                realizations = []

            if realizations:
                selected = realizations[0]
                method_fqn = getattr(selected, "code_method_fqn", None)
                if method_fqn:
                    return (method_fqn, True, None)

        # fallback — action.realizations[0]
        # (primary_input 미상이거나 type-별 realization 없는 경우)
        try:
            action = self._ont.get_action(action_fqn)
        except Exception as exc:
            logger.warning("get_action(%s) 실패 — %s", action_fqn, exc)
            action = None

        if action is not None:
            for r in (getattr(action, "realizations", None) or []):
                method_fqn = getattr(r, "code_method_fqn", None)
                if method_fqn:
                    # fallback 도 consistent=True (stub 의 보수적 처리)
                    return (method_fqn, True, None)

        # 진짜 fallback 도 없음
        if primary_type is None:
            return (
                None,
                False,
                "primary_input slot not declared and action has no realizations",
            )
        return (
            None,
            False,
            f"no realization for input type {primary_type!r} on action {action_fqn!r}",
        )

    # legacy — 본 메서드는 fallback 으로 통합돼 더 이상 별도로 호출되지 않음
    def _select_realization_legacy(
        self, action_fqn: str, inputs: RunInputs
    ) -> tuple[Optional[str], bool, Optional[str]]:
        """이전 echo-stub 의 strict 셀렉터 — 호환성 위해 보존 (호출 안 함).

        primary_input_slot 없음 → 즉시 inconsistent.
        새 _select_realization 가 fallback 추가로 대체.
        """
        slot = inputs.primary_input_slot
        if slot is None:
            return (None, False, "primary_input slot not declared")
        typed_value = inputs.slots.get(slot)
        if typed_value is None:
            return (None, False, f"primary_input slot {slot!r} not in RunInputs.slots")
        primary_type = typed_value.type_
        try:
            realizations = self._ont.get_realizations_for_input_type(action_fqn, primary_type)
        except Exception:
            realizations = []
        if not realizations:
            return (None, False, f"no realization for {primary_type!r} on {action_fqn!r}")
        selected = realizations[0]
        method_fqn = getattr(selected, "code_method_fqn", None)
        if method_fqn is None:
            return (
                None,
                False,
                f"realization for {action_fqn} missing code_method_fqn attribute",
            )
        return (method_fqn, True, None)

    # ─── 내부 — anchor auto-hit (spec 05 §3.4.5 step 3) ─────────

    def _capture_anchors(self, action_fqn: str) -> list[AnchorHit]:
        try:
            bindings = self._ont.get_anchor_bindings_for_action(action_fqn) or []
        except Exception as exc:
            logger.warning(
                "get_anchor_bindings_for_action(%s) 실패 — %s",
                action_fqn, exc,
            )
            return []

        hits: list[AnchorHit] = []
        for b in bindings:
            anchor_id = getattr(b, "id", None) or getattr(b, "anchor_id", None)
            if anchor_id is None:
                logger.debug("anchor binding without id/anchor_id — skip")
                continue
            marker = getattr(b, "anchor_locator", None) or getattr(b, "marker", "")
            line = getattr(b, "line", 0)
            hits.append(AnchorHit(
                anchor_id=anchor_id,
                marker=marker,
                line=line,
                captured_value=None,  # stub 은 runtime 값 없음
            ))
        return hits

    # ─── 내부 — BR auto-pass (spec 05 §3.4.5 step 4) ────────────

    def _capture_brs(self, action_fqn: str) -> list[BRTrigger]:
        """Action.preconditions + postconditions 의 BR fqn 모두 passed 로 변환.

        spec 05 §3.4.5 의 br_violation 시나리오 처리는 후속 iteration —
        stub 첫 iter 는 모두 passed.
        """
        try:
            action = self._ont.get_action(action_fqn)
        except Exception as exc:
            logger.warning("get_action(%s) 실패 — %s", action_fqn, exc)
            return []
        if action is None:
            return []

        preconditions = list(getattr(action, "preconditions", None) or [])
        postconditions = list(getattr(action, "postconditions", None) or [])
        all_brs = preconditions + postconditions

        return [
            BRTrigger(
                br_fqn=br_fqn,
                enforcer_method_fqn=None,
                outcome="passed",
                violation_path=None,
                expected=None,
                actual=None,
            )
            for br_fqn in all_brs
        ]


__all__ = ["JavaSandbox", "StubJavaSandbox"]
