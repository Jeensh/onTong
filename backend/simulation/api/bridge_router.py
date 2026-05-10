"""Phase 6-D — OntologyBridge API.

엔드포인트:
- GET  /api/simulation/bridge/terms                 등록된 도메인 용어 목록
- GET  /api/simulation/bridge/term/{term}/overlay   용어 → 영향 step + 추천 시나리오 + Section 2 ontology overlay
- GET  /api/simulation/bridge/step/{step_id}/terms  step → 영향 용어 (역방향)
- GET  /api/simulation/bridge/index                 전체 step ↔ term 인덱스
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agents.scenario_assistant import AssistRequest, assist
from ..client.ontology_client import OntologyClient
from ..ontology_bridge.bridge import OntologyBridge

router = APIRouter(prefix="/api/simulation/bridge", tags=["simulation-bridge"])

_bridge: OntologyBridge | None = None


def _get_bridge() -> OntologyBridge:
    global _bridge
    if _bridge is None:
        client = OntologyClient(in_process=True)
        _bridge = OntologyBridge(client=client)
    return _bridge


@router.get("/terms")
def list_terms():
    return {"items": OntologyBridge.all_terms(), "count": len(OntologyBridge.all_terms())}


@router.get("/term/{term}/overlay")
async def term_overlay(term: str):
    bridge = _get_bridge()
    return await bridge.overlay(term)


@router.get("/step/{step_id}/terms")
def step_terms(step_id: str):
    terms = OntologyBridge.step_to_terms(step_id)
    return {"step_id": step_id, "terms": terms, "count": len(terms)}


@router.get("/index")
def full_index():
    return {"step_to_terms": OntologyBridge.all_step_to_terms()}


# ─── Phase 7-B — AI 시나리오 어시스턴트 ────────────────────────────


class AssistPayload(BaseModel):
    natural_language: str = Field(..., min_length=1, max_length=500)
    prefer_llm: bool = True


@router.post("/assist")
async def assist_endpoint(payload: AssistPayload):
    """자연어 → ScenarioDraft (step_id + inputs + rationale + confidence + method)."""
    draft = await assist(AssistRequest(
        natural_language=payload.natural_language,
        prefer_llm=payload.prefer_llm,
    ))
    return draft.model_dump()
