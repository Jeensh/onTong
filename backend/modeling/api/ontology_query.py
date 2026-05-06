"""OntologyQueryClient 구현 — Code/Domain/Mapping store 통합 facade.

Agent 는 이 구현을 직접 import 하지 않는다 (정적 검사가 차단). 대신 main.py 가
인스턴스화해서 OntologyQueryClient Protocol 로 주입.

설계:
- 모든 store 인스턴스를 lazy 로 보유 (생성자에서 주입 가능 — 테스트 편의)
- internal model 그대로 contract DTO 와 호환 (alias 라서 변환 불필요)
- search 는 단순 substring/prefix 매칭 + score (FTS5 는 Phase 2)
"""
from __future__ import annotations

import logging
from typing import Iterable

from backend.modeling.code_layer.schema import (
    CodeTypeKind, CodeTypeRole, MethodRole,
)
from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer.schema import TermKind
from backend.modeling.domain_layer.resolver import effective_parts as _eff_parts
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer.path import parse_path, validate_path, PathParseError
from backend.modeling.mapping_layer.schema import (
    ActionKind, RealizationScope, VerificationLevel,
)
from backend.modeling.mapping_layer.store import MappingLayerStore
from backend.shared.contracts.ontology_query import (
    ActionDTO, AmbiguousCallSiteDTO, AnchorBindingDTO, CallSiteDTO,
    CodeMethodDTO, CodeTypeDTO, CompositionDTO, RealizationDTO,
    SearchHitDTO, TermDTO, UnmappedMethodDTO, VerificationProgressDTO,
)

logger = logging.getLogger(__name__)


