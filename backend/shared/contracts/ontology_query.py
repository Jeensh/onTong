"""Ontology Query Contract — Agent boundary.

Agent (backend/agents/**) 는 이 module 만 import 한다.
Internal model (backend.modeling.{code,domain,mapping}_layer.schema) 직접 import 금지.

설계:
- DTO 는 internal Pydantic model 의 alias (frozen=True 정합).
  → contract 변경 없이 internal field 추가 가능.
  → field 제거/변경 시 contract bump 필요.
- OntologyQueryClient Protocol — Agent 가 의존하는 추상.
  실제 구현은 backend/modeling/api/ontology_query.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Protocol

# ---------------------------------------------------------------------------
# DTO — internal model alias
# ---------------------------------------------------------------------------
from backend.modeling.code_layer.schema import (
    CallSite as CallSiteDTO,
    CodeMethod as CodeMethodDTO,
    CodeType as CodeTypeDTO,
)
from backend.modeling.domain_layer.schema import (
    BusinessRule as BusinessRuleDTO,
    BusinessTerm as TermDTO,
    Composition as CompositionDTO,
    Inheritance as InheritanceDTO,
)
from backend.modeling.mapping_layer.schema import (
    Action as ActionDTO,
    ActionEffect as ActionEffectDTO,
    ActionParam as ActionParamDTO,
    AnchorBinding as AnchorBindingDTO,
    Realization as RealizationDTO,
    TypeRealization as TypeRealizationDTO,
    VerificationLevel,
)


# ---------------------------------------------------------------------------
# 가벼운 추가 DTO (Query 전용)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VerificationProgressDTO:
    repo_id: str
    total_actions: int
    by_level: dict[str, int]            # level value → count


@dataclass(frozen=True)
class SearchHitDTO:
    fqn: str
    label: str
    kind: Literal["term", "action", "code_type", "code_method", "rule"]
    domain: str = ""
    score: float = 0.0


@dataclass(frozen=True)
class AmbiguousCallSiteDTO:
    """사용자 큐 데이터 — 후보 + 컨텍스트 + LLM 추천 (D3 메모)."""
    call_site: CallSiteDTO
    caller_term_fqn: str | None              # caller 의 declared_on_term (있으면 컨텍스트)
    caller_business_process: str | None      # 향후 BusinessProcess 지원 시
    suggested_choice_fqn: str | None         # LLM 추천 (없으면 None)
    suggested_rationale: str = ""


@dataclass(frozen=True)
class UnmappedMethodDTO:
    code_method: CodeMethodDTO
    parent_type_role: str                    # CodeTypeRole value
    reason: str                              # "no Action candidate" / "all candidates rejected"


# ---------------------------------------------------------------------------
# OntologyQueryClient — Agent 가 호출할 추상 인터페이스
# ---------------------------------------------------------------------------
class OntologyQueryClient(Protocol):
    """Agent 가 의존하는 ontology API. 구현체는 internal stores 호출."""

    # ---- Term ----
    def get_term(self, fqn: str) -> TermDTO | None: ...
    def list_terms(
        self, repo_id: str | None = None,
        kind: str | None = None,            # "atomic" | "composite"
        domain: str | None = None,
    ) -> list[TermDTO]: ...
    def effective_parts(
        self, term_fqn: str, repo_id: str | None = None,
    ) -> list[CompositionDTO]:
        """transitive closure (own + inherited via extends/implements)."""
        ...
    def resolve_path(
        self, action_fqn: str, slot_path: str, repo_id: str | None = None,
    ) -> tuple[bool, str | None, str]:
        """(ok, last_term_fqn, error_message). path syntax + Domain 그래프 traversal 검증."""
        ...

    # ---- Code ----
    def get_code_type(self, fqn: str) -> CodeTypeDTO | None: ...
    def list_code_types(
        self, repo_id: str | None = None,
        kind: str | None = None,            # CodeTypeKind value
        role: str | None = None,            # CodeTypeRole value
    ) -> list[CodeTypeDTO]: ...
    def get_call_sites(self, caller_method_fqn: str) -> list[CallSiteDTO]: ...
    def get_method(self, code_method_fqn: str) -> CodeMethodDTO | None:
        """단일 method lookup. body_text / params / return_type 등 전체 surface."""
        ...
    def get_method_callers(
        self, callee_method_fqn: str, repo_id: str | None = None,
    ) -> list[CallSiteDTO]:
        """역방향 caller 검색 — best-effort (Java 정적 분석 한계)."""
        ...

    # ---- Action ----
    def get_action(self, fqn: str) -> ActionDTO | None: ...
    def list_actions(
        self, repo_id: str | None = None,
        kind: str | None = None,            # ActionKind value
        declared_on_term: str | None = None,
        verification_min: VerificationLevel | None = None,
    ) -> list[ActionDTO]: ...
    def get_realizations_for_input_type(
        self, action_fqn: str, code_type_fqn: str,
    ) -> list[RealizationDTO]:
        """다형성 dispatch — input 의 runtime type 으로 매칭되는 realizations."""
        ...

    # ---- Anchor ----
    def get_anchor_bindings_for_action(self, action_fqn: str) -> list[AnchorBindingDTO]: ...
    def get_anchor_bindings_for_method(self, code_method_fqn: str) -> list[AnchorBindingDTO]: ...

    # ---- Mapping queue (사용자 큐 데이터) ----
    def list_unmapped_methods(self, repo_id: str | None = None) -> list[UnmappedMethodDTO]: ...
    def list_ambiguous_call_sites(self, repo_id: str | None = None) -> list[AmbiguousCallSiteDTO]: ...
    def get_verification_progress(self, repo_id: str) -> VerificationProgressDTO: ...

    # ---- Search ----
    def search(
        self, query: str, repo_id: str | None = None, limit: int = 20,
    ) -> list[SearchHitDTO]:
        """FTS 통합 — Term / Action / CodeType / CodeMethod / Rule 모두."""
        ...

    def suggest(
        self, query: str, repo_id: str | None = None, n: int = 5,
    ) -> list[SearchHitDTO]:
        """0-hit fallback — fuzzy label 매칭으로 근사 추천 (did-you-mean)."""
        ...
