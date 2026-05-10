"""Cross-section + Agent boundary contracts.

Agent (backend/agents/**) 는 ontology Core 에 직접 import 하지 않고 이 모듈만 사용한다.
정적 검사 (tools/check_agent_isolation.py) 가 위반 시 fail.

Public API:
- ontology_query : OntologyQueryClient Protocol + DTO 들 (Section 2 Core Query API)
- ontology       : Section 2 ↔ Section 3 messaging contract (Intent / Status / OntologyRequest 등)
"""
from backend.shared.contracts.ontology_query import (
    # DTOs (alias for internal Pydantic models)
    ActionDTO,
    ActionEffectDTO,
    ActionParamDTO,
    AnchorBindingDTO,
    BusinessRuleDTO,
    CallSiteDTO,
    CodeMethodDTO,
    CodeTypeDTO,
    CompositionDTO,
    InheritanceDTO,
    RealizationDTO,
    TermDTO,
    TypeRealizationDTO,
    VerificationLevel,
    VerificationProgressDTO,
    SearchHitDTO,
    AmbiguousCallSiteDTO,
    UnmappedMethodDTO,
    # Client interface
    OntologyQueryClient,
)
from backend.shared.contracts.ontology import (
    ImpactAnalysisResult,
    Intent,
    LocatorResult,
    MissingInfo,
    MissingInfoQuestion,
    OntologyRequest,
    OntologyResponse,
    Status,
    TestDataResult,
    VisualizationHint,
)

__all__ = [
    # ── Section 2 Core Query API (ontology_query DTOs) ────────────────
    "ActionDTO",
    "ActionEffectDTO",
    "ActionParamDTO",
    "AnchorBindingDTO",
    "BusinessRuleDTO",
    "CallSiteDTO",
    "CodeMethodDTO",
    "CodeTypeDTO",
    "CompositionDTO",
    "InheritanceDTO",
    "RealizationDTO",
    "TermDTO",
    "TypeRealizationDTO",
    "VerificationLevel",
    "VerificationProgressDTO",
    "SearchHitDTO",
    "AmbiguousCallSiteDTO",
    "UnmappedMethodDTO",
    "OntologyQueryClient",
    # ── Section 2 ↔ Section 3 messaging (ontology) ────────────────────
    "Intent",
    "Status",
    "OntologyRequest",
    "MissingInfoQuestion",
    "MissingInfo",
    "VisualizationHint",
    "OntologyResponse",
    "ImpactAnalysisResult",
    "TestDataResult",
    "LocatorResult",
]
