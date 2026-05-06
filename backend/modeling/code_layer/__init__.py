"""Code Layer — Java 충실 mirror (CORE Phase C2).

Two-Layer 아키텍처의 Code Layer. Java 의 모든 사실 (extends/implements/abstract/
private/helper/annotation) 을 잃지 않고 보존한다. Domain Layer 와 Mapping Layer 와
명시적으로 분리되어, agent 들은 Query API 만 통해 접근한다.

Modules:
- schema       : Pydantic DTO (CodeType / CodeField / CodeMethod / CallSite)
- store        : SQLAlchemy ORM + Store API (read/write SQLite)
- adapter      : 기존 java_parser ParseResult → 새 schema 매핑
- role_classifier : Class.role / Method.role 자동 분류 (annotation + 이름 패턴)
- callsite_analyzer : Java 정적 dispatch 추적 (Case 1~4 자동, Case 5~7 unresolved 마킹)

결정 기반:
- D1=C  : Two-Layer 분리 (Code 와 Domain 별도 레이어)
- D2=A  : Class.role 자동 분류 (domain / framework / infra / unknown)
- D3=A+ : CallSiteAnalyzer 정적 분석, 모호 case 사용자 큐
- Q2'=C : 사용자 직접 매핑 + LLM 보조 (큐 데이터에 컨텍스트 포함)
"""
from backend.modeling.code_layer.schema import (
    CodeType,
    CodeTypeKind,
    CodeTypeRole,
    CodeField,
    CodeMethod,
    CodeMethodParam,
    CodeMethodAnchor,
    MethodRole,
    CallSite,
    CallCandidate,
    CallAnalysisSource,
)

__all__ = (
    "CodeType",
    "CodeTypeKind",
    "CodeTypeRole",
    "CodeField",
    "CodeMethod",
    "CodeMethodParam",
    "CodeMethodAnchor",
    "MethodRole",
    "CallSite",
    "CallCandidate",
    "CallAnalysisSource",
)
