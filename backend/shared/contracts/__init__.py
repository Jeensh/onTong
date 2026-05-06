"""Cross-section + Agent boundary contracts.

Agent (backend/agents/**) 는 ontology Core 에 직접 import 하지 않고 이 모듈만 사용한다.
정적 검사 (tools/check_agent_isolation.py) 가 위반 시 fail.

Public API:
- ontology_query : OntologyQueryClient Protocol + DTO 들
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

__all__ = [
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
]
