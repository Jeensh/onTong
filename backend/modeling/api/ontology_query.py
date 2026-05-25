"""OntologyQueryClient 구현 — Code/Domain/Mapping store 통합 facade.

Agent 는 이 구현을 직접 import 하지 않는다 (정적 검사가 차단). 대신 main.py 가
인스턴스화해서 OntologyQueryClient Protocol 로 주입.

설계:
- 모든 store 인스턴스를 lazy 로 보유 (생성자에서 주입 가능 — 테스트 편의)
- internal model 그대로 contract DTO 와 호환 (alias 라서 변환 불필요)
- search 는 단순 substring/prefix 매칭 + score (FTS5 는 Phase 2)
"""
from __future__ import annotations

import difflib
import logging
import re
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

    def get_method(self, code_method_fqn: str):
        return self.code.get_method(code_method_fqn)

    def get_method_callers(
        self, callee_method_fqn: str, repo_id: str | None = None,
    ) -> list[CallSiteDTO]:
        return self.code.get_method_callers(callee_method_fqn, repo_id=repo_id)

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
        """단순 substring + prefix + camelCase 토큰 fallback (in-memory). FTS5 는 Phase 2.

        camelCase 토큰 매칭: `slabWidth` → {slab, width} 분해 후 term alias `width` 와
        교차 → score 0.4+ — 한/영 bilingual 검색 (영문 코드명 ↔ 한국어 도메인 alias) 의 핵심.
        """
        if not query.strip():
            return []
        q_raw = query.strip()
        q = q_raw.lower()
        q_tokens = _tokenize(q_raw)  # camelCase 유지된 원본으로 토크나이즈
        # R4-1: 한국어 핵심 어휘 ↔ 영문 매핑. action label 이 영문 (final_width_range_실행)
        # 인데 사용자가 한국어 "최종" 으로 시작하면 데이터 자체가 안 잡혔던 페르소나 B 회귀.
        # 매핑은 도메인 어휘만 (정확한 1:1 의미). 일반 단어는 false-positive 위험으로 제외.
        _KO_TO_EN_SYNONYMS = {
            "최종": "final", "폭": "width", "너비": "width", "두께": "thickness",
            "길이": "length", "중량": "weight", "단중": "weight", "비중": "gravity",
            "분할": "split", "매수": "count", "주문": "order", "설계": "design",
            "설비": "spec", "공정": "process", "이력": "history", "범위": "range",
            "검증": "validate", "정합성": "integrity",
        }
        # query 자체가 한국어 단일 어휘면 영문 alias 도 같이 매칭 시도. 다중 토큰이면 각 token 변환.
        q_synonyms: list[str] = []
        if q in _KO_TO_EN_SYNONYMS:
            q_synonyms.append(_KO_TO_EN_SYNONYMS[q])
        for tok in q_tokens:
            mapped = _KO_TO_EN_SYNONYMS.get(tok)
            if mapped:
                q_synonyms.append(mapped)
        hits: list[SearchHitDTO] = []

        # R3-3: 한국어 1-token query 는 음절 단위 substring 매칭이 자연. 예: "설계" 가
        # "Slab설계_실행" 의 중간에 있어도 사실상 token match (Korean 합성어는 syllable
        # 단위로 의미가 합쳐짐). 이전엔 substring 0.6 → kind boost 후도 term startswith
        # 0.85 에 밀려 action 이 #12 등수. 0.8 로 bump.
        _q_is_korean = bool(q) and not q.isascii()

        def _score(label: str, fqn: str) -> float:
            ll = label.lower()
            ff = fqn.lower()
            if ll == q or ff == q:
                return 1.0
            if ll.startswith(q) or ff.startswith(q):
                return 0.85
            if q in ll or q in ff:
                # Korean substring 은 합성어 중간 매칭이라도 의미 있음 — "설계" 가 "Slab설계"
                # 안에 있으면 사실상 token boundary 와 동등. 영문 substring (0.6) 보다 강함.
                return 0.85 if _q_is_korean else 0.6
            # R4-1: 한국어 synonym 영문 매칭 — "최종" → "final" 처럼 한국어 query 가 영문
            # label/fqn 에 매칭. synonym 도 substring (q_synonym in ll/ff) 확인. 직접 매칭의
            # 0.85 보다 한 단계 낮은 0.75 — 의미 변환이라 약간 약함.
            for syn in q_synonyms:
                if syn in ll or syn in ff:
                    return 0.75
            # Token-level fallback — camelCase / snake_case 분해 후 교집합.
            # fqn 전체 segment 토큰화 (e.g., term.scm.slab.width → {term, scm, slab, width})
            # match_ratio (matched / q_tokens) 가 높을수록 강한 신호.
            if q_tokens:
                cand_tokens = _tokenize(label) | _tokenize(fqn)
                # 'term' / 'action' 같은 namespace prefix 제거 (noise 토큰)
                cand_tokens -= {"term", "action", "rule"}
                matched = q_tokens & cand_tokens
                if matched:
                    ratio = len(matched) / max(len(q_tokens), 1)
                    return min(0.85, 0.45 + 0.4 * ratio)
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
                # R3-3: workflow action 은 top-level entry — 같은 score 라도 가산점.
                # "설계" 검색 시 history_controller term 보다 Slab설계_실행 workflow 가 위로.
                if a.kind == ActionKind.WORKFLOW:
                    s = min(1.0, s + 0.05)
                # R5-5: 한국어 → 영문 synonym 경로로 action 도달 시 추가 boost.
                # term kind boost (×1.15) 차이를 raw score 단에서 메워야 action 이 위로 옴.
                # "최종" 검색 시 action #6 였던 회귀 fix.
                if _q_is_korean and q_synonyms and s <= 0.80:
                    s = min(0.95, s + 0.07)
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
        # R2-4: rule statement 에서 (DG\d+) 마커 추출 → 별도 alias 로 매칭. 이전엔
        # statement[:40] 만 substring 매칭이라 "(DG001)" 끝부분이 잘리거나 score 0.6 (action
        # 0.85 에 밀려 limit=20 cutoff) 됐음. DG 마커를 explicit alias 로 만들면 exact match.
        # 또한 "DG" 만 쳐도 모든 DG 마커 가진 룰을 surface 하도록 prefix-match 도 처리.
        _dg_marker_re = re.compile(r"\(DG\d+\)|\bDG\d+\b", re.IGNORECASE)
        _q_dg_prefix = q.upper().startswith("DG") and (q.upper() == "DG" or q[2:].rstrip().isdigit() or len(q) <= 2)
        for r in self.domain.list_rules(repo_id=repo_id):
            s = _score(r.statement, r.fqn)
            # DG 마커 추출 후 별도 score 시도 — 마커가 query 와 정확히 일치하면 1.0.
            markers = [m.strip("()").upper() for m in _dg_marker_re.findall(r.statement)]
            for marker in markers:
                s = max(s, _score(marker, r.fqn))
            # "DG" prefix query 면 DG 마커 가진 모든 rule 을 0.95 로 강제 surface — 운영자가
            # "DG 룰 다 보고 싶다" 했을 때 17 rule 중 9 개 (DG-marked) 가 안 나오는 회귀 방지.
            # 0.85 면 action 0.85 * kind_boost 1.10 = 0.935 와 충돌해 20-limit 밖으로 cut off.
            # 0.95 면 rule kind_boost 1.05 = 0.9975 로 top.
            if _q_dg_prefix and markers:
                s = max(s, 0.95)
            # R6 (페르소나 C round 6): 한국어 쿼리 — rule statement 본문에 한국어 substring
            # 매칭 시 action +0.07 boost 와 균형. width/length/thickness invariant BR 이
            # "폭"/"두께" 검색에서 action 들 + term 들에 밀려 limit cut off 되던 회귀 fix.
            if _q_is_korean and 0 < s <= 0.85 and q in r.statement.lower():
                s = min(0.95, s + 0.07)
            if s > 0:
                hits.append(SearchHitDTO(fqn=r.fqn, label=r.statement[:60],
                    kind="rule", domain="", score=s))

        # Kind diversity: 같은 substring score 라도 term/action 이 code_method 보다 의미 풍부.
        # 또한 bilingual token-match 된 term 이 substring 만 일치한 code_method 보다 useful.
        # → score 에 kind 별 multiplier 적용 + tie-break 우선순위 유지.
        # 단, 쿼리가 PascalCase Java class identifier 모양 (`SdFinal...`) 이면 코드를 위로 —
        # 인시던트 1차 대응 시 test-class term 이 실제 code class 보다 위에 오면 혼란.
        # camelCase variable (`slabWidth`) 는 codey 로 판정하지 않음 — bilingual term 매칭이
        # 더 유용한 케이스 (영문 변수명 ↔ 한국어 도메인 alias).
        _is_codey_query = (
            len(q_raw) >= 3
            and q_raw[0].isupper()
            and any(c.islower() for c in q_raw[1:])
            and q_raw.isascii()
            and " " not in q_raw
            and "." not in q_raw
        )
        _KIND_RANK = {"term": 0, "action": 1, "code_type": 2, "code_method": 3, "rule": 4}
        if _is_codey_query:
            _KIND_BOOST = {"code_type": 1.15, "code_method": 1.10, "action": 1.0, "rule": 0.95, "term": 0.9}
        else:
            _KIND_BOOST = {"term": 1.15, "action": 1.10, "rule": 1.05, "code_type": 1.0, "code_method": 0.95}
        hits.sort(key=lambda h: (
            -(h.score * _KIND_BOOST.get(h.kind, 1.0)),
            _KIND_RANK.get(h.kind, 9),
            h.fqn,
        ))
        return hits[:limit]

    def suggest(
        self, query: str, repo_id: str | None = None, n: int = 5,
    ) -> list[SearchHitDTO]:
        """Did-you-mean fallback — search() 0 hit 시 fuzzy label 매칭으로 근사 추천.

        difflib SequenceMatcher 기반 (1~2자 오타 / 어순 차이 / 부분 매칭) → 항상 SearchHitDTO
        반환 (kind 보존, score 는 difflib ratio 그대로). 호출 측이 0-hit 일 때만 호출하는
        걸 가정. 검색 본체와 달리 camelCase 토큰화는 안 함 (search 가 이미 시도했으므로
        fallback 의 fallback 으로 difflib 만).
        """
        q = query.strip().lower()
        if not q:
            return []
        # 모든 entity 의 label/alias 풀 모음 — (label, fqn, kind, domain) 튜플.
        pool: list[tuple[str, str, str, str]] = []
        for t in self.domain.list_terms(repo_id=repo_id):
            pool.append((t.label, t.fqn, "term", t.domain))
            for a in t.aliases:
                pool.append((a, t.fqn, "term", t.domain))
        for a in self.mapping.list_actions(repo_id=repo_id):
            pool.append((a.label, a.fqn, "action", a.domain))
            for al in a.aliases:
                pool.append((al, a.fqn, "action", a.domain))
        for ct in self.code.list_types(repo_id=repo_id):
            pool.append((ct.simple_name, ct.fqn, "code_type", ""))
        for m in self.code.list_methods(repo_id=repo_id):
            pool.append((m.name, m.fqn, "code_method", ""))
        # 같은 fqn 의 label 여러 개 (alias) 중 best score 만 유지
        scored: dict[str, SearchHitDTO] = {}
        for label, fqn, kind, domain in pool:
            ratio = difflib.SequenceMatcher(None, q, label.lower()).ratio()
            if ratio < 0.5:
                continue
            existing = scored.get(fqn)
            if existing is None or existing.score < ratio:
                scored[fqn] = SearchHitDTO(
                    fqn=fqn, label=label, kind=kind,  # type: ignore[arg-type]
                    domain=domain, score=ratio,
                )
        return sorted(scored.values(), key=lambda h: -h.score)[:n]


_CAMEL_TOKEN_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$|[^A-Za-z])|[0-9]+")


def _tokenize(text: str) -> set[str]:
    """camelCase / snake_case / dot.path / space 모두 분해 → lowercase 토큰 집합.

    예: 'slabWidth' → {'slab', 'width'}
        'sd_max_split_count' → {'sd', 'max', 'split', 'count'}
        'Slab 두께' → {'Slab', '두께'} (한국어는 공백 기준)
    너무 짧은 (≤1자) 영문 토큰은 noise 라 제외.
    """
    if not text:
        return set()
    out: set[str] = set()
    # 영문/숫자 camelCase 분해
    for m in _CAMEL_TOKEN_RE.finditer(text):
        tok = m.group(0).lower()
        if len(tok) >= 2 or any(ord(c) > 127 for c in tok):
            out.add(tok)
    # 한국어 / 기타 — 공백 / underscore / dot 으로 split
    for piece in re.split(r"[\s._-]+", text):
        if not piece:
            continue
        if any(ord(c) > 127 for c in piece):
            out.add(piece.lower())
    return out


__all__ = ("OntologyQueryClientImpl",)
