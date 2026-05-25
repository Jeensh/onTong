"""자동 매핑 추천 — Code Layer → Domain / Mapping Layer 후보 생성.

P3-3 핵심 모듈. CodeLayerStore 의 import 결과를 받아 사람이 검토할 후보를 만든다.
어떤 것도 자동으로 confirm 하지 않음 — 모두 `confirmed=False` 또는 read-only DTO.

생성하는 3 종류:
1. BusinessTerm 후보 — CodeType.role=domain 에서 (Jpo/PK 제외, *Entity / Designer / Action / Driver / Validator 등)
2. Action 후보 — Method.role=business 에서 (private 짧은 helper 제외)
3. TypeRealization 후보 — CodeType ↔ BusinessTerm name 매칭 (PRIMARY) +
   "Entity 가 다수 Jpo 를 평탄화 흡수" 패턴에 대한 PARTIAL 자동 제안

스코어:
- 1.0: glossary 정확 매칭 (한국어 label 직접 보유) — UI 에서 "high"
- 0.8: simple_name 정규화 + alias 매칭 — UI 에서 "medium"
- 0.5: 패턴만으로 추정 (예: *Action → action) — UI 에서 "low"
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from backend.modeling.code_layer.schema import (
    CodeMethod,
    CodeType,
    CodeTypeKind,
    CodeTypeRole,
    MethodRole,
)
from backend.modeling.domain_layer.schema import BusinessTerm, TermKind
from backend.modeling.mapping_layer.schema import (
    Action,
    ActionKind,
    DispatchSource,
    Realization,
    RealizationScope,
    TypeRealization,
    VerificationLevel,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 도메인 glossary — slab-design 데모용 (p3_demo_repo_analysis.md 정합).
# 코드 식별자 → (한국어 label, kind, root_entity 여부, struct_like_hint, aliases)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _GlossaryEntry:
    label: str
    kind: TermKind = TermKind.COMPOSITE
    is_root_entity: bool = False
    struct_like_hint: bool = False
    aliases: tuple[str, ...] = ()


_SLAB_GLOSSARY: dict[str, _GlossaryEntry] = {
    # 주문 도메인
    "Order":             _GlossaryEntry("주문", is_root_entity=True),
    "SDOrderEntity":     _GlossaryEntry("주문", is_root_entity=True, aliases=("Order",)),
    "OrderOs":           _GlossaryEntry("주문스펙", struct_like_hint=True),
    "SDOrderOsJpo":      _GlossaryEntry("주문스펙", struct_like_hint=True, aliases=("OrderOs",)),
    "OrderChemical":     _GlossaryEntry("화학성분", struct_like_hint=True),
    "OrderQd":           _GlossaryEntry("품질데이터", struct_like_hint=True),
    # Slab / 결과
    "Slab":              _GlossaryEntry("Slab"),
    "SDSlabEntity":      _GlossaryEntry("Slab", aliases=("Slab",)),
    "SlabResult":        _GlossaryEntry("결과"),
    "SlabDesignHist":    _GlossaryEntry("이력"),
    # 도메인 atomics (struct_like 도 합쳐서 일단 composite 로)
    "Grade":             _GlossaryEntry("강종"),
    "Product":           _GlossaryEntry("품종", aliases=("ProductType","ProductName","ProductKind")),
    "Plant":             _GlossaryEntry("공장"),
    "Process":           _GlossaryEntry("공정"),
    "ConfirmedPlantCd":  _GlossaryEntry("확정공정코드"),
    "PackagingWeight":   _GlossaryEntry("포장단중", struct_like_hint=True),
    "UnitWeight":        _GlossaryEntry("단중"),
    "ProductivityRate":  _GlossaryEntry("실수율"),
    "Cmpcd":             _GlossaryEntry("온톨로지"),
    "OrgCd":             _GlossaryEntry("소"),
    # spec / rule master
    "HrSpec":            _GlossaryEntry("HR스펙"),
    "CastSpec":          _GlossaryEntry("주조스펙"),
    "EdgingSpec":        _GlossaryEntry("EDGING스펙"),
    "EdgingGroup":       _GlossaryEntry("EDGING그룹"),
    "EdgingRule":        _GlossaryEntry("EDGING룰"),
    "CustomerStd":       _GlossaryEntry("고객표준"),
    "HrMinWgt":          _GlossaryEntry("HR최소중량"),
    "HrMaxWgt":          _GlossaryEntry("HR최대중량"),
    "ProductivityStd":   _GlossaryEntry("실수율표준"),
    # 검증
    "ValidationResult":  _GlossaryEntry("검증결과"),
    "SdErrorCode":       _GlossaryEntry("에러코드"),
}

# 메서드 이름 → 한국어 라벨 (도메인 액션 위주)
_METHOD_LABEL_GLOSSARY: dict[str, str] = {
    "design":            "Slab설계_실행",
    "validate":          "정합성_검증",
    "classify":          "분류",
    "execute":           "실행",
    "calculate":         "계산",
    "extract":           "추출",
    "save":              "저장",
    "split":             "분할",
    "recalc":            "재계산",
    "check":             "체크",
    "resolve":           "결정",
    "drive":             "구동",
}

# Domain 분류 (보고서 기반)
_DOMAIN_HINTS: dict[str, str] = {
    "Order":   "scm.order",
    "Slab":    "scm.slab",
    "Spec":    "scm.spec",
    "Grade":   "scm.grade",
    "Product": "scm.product",
    "Plant":   "scm.plant",
    "Process": "scm.process",
}


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------
@dataclass
class TermCandidate:
    suggested: BusinessTerm
    derived_from_code_type_fqn: str
    confidence: float
    reason: str


@dataclass
class ActionCandidate:
    suggested: Action
    derived_from_method_fqn: str
    confidence: float
    reason: str


@dataclass
class TypeRealizationCandidate:
    suggested: TypeRealization
    confidence: float
    reason: str


@dataclass
class RecommendationResult:
    term_candidates: list[TermCandidate] = field(default_factory=list)
    action_candidates: list[ActionCandidate] = field(default_factory=list)
    type_realization_candidates: list[TypeRealizationCandidate] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "terms": len(self.term_candidates),
            "actions": len(self.action_candidates),
            "type_realizations": len(self.type_realization_candidates),
        }


# ---------------------------------------------------------------------------
# 헬퍼 — 이름 정규화
# ---------------------------------------------------------------------------
_PREFIX_RE = re.compile(r"^(SD|Sd)")     # slab-design 도메인 prefix
_SUFFIX_RE = re.compile(r"(Entity|Jpo|PK|Dto|DTO|Service|Logic|Wrapper)$")
_CAMEL_BOUND_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _normalize_simple_name(name: str) -> str:
    """`SDSlabEntity` → `Slab`, `SDOrderOsJpo` → `OrderOs`. glossary 매칭용."""
    s = _PREFIX_RE.sub("", name)
    s = _SUFFIX_RE.sub("", s)
    return s


def _camel_to_snake(name: str) -> str:
    return _CAMEL_BOUND_RE.sub("_", name).lower()


def _term_fqn(domain: str, label_or_simple: str) -> str:
    return f"term.{domain}.{_camel_to_snake(label_or_simple)}"


def _action_fqn(domain: str, label: str) -> str:
    return f"action.{domain}.{label}"


def _domain_for(simple_name: str) -> str:
    for hint, dom in _DOMAIN_HINTS.items():
        if hint in simple_name:
            return dom
    return "scm"


# ---------------------------------------------------------------------------
# BusinessTerm 후보
# ---------------------------------------------------------------------------
def _term_from_code_type(ct: CodeType, repo_id: str) -> TermCandidate | None:
    """role=domain CodeType → BusinessTerm 후보 1개. 매칭 실패 시 None.

    skip:
    - kind=enum (Term 으로 쓰진 않음 — BusinessRule/atomic enum 으로 별도 처리해야)
    - is_abstract 인 *Action / *Validator (이건 Action 후보로 빠짐)
    """
    name = ct.simple_name
    norm = _normalize_simple_name(name)

    # *Action / *Designer / *Driver / *Validator / *Service / *Logic / *Wrapper / *Extractor
    # → Action 후보 클래스이므로 BusinessTerm 후보 X
    skip_suffixes = ("Action","Designer","Driver","Validator","Service","Logic","Wrapper","Extractor",
                     "Classifier","Calculator","Resolver","Provider")
    if any(name.endswith(s) for s in skip_suffixes):
        return None

    domain = _domain_for(norm)
    confidence: float
    reason: str
    label: str
    aliases: list[str] = []
    is_root = False
    struct_like = False
    kind = TermKind.COMPOSITE

    # 1) 정확 매칭
    entry = _SLAB_GLOSSARY.get(name) or _SLAB_GLOSSARY.get(norm)
    if entry is not None:
        label = entry.label
        kind = entry.kind
        is_root = entry.is_root_entity
        struct_like = entry.struct_like_hint
        aliases = list(entry.aliases) + [name]
        confidence = 1.0
        reason = f"glossary 정확 매칭 ({norm} → {label})"
    else:
        # 2) 패턴 fallback — Entity / Jpo / 일반 record 류
        label = norm or name
        confidence = 0.5
        if name.endswith("Entity"):
            is_root = True
            confidence = 0.7
            reason = f"이름 패턴: *Entity → root_entity 추정"
        elif name.endswith("Jpo"):
            struct_like = True
            confidence = 0.7
            reason = f"이름 패턴: *Jpo → DB row 평탄 매핑 대상 (PARTIAL 후보)"
        elif ct.kind == CodeTypeKind.ENUM:
            return None  # enum 은 별도 처리 (atomic enum_values 로)
        else:
            reason = f"패턴 추론 (glossary miss, simple_name={norm})"
        aliases = [name]

    term = BusinessTerm(
        fqn=_term_fqn(domain, norm or name),
        label=label,
        aliases=aliases,
        domain=domain,
        description=f"자동 추천 — {ct.fqn}",
        kind=kind,
        is_root_entity=is_root,
        struct_like_hint=struct_like,
        confirmed=False,
        repo_id=repo_id,
        source="auto",
    )
    return TermCandidate(
        suggested=term,
        derived_from_code_type_fqn=ct.fqn,
        confidence=confidence,
        reason=reason,
    )


def recommend_terms(
    types: list[CodeType], repo_id: str,
) -> list[TermCandidate]:
    """role=domain | infra(*Jpo) 인 CodeType → BusinessTerm 후보."""
    out: list[TermCandidate] = []
    seen_fqns: set[str] = set()
    for ct in types:
        # domain 또는 *Jpo (infra 지만 도메인 컨셉 보유 — partial term 후보)
        accept = (ct.role == CodeTypeRole.DOMAIN) or (ct.simple_name.endswith("Jpo"))
        if not accept:
            continue
        cand = _term_from_code_type(ct, repo_id)
        if cand is None:
            continue
        # 같은 term fqn 중복 — 신뢰도 높은 것만 유지
        existing_idx = next(
            (i for i, c in enumerate(out) if c.suggested.fqn == cand.suggested.fqn),
            None,
        )
        if existing_idx is None:
            out.append(cand)
            seen_fqns.add(cand.suggested.fqn)
        else:
            if cand.confidence > out[existing_idx].confidence:
                out[existing_idx] = cand
    return out


# ---------------------------------------------------------------------------
# Action 후보
# ---------------------------------------------------------------------------
def _action_kind_for(method: CodeMethod, parent: CodeType) -> ActionKind:
    """Method 특성으로 ActionKind 추정."""
    body = method.body_text or ""
    # workflow heuristic: design / orchestrate / process / drive
    name_l = method.name.lower()
    if name_l in ("design", "drive", "orchestrate", "process") and len(body.splitlines()) > 20:
        return ActionKind.WORKFLOW
    # effectful: void return + body 안 'save' / 'persist' / 'repository' / 'insert' / 'update' / 'delete'
    has_side_effect = any(
        kw in body.lower() for kw in ("save(", "persist(", "repository", "insert", ".update(", ".delete(")
    )
    if method.return_type in ("void", "") or has_side_effect:
        return ActionKind.EFFECTFUL
    return ActionKind.PURE_FUNCTION


def _action_label(method_name: str, parent_name: str) -> str:
    """slab-design 컨벤션 기반 한국어 라벨."""
    # *Action 클래스의 execute() → 클래스 이름에서 추출
    if method_name == "execute" and parent_name.endswith("Action"):
        # SdLengthRangeAction → 길이범위_산정
        base = _normalize_simple_name(parent_name).replace("Action", "")
        snake = _camel_to_snake(base)
        return f"{snake}_실행"
    label = _METHOD_LABEL_GLOSSARY.get(method_name)
    if label:
        return label
    # camelCase → snake (영어 fallback)
    return _camel_to_snake(method_name)


_GENERIC_HELPER_NAMES = {
    "lookup", "find", "findFirstMatch", "findOne", "findAll",
    "get", "set", "put", "remove", "size", "isEmpty",
    "of", "from", "newInstance", "build",
}


def _declared_on_term(
    method: CodeMethod, parent: CodeType,
    *, code_to_term: dict[str, str], simple_to_term: dict[str, str],
) -> str | None:
    """우선순위:
    1. parent CodeType 자체가 term 후보 → 그 term
    2. 첫 번째 param 의 type (simple name) 이 term 후보로 매칭 → 그 term
    """
    if parent.fqn in code_to_term:
        return code_to_term[parent.fqn]
    for p in method.params:
        # type 이 'SDOrderEntity' 처럼 simple name 만 들어있을 수 있음
        simple = p.type.split(".")[-1].rstrip("[]>")
        t = simple_to_term.get(simple)
        if t:
            return t
    return None


def recommend_actions(
    types: list[CodeType], repo_id: str,
    *,
    term_candidates: Iterable[TermCandidate] = (),
) -> list[ActionCandidate]:
    """Method.role=business → Action 후보 + 자기 본인 Realization 1개 첨부."""
    # CodeType.fqn → 후보 term fqn (declared_on_term 자동 추정)
    by_code: dict[str, str] = {}
    by_simple: dict[str, str] = {}
    for c in term_candidates:
        by_code[c.derived_from_code_type_fqn] = c.suggested.fqn
        # simple_name 매핑 — c.derived_from_code_type_fqn 의 마지막 segment
        simple = c.derived_from_code_type_fqn.split(".")[-1]
        by_simple.setdefault(simple, c.suggested.fqn)

    out: list[ActionCandidate] = []
    seen_action_fqns: set[str] = set()
    for ct in types:
        if ct.role not in (CodeTypeRole.DOMAIN,):
            continue
        for m in ct.methods:
            if m.role != MethodRole.BUSINESS:
                continue
            if m.is_constructor:
                continue
            if m.name.startswith("_") or m.name in ("toString", "equals", "hashCode"):
                continue
            # generic helper 필터 (lookup / find / get 류 — 진짜 도메인 동사 아님)
            if m.name in _GENERIC_HELPER_NAMES:
                continue

            kind = _action_kind_for(m, ct)
            label = _action_label(m.name, ct.simple_name)
            domain = _domain_for(ct.simple_name)
            action_fqn = _action_fqn(domain, label)

            # fqn 중복 시 — parent simple name 으로 disambiguate
            if action_fqn in seen_action_fqns:
                action_fqn = f"{action_fqn}__{_camel_to_snake(_normalize_simple_name(ct.simple_name))}"
            seen_action_fqns.add(action_fqn)

            # WORKFLOW 는 realizations 비어있어야 (schema 강제). 그 외엔 self realization 1개.
            realizations: list[Realization] = []
            if kind != ActionKind.WORKFLOW:
                realizations = [Realization(
                    code_method_fqn=m.fqn,
                    is_override=m.is_override,
                    dispatch_source=DispatchSource.SINGLE_IMPL,
                    confidence=1.0,
                    scope=RealizationScope.PRIMARY,
                    confirmed=False,
                    rationale=f"자동 매칭: {ct.simple_name}.{m.name}",
                )]

            decl_on = _declared_on_term(
                m, ct, code_to_term=by_code, simple_to_term=by_simple,
            )
            action = Action(
                fqn=action_fqn,
                label=label,
                aliases=[m.name],
                domain=domain,
                description=f"자동 추천 — {m.fqn}",
                kind=kind,
                declared_on_term=decl_on,
                realizations=realizations,
                verification_level=VerificationLevel.DRAFT,
                repo_id=repo_id,
            )

            # 신뢰도: 클래스 + 메서드 명 모두 glossary hit 인 경우 1.0, 한쪽만 0.7, 둘 다 miss 0.5
            class_hit = ct.simple_name in _SLAB_GLOSSARY or _normalize_simple_name(ct.simple_name) in _SLAB_GLOSSARY
            method_hit = m.name in _METHOD_LABEL_GLOSSARY or (m.name == "execute" and ct.simple_name.endswith("Action"))
            confidence = 1.0 if (class_hit and method_hit) else (0.7 if class_hit or method_hit else 0.5)

            out.append(ActionCandidate(
                suggested=action,
                derived_from_method_fqn=m.fqn,
                confidence=confidence,
                reason=f"{ct.simple_name}.{m.name} → kind={kind.value}, label={label!r}",
            ))
    return out


# ---------------------------------------------------------------------------
# TypeRealization 후보
# ---------------------------------------------------------------------------
def recommend_type_realizations(
    types: list[CodeType], repo_id: str,
    *,
    term_candidates: Iterable[TermCandidate],
) -> list[TypeRealizationCandidate]:
    """CodeType ↔ Term 매칭. PRIMARY 1대1 + Entity 가 다수 Jpo 흡수 시 PARTIAL 자동 추가.

    PARTIAL 휴리스틱: `*Entity` 클래스가 같은 prefix `*Jpo` 클래스들과 같은 domain 인 경우,
    각 Jpo 의 term 이 Entity 의 PARTIAL 매핑 대상이라고 추정 (fragment 평탄화 패턴).
    """
    # term_fqn → TermCandidate (편의 lookup)
    by_code_fqn: dict[str, TermCandidate] = {
        c.derived_from_code_type_fqn: c for c in term_candidates
    }

    out: list[TypeRealizationCandidate] = []

    # 1) PRIMARY — TermCandidate 가 있는 모든 CodeType
    for ct in types:
        cand = by_code_fqn.get(ct.fqn)
        if cand is None:
            continue
        out.append(TypeRealizationCandidate(
            suggested=TypeRealization(
                code_type_fqn=ct.fqn,
                term_fqn=cand.suggested.fqn,
                scope=RealizationScope.PRIMARY,
                confidence=cand.confidence,
                source="name_match" if cand.confidence >= 0.8 else "auto",
                confirmed=False,
                rationale=cand.reason,
                repo_id=repo_id,
            ),
            confidence=cand.confidence,
            reason=f"PRIMARY: {ct.simple_name} → {cand.suggested.label}",
        ))

    # 2) PARTIAL — *Entity 가 *Jpo 들의 fragment 를 흡수하는 패턴
    entities = [t for t in types if t.simple_name.endswith("Entity") and t.role == CodeTypeRole.DOMAIN]
    jpos = [t for t in types if t.simple_name.endswith("Jpo")]
    for ent in entities:
        ent_norm = _normalize_simple_name(ent.simple_name)  # "Order" / "Slab" / ...
        # 같은 prefix 의 Jpo 들 (e.g. SDOrderJpo, SDOrderOsJpo, SDOrderOmJpo, SDOrderQdJpo)
        related_jpos = [
            j for j in jpos
            if _normalize_simple_name(j.simple_name).startswith(ent_norm)
            and _normalize_simple_name(j.simple_name) != ent_norm
        ]
        for j in related_jpos:
            j_cand = by_code_fqn.get(j.fqn)
            if j_cand is None:
                continue
            out.append(TypeRealizationCandidate(
                suggested=TypeRealization(
                    code_type_fqn=ent.fqn,
                    term_fqn=j_cand.suggested.fqn,
                    scope=RealizationScope.PARTIAL,
                    confidence=0.7,
                    source="auto",
                    confirmed=False,
                    rationale=f"평탄화 흡수 패턴: {ent.simple_name} 가 {j.simple_name} 의 필드를 보유",
                    repo_id=repo_id,
                ),
                confidence=0.7,
                reason=f"PARTIAL: {ent.simple_name} ⊃ {j.simple_name} fragment",
            ))

    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_recommendations(
    types: list[CodeType], *, repo_id: str,
) -> RecommendationResult:
    terms = recommend_terms(types, repo_id)
    actions = recommend_actions(types, repo_id, term_candidates=terms)
    realizations = recommend_type_realizations(types, repo_id, term_candidates=terms)
    logger.info(
        "recommendations: %d terms / %d actions / %d realizations",
        len(terms), len(actions), len(realizations),
    )
    return RecommendationResult(
        term_candidates=terms,
        action_candidates=actions,
        type_realization_candidates=realizations,
    )


__all__ = (
    "TermCandidate", "ActionCandidate", "TypeRealizationCandidate",
    "RecommendationResult", "build_recommendations",
    "recommend_terms", "recommend_actions", "recommend_type_realizations",
)
