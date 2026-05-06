"""VerificationLevel 자동 계산 (시뮬 신뢰도 calibration, v5 §1.2).

상태 진척:
- UNMAPPED         : Realization 0 (Action 후보만 있음)
- DRAFT            : Realization >=1, but params/output 미확정 또는 confirmed=False
- SIGNATURE_LOCKED : 모든 ActionParam.confirmed = True, output 정의 OK, primary realization confirmed
- BODY_ANCHORED    : 추가 조건 — anchors 모두 confirmed
- SIM_VERIFIED     : 외부 신호 — 시뮬 1회 이상 통과 (Simulation Agent 가 갱신)
- PR_PROVEN        : 외부 신호 — draft PR 만들어진 적 (PR Agent 가 갱신)

이 함수는 SIGNATURE_LOCKED / BODY_ANCHORED 까지 자동 계산. SIM/PR 은 외부 입력으로 받음.
"""
from __future__ import annotations

from typing import Iterable

from backend.modeling.mapping_layer.schema import (
    Action,
    AnchorBinding,
    Realization,
    RealizationScope,
    VerificationLevel,
)


def compute_verification_level(
    action: Action,
    *,
    anchor_bindings: Iterable[AnchorBinding] = (),
    sim_passed: bool = False,
    pr_proven: bool = False,
) -> VerificationLevel:
    """Action 의 verification level 자동 계산.

    sim_passed/pr_proven 는 외부 신호 (Simulation Agent 등) 가 주입.
    """
    # PR_PROVEN — 가장 높음
    if pr_proven:
        return VerificationLevel.PR_PROVEN

    # 1. Realization 없음 → UNMAPPED (workflow 는 sub_actions 로 대체 가능)
    has_primary = any(
        r.scope == RealizationScope.PRIMARY for r in action.realizations
    )
    has_workflow_subs = bool(action.sub_actions) and action.kind.value == "workflow"
    if not has_primary and not has_workflow_subs:
        return VerificationLevel.UNMAPPED

    # 2. SIGNATURE_LOCKED 조건
    #    - 모든 params confirmed (params 가 0 인 case 도 OK — 무인자 함수)
    #    - primary realization 중 최소 1개 confirmed
    params_locked = all(p.confirmed for p in action.params)
    primary_confirmed = any(
        r.scope == RealizationScope.PRIMARY and r.confirmed
        for r in action.realizations
    )
    if not (params_locked and (primary_confirmed or has_workflow_subs)):
        return VerificationLevel.DRAFT

    # 3. BODY_ANCHORED — anchor binding 모두 confirmed
    abs_list = list(anchor_bindings)
    body_anchored = bool(abs_list) and all(ab.confirmed for ab in abs_list)
    if not body_anchored:
        return VerificationLevel.SIGNATURE_LOCKED

    # 4. SIM_VERIFIED — 외부 신호
    if sim_passed:
        return VerificationLevel.SIM_VERIFIED

    return VerificationLevel.BODY_ANCHORED


def can_simulate(level: VerificationLevel) -> bool:
    """Q8=A Strict gate — SIGNATURE_LOCKED 이상이어야 시뮬 가능."""
    order = [
        VerificationLevel.UNMAPPED,
        VerificationLevel.DRAFT,
        VerificationLevel.SIGNATURE_LOCKED,
        VerificationLevel.BODY_ANCHORED,
        VerificationLevel.SIM_VERIFIED,
        VerificationLevel.PR_PROVEN,
    ]
    return order.index(level) >= order.index(VerificationLevel.SIGNATURE_LOCKED)


__all__ = ("compute_verification_level", "can_simulate")
