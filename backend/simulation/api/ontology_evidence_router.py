"""Ontology Evidence — SimResult 의 결과가 어느 ontology entity 에서 derive 됐는지 추적.

요구사항 2 (STEP 3f): Section 3 의 시뮬 결과가 ontology 모델링 (Section 2) 기반임을
사용자가 명시적으로 느낄 수 있게.

각 SimResult 항목 → ontology source 매핑:
- delegation_trace[i].action_fqn        → modeling.api.ontology_query.get_action(fqn) 결과
- delegation_trace[i].realized_method   → action.realizations[0].code_method_fqn
- br_evidence[i].br_fqn                 → action.preconditions / postconditions 매핑
- anchor_evidence[i].anchor_id          → ontology_client.get_anchor_bindings_for_action(action_fqn)

본 endpoint 는 RunHandle.run_id 로 SimResult 를 fetch 후, 각 evidence 항목별 ontology source
trace 반환. UI 가 "이 결과가 ontology 의 어디에서 나왔는지" 시각화 가능.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.simulation.api.run_handle import RunHandleStore
from backend.simulation.api.spec_router import (
    get_run_plan_builder,
    get_store,
    _build_default_ontology_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation", tags=["simulation-ontology-evidence"])


# ─── 응답 모델 ────────────────────────────────────────────────────


class OntologyTrace(BaseModel):
    """단일 evidence 항목의 ontology source trace."""

    model_config = ConfigDict(extra="forbid")

    evidence_kind: str  # "action" / "br" / "anchor" / "realized_method"
    evidence_id: str    # action_fqn / br_fqn / anchor_id / method_fqn
    ontology_source: str  # "Action" / "Action.preconditions" / "AnchorBinding" / "Realization"
    ontology_facade_call: str  # 어떤 facade 메서드로 derive 됐는지
    ontology_data: dict[str, Any] = Field(default_factory=dict)
    """fetched ontology entity 의 핵심 필드 (요약)."""

    explanation: str = ""
    """사람-친화 한국어 설명."""


class RunOntologyEvidence(BaseModel):
    """RunHandle.run_id 의 SimResult → ontology source 종합 trace."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    action_fqn: str
    ontology_facade: str = "backend.modeling.api.ontology_query.OntologyQueryClientImpl"
    ontology_transport: str = "in-process facade (HTTP 우회)"

    traces: list[OntologyTrace] = Field(default_factory=list)
    """각 evidence 항목별 ontology source trace."""

    summary: dict[str, int] = Field(default_factory=dict)
    """카테고리별 trace 수 — UI 가 카운트 표시."""


# ─── helper — SimResult / ChangeSpec → traces ────────────────────


def _trace_action(action_fqn: str, ont) -> OntologyTrace:
    """root action 의 ontology source — get_action(fqn)."""
    try:
        action = ont.get_action(action_fqn)
    except Exception as exc:
        return OntologyTrace(
            evidence_kind="action",
            evidence_id=action_fqn,
            ontology_source="Action",
            ontology_facade_call=f"get_action({action_fqn!r})",
            ontology_data={"error": str(exc)},
            explanation=f"❌ ontology 조회 실패: {exc}",
        )
    if action is None:
        return OntologyTrace(
            evidence_kind="action",
            evidence_id=action_fqn,
            ontology_source="Action",
            ontology_facade_call=f"get_action({action_fqn!r})",
            ontology_data={},
            explanation=f"⚠ ontology 에 등록 안 된 action — verdict 정합성 영향",
        )
    return OntologyTrace(
        evidence_kind="action",
        evidence_id=action_fqn,
        ontology_source="Action (mapping_layer.schema.Action)",
        ontology_facade_call=f"OntologyQueryClient.get_action({action_fqn!r})",
        ontology_data={
            "fqn": action.fqn,
            "kind": action.kind.value if hasattr(action.kind, "value") else str(action.kind),
            "label": getattr(action, "label", None),
            "declared_on_term": getattr(action, "declared_on_term", None),
            "sub_actions_count": len(getattr(action, "sub_actions", []) or []),
            "realizations_count": len(getattr(action, "realizations", []) or []),
        },
        explanation=(
            f"✅ Section 2 ontology 의 Action 노드 — "
            f"label={getattr(action, 'label', '?')!r}, "
            f"sub_actions={len(getattr(action, 'sub_actions', []) or [])}개, "
            f"realizations={len(getattr(action, 'realizations', []) or [])}개"
        ),
    )


