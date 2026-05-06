"""FastAPI router — /api/ontology/* — Ontology Query API REST 노출.

Agent 가 HTTP 로 호출하거나 (다른 프로세스), Workbench UI 가 사용.
같은 의미를 Python facade (OntologyQueryClientImpl) 와 REST 가 둘 다 제공.

OpenAPI spec 자동 생성 — http://host/docs.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.modeling.api.ontology_query import OntologyQueryClientImpl
from backend.shared.contracts.ontology_query import (
    ActionDTO, AmbiguousCallSiteDTO, AnchorBindingDTO, CallSiteDTO,
    CodeTypeDTO, CompositionDTO, RealizationDTO, SearchHitDTO,
    TermDTO, UnmappedMethodDTO, VerificationLevel, VerificationProgressDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology", tags=["ontology"])

# 모듈 레벨 client (싱글톤). main.py 가 init() 으로 교체 가능.
_client: OntologyQueryClientImpl | None = None


def init(client: OntologyQueryClientImpl | None = None) -> None:
    global _client
    _client = client or OntologyQueryClientImpl()
    logger.info("ontology_router init OK")


def _q() -> OntologyQueryClientImpl:
    if _client is None:
        # auto init for dev/test
        init()
    assert _client is not None
    return _client


# 라우트 등록 순서 주의: catchall path ({fqn:path}) 보다 specific endpoint 가 먼저 와야 함.
# FastAPI 는 등록 순서대로 매칭하므로 list / queue 류를 먼저 두고, 마지막에 catchall.

# ---------------------------------------------------------------------------
# Term — list 먼저, 그 후 catchall
# ---------------------------------------------------------------------------
@router.get("/terms", response_model=list[TermDTO])
def list_terms(
    repo_id: str | None = Query(None),
    kind: str | None = Query(None, pattern="^(atomic|composite)$"),
    domain: str | None = Query(None),
) -> list[TermDTO]:
    return _q().list_terms(repo_id=repo_id, kind=kind, domain=domain)


# ---------------------------------------------------------------------------
# Code — list 먼저
# ---------------------------------------------------------------------------
@router.get("/code-types", response_model=list[CodeTypeDTO])
def list_code_types(
    repo_id: str | None = Query(None),
    kind: str | None = Query(None),
    role: str | None = Query(None),
) -> list[CodeTypeDTO]:
    return _q().list_code_types(repo_id=repo_id, kind=kind, role=role)


# ---------------------------------------------------------------------------
# Action — list 먼저
# ---------------------------------------------------------------------------
@router.get("/actions", response_model=list[ActionDTO])
def list_actions(
    repo_id: str | None = Query(None),
    kind: str | None = Query(None, pattern="^(pure_function|effectful|workflow)$"),
    declared_on_term: str | None = Query(None),
    verification_min: VerificationLevel | None = Query(None),
) -> list[ActionDTO]:
    return _q().list_actions(
        repo_id=repo_id, kind=kind,
        declared_on_term=declared_on_term, verification_min=verification_min,
    )


# ---------------------------------------------------------------------------
# Term/Action specific suffix endpoints — catchall 보다 먼저!
# ---------------------------------------------------------------------------
@router.get("/terms/{term_fqn}/effective-parts", response_model=list[CompositionDTO])
def effective_parts(term_fqn: str, repo_id: str | None = None) -> list[CompositionDTO]:
    return _q().effective_parts(term_fqn, repo_id=repo_id)


@router.get("/code-methods/{caller_method_fqn}/call-sites",
            response_model=list[CallSiteDTO])
def get_call_sites(caller_method_fqn: str) -> list[CallSiteDTO]:
    return _q().get_call_sites(caller_method_fqn)


@router.get("/actions/{action_fqn}/realizations-for-input",
            response_model=list[RealizationDTO])
def get_realizations_for_input_type(
    action_fqn: str,
    code_type_fqn: str = Query(..., description="input 의 runtime CodeType fqn"),
) -> list[RealizationDTO]:
    return _q().get_realizations_for_input_type(action_fqn, code_type_fqn)


@router.get("/actions/{action_fqn}/resolve-path", response_model=dict[str, Any])
def resolve_path(
    action_fqn: str,
    slot_path: str = Query(..., description="path syntax (params[0]<X>.spec.y)"),
    repo_id: str | None = Query(None),
) -> dict[str, Any]:
    ok, last, err = _q().resolve_path(action_fqn, slot_path, repo_id=repo_id)
    return {"ok": ok, "last_term_fqn": last, "error": err}


@router.get("/actions/{action_fqn}/anchor-bindings",
            response_model=list[AnchorBindingDTO])
def get_anchor_bindings_for_action(action_fqn: str) -> list[AnchorBindingDTO]:
    return _q().get_anchor_bindings_for_action(action_fqn)


@router.get("/code-methods/{code_method_fqn}/anchor-bindings",
            response_model=list[AnchorBindingDTO])
def get_anchor_bindings_for_method(code_method_fqn: str) -> list[AnchorBindingDTO]:
    return _q().get_anchor_bindings_for_method(code_method_fqn)


# ---------------------------------------------------------------------------
# Catchall — get_by_fqn (마지막)
# ---------------------------------------------------------------------------
@router.get("/terms/{fqn}", response_model=TermDTO | None)
def get_term(fqn: str) -> TermDTO | None:
    return _q().get_term(fqn)


@router.get("/code-types/{fqn}", response_model=CodeTypeDTO | None)
def get_code_type(fqn: str) -> CodeTypeDTO | None:
    return _q().get_code_type(fqn)


@router.get("/actions/{fqn}", response_model=ActionDTO | None)
def get_action(fqn: str) -> ActionDTO | None:
    return _q().get_action(fqn)


# ---------------------------------------------------------------------------
# Mapping queue
# ---------------------------------------------------------------------------
@router.get("/queue/unmapped-methods", response_model=list[UnmappedMethodDTO])
def list_unmapped_methods(repo_id: str | None = Query(None)) -> list[UnmappedMethodDTO]:
    return _q().list_unmapped_methods(repo_id=repo_id)


@router.get("/queue/ambiguous-call-sites", response_model=list[AmbiguousCallSiteDTO])
def list_ambiguous_call_sites(
    repo_id: str | None = Query(None),
) -> list[AmbiguousCallSiteDTO]:
    return _q().list_ambiguous_call_sites(repo_id=repo_id)


@router.get("/queue/verification-progress/{repo_id}",
            response_model=VerificationProgressDTO)
def get_verification_progress(repo_id: str) -> VerificationProgressDTO:
    return _q().get_verification_progress(repo_id)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
@router.get("/search", response_model=list[SearchHitDTO])
def search(
    q: str = Query(..., min_length=1),
    repo_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
) -> list[SearchHitDTO]:
    return _q().search(q, repo_id=repo_id, limit=limit)