class OntologyQueryClientImpl:
    """OntologyQueryClient Protocol 구현."""

    def __init__(
        self,
        code_store: CodeLayerStore | None = None,
        domain_store: DomainLayerStore | None = None,
        mapping_store: MappingLayerStore | None = None,
    ) -> None:
        self.code = code_store or CodeLayerStore()
        self.domain = domain_store or DomainLayerStore()
        self.mapping = mapping_store or MappingLayerStore()

    # ---- Term ----
    def get_term(self, fqn: str) -> TermDTO | None:
        return self.domain.get_term(fqn)

    def list_terms(
        self, repo_id: str | None = None,
        kind: str | None = None,
        domain: str | None = None,
    ) -> list[TermDTO]:
        kind_enum = TermKind(kind) if kind else None
        return self.domain.list_terms(repo_id=repo_id, kind=kind_enum, domain=domain)

    def effective_parts(
        self, term_fqn: str, repo_id: str | None = None,
    ) -> list[CompositionDTO]:
        # Domain Layer 의 모든 inheritance/composition 사용 (repo 격리 시 store 가 필터)
        inh = self.domain.list_inheritance(repo_id=repo_id)
        comp = self.domain.list_composition(repo_id=repo_id)
        return _eff_parts(term_fqn, inh, comp)

    def resolve_path(
        self, action_fqn: str, slot_path: str, repo_id: str | None = None,
    ) -> tuple[bool, str | None, str]:
        action = self.mapping.get_action(action_fqn)
        if action is None:
            return (False, None, f"unknown action {action_fqn!r}")
        try:
            pp = parse_path(slot_path)
        except PathParseError as e:
            return (False, None, str(e))
        ap = [(p.name, p.object_ref_term) for p in action.params]
        terms = self.domain.list_terms(repo_id=repo_id)
        inh = self.domain.list_inheritance(repo_id=repo_id)
        comp = self.domain.list_composition(repo_id=repo_id)
        v = validate_path(pp, action_params=ap, terms=terms,
            inheritance=inh, composition=comp)
        return (v.ok, v.last_term_fqn, v.error)

    # ---- Code ----
    def get_code_type(self, fqn: str) -> CodeTypeDTO | None:
        return self.code.get_type(fqn)

    def list_code_types(
        self, repo_id: str | None = None,
        kind: str | None = None,
        role: str | None = None,
    ) -> list[CodeTypeDTO]:
        k = CodeTypeKind(kind) if kind else None
        r = CodeTypeRole(role) if role else None
        return self.code.list_types(repo_id=repo_id, kind=k, role=r)

    def get_call_sites(self, caller_method_fqn: str) -> list[CallSiteDTO]:
        return self.code.get_call_sites(caller_method_fqn)

    # ---- Action ----
    def get_action(self, fqn: str) -> ActionDTO | None:
        return self.mapping.get_action(fqn)

    def list_actions(
        self, repo_id: str | None = None,
        kind: str | None = None,
        declared_on_term: str | None = None,
        verification_min: VerificationLevel | None = None,
    ) -> list[ActionDTO]:
        k = ActionKind(kind) if kind else None
        return self.mapping.list_actions(
            repo_id=repo_id, kind=k, declared_on_term=declared_on_term,
            verification_min=verification_min,
        )

    def get_realizations_for_input_type(
        self, action_fqn: str, code_type_fqn: str,
    ) -> list[RealizationDTO]:
        """다형성 dispatch — code_type_fqn 의 ancestor 중 매칭되는 realization."""
        all_reals = self.mapping.list_realizations(action_fqn)
        # 정확 매칭 우선
        exact = [r for r in all_reals if r.applies_to_code_type_fqn == code_type_fqn]
        if exact:
            return exact
        # base 매칭 (applies_to None)
        base = [r for r in all_reals if r.applies_to_code_type_fqn is None]
        return base

    # ---- Anchor ----
    def get_anchor_bindings_for_action(self, action_fqn: str) -> list[AnchorBindingDTO]:
        return self.mapping.get_anchor_bindings_for_action(action_fqn)

    def get_anchor_bindings_for_method(self, code_method_fqn: str) -> list[AnchorBindingDTO]:
        return self.mapping.get_anchor_bindings_for_method(code_method_fqn)

    # ---- Mapping queue ----
    def list_unmapped_methods(self, repo_id: str | None = None) -> list[UnmappedMethodDTO]:
        """Method.role=BUSINESS 이면서 Realization 0 인 메서드."""
        out: list[UnmappedMethodDTO] = []
        all_methods = self.code.list_methods(repo_id=repo_id, role=MethodRole.BUSINESS)
        # 매핑된 method_fqn 수집
        # 단순화: list_actions → realizations → method_fqn 전부 수집
        mapped_methods: set[str] = set()
        for a in self.mapping.list_actions(repo_id=repo_id):
            for r in a.realizations:
                mapped_methods.add(r.code_method_fqn)
        for m in all_methods:
            if m.fqn in mapped_methods:
                continue
            parent_type = self.code.get_type(m.parent_type_fqn)
            parent_role = parent_type.role.value if parent_type else "unknown"
            out.append(UnmappedMethodDTO(
                code_method=m,
                parent_type_role=parent_role,
                reason="no Action realization",
            ))
        return out

    def list_ambiguous_call_sites(
        self, repo_id: str | None = None,
    ) -> list[AmbiguousCallSiteDTO]:
        sites = self.code.list_ambiguous_call_sites(repo_id=repo_id)
        out: list[AmbiguousCallSiteDTO] = []
        for cs in sites:
            # caller method 의 declared_on_term 컨텍스트 (있으면)
            caller_term = None
            caller_method = self.code.get_method(cs.caller_method_fqn)
            if caller_method is not None:
                tr = self.mapping.get_term_for_code_type(caller_method.parent_type_fqn)
                caller_term = tr.term_fqn if tr else None
            out.append(AmbiguousCallSiteDTO(
                call_site=cs,
                caller_term_fqn=caller_term,
                caller_business_process=None,    # Phase 2 (BusinessProcess 미구현)
                suggested_choice_fqn=None,       # Phase 2 (LLM hook)
                suggested_rationale="",
            ))
        return out

    def get_verification_progress(self, repo_id: str) -> VerificationProgressDTO:
        actions = self.mapping.list_actions(repo_id=repo_id)
        by_level: dict[str, int] = {}
        for a in actions:
            by_level[a.verification_level.value] = by_level.get(a.verification_level.value, 0) + 1
        return VerificationProgressDTO(
            repo_id=repo_id,
            total_actions=len(actions),
            by_level=by_level,
        )

    # ---- Search ----
    def search(
        self, query: str, repo_id: str | None = None, limit: int = 20,
    ) -> list[SearchHitDTO]:
        """단순 substring + prefix 매칭 (in-memory). FTS5 는 Phase 2."""
        if not query.strip():
            return []
        q = query.strip().lower()
        hits: list[SearchHitDTO] = []

        def _score(label: str, fqn: str) -> float:
            ll = label.lower()
            ff = fqn.lower()
            if ll == q or ff == q:
                return 1.0
            if ll.startswith(q) or ff.startswith(q):
                return 0.85
            if q in ll or q in ff:
                return 0.6
            return 0.0

        for t in self.domain.list_terms(repo_id=repo_id):
            s = _score(t.label, t.fqn)
            for a in t.aliases:
                s = max(s, _score(a, t.fqn))
            if s > 0:
                hits.append(SearchHitDTO(fqn=t.fqn, label=t.label, kind="term",
                    domain=t.domain, score=s))
        for a in self.mapping.list_actions(repo_id=repo_id):
            s = _score(a.label, a.fqn)
            for al in a.aliases:
                s = max(s, _score(al, a.fqn))
            if s > 0:
                hits.append(SearchHitDTO(fqn=a.fqn, label=a.label, kind="action",
                    domain=a.domain, score=s))
        for ct in self.code.list_types(repo_id=repo_id):
            s = _score(ct.simple_name, ct.fqn)
            if s > 0:
                hits.append(SearchHitDTO(fqn=ct.fqn, label=ct.simple_name,
                    kind="code_type", domain="", score=s))
        for m in self.code.list_methods(repo_id=repo_id):
            s = _score(m.name, m.fqn)
            if s > 0:
                hits.append(SearchHitDTO(fqn=m.fqn, label=m.name,
                    kind="code_method", domain="", score=s))
        for r in self.domain.list_rules(repo_id=repo_id):
            s = _score(r.statement[:40], r.fqn)
            if s > 0:
                hits.append(SearchHitDTO(fqn=r.fqn, label=r.statement[:60],
                    kind="rule", domain="", score=s))

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]


__all__ = ("OntologyQueryClientImpl",)
