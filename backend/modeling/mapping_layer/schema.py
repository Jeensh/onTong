"""Mapping Layer Pydantic schema.

설계 정합:
- Q1' = A : 단일 Action + VerificationLevel (Function 분리 X)
- Q2' = C : 사용자 직접 매핑 + LLM 보조 (큐)
- Q4' = A : Anchor fragment-level binding (메서드 매핑 없이도 가능)
- Q5  = C : pre/postcondition 자동 추출 + 사용자 confirm
- Q6  = B : 영문 fqn + 한국어 label
- Q7' = A : Workflow 는 Action.kind=workflow + sub_actions
- Q8  = A : Strict signature lock — confirmed 안 되면 시뮬 거부
- Q9  = C : 정형 effect (op + target_term + target_attr)
- D3  = A+: Realization.dispatch_source 9-enum (Case 1~7 + user_confirmed + static_unresolved)
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ActionKind(StrEnum):
    """Action 분류 — 시뮬레이션 신뢰도 calibration.

    - PURE_FUNCTION : 입력만으로 출력 결정. 결정적 시뮬, effects 비어있어야 함.
    - EFFECTFUL     : 외부 호출 / 상태 변경. mock 하에 가설적 시뮬.
    - WORKFLOW      : sub_actions 순차 실행. realized_by 비어있고 sub_actions 채움.
    """
    PURE_FUNCTION = "pure_function"
    EFFECTFUL     = "effectful"
    WORKFLOW      = "workflow"


class ActionEffectOp(StrEnum):
    """Action effect 의 동작 종류."""
    CREATE = "create"
    MUTATE = "mutate"
    READ   = "read"
    DELETE = "delete"


class RealizationScope(StrEnum):
    PRIMARY = "primary"   # 한 (action, applies_to_subtype) 당 1개
    PARTIAL = "partial"


class DispatchSource(StrEnum):
    """Realization 이 어떻게 결정됐는가 (D3 7-case + 사용자/모호 + 수동 audit)."""
    SINGLE_IMPL       = "single_impl"
    INSTANCEOF_GUARD  = "instanceof_guard"
    ANNOTATION        = "annotation"
    FACTORY_BRANCH    = "factory_branch"
    GENERIC_BOUND     = "generic_bound"
    STRATEGY_MAP      = "strategy_map"
    REFLECTION        = "reflection"
    USER_CONFIRMED    = "user_confirmed"
    STATIC_UNRESOLVED = "static_unresolved"
    AUDIT             = "audit"   # 수동 audit 스크립트로 채워진 realization (Risk N 분석 등)


class VerificationLevel(StrEnum):
    """시뮬 신뢰도 calibration (우리 고유 개념, v5 §1.2)."""
    UNMAPPED         = "unmapped"            # Realization 0
    DRAFT            = "draft"               # 후보만, 미확정
    SIGNATURE_LOCKED = "signature_locked"    # params/output 모두 confirmed
    BODY_ANCHORED    = "body_anchored"       # 본체 anchor 모두 confirmed
    SIM_VERIFIED     = "sim_verified"        # 시뮬 1회 이상 통과
    PR_PROVEN        = "pr_proven"           # draft PR 까지 만들어져본 적


# ---------------------------------------------------------------------------
# TypeRealization (CodeType ↔ BusinessTerm)
# ---------------------------------------------------------------------------
class TypeRealization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code_type_fqn: str = Field(min_length=1)   # "com.scm.RushOrder"
    term_fqn: str = Field(min_length=1)        # "term.scm.rush_order"
    scope: RealizationScope = RealizationScope.PRIMARY
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str = "user"                       # manual / name_match / embedding / llm / user
    confirmed: bool = False
    confirmed_by: str | None = None
    rationale: str = ""
    repo_id: str = ""


# ---------------------------------------------------------------------------
# ActionParam — Action 의 입력
# ---------------------------------------------------------------------------
class ActionParam(BaseModel):
    """Action.params 한 슬롯.

    type 가 primitive (int/float/string/bool) 면 단순 값.
    type 가 'object_ref' 면 object_ref_term 으로 BusinessTerm 가리킴.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)              # 한국어 또는 영어 (Q6=B 둘 다 가능)
    type: str = Field(min_length=1)              # "int" / "float" / "string" / "bool" / "object_ref"
    object_ref_term: str | None = None           # type="object_ref" 일 때 BusinessTerm fqn
    unit: str | None = None
    range: list[float] | None = None
    nullable: bool = False
    description: str = ""

    # anchor 연결 (확정 진척도)
    anchor_locator: str | None = None            # method body 안의 어느 anchor
    confirmed: bool = False

    @model_validator(mode="after")
    def _ref_consistency(self) -> "ActionParam":
        if self.type == "object_ref" and not self.object_ref_term:
            raise ValueError(
                f"ActionParam.type='object_ref' requires object_ref_term, name={self.name!r}"
            )
        if self.type != "object_ref" and self.object_ref_term:
            raise ValueError(
                f"ActionParam.object_ref_term set but type={self.type!r}, name={self.name!r}"
            )
        if self.range is not None:
            if len(self.range) != 2:
                raise ValueError(f"ActionParam.range must be [min,max], got {self.range}")
            if self.range[0] > self.range[1]:
                raise ValueError(f"ActionParam.range[min]>max: {self.range}")
        return self


class ActionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: str = Field(min_length=1)
    object_ref_term: str | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# ActionEffect — Q9=C 정형
# ---------------------------------------------------------------------------
class ActionEffect(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    op: ActionEffectOp
    target_term: str = Field(min_length=1)        # BusinessTerm fqn
    target_attr: str | None = None                # term 의 어느 속성 (composite path segment)
    description: str = ""


# ---------------------------------------------------------------------------
# Realization (Action ↔ CodeMethod 다형성)
# ---------------------------------------------------------------------------
class Realization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code_method_fqn: str = Field(min_length=1)     # "com.scm.RushOrder.validate"
    applies_to_code_type_fqn: str | None = None    # subtype filter (None = base)
    is_override: bool = False
    dispatch_source: DispatchSource
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    scope: RealizationScope = RealizationScope.PRIMARY
    confirmed: bool = False
    rationale: str = ""


# ---------------------------------------------------------------------------
# Action — 1급 동사 노드
# ---------------------------------------------------------------------------
class Action(BaseModel):
    """Action 1급 노드 — Q1'=A 정합 (Function 분리 X, kind 로 구분)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    fqn: str = Field(min_length=1)              # "action.scm.주문_검증"
    label: str = Field(min_length=1)            # "주문 검증" (한국어)
    aliases: list[str] = Field(default_factory=list)
    domain: str = ""
    description: str = ""

    kind: ActionKind
    is_abstract: bool = False                   # Java abstract method 정합
    declared_on_term: str | None = None         # 어느 BusinessTerm 에 선언

    params: list[ActionParam] = Field(default_factory=list)
    output: ActionOutput | None = None
    preconditions: list[str] = Field(default_factory=list)    # BusinessRule fqn
    postconditions: list[str] = Field(default_factory=list)
    effects: list[ActionEffect] = Field(default_factory=list)

    realizations: list[Realization] = Field(default_factory=list)
    sub_actions: list[str] = Field(default_factory=list)      # workflow 일 때 Action fqn

    verification_level: VerificationLevel = VerificationLevel.UNMAPPED
    signature_locked_at: datetime | None = None
    confirmed_by: str | None = None
    repo_id: str = ""

    @model_validator(mode="after")
    def _kind_invariants(self) -> "Action":
        # PURE_FUNCTION → effects 비어있어야
        if self.kind == ActionKind.PURE_FUNCTION and self.effects:
            raise ValueError(
                f"Action {self.fqn}: kind=pure_function but has {len(self.effects)} effects"
            )
        # WORKFLOW → realizations 비어있고 sub_actions 채워야
        if self.kind == ActionKind.WORKFLOW:
            if self.realizations:
                raise ValueError(
                    f"Action {self.fqn}: kind=workflow cannot have direct realizations "
                    f"(use sub_actions instead)"
                )
            # sub_actions 가 비어있는 workflow 는 허용 (build 중인 상태 — 사용자 큐)
        # PRIMARY 다중 (같은 applies_to_subtype) 금지 — store 에서 검사 (DTO 단계 X)
        return self


# ---------------------------------------------------------------------------
# AnchorBinding (Q4'=A fragment-level)
# ---------------------------------------------------------------------------
class AnchorBinding(BaseModel):
    """Code anchor → Action slot binding (메서드 매핑 없이도 OK).

    Q4'=A 정합: code_method_fqn 의 anchor 가 Action 의 어느 slot 에 binding.
    target_slot 은 path syntax (e.g., "params[0]<RushOrder>.spec.diameter.range[1]").
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)                  # sha1(code_method|anchor|action|slot)[:16]
    anchor_locator: str = Field(min_length=1)      # "param[0]" / "literal:0.10" 등
    code_method_fqn: str = Field(min_length=1)
    target_action_fqn: str = Field(min_length=1)
    target_slot: str = Field(min_length=1)         # path string
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: str = "user"                           # alias_exact / literal_match / llm / user
    confirmed: bool = False
    rationale: str = ""
    repo_id: str = ""
    # 2026-05-10: anchor 가 가리키는 source code line 번호 (1-indexed). NULL = 미할당.
    line: int | None = None
