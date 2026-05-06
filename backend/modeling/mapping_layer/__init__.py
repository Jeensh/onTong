"""Mapping Layer — Code Layer ↔ Domain Layer 매핑 + Action 1급 (CORE Phase C4).

Two-Layer 의 가운데 이음매. Code (Java 충실) 와 Domain (비즈니스 의미) 를 잇는
4 종 매핑:

1. **TypeRealization** : CodeType ↔ BusinessTerm (어느 Java 클래스가 어느 도메인 term)
2. **Action**          : 동사 1급 노드. params/output/effects/preconditions
3. **Realization**     : Action ↔ CodeMethod 다형성 (다중, dispatch_source 별)
4. **AnchorBinding**   : code anchor (literal/branch/...) ↔ Action slot (composite path)

부가:
- VerificationLevel state machine (UNMAPPED → ... → PR_PROVEN)
- Path syntax parser (`params[0]<Subtype>.spec.diameter.range[1]`)

Modules:
- schema    : Pydantic DTO
- orm       : SQLAlchemy ORM
- store     : CRUD store
- path      : path syntax parse + validate (against Domain Layer graph)
- verification : VerificationLevel 자동 계산
"""
from backend.modeling.mapping_layer.schema import (
    Action,
    ActionEffect,
    ActionEffectOp,
    ActionKind,
    ActionParam,
    AnchorBinding,
    DispatchSource,
    Realization,
    RealizationScope,
    TypeRealization,
    VerificationLevel,
)

__all__ = (
    "Action",
    "ActionKind",
    "ActionParam",
    "ActionEffect",
    "ActionEffectOp",
    "Realization",
    "RealizationScope",
    "DispatchSource",
    "AnchorBinding",
    "TypeRealization",
    "VerificationLevel",
)
