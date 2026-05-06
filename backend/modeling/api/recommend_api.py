"""FastAPI router — /api/ontology/repos/{repo_id}/recommend — 자동 매핑 추천.

P3-3 — Code Layer 의 import 결과를 받아 BusinessTerm/Action/TypeRealization 후보를
생성한다. 결과는 read-only DTO 로 반환 (확정은 사용자가 큐 UI 에서). `persist=true` 면
domain/mapping store 에 `confirmed=False` 로 영속.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.modeling.code_layer.recommender import build_recommendations
from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer.store import MappingLayerStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-recommend"])


class TermCandidateDTO(BaseModel):
    suggested: dict[str, Any]
    derived_from_code_type_fqn: str
    confidence: float
    reason: str


class ActionCandidateDTO(BaseModel):
    suggested: dict[str, Any]
    derived_from_method_fqn: str
    confidence: float
    reason: str


class TypeRealizationCandidateDTO(BaseModel):
    suggested: dict[str, Any]
    confidence: float
    reason: str


class RecommendationResponse(BaseModel):
    repo_id: str
    summary: dict[str, int]
    persisted: bool
    persisted_counts: dict[str, int] = {}
    term_candidates: list[TermCandidateDTO]
    action_candidates: list[ActionCandidateDTO]
    type_realization_candidates: list[TypeRealizationCandidateDTO]


@router.post("/{repo_id}/recommend", response_model=RecommendationResponse)
def recommend(
    repo_id: str,
    persist: bool = Query(False, description="True 면 store 에 confirmed=False 로 영속"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
) -> RecommendationResponse:
    code_store = CodeLayerStore()
    types = code_store.list_types(repo_id=repo_id)
    if not types:
        raise HTTPException(
            status_code=404,
            detail=f"no CodeTypes for repo_id={repo_id} — run import 먼저",
        )

    result = build_recommendations(types, repo_id=repo_id)

    # filter by min_confidence + sort by confidence DESC
    terms = sorted(
        (c for c in result.term_candidates if c.confidence >= min_confidence),
        key=lambda c: -c.confidence,
    )
    actions = sorted(
        (c for c in result.action_candidates if c.confidence >= min_confidence),
        key=lambda c: -c.confidence,
    )
    realizations = sorted(
        (c for c in result.type_realization_candidates if c.confidence >= min_confidence),
        key=lambda c: -c.confidence,
    )

    persisted_counts: dict[str, int] = {}
    if persist:
        # domain: BusinessTerm
        dstore = DomainLayerStore()
        n_t = dstore.upsert_terms(repo_id, [c.suggested for c in terms])
        persisted_counts["terms"] = n_t

        # mapping: Action + TypeRealization
        mstore = MappingLayerStore()
        n_a = mstore.upsert_actions(repo_id, [c.suggested for c in actions])
        persisted_counts["actions"] = n_a
        n_r = mstore.upsert_type_realizations(repo_id, [c.suggested for c in realizations])
        persisted_counts["type_realizations"] = n_r

        logger.info(
            "recommend persisted: repo=%s terms=%d actions=%d realizations=%d",
            repo_id, n_t, n_a, n_r,
        )

    return RecommendationResponse(
        repo_id=repo_id,
        summary={
            "terms": len(terms),
            "actions": len(actions),
            "type_realizations": len(realizations),
        },
        persisted=persist,
        persisted_counts=persisted_counts,
        term_candidates=[
            TermCandidateDTO(
                suggested=c.suggested.model_dump(mode="json"),
                derived_from_code_type_fqn=c.derived_from_code_type_fqn,
                confidence=c.confidence,
                reason=c.reason,
            )
            for c in terms
        ],
        action_candidates=[
            ActionCandidateDTO(
                suggested=c.suggested.model_dump(mode="json"),
                derived_from_method_fqn=c.derived_from_method_fqn,
                confidence=c.confidence,
                reason=c.reason,
            )
            for c in actions
        ],
        type_realization_candidates=[
            TypeRealizationCandidateDTO(
                suggested=c.suggested.model_dump(mode="json"),
                confidence=c.confidence,
                reason=c.reason,
            )
            for c in realizations
        ],
    )