def _trace_realized_method(action_fqn: str, method_fqn: str, ont) -> OntologyTrace:
    """realized_method_fqn 이 어느 Realization 에서 왔는지."""
    try:
        action = ont.get_action(action_fqn)
        if action is None:
            raise ValueError("action not found")
        match = next(
            (r for r in (getattr(action, "realizations", None) or [])
             if getattr(r, "code_method_fqn", None) == method_fqn),
            None,
        )
        if match is None:
            return OntologyTrace(
                evidence_kind="realized_method",
                evidence_id=method_fqn,
                ontology_source="Realization (mapping_layer.schema.Realization)",
                ontology_facade_call=f"action.realizations 안에서 검색",
                ontology_data={"action_fqn": action_fqn, "method_fqn": method_fqn},
                explanation=f"⚠ Action.realizations 에 매칭되는 entry 없음 — fallback dispatch 추정",
            )
        return OntologyTrace(
            evidence_kind="realized_method",
            evidence_id=method_fqn,
            ontology_source="Realization (mapping_layer.schema.Realization)",
            ontology_facade_call=f"OntologyQueryClient.get_action({action_fqn!r}).realizations",
            ontology_data={
                "code_method_fqn": match.code_method_fqn,
                "applies_to_code_type_fqn": getattr(match, "applies_to_code_type_fqn", None),
                "confirmed": getattr(match, "confirmed", False),
                "confidence": getattr(match, "confidence", 0.0),
                "scope": getattr(match, "scope", None) and (
                    match.scope.value if hasattr(match.scope, "value") else str(match.scope)
                ),
            },
            explanation=(
                f"✅ Realization → Java method `{method_fqn}` "
                f"(confirmed={getattr(match, 'confirmed', False)}, "
                f"confidence={getattr(match, 'confidence', 0.0):.2f})"
            ),
        )
    except Exception as exc:
        return OntologyTrace(
            evidence_kind="realized_method",
            evidence_id=method_fqn,
            ontology_source="Realization",
            ontology_facade_call="action.realizations",
            ontology_data={"error": str(exc)},
            explanation=f"❌ ontology trace 실패: {exc}",
        )


def _trace_br(action_fqn: str, br_fqn: str, ont) -> OntologyTrace:
    """BR fqn 이 Action.preconditions / postconditions 중 어느 쪽인지."""
    try:
        action = ont.get_action(action_fqn)
        if action is None:
            raise ValueError("action not found")
        pre = list(getattr(action, "preconditions", None) or [])
        post = list(getattr(action, "postconditions", None) or [])
        if br_fqn in pre:
            kind = "precondition"
        elif br_fqn in post:
            kind = "postcondition"
        else:
            kind = "(unknown — Action 에 없음, transitive 또는 다른 source)"
        return OntologyTrace(
            evidence_kind="br",
            evidence_id=br_fqn,
            ontology_source=f"Action.{kind}",
            ontology_facade_call=f"get_action({action_fqn!r}).preconditions/postconditions",
            ontology_data={
                "br_fqn": br_fqn,
                "kind": kind,
                "action_fqn": action_fqn,
            },
            explanation=f"✅ BusinessRule {br_fqn!r} — Action.{kind} 로 enumerate",
        )
    except Exception as exc:
        return OntologyTrace(
            evidence_kind="br",
            evidence_id=br_fqn,
            ontology_source="Action.{pre,post}conditions",
            ontology_facade_call="get_action(...).preconditions/postconditions",
            ontology_data={"error": str(exc)},
            explanation=f"❌ ontology trace 실패: {exc}",
        )


def _trace_anchor(action_fqn: str, anchor_id: str, ont) -> OntologyTrace:
    """anchor_id 가 어느 AnchorBinding 인지."""
    try:
        bindings = ont.get_anchor_bindings_for_action(action_fqn) or []
        match = next(
            (b for b in bindings if getattr(b, "id", None) == anchor_id),
            None,
        )
        if match is None:
            return OntologyTrace(
                evidence_kind="anchor",
                evidence_id=anchor_id,
                ontology_source="AnchorBinding",
                ontology_facade_call=f"get_anchor_bindings_for_action({action_fqn!r})",
                ontology_data={"anchor_id": anchor_id},
                explanation=f"⚠ anchor_id 가 binding 목록에 없음 — sub-action 의 anchor 추정",
            )
        return OntologyTrace(
            evidence_kind="anchor",
            evidence_id=anchor_id,
            ontology_source="AnchorBinding (mapping_layer.schema.AnchorBinding)",
            ontology_facade_call=f"OntologyQueryClient.get_anchor_bindings_for_action({action_fqn!r})",
            ontology_data={
                "id": match.id,
                "anchor_locator": getattr(match, "anchor_locator", None),
                "code_method_fqn": getattr(match, "code_method_fqn", None),
                "target_action_fqn": getattr(match, "target_action_fqn", None),
                "target_slot": getattr(match, "target_slot", None),
                "confirmed": getattr(match, "confirmed", False),
            },
            explanation=(
                f"✅ AnchorBinding {anchor_id!r} — "
                f"locator={getattr(match, 'anchor_locator', '?')!r} "
                f"on method `{getattr(match, 'code_method_fqn', '?')}`"
            ),
        )
    except Exception as exc:
        return OntologyTrace(
            evidence_kind="anchor",
            evidence_id=anchor_id,
            ontology_source="AnchorBinding",
            ontology_facade_call="get_anchor_bindings_for_action",
            ontology_data={"error": str(exc)},
            explanation=f"❌ ontology trace 실패: {exc}",
        )


# ─── Endpoint ─────────────────────────────────────────────────────


