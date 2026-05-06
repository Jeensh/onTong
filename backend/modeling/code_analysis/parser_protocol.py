"""Language-agnostic code parser protocol and plug-in kind registries.

OD-11 Round 1 (rev.3) — code-side ontology schema.

기존 고정 Enum (EntityKind / RelationKind) 대신 런타임 등록이 가능한
*Registry* 패턴을 사용한다. 외부 파서 플러그인은 자신만의 kind 를
`EntityKindRegistry.register(...)` / `RelationKindRegistry.register(...)` 로
주입할 수 있다.

Round 1 기본 수록:
  - 16 entity kinds (code 7 / spring 6 / db 2 / config 1)
  - 18 relation kinds (code 8 / spring 5 / db 2 / config 1 / lineage 2)  # B7-2 reflects_as 추가

Round 2 추가 (OD-11-C1 합의) :
  - +2 entity kinds (concept 2) — business_term / business_rule
  - +3 relation kinds (concept 3) — realizes / validates / derived_from (예약)

Round 3 추가 (OD-11-D1 합의, Q1~Q9) :
  - +5 entity kinds (concept)  — business_process / role / manual_document / manual_section / manual_fragment
  - +6 relation kinds (concept) — part_of / responsible_for / parent_process / described_in / conflicts_with / missing_in
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Iterable, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Kind Specs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EntityKindSpec:
    """Metadata describing a single entity kind."""
    kind: str
    category: str          # "code" | "spring" | "db" | "config" | "<plugin>"
    description: str = ""


@dataclass(frozen=True)
class RelationKindSpec:
    """Metadata describing a single relation (edge) kind."""
    kind: str
    category: str          # "code" | "spring" | "db" | "config" | "lineage" | "<plugin>"
    description: str = ""


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------
class EntityKindRegistry:
    """Runtime-extensible registry of known entity kinds."""

    _kinds: ClassVar[dict[str, EntityKindSpec]] = {}

    @classmethod
    def register(cls, spec: EntityKindSpec) -> None:
        existing = cls._kinds.get(spec.kind)
        if existing is not None and existing != spec:
            raise ValueError(
                f"Entity kind '{spec.kind}' already registered with a different spec"
            )
        cls._kinds[spec.kind] = spec

    @classmethod
    def get(cls, kind: str) -> EntityKindSpec | None:
        return cls._kinds.get(kind)

    @classmethod
    def is_registered(cls, kind: str) -> bool:
        return kind in cls._kinds

    @classmethod
    def all_kinds(cls) -> list[str]:
        return list(cls._kinds.keys())

    @classmethod
    def of_category(cls, category: str) -> list[str]:
        return [k for k, s in cls._kinds.items() if s.category == category]


class RelationKindRegistry:
    """Runtime-extensible registry of known relation kinds."""

    _kinds: ClassVar[dict[str, RelationKindSpec]] = {}

    @classmethod
    def register(cls, spec: RelationKindSpec) -> None:
        existing = cls._kinds.get(spec.kind)
        if existing is not None and existing != spec:
            raise ValueError(
                f"Relation kind '{spec.kind}' already registered with a different spec"
            )
        cls._kinds[spec.kind] = spec

    @classmethod
    def get(cls, kind: str) -> RelationKindSpec | None:
        return cls._kinds.get(kind)

    @classmethod
    def is_registered(cls, kind: str) -> bool:
        return kind in cls._kinds

    @classmethod
    def all_kinds(cls) -> list[str]:
        return list(cls._kinds.keys())

    @classmethod
    def of_category(cls, category: str) -> list[str]:
        return [k for k, s in cls._kinds.items() if s.category == category]


# ---------------------------------------------------------------------------
# Default Round 1 registrations
# ---------------------------------------------------------------------------
_DEFAULT_ENTITY_KINDS: tuple[EntityKindSpec, ...] = (
    # code (7)
    EntityKindSpec("package",        "code",   "Java/Kotlin 패키지"),
    EntityKindSpec("class",          "code",   "클래스 선언"),
    EntityKindSpec("interface",      "code",   "인터페이스 선언"),
    EntityKindSpec("enum",           "code",   "Enum 선언"),
    EntityKindSpec("method",         "code",   "메서드/함수"),
    EntityKindSpec("field",          "code",   "필드/프로퍼티"),
    EntityKindSpec("constructor",    "code",   "생성자"),
    # spring (6)
    EntityKindSpec("spring_bean",    "spring", "@Component/@Service/@Bean 등 Spring Bean"),
    EntityKindSpec("http_endpoint",  "spring", "@RequestMapping 등 HTTP 엔드포인트"),
    EntityKindSpec("aspect",         "spring", "@Aspect 로 선언된 AOP 대상"),
    EntityKindSpec("scheduled_task", "spring", "@Scheduled 작업"),
    EntityKindSpec("msg_listener",   "spring", "@KafkaListener / @RabbitListener / @JmsListener"),
    EntityKindSpec("event_type",     "spring", "ApplicationEvent 타입"),
    # spring (3) — P29-1/P29-2
    EntityKindSpec("tx_marker",      "spring", "@Transactional 메서드/클래스 marker (propagation, isolation, read_only)"),
    EntityKindSpec("async_marker",   "spring", "@Async 메서드 또는 @TransactionalEventListener.phase marker"),
    EntityKindSpec("mapper_method",  "spring", "MyBatis @Mapper interface method (@Select/@Insert/@Update/@Delete 또는 XML mapper)"),
    # db (2)
    EntityKindSpec("db_table",       "db",     "관계형 DB 테이블"),
    EntityKindSpec("db_column",      "db",     "관계형 DB 컬럼"),
    # config (1)
    EntityKindSpec("config_property","config", "application.yml/.properties 구성 키"),
    # concept (2) — OD-11 Round 2 §2 (C1 합의)
    EntityKindSpec("business_term",    "concept", "Round 2 BusinessTerm 노드 (비즈니스 용어)"),
    EntityKindSpec("business_rule",    "concept", "Round 2 BusinessRule 노드 (비즈니스 규칙)"),
    # concept — OD-11 Round 3 Layer A (D1 합의 Q1=C, Q2=A)
    EntityKindSpec("business_process", "concept", "Round 3 BusinessProcess 노드 (업무 프로세스 허브)"),
    EntityKindSpec("role",             "concept", "Round 3 Role 노드 (조직 팀 단위, team. 접두어)"),
    # concept — OD-11 Round 3 Layer B (D1 합의 Q3=C, Q8=B)
    EntityKindSpec("manual_document",  "concept", "Round 3 기준서 문서 (authoritative flag 포함)"),
    EntityKindSpec("manual_section",   "concept", "Round 3 기준서 섹션 (논리 단위)"),
    EntityKindSpec("manual_fragment",  "concept", "Round 3 기준서 프래그먼트 (text/image/table/formula/ocr_text 검색 단위)"),
)

_DEFAULT_RELATION_KINDS: tuple[RelationKindSpec, ...] = (
    # code (7)
    RelationKindSpec("contains",      "code",    "상위 → 하위 포함 (package→class, class→method)"),
    RelationKindSpec("calls",         "code",    "method → method 호출"),
    RelationKindSpec("extends",       "code",    "class → class 상속"),
    RelationKindSpec("implements",    "code",    "class → interface 구현"),
    RelationKindSpec("depends_on",    "code",    "class → class import/참조"),
    RelationKindSpec("reads",         "code",    "method → field 읽기"),
    RelationKindSpec("writes",        "code",    "method → field 쓰기"),
    # spring (5)
    RelationKindSpec("autowires",     "spring",  "bean → bean 주입 (@Autowired/@Inject)"),
    RelationKindSpec("intercepts",    "spring",  "aspect → target (@Around 등)"),
    RelationKindSpec("maps_url",      "spring",  "http_endpoint → method 바인딩"),
    RelationKindSpec("publishes",     "spring",  "method → event_type 발행"),
    RelationKindSpec("handles",       "spring",  "method → event_type 수신"),
    # spring (1) — P30-2
    RelationKindSpec("calls_via_event","spring", "publisher method → handler method 합성 엣지 (event_type 매개)"),
    # db (2)
    RelationKindSpec("reads_table",   "db",      "method/class → db_table SELECT"),
    RelationKindSpec("writes_table",  "db",      "method/class → db_table INSERT/UPDATE/DELETE"),
    # config (1)
    RelationKindSpec("has_config",    "config",  "spring_bean/method → config_property"),
    # lineage (2) — OD-11 Round 1 §6-B
    RelationKindSpec("derives_from",  "lineage", "field/column → field/column 파생 (via_methods 경로 기록)"),
    RelationKindSpec("propagates_to", "lineage", "field/column → field/column 전파 (정방향)"),
    # reflection (1) — OD-11 B7-2
    RelationKindSpec("reflects_as",   "code",    "method → method/field 런타임 리플렉션 해소 (B7-2 runtime trace)"),
    # concept (3) — OD-11 Round 2 §3 (C1 합의 : REALIZES / VALIDATES 1차 / DERIVED_FROM 예약)
    RelationKindSpec("realizes",        "concept", "business_term → method/class 구현 엣지 (ConceptBinding)"),
    RelationKindSpec("validates",       "concept", "business_rule → method 검증 엣지 (단계적 A→B→C)"),
    RelationKindSpec("derived_from",    "concept", "business_term → business_term 파생 (예약, Round 2 범위 외)"),
    # concept (6) — OD-11 Round 3 §3 (D1 합의 Q1~Q9)
    RelationKindSpec("part_of",         "concept", "code/term/rule → business_process 소속 (PartOfBinding)"),
    RelationKindSpec("responsible_for", "concept", "role → process/code 책임 (RoleBinding, owner/approver/reviewer/notify)"),
    RelationKindSpec("parent_process",  "concept", "business_process → business_process 계층 (Q1=C, cycle 금지 DAG)"),
    RelationKindSpec("described_in",    "concept", "code/term/rule → manual_section 또는 manual_fragment (Q3=C)"),
    RelationKindSpec("conflicts_with",  "concept", "code ↔ manual_section 충돌 (gap_mode ∈ hierarchical|llm_only, Q4=C+A)"),
    RelationKindSpec("missing_in",      "concept", "단방향 누락 (code_only | manual_only, Q6=A)"),
)

for _spec in _DEFAULT_ENTITY_KINDS:
    EntityKindRegistry.register(_spec)

for _spec in _DEFAULT_RELATION_KINDS:
    RelationKindRegistry.register(_spec)


# ---------------------------------------------------------------------------
# IDE-friendly string constants (자동완성용)
# ---------------------------------------------------------------------------
class EntityKinds:
    """Convenience string constants for default entity kinds."""
    PACKAGE = "package"
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    METHOD = "method"
    FIELD = "field"
    CONSTRUCTOR = "constructor"
    SPRING_BEAN = "spring_bean"
    HTTP_ENDPOINT = "http_endpoint"
    ASPECT = "aspect"
    SCHEDULED_TASK = "scheduled_task"
    MSG_LISTENER = "msg_listener"
    EVENT_TYPE = "event_type"
    TX_MARKER = "tx_marker"               # P29-1 — @Transactional method/class
    ASYNC_MARKER = "async_marker"         # P29-1 — @Async method
    MAPPER_METHOD = "mapper_method"       # P29-2 — MyBatis @Mapper interface method
    DB_TABLE = "db_table"
    DB_COLUMN = "db_column"
    CONFIG_PROPERTY = "config_property"
    BUSINESS_TERM = "business_term"
    BUSINESS_RULE = "business_rule"
    BUSINESS_PROCESS = "business_process"
    ROLE = "role"
    MANUAL_DOCUMENT = "manual_document"
    MANUAL_SECTION = "manual_section"
    MANUAL_FRAGMENT = "manual_fragment"


class RelationKinds:
    """Convenience string constants for default relation kinds."""
    CONTAINS = "contains"
    CALLS = "calls"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    DEPENDS_ON = "depends_on"
    READS = "reads"
    WRITES = "writes"
    AUTOWIRES = "autowires"
    INTERCEPTS = "intercepts"
    MAPS_URL = "maps_url"
    PUBLISHES = "publishes"
    HANDLES = "handles"
    READS_TABLE = "reads_table"
    WRITES_TABLE = "writes_table"
    HAS_CONFIG = "has_config"
    DERIVES_FROM = "derives_from"
    PROPAGATES_TO = "propagates_to"
    REFLECTS_AS = "reflects_as"
    REALIZES = "realizes"
    VALIDATES = "validates"
    DERIVED_FROM = "derived_from"
    PART_OF = "part_of"
    RESPONSIBLE_FOR = "responsible_for"
    PARENT_PROCESS = "parent_process"
    DESCRIBED_IN = "described_in"
    CONFLICTS_WITH = "conflicts_with"
    MISSING_IN = "missing_in"


# ---------------------------------------------------------------------------
# Entities / Relations / ParseResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CodeEntity:
    """A single code element extracted by a parser.

    `kind` 는 `EntityKindRegistry` 에 등록된 값이어야 한다.
    `attributes` 는 Round 1 §6 확장 속성을 담기 위한 자유 폼 딕셔너리
    (precondition / postcondition / input_domain / value_flow / reflection_escape ...).
    """
    kind: str
    qualified_name: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    modifiers: list[str] = field(default_factory=list)
    parent: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not EntityKindRegistry.is_registered(self.kind):
            raise ValueError(
                f"Unknown entity kind: '{self.kind}'. "
                f"Register via EntityKindRegistry.register(EntityKindSpec(...)) first."
            )


@dataclass(frozen=True)
class CodeRelation:
    """A directed relationship between two code entities.

    `attributes` 는 lineage(via_methods/confidence), spring(profile/condition) 등
    에지별 확장 속성을 담는 자유 폼 딕셔너리.
    """
    kind: str
    source: str
    target: str
    file_path: str | None = None
    line: int | None = None
    attributes: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not RelationKindRegistry.is_registered(self.kind):
            raise ValueError(
                f"Unknown relation kind: '{self.kind}'. "
                f"Register via RelationKindRegistry.register(RelationKindSpec(...)) first."
            )


@dataclass
class ParseResult:
    """Output of parsing a single source file."""
    entities: list[CodeEntity]
    relations: list[CodeRelation]
    file_path: str
    language: str
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class CodeParser(Protocol):
    """Language-specific parser plugin interface."""

    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles (e.g., ['.java'])."""
        ...

    def language_name(self) -> str:
        """Human-readable language name (e.g., 'Java')."""
        ...

    def parse_file(self, file_path: Path, content: str) -> ParseResult:
        """Parse a single source file into entities and relations."""
        ...


__all__: Iterable[str] = (
    "EntityKindSpec",
    "RelationKindSpec",
    "EntityKindRegistry",
    "RelationKindRegistry",
    "EntityKinds",
    "RelationKinds",
    "CodeEntity",
    "CodeRelation",
    "ParseResult",
    "CodeParser",
)
