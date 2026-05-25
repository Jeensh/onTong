"""Phase 2 Step 4c — Gate III impact handler.

selected ActionRef → ontology.caller_graph + sim_v2.quick_diagnose →
`GateExecutedImpact` payload.

Gate II 를 skip 한 impact 분기 (spec v2 §2 state machine):
target_selected → executed (impact)

Q5 비전: caller_graph 가 비어있을 수 있음 (sec2 API 미제공 / sim_v2 데이터 부재).
그래도 sim_v2.quick_diagnose 결과만으로도 surface 가능 ("빠진 내용은 빠진대로").
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .ontology_client import OntologyClient
from .schemas import (
    ActionRef,
    AffectedMethod,
    Finding,
    GateExecutedImpact,
    Provenance,
)
from .tools import call_ontology_get_caller_graph, call_sim_v2_quick_diagnose

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


async def build_gate_iii_impact(
    *,
    target: ActionRef,
    repo_id: str,
    ontology_client: OntologyClient,
) -> GateExecutedImpact:
    """Gate III impact 결과 = `GateExecutedImpact` payload.

    Pipeline (병렬):
      1) caller_graph = ontology.get_caller_graph(target.code_method_fqn)
      2) action = sim_v2.load_action(target.action_id)
      3) diagnose = sim_v2.quick_diagnose_action(action) (action 있으면)
    """
    caller_task = call_ontology_get_caller_graph(
        ontology_client,
        method_fqn=target.code_method_fqn,
        repo_id=repo_id,
    )
    action_task = _load_action_async(
        action_fqn=target.action_id, repo_id=repo_id,
    )
    caller_result, action = await asyncio.gather(caller_task, action_task)
    affected_methods: list[AffectedMethod] = list(caller_result.data or [])

    diagnose: dict[str, Any] | None = None
    diagnose_prov: Provenance | None = None
    if action is not None:
        diagnose_result = await call_sim_v2_quick_diagnose(action=action)
        diagnose = diagnose_result.data
        diagnose_prov = diagnose_result.provenance

    findings = _diagnose_to_findings(diagnose)
    confidence = _impact_confidence(diagnose, caller_count=len(affected_methods))

    sources: list[Provenance] = [caller_result.provenance]
    if diagnose_prov is not None:
        sources.append(diagnose_prov)
    if action is None:
        sources.append(Provenance(
            source="sim_v2",
            detail=f"load_action({target.action_id!r}) returned None — diagnose skipped",
            confidence=0.0,
        ))

    return GateExecutedImpact(
        affected_methods=affected_methods,
        sim_v2_findings=findings,
        confidence=confidence,
        sources=sources,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


async def _load_action_async(*, action_fqn: str, repo_id: str):
    from backend.section3 import sim_v2_bridge as sb

    def _run():
        s = sb.open_sim_v2_session()
        if s is None:
            return None
        try:
            return sb.load_action(s, action_fqn, repo_id)
        finally:
            s.close()

    return await asyncio.to_thread(_run)


def _diagnose_to_findings(
    diagnose: dict[str, Any] | None,
) -> list[Finding]:
    """quick_diagnose_action dict → Finding list.

    dict shape: {"ok", "fixtures", "stubs", "passing", "primary_failure"}
    """
    if diagnose is None:
        return [Finding(
            kind="diagnose_skipped",
            severity="warn",
            message="action 못 찾아 sim_v2 진단을 실행하지 않음",
        )]

    ok = bool(diagnose.get("ok"))
    fixtures = int(diagnose.get("fixtures", 0))
    passing = int(diagnose.get("passing", 0))
    stubs = int(diagnose.get("stubs", 0))
    primary = str(diagnose.get("primary_failure", "")).strip()

    findings: list[Finding] = []
    if ok and fixtures > 0:
        findings.append(Finding(
            kind="quick_diagnose_passing",
            severity="info",
            message=f"{passing}/{fixtures} fixtures pass · {stubs} stubs",
        ))
    else:
        findings.append(Finding(
            kind="quick_diagnose_blocked",
            severity="warn" if fixtures > 0 else "error",
            message=(
                primary or "quick_diagnose 가 결과를 내지 못함"
            ),
        ))
        if primary:
            findings.append(Finding(
                kind="primary_failure",
                severity="warn",
                message=primary,
            ))
    return findings


def _impact_confidence(
    diagnose: dict[str, Any] | None,
    *,
    caller_count: int,
) -> float:
    """ok + passing/fixtures + caller_count 기반 (Phase 12 — caller_count aware).

    - ok=True + fixtures>0 + caller_count>0: 0.8 + 0.2 * (passing/fixtures) → 0.8~1.0
    - ok=True + fixtures>0 + caller_count=0: 0.3 + 0.2 * (passing/fixtures) → 0.3~0.5
       (caller 정보 부재 시 "변경 안전" 으로 오해 못 하게 cap)
    - ok=False: 0.2 + 0.2 if caller_count>0 → 0.2~0.4
    - diagnose=None: 0.3
    """
    if diagnose is None:
        return 0.3
    fixtures = int(diagnose.get("fixtures", 0))
    passing = int(diagnose.get("passing", 0))
    if bool(diagnose.get("ok")) and fixtures > 0:
        ratio = passing / fixtures
        if caller_count > 0:
            return round(0.8 + 0.2 * ratio, 3)
        # caller graph 없음 → diagnostic 만으로는 "안전" 결론 불가
        return round(0.3 + 0.2 * ratio, 3)
    # blocked
    base = 0.2
    if caller_count > 0:
        base += 0.2  # caller graph 가 있으면 정보 부족해도 그래도 surface
    return round(base, 3)


__all__ = ["build_gate_iii_impact"]
