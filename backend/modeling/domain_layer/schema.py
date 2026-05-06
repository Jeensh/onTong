"""Domain Layer Pydantic schema — BusinessTerm + Inheritance + Composition + BusinessRule.

설계 원칙 (v5 결정):
- 2-kind: atomic | composite (kind 자체는 단순)
- 4 facets (조합 가능 boolean): is_abstract / is_interface / is_root_entity / struct_like_hint
- 깊이 무제한 (graph), 사이클 금지 (validator 별도)
- Java OO 표현 (extends/implements/abstract/interface) 모두 가능

Frozen invariants:
- kind=atomic 의 parts 금지 → store/validator 단계 (schema 단계 X — graph 단계 검사)
- is_interface=True → is_abstract 자동 True (interface 는 implementation 없음)
- atomic 일 때 value_type 권장 (필수는 아님 — 점진 채움)
"""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TermKind(StrEnum):
    """BusinessTerm 종류 — 2종 (v5 결정 simplification).

    - ATOMIC    : primitive 값 (C 함량 float, 직경 mm, 주문번호 string)
    - COMPOSITE : 다른 term 들로 구성 (주문 = 주문스펙 + 화학성분 + ...)
    """
    ATOMIC    = "atomic"
    COMPOSITE = "composite"


class ValueType(StrEnum):
    """ATOMIC term 의 value 타입."""
    INT       = "int"
    FLOAT     = "float"
    STRING    = "string"
    BOOL      = "bool"
    TIMESTAMP = "timestamp"


class InheritanceKind(StrEnum):
    """IS_A 관계 종류 (Java extends/implements 정합)."""
    EXTENDS    = "extends"     # 단일 부모 (Java single class inheritance)
    IMPLEMENTS = "implements"  # 다중 인터페이스 구현


class Cardinality(StrEnum):
    """HAS_A 관계 cardinality."""
    ONE        = "1:1"   # 필수, 1개
    OPTIONAL   = "0:1"   # 선택, 0 or 1
    MANY       = "1:N"   # 필수, 1+
    MANY_OPT   = "0:N"   # 선택, 0+


class RuleSeverity(StrEnum):
    """BusinessRule 위반 시 처리."""
    HARD = "hard"   # 위반 시 차단
    SOFT = "soft"   # 경고만


# ---------------------------------------------------------------------------
# BusinessTerm
# ---------------------------------------------------------------------------
class BusinessTerm(BaseModel):
    """비즈니스 용어 노드 — Domain Layer 의 핵심.

    예 (v5 메모리 정합):
        주문 (composite, is_root_entity=True)
        주문스펙 (composite, struct_like_hint=True)
        화학성분 (composite, struct_like_hint=True)
        C 함량 (atomic, value_type=float, unit="%", range=[0.10, 0.25])
        Trackable (composite, is_abstract=True, is_interface=True)
        Order (composite, is_abstract=True)
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    fqn: str = Field(min_length=1)              # "term.scm.order"
    label: str = Field(min_length=1)            # "주문" (한국어, Q6=B)
    aliases: list[str] = Field(default_factory=list)
    domain: str = ""                            # "scm" / "purchasing" / ...
    description: str = ""

    kind: TermKind                              # atomic | composite

    # facets (조합 가능 boolean)
    is_abstract: bool       = False
    is_interface: bool      = False             # is_abstract 자동 True
    is_root_entity: bool    = False             # 독립 lifecycle (검색 가능 entity)
    struct_like_hint: bool  = False             # UI inline 렌더링 hint (Address 류)

    # ATOMIC 일 때만 사용 (validator 가 강제)
    value_type:  ValueType | None = None
    unit:        str | None = None              # "mm" / "%" / "kg"
    range:       list[float] | None = None      # [min, max]
    enum_values: list[str] | None = None        # string enum

    # 메타
    confirmed: bool = False
    repo_id: str = ""
    source: Literal["manual", "auto", "llm", "user"] = "user"

    @model_validator(mode="after")
    def _facet_consistency(self) -> "BusinessTerm":
        # interface → abstract 자동 보정
        if self.is_interface and not self.is_abstract:
            object.__setattr__(self, "is_abstract", True)
        # atomic 의 facet 제한
        if self.kind == TermKind.ATOMIC:
            if self.is_interface:
                raise ValueError(
                    f"atomic term {self.fqn} cannot be interface"
                )
            if self.struct_like_hint:
                raise ValueError(
                    f"atomic term {self.fqn} cannot have struct_like_hint (only composite)"
                )
        # range 형식
        if self.range is not None and len(self.range) != 2:
            raise ValueError(
                f"term {self.fqn}.range must be [min, max] (length 2), got {self.range}"
            )
        if self.range is not None and self.range[0] > self.range[1]:
            raise ValueError(
                f"term {self.fqn}.range[min] > range[max]: {self.range}"
            )
        return self


# ---------------------------------------------------------------------------
# Inheritance (IS_A) — extends + implements
# ---------------------------------------------------------------------------
class Inheritance(BaseModel):
    """IS_A 관계 — child_fqn 이 parent_fqn 의 서브타입."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    child_fqn: str = Field(min_length=1)
    parent_fqn: str = Field(min_length=1)
    kind: InheritanceKind
    repo_id: str = ""

    @model_validator(mode="after")
    def _no_self_loop(self) -> "Inheritance":
        if self.child_fqn == self.parent_fqn:
            raise ValueError(
                f"inheritance self-loop forbidden: {self.child_fqn}"
            )
        return self


# ---------------------------------------------------------------------------
# Composition (HAS_A)
# ---------------------------------------------------------------------------
class Composition(BaseModel):
    """HAS_A 관계 — parent_fqn 이 child_fqn 을 part 로 가짐."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_fqn: str = Field(min_length=1)
    child_fqn: str = Field(min_length=1)
    role_name: str = Field(min_length=1)        # "spec" / "composition" / "quality"
    cardinality: Cardinality = Cardinality.ONE
    required: bool = True
    description: str = ""
    repo_id: str = ""

    @model_validator(mode="after")
    def _no_self_loop(self) -> "Composition":
        if self.parent_fqn == self.child_fqn:
            raise ValueError(
                f"composition self-loop forbidden: {self.parent_fqn}"
            )
        return self


# ---------------------------------------------------------------------------
# BusinessRule
# ---------------------------------------------------------------------------
class BusinessRule(BaseModel):
    """비즈니스 규칙 노드 — Action.preconditions/postconditions 가 참조."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    fqn: str = Field(min_length=1)              # "rule.scm.c_range"
    statement: str = Field(min_length=1)        # "0.10 ≤ C ≤ 0.25"
    severity: RuleSeverity = RuleSeverity.HARD
    terms_ref: list[str] = Field(default_factory=list)   # 참조 term fqn
    source: str = ""                            # 출처 (매뉴얼 fragment / 코드 추출)
    confirmed: bool = False
    repo_id: str = ""
