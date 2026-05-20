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
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer.store import MappingLayerStore
from backend.shared.contracts.ontology_query import (
    ActionDTO, AmbiguousCallSiteDTO, AnchorBindingDTO, BusinessRuleDTO,
    CallSiteDTO, CodeMethodDTO, CodeTypeDTO, CompositionDTO, RealizationDTO,
    SearchHitDTO, TermDTO, UnmappedMethodDTO, VerificationLevel,
    VerificationProgressDTO,
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


@router.get("/code-methods/{code_method_fqn:path}/body",
            response_model=dict[str, Any])
def get_method_body(code_method_fqn: str) -> dict[str, Any]:
    """sec3 multiturn Gate II body 소스 — Section 3 협업 (Phase 4)."""
    method = _q().get_method(code_method_fqn)
    if method is None:
        raise HTTPException(
            status_code=404,
            detail=f"code_method not found: {code_method_fqn}",
        )
    return {
        "fqn": method.fqn,
        "body_text": method.body_text or "",
        "line_start": method.line_start,
        "line_end": method.line_end,
        "return_type": method.return_type,
    }


_MATCH_STRENGTH = {
    "receiver_exact":     0.95,
    "receiver_short":     0.85,
    "runtime_type":       0.85,
    "package_proximity":  0.70,
    "name_only":          0.50,
}


@router.get("/code-methods/{callee_method_fqn:path}/callers",
            response_model=dict[str, Any])
def get_method_callers(
    callee_method_fqn: str,
    repo_id: str | None = Query(None),
    min_strength: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
        description=(
            "match strength 의 최소값. 0.0 = 모두, 0.5 = name_only 포함, "
            "0.7 = package_proximity 이상, 0.85 = receiver/runtime, 0.95 = exact 만."
        ),
    ),
) -> dict[str, Any]:
    """역방향 caller 검색 — Section 3 Gate III impact 협업 (Phase 4 + Phase 10).

    반환: `{"callers": [{"fqn", "distance", "via", "match_kind", "strength"}, ...]}`

    Phase 10 — `match_kind` 5종 (receiver_exact > receiver_short ≈ runtime_type >
    package_proximity > name_only) + `strength` (0.50~0.95) 노출. caller 중복은
    가장 강한 match_kind 만 surface.
    """
    pairs = _q_with_match(callee_method_fqn, repo_id)
    # 같은 caller 중복 — 가장 강한 match 만 keep
    by_caller: dict[str, tuple[Any, str]] = {}
    for cs, mk in pairs:
        prev = by_caller.get(cs.caller_method_fqn)
        if prev is None or _MATCH_STRENGTH.get(mk, 0.0) > _MATCH_STRENGTH.get(prev[1], 0.0):
            by_caller[cs.caller_method_fqn] = (cs, mk)

    out: list[dict[str, Any]] = []
    for fqn, (cs, mk) in by_caller.items():
        strength = _MATCH_STRENGTH.get(mk, 0.0)
        if strength < min_strength:
            continue
        src = (
            cs.analysis_source if isinstance(cs.analysis_source, str)
            else cs.analysis_source.value
        )
        via = "interface_impl" if ("interface" in src or "impl" in src) else "direct_caller"
        out.append({
            "fqn": fqn,
            "distance": 1,
            "via": via,
            "match_kind": mk,
            "strength": strength,
        })
    # 강한 신호 먼저
    out.sort(key=lambda x: -x["strength"])
    return {"callers": out}


def _q_with_match(callee_method_fqn: str, repo_id: str | None):
    """Best-effort fallback — sec2 store 인 경우 with_match 사용, 아니면 wrap."""
    q = _q()
    code_store = getattr(q, "code", None)
    if code_store is not None and hasattr(code_store, "get_method_callers_with_match"):
        return code_store.get_method_callers_with_match(
            callee_method_fqn, repo_id=repo_id,
        )
    # Fallback — match_kind 정보 없음, name_only 로 균등 태깅
    callsites = q.get_method_callers(callee_method_fqn, repo_id=repo_id)
    return [(cs, "name_only") for cs in callsites]


@router.get("/entities/{entity_name}/schema",
            response_model=dict[str, Any])
