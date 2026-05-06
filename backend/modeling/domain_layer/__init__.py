"""Domain Layer — 비즈니스 의미 모델 (CORE Phase C3).

Two-Layer 아키텍처의 Domain Layer. 사용자가 직접 보고 편집하는 비즈니스 의미.
Java 코드의 사실 (Code Layer) 와 분리되어 있어, 코드 노이즈 (BaseEntity 등) 가
새어들지 않는다.

Modules:
- schema    : Pydantic DTO (BusinessTerm + Inheritance + Composition + BusinessRule)
- orm       : SQLAlchemy ORM (4 테이블)
- store     : CRUD + repo 격리 + idempotent upsert
- validator : 사이클 / atomic-parts / facet 일관성 검사
- resolver  : effective_parts (extends + implements 통한 transitive closure)

결정 기반:
- D1=C  : Two-Layer 분리 (Domain ↔ Code 별도 layer)
- D2=A  : Class.role 자동 분류 결과로 Code Layer 의 domain class 만 BusinessTerm 후보
- C2=A  : 풍부 path syntax (resolver 가 traversal 가능 구조 보장)
- C4=A  : Java 자동 추출 → 사용자 confirm (이 모듈은 schema/store/validator 만, 추출은 별도)

핵심 결정 (사용자 진화):
- v4 의 4-kind (atomic/bundle/aggregate/reference) 폐기
- v5 의 2-kind (atomic/composite) + facets (is_abstract/is_interface/is_root_entity/struct_like_hint)
- Inheritance 신설 (Java OO 표현력)
"""
from backend.modeling.domain_layer.schema import (
    BusinessRule,
    BusinessTerm,
    Cardinality,
    Composition,
    Inheritance,
    InheritanceKind,
    RuleSeverity,
    TermKind,
    ValueType,
)

__all__ = (
    "BusinessTerm",
    "TermKind",
    "ValueType",
    "Inheritance",
    "InheritanceKind",
    "Composition",
    "Cardinality",
    "BusinessRule",
    "RuleSeverity",
)