def _get_ontology_client():
    """spec_router 와 같은 ontology singleton 공유."""
    from backend.simulation.api import spec_router as sr
    if sr._ontology_client is None:
        sr._ontology_client = _build_default_ontology_client()
    return sr._ontology_client


@router.get("/runs/{run_id}/ontology-evidence", response_model=RunOntologyEvidence)
def get_ontology_evidence(
    run_id: str,
    store: RunHandleStore = Depends(get_store),
) -> RunOntologyEvidence:
    """SimResult 의 모든 evidence 항목 → ontology source trace.

    GET /api/simulation/runs/{run_id}/ontology-evidence

    각 항목별로:
    - 어느 ontology entity 에서 derive 됐는지 (Action / Realization / BR / AnchorBinding)
    - 어떤 facade 메서드로 fetch 했는지 (예: get_action / get_anchor_bindings_for_action)
    - ontology entity 의 핵심 필드 요약
    - 사람-친화 한국어 설명

    UI 가 이 응답을 받아 SimResult 옆에 "ontology 근거" 토글로 표시.
    """
    handle = store.get(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")
    sim_result = store.get_sim_result(run_id)
    if sim_result is None:
        raise HTTPException(
            status_code=404,
            detail=f"sim_result for {run_id!r} not available — status={handle.status}",
        )
    change_spec = store.get_change_spec(run_id)
    if change_spec is None:
        raise HTTPException(
            status_code=404,
            detail=f"change_spec for {run_id!r} not found",
        )

    ont = _get_ontology_client()
    traces: list[OntologyTrace] = []

    # 1. root action
    traces.append(_trace_action(change_spec.action_fqn, ont))

    # 2. delegation_trace 의 각 frame 의 realized_method
    for frame in sim_result.delegation_trace:
        if frame.realized_method_fqn:
            traces.append(_trace_realized_method(
                frame.action_fqn, frame.realized_method_fqn, ont
            ))

    # 3. br_evidence
    for br_ev in sim_result.br_evidence:
        traces.append(_trace_br(change_spec.action_fqn, br_ev.br_fqn, ont))

    # 4. anchor_evidence
    for an_ev in sim_result.anchor_evidence:
        # anchor 는 어느 frame 의 action 에서 왔는지 알 수 없음 (현재 SimResult 에 frame 매핑 없음)
        # → root action 으로 시도, 매칭 안 되면 sub-action 추정 안내
        traces.append(_trace_anchor(change_spec.action_fqn, an_ev.anchor_id, ont))

    # 카테고리별 카운트
    summary: dict[str, int] = {}
    for t in traces:
        summary[t.evidence_kind] = summary.get(t.evidence_kind, 0) + 1

    return RunOntologyEvidence(
        run_id=run_id,
        action_fqn=change_spec.action_fqn,
        traces=traces,
        summary=summary,
    )


@router.get("/ontology-evidence/by-action", response_model=RunOntologyEvidence)
def get_ontology_evidence_by_action(action_fqn: str) -> RunOntologyEvidence:
    """run_id 없이 action_fqn 만으로 ontology evidence 조회.

    GET /api/simulation/ontology-evidence/by-action?action_fqn=...

    SandboxPanel / JavaPythonComparePanel / NavigatorPanel 같은 곳에서 spec 03 run 을
    트리거하지 않고도 "이 기능이 ontology 의 어떤 entity 와 연결되어 있는지" 를
    사용자에게 즉시 보여주기 위한 lightweight endpoint.

    response 의 run_id 는 빈 문자열, traces 는 action / realizations / preconditions /
    postconditions / anchor_bindings 를 ontology 에서 직접 enumerate.
    """
    ont = _get_ontology_client()
    traces: list[OntologyTrace] = []

    # 1. root action
    traces.append(_trace_action(action_fqn, ont))

    # 2. realizations — action.realizations 의 각 method
    try:
        action = ont.get_action(action_fqn)
    except Exception:
        action = None

    if action is not None:
        for r in (getattr(action, "realizations", None) or []):
            method_fqn = getattr(r, "code_method_fqn", None)
            if method_fqn:
                traces.append(_trace_realized_method(action_fqn, method_fqn, ont))

        # 3. preconditions / postconditions
        for br in (getattr(action, "preconditions", None) or []):
            traces.append(_trace_br(action_fqn, br, ont))
        for br in (getattr(action, "postconditions", None) or []):
            traces.append(_trace_br(action_fqn, br, ont))

    # 4. anchor bindings
    try:
        bindings = ont.get_anchor_bindings_for_action(action_fqn) or []
    except Exception:
        bindings = []
    for b in bindings:
        anchor_id = getattr(b, "id", None)
        if anchor_id:
            traces.append(_trace_anchor(action_fqn, anchor_id, ont))

    summary: dict[str, int] = {}
    for t in traces:
        summary[t.evidence_kind] = summary.get(t.evidence_kind, 0) + 1

    return RunOntologyEvidence(
        run_id="",
        action_fqn=action_fqn,
        traces=traces,
        summary=summary,
    )


__all__ = ["router"]