def get_entity_schema(
    entity_name: str,
    repo_id: str | None = Query(None),
) -> dict[str, Any]:
    """entity 의 schema (CodeType.fields) — Section 3 Gate II 협업 (Phase 4).

    entity_name 매칭: simple_name 또는 fqn 의 마지막 segment.
    반환: {"entity_name", "fields": [{"name","type_name","nullable"}, ...]}
    """
    # simple_name 매칭 — list_code_types 후 일치 검색
    matches = []
    for ct in _q().list_code_types(repo_id=repo_id):
        if ct.simple_name == entity_name or ct.fqn == entity_name:
            matches.append(ct)
            break
        if ct.fqn.endswith("." + entity_name):
            matches.append(ct)
    if not matches:
        raise HTTPException(
            status_code=404, detail=f"entity not found: {entity_name}",
        )
    ct = matches[0]
    return {
        "entity_name": ct.simple_name,
        "fqn": ct.fqn,
        "fields": [
            {
                "name": f.name,
                "type_name": f.type,
                "nullable": "Nullable" in f.annotations
                            or f.type.startswith("Optional<"),
            }
            for f in ct.fields
        ],
    }


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


@router.get("/search/suggest", response_model=list[SearchHitDTO])
def search_suggest(
    q: str = Query(..., min_length=1),
    repo_id: str | None = Query(None),
    n: int = Query(5, ge=1, le=10),
) -> list[SearchHitDTO]:
    """Did-you-mean — search() 가 0 hit 일 때 호출하는 fuzzy label 추천."""
    return _q().suggest(q, repo_id=repo_id, n=n)


# ---------------------------------------------------------------------------
# BusinessRule + AnchorBinding list (전체) — UI 의 "온톨로지" 탭에서 노출용.
# 02-ontology-api-additions.md 의 신규 endpoint 일부 1차 구현.
# ---------------------------------------------------------------------------
@router.get("/business-rules", response_model=list[BusinessRuleDTO])
def list_business_rules(repo_id: str | None = Query(None)) -> list[BusinessRuleDTO]:
    rules = DomainLayerStore().list_rules(repo_id=repo_id)
    return [BusinessRuleDTO.model_validate(r.model_dump()) for r in rules]


@router.get("/anchor-bindings", response_model=list[AnchorBindingDTO])
def list_anchor_bindings(repo_id: str | None = Query(None)) -> list[AnchorBindingDTO]:
    bindings = MappingLayerStore().list_anchor_bindings(repo_id=repo_id)
    return [AnchorBindingDTO.model_validate(b.model_dump()) for b in bindings]


# ---------------------------------------------------------------------------
# delegates-to-tree — workflow 의 transitive sub_actions 펼침
# (02 명세 Section 2.1, 핵심 신규 endpoint).
# ---------------------------------------------------------------------------
@router.get("/actions/{action_fqn:path}/delegates-to-tree", response_model=dict[str, Any])
def get_delegates_to_tree(
    action_fqn: str,
    max_depth: int = Query(10, ge=1, le=30),
) -> dict[str, Any]:
    """Action 의 sub_actions 를 BFS 로 transitive 펼침.

    Returns:
        {action_fqn, kind, children: [{action_fqn, kind, children: [...]}], cycle_detected: bool}
    """
    store = MappingLayerStore()
    visited: set[str] = set()

    def build(fqn: str, depth: int) -> dict[str, Any]:
        node: dict[str, Any] = {
            "action_fqn": fqn,
            "kind": "unknown",
            "children": [],
            "cycle_detected": False,
        }
        if depth >= max_depth:
            return node
        if fqn in visited:
            node["cycle_detected"] = True
            return node
        visited.add(fqn)
        action = store.get_action(fqn)
        if action is None:
            return node
        node["kind"] = action.kind.value
        for sub_fqn in action.sub_actions:
            node["children"].append(build(sub_fqn, depth + 1))
        return node

    root_action = store.get_action(action_fqn)
    if root_action is None:
        raise HTTPException(status_code=404, detail=f"Action not found: {action_fqn}")
    return build(action_fqn, 0)
