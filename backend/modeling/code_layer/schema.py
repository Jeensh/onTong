"""Code Layer Pydantic schema — Java 충실 mirror.

설계 원칙:
- Java 의 사실을 손실 없이 보존 (extends 단일 / implements 다중 / abstract / annotations / modifiers)
- Code-only (BaseEntity, AbstractAuditable 등) 와 도메인 의미 클래스를 role 로 구분
- Method 도 마찬가지로 role 로 (business / helper / adapter / unknown)
- anchors (param/local/return/branch/literal/field/field_access) 그대로 보존

Frozen invariants:
- interface 는 자동으로 is_abstract=True
- enum 은 abstract 불가
- extends 는 단일 (interface 면 None — interface 는 상속 chain 별도 처리)
- override 메서드는 반드시 부모 클래스에 같은 signature 가 존재해야 함 (validator 별도, schema 단계 X)
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class CodeTypeKind(StrEnum):
    """Java 타입 종류."""
    CLASS          = "class"
    ABSTRACT_CLASS = "abstract_class"
    INTERFACE      = "interface"
    ENUM           = "enum"
    RECORD         = "record"


class CodeTypeRole(StrEnum):
    """타입의 역할 분류 (D2=A 자동 분류).

    - DOMAIN    : 비즈니스 의미. BusinessTerm 으로 승격 후보.
    - FRAMEWORK : Spring / JPA / Hibernate 등 프레임워크 클래스.
    - INFRA     : Repository / Mapper / Adapter / DTO / Util 등 인프라.
    - UNKNOWN   : 자동 분류 실패. 사용자 큐.
    """
    DOMAIN     = "domain"
    FRAMEWORK  = "framework"
    INFRA      = "infra"
    UNKNOWN    = "unknown"


class MethodRole(StrEnum):
    """메서드의 역할 분류 (Q2'=C + 자동 보조).

    - BUSINESS : Action 매핑 후보. public, 비-getter, 비즈니스 의미 있는 이름.
    - HELPER   : private util / Internal 패턴. Action 매핑 면제.
    - ADAPTER  : getter/setter / DTO 변환. Action 매핑 면제.
    - UNKNOWN  : 자동 분류 실패. 사용자 큐.
    """
    BUSINESS = "business"
    HELPER   = "helper"
    ADAPTER  = "adapter"
    UNKNOWN  = "unknown"


class CallAnalysisSource(StrEnum):
    """CallSite 의 dispatch 추론 출처 (D3 7-case).

    Case 1~4 자동:
    - SINGLE_IMPL      : 인터페이스에 impl 1개만 → 확정
    - INSTANCEOF_GUARD : if (x instanceof T) {...} 분기 안 cast → 확정
    - ANNOTATION       : @Service 단일 등록 → Spring DI 확정
    - FACTORY_BRANCH   : factory 의 if-else / switch 분기별 확정

    Case 5~7 사용자 큐 (with 후보·컨텍스트):
    - GENERIC_BOUND       : T extends Order 같은 generic upper bound 만 확정 (narrow 가능)
    - STRATEGY_MAP        : Map<String, X>.get(key).method() — 동적 dispatch
    - REFLECTION          : Class.forName / SPI / ServiceLoader — 정적 분석 불가

    합성:
    - STATIC_UNRESOLVED   : 위 분류에 안 맞는 모호 (사용자 큐)
    - USER_CONFIRMED      : 사용자가 명시 confirm 한 결과

    Noise filter (2026-05-10 batch cleanup 단계 도입):
    - AUTO_FILTERED_STDLIB         : java.util / java.lang / 표준 라이브러리 호출 — 도메인 무관
    - AUTO_FILTERED_STREAM_OPTIONAL: stream().map() / Optional.of() 같은 fluent chain — 분석 무관
    """
    SINGLE_IMPL                    = "single_impl"
    INSTANCEOF_GUARD               = "instanceof_guard"
    ANNOTATION                     = "annotation"
    FACTORY_BRANCH                 = "factory_branch"
    GENERIC_BOUND                  = "generic_bound"
    STRATEGY_MAP                   = "strategy_map"
    REFLECTION                     = "reflection"
    STATIC_UNRESOLVED              = "static_unresolved"
    USER_CONFIRMED                 = "user_confirmed"
    AUTO_FILTERED_STDLIB           = "auto_filtered_stdlib"
    AUTO_FILTERED_STREAM_OPTIONAL  = "auto_filtered_stream_optional"


# ---------------------------------------------------------------------------
# CodeField — 클래스 안의 필드
# ---------------------------------------------------------------------------
class CodeField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)        # Java type 문자열 ("List<Order>" 등)
    modifiers: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)
    is_collection: bool = False             # List/Set/Map 류
    element_type: str | None = None         # collection 일 때 element type
    line: int | None = None


# ---------------------------------------------------------------------------
# CodeMethod — Java 메서드 (생성자 포함)
# ---------------------------------------------------------------------------
class CodeMethodParam(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    type: str = ""


class CodeMethodAnchor(BaseModel):
    """기존 7-anchor 보존 (param/local/return/branch/literal/field/field_access)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    method_fqn: str
    kind: str          # AnchorKind enum 값 (호환성 위해 string)
    locator: str       # "param[0]" / "local:latest" / "literal:0.10" 등
    line: int | None = None
    snippet: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class CodeMethod(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fqn: str = Field(min_length=1)         # "com.scm.Order.validate"
    name: str = Field(min_length=1)        # "validate"
    parent_type_fqn: str = Field(min_length=1)   # "com.scm.Order"

    # signature
    params: list[CodeMethodParam] = Field(default_factory=list)
    return_type: str = ""                  # "void" / "ValidationResult" / ...

    # modifiers / annotations
    modifiers: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)

    # 분류
    role: MethodRole = MethodRole.UNKNOWN
    is_abstract: bool = False              # interface method 또는 abstract 키워드
    is_override: bool = False              # @Override 또는 부모 시그니처 매칭
    is_constructor: bool = False

    # body
    body_text: str | None = None           # raw Java source
    line_start: int | None = None
    line_end: int | None = None

    # anchors (P14 호환)
    anchors: list[CodeMethodAnchor] = Field(default_factory=list)

    # 자유 부가정보 (mutations / value_flow / extracted_rules 등 — 점진 정형화)
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CodeType — Java 클래스/인터페이스/enum
# ---------------------------------------------------------------------------
class CodeType(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fqn: str = Field(min_length=1)         # "com.acme.scm.Order"
    simple_name: str = Field(min_length=1) # "Order"
    package: str = ""                      # "com.acme.scm"

    kind: CodeTypeKind
    role: CodeTypeRole = CodeTypeRole.UNKNOWN
    is_abstract: bool = False              # kind 에 더해 명시 (interface 자동 True)

    extends: str | None = None             # 단일 부모 클래스 fqn (interface 면 None)
    implements: list[str] = Field(default_factory=list)
    extends_interfaces: list[str] = Field(default_factory=list)  # interface 가 다른 interface 상속

    fields: list[CodeField] = Field(default_factory=list)
    methods: list[CodeMethod] = Field(default_factory=list)

    modifiers: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)

    # source location
    source_file: str = ""
    line_start: int | None = None
    line_end: int | None = None

    # repository / repo_id (multi-repo 지원)
    repo_id: str = ""

    @model_validator(mode="after")
    def _check_kind_invariants(self) -> "CodeType":
        # interface 는 자동 abstract
        if self.kind == CodeTypeKind.INTERFACE and not self.is_abstract:
            object.__setattr__(self, "is_abstract", True)
        # enum 은 abstract 불가
        if self.kind == CodeTypeKind.ENUM and self.is_abstract:
            raise ValueError(f"enum {self.fqn} cannot be abstract")
        # interface 는 extends (single class) 가질 수 없음 — 대신 extends_interfaces 사용
        if self.kind == CodeTypeKind.INTERFACE and self.extends is not None:
            raise ValueError(
                f"interface {self.fqn} cannot have 'extends' (single class). "
                f"Use 'extends_interfaces' for interface-to-interface inheritance."
            )
        return self


# ---------------------------------------------------------------------------
# CallSite — 한 호출 사이트의 dispatch 추론
# ---------------------------------------------------------------------------
class CallCandidate(BaseModel):
    """한 호출 사이트의 가능한 runtime type 1개 (D3 사용자 큐 컨텍스트)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    code_type_fqn: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""              # "유일 impl" / "instanceof guard line 38" / "@Service 단일"


class CallSite(BaseModel):
    """Java 호출 사이트의 정적 분석 결과 (D3 7-case)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)              # sha1(caller|line|callee_name)[:16]
    caller_method_fqn: str = Field(min_length=1)
    callee_simple_name: str = Field(min_length=1)
    callee_receiver_static_type: str = ""      # static type (e.g., "Validator")
    line: int | None = None

    # 분석 결과
    possible_runtime_types: list[CallCandidate] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)  # 1.0 = 단일 확정, < 1.0 = 모호
    analysis_source: CallAnalysisSource

    # user 큐
    needs_user_confirm: bool = False
    user_confirmed_type: str | None = None
    user_confirmed_at: str | None = None       # ISO 8601 timestamp

    # repo
    repo_id: str = ""
