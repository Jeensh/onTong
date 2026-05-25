"""Schemas for the 3-gate multiturn agent (CHAT_REDESIGN_SPEC.md v2 §4).

Pydantic v2 discriminator unions:
    - Outer:  GatePayload    on "kind"  (target_selected / bundle_prepared / executed)
    - Inner:  GateExecuted   on "mode"  (simulate / impact)

Provenance 는 모든 gate payload 의 first-class 필드 — Q5 비전 ("확실한 근거").
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Provenance — Q5 비전
# ─────────────────────────────────────────────────────────────────────────────


ProvenanceSource = Literal[
    "ontology",        # Section 2 API
    "sim_v2",          # sim_v2 자산
    "llm_inference",   # LLM 추론
    "user_input",      # 사용자 입력
]


class Provenance(BaseModel):
    """단일 정보 출처. confidence 가 None 이면 적용 불가 (e.g. user_input)."""
    source: ProvenanceSource
    detail: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Common sub-models
# ─────────────────────────────────────────────────────────────────────────────


class CodeLocation(BaseModel):
    file_path: str
    line_start: int
    line_end: int


class ActionCandidate(BaseModel):
    """Gate I 의 후보 한 행.

    Phase 11: location + body_preview 를 함께 surface.
    Phase 12 Activation: ontology.db 의 풍부한 메타데이터 surface — frontend 가
    "도메인 액션 vs helper" / "Spring annotations" / "linked term" 등을 표시.
    """
    action_id: str
    label: str                         # 한국어 label
    score: float                       # ranking score (sim_v2 또는 ontology)
    code_method_fqn: str
    aliases: list[str] = Field(default_factory=list)
    location: CodeLocation | None = None
    body_preview: str | None = None    # 첫 5 줄 정도의 발췌
    return_type: str | None = None

    # Phase 12 — ontology 풍부 메타 (모두 optional, backward-compat)
    role: str | None = None              # code_methods.role: business/adapter/helper/unknown
    parent_role: str | None = None       # code_types.role: domain/infra/framework/unknown
    annotations: list[str] = Field(default_factory=list)  # @Service, @Transactional, ...
    declared_on_term: str | None = None  # actions.declared_on_term — domain term linkage


class ActionRef(BaseModel):
    """선택된 target — Gate II/III 가 참조."""
    action_id: str
    code_method_fqn: str
    repo_id: str
    location: CodeLocation


class IdiomDiff(BaseModel):
    """W75 idiom rewriter 의 결과 한 항목."""
    idiom_name: str                    # e.g. "List.add", "BigDecimal"
    java_snippet: str
    python_snippet: str


class FixtureRow(BaseModel):
    """W71 fixture synthesizer 의 결과 한 행."""
    fixture_id: str
    args: dict[str, Any]


class SchemaField(BaseModel):
    name: str
    type_name: str                     # e.g. "decimal(10,2)"
    nullable: bool = False


class SchemaSummary(BaseModel):
    entity_name: str
    fields: list[SchemaField] = Field(default_factory=list)


class CaseResult(BaseModel):
    """Gate III sim 의 case 한 행."""
    fixture_id: str
    status: Literal["PASS", "FAIL", "ERROR", "SKIPPED"]
    output: Any | None = None
    error_class: str | None = None
    error_message: str | None = None


InvariantStatus = Literal[
    "clean",                           # 모든 case PASS
    "fail_nondeterministic",
    "fail_unexpected_throw",
    "fail_return_type",
    "error",                           # 실행 자체 실패
]


class BaselineDiff(BaseModel):
    """W73 Java baseline 과의 비교 결과."""
    fixture_id: str
    java_expected: Any
    python_actual: Any
    matches: bool


class AffectedMethod(BaseModel):
    """Gate III impact 분기의 영향 받는 메서드.

    `match_kind` (Phase 10, optional): "receiver_exact" / "receiver_short" /
    "runtime_type" / "package_proximity" / "name_only". 강한 신호일수록 영향도
    가능성이 높음. legacy 응답 호환을 위해 optional.
    """
    fqn: str
    distance: int                      # caller graph hop
    via: str                           # e.g. "direct_caller", "interface_impl"
    match_kind: str | None = None      # Phase 10 — 5가지 heuristic 중 하나
    strength: float | None = None      # Phase 10 — 0.50~0.95


class Finding(BaseModel):
    """sim_v2 quick_diagnose_action 의 finding 한 항목."""
    kind: str                          # e.g. "param_signature_drift"
    severity: Literal["info", "warn", "error"]
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Gate payloads
# ─────────────────────────────────────────────────────────────────────────────


class GateIntentClassified(BaseModel):
    """Phase 21b — Gate I-a: intent 분류만 (candidates 미수행).

    사용자 vision: 의도 분류 후 "맞아?" 묻고 → confirm 후 candidates 진행.
    잘못된 intent 분류를 사용자가 candidate 보기 전에 catch.
    """
    kind: Literal["intent_classified"] = "intent_classified"
    intent: Literal[
        "simulate", "impact", "ambiguous", "locate", "explain", "hypothesis",
    ]
    user_query: str
    search_terms: list[str] = Field(default_factory=list)
    # Phase 13c — hypothesis intent 에서만 채워짐.
    conditions: list[dict[str, str]] = Field(default_factory=list)
    sources: list[Provenance]


class GateTarget(BaseModel):
    """Gate I-b — candidates 후보 list + 선택.

    Phase 21b 분할: 이전엔 intent + candidates 한번에. 이제 intent 는
    `GateIntentClassified` (turn 2), candidates 는 GateTarget (turn 3).
    `intent`/`conditions` 는 turn 2 에서 이미 surface 된 값을 carry.

    Phase 13b — `suggestions`: 0-cand 시 LLM 추출 search_terms 인접 term 추천
    (`business_terms.aliases_json` substring 매칭) → 사용자가 다른 키워드로
    재시도 유도.
    """
    kind: Literal["target_selected"] = "target_selected"
    intent: Literal[
        "simulate", "impact", "ambiguous", "locate", "explain", "hypothesis",
    ]
    user_query: str
    candidates: list[ActionCandidate]
    recommended_index: int | None
    selected: ActionRef | None
    sources: list[Provenance]
    suggestions: list[str] = Field(default_factory=list)
    # Phase 13c — hypothesis intent 에서만 채워짐. 다른 intent 면 빈 list.
    conditions: list[dict[str, str]] = Field(default_factory=list)


class GateBundle(BaseModel):
    """Gate II — Java/Python/fixture 묶음 (사용자 inline edit 가능)."""
    kind: Literal["bundle_prepared"] = "bundle_prepared"
    target: ActionRef
    java_source: str
    python_source: str
    idiom_diffs: list[IdiomDiff]
    fixtures: list[FixtureRow]
    schema_summary: SchemaSummary
    sources: list[Provenance]
    confidence: float = Field(ge=0.0, le=1.0)


class GateExecutedSimulation(BaseModel):
    """Gate III — 시뮬 분기 (실행 결과 + invariant)."""
    kind: Literal["executed_simulation"] = "executed_simulation"
    mode: Literal["simulate"] = "simulate"   # UI sugar (kind 에 이미 인코딩됨)
    results: list[CaseResult]
    invariant_status: InvariantStatus
    baseline_diff: list[BaselineDiff] | None = None
    sources: list[Provenance]


class GateExecutedImpact(BaseModel):
    """Gate III — 영향도 분기 (caller graph + finding)."""
    kind: Literal["executed_impact"] = "executed_impact"
    mode: Literal["impact"] = "impact"        # UI sugar
    affected_methods: list[AffectedMethod]
    sim_v2_findings: list[Finding]
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[Provenance]


class BusinessRuleEvidence(BaseModel):
    """business_rules.statement surface — Q5 "확실한 근거".

    Phase 13a — executed_lookup 의 evidence 단위. severity 와 statement 만 (link 는
    Provenance 에 별도).
    """
    fqn: str
    statement: str
    severity: str   # hard / soft / WARNING / INFO 등 (도메인 정의 그대로)


HypothesisVerdict = Literal[
    "yes",         # body 가 명확히 해당 조건 → 결과를 코드로 표현
    "likely_yes",  # body 에 관련 분기 발견 (LLM 추론)
    "likely_no",   # 관련 분기 없음 + 다른 default 동작
    "no",          # body 가 조건과 무관 (명확히)
    "unknown",     # 추론 불가
]


class GateExecutedHypothesis(BaseModel):
    """Phase 13c — hypothesis intent 응답.

    "X 가 Y 이면 어떻게?" 같은 boundary / edge-case 질의에 대해 body + business_rules
    를 evidence 로 verdict (yes/no/likely_*/unknown) 회신. 최QA 페르소나 1:1 해결.
    """
    kind: Literal["executed_hypothesis"] = "executed_hypothesis"
    mode: Literal["hypothesis"] = "hypothesis"
    target: ActionRef
    conditions: list[dict[str, str]]
    body_text: str
    file_path: str
    line_start: int
    line_end: int
    verdict: HypothesisVerdict
    reasoning: str
    evidence: list[BusinessRuleEvidence] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[Provenance]


class GateExecutedLookup(BaseModel):
    """Phase 13a — locate / explain intent 응답.

    Gate II / III 우회. body + file + caller + linked term + business_rules
    한 카드에 통합 surface (박주니어 / 김PM 페르소나 1:1 해결 목적).
    """
    kind: Literal["executed_lookup"] = "executed_lookup"
    mode: Literal["locate", "explain"]
    target: ActionRef
    body_text: str
    file_path: str
    line_start: int
    line_end: int
    return_type: str
    linked_action_label: str | None = None
    linked_term: str | None = None
    callers: list[AffectedMethod] = Field(default_factory=list)
    business_rules: list[BusinessRuleEvidence] = Field(default_factory=list)
    sources: list[Provenance]


# Flat union — 6 leaf 모두 단일 discriminator (kind) 로 구분.
GatePayload = Annotated[
    Union[
        GateIntentClassified, GateTarget, GateBundle,
        GateExecutedSimulation, GateExecutedImpact, GateExecutedLookup,
        GateExecutedHypothesis,
    ],
    Field(discriminator="kind"),
]


__all__ = [
    # Provenance
    "Provenance",
    "ProvenanceSource",
    # Sub-models
    "ActionCandidate",
    "ActionRef",
    "AffectedMethod",
    "BaselineDiff",
    "CaseResult",
    "CodeLocation",
    "Finding",
    "FixtureRow",
    "HypothesisVerdict",
    "IdiomDiff",
    "InvariantStatus",
    "SchemaField",
    "SchemaSummary",
    # Gate payloads
    "BusinessRuleEvidence",
    "GateBundle",
    "GateExecutedHypothesis",
    "GateExecutedImpact",
    "GateExecutedLookup",
    "GateIntentClassified",
    "GateExecutedSimulation",
    "GatePayload",
    "GateTarget",
]
