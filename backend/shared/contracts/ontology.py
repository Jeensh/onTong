"""Section 2 (Modeling) ↔ Section 3 (Simulation) Ontology API Contract.

설계 원칙(`docs/simulation/section2-section3-protocol.md` §0):
1. 단일 진입점 — Section 3은 ``POST /api/modeling/ontology/query``로 Section 2를 호출.
2. Intent 기반 분기 — 5종 intent로 핸들러 결정.
3. Status 기반 응답 — 5종 status로 응답 상태 구분.
4. 타입 안전성 — 모든 요청/응답은 Pydantic 모델로 검증.
5. 확장 가능 — parameters/result는 dict로 두어 Agent별 자유 확장.

기존 ``simulation.py``의 OutputFormat/SimulationRequest 등 시뮬레이션 계약과는
별개의 모듈이므로 import 충돌이 없다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Intent(str, Enum):
    """요청 의도 (Section 2가 어떤 핸들러를 사용할지 결정)."""

    QUERY = "query"
    SIMULATE = "simulate"
    IMPACT_ANALYSIS = "impact_analysis"
    OPTIMIZE = "optimize"
    EXPLAIN = "explain"


class Status(str, Enum):
    """응답 상태."""

    SUCCESS = "success"
    PARTIAL = "partial"
    NEED_MORE_INFO = "need_more_info"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


# ─────────────────────────────────────────────────────────────
# 요청 모델
# ─────────────────────────────────────────────────────────────


class OntologyRequest(BaseModel):
    """Section 3 → Section 2 요청."""

    request_id: str = Field(..., description="요청 추적용 고유 ID (UUID 권장)")
    intent: Intent = Field(..., description="요청 의도. 5종 중 하나")
    natural_language: str | None = Field(
        None, description="원본 사용자 발화 (자연어 디버깅/로깅용)"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="구조화된 파라미터. intent별로 스키마 다름",
    )
    context: dict[str, Any] | None = Field(
        None, description="대화 히스토리, 온톨로지 버전 등 컨텍스트"
    )
    expected_output: dict[str, Any] | None = Field(
        None, description="원하는 응답 형식 힌트 (예: visualization type)"
    )


# ─────────────────────────────────────────────────────────────
# Missing Info (HITL 트리거)
# ─────────────────────────────────────────────────────────────


class MissingInfoQuestion(BaseModel):
    """추가 정보 요청 — UI 자동 생성용."""

    field: str = Field(..., description="채워야 할 필드 키")
    question: str = Field(..., description="사용자에게 표시할 질문")
    input_type: Literal[
        "select", "multi_select", "text", "number", "date_range", "structured_form"
    ] = Field(..., description="UI 입력 타입")
    options: list[dict[str, str]] | None = Field(
        None, description="select/multi_select 시 선택지"
    )
    default_value: Any | None = None


class MissingInfo(BaseModel):
    """need_more_info 응답에 첨부됨."""

    questions: list[MissingInfoQuestion]
    reason: str = Field(..., description="왜 추가 정보가 필요한지 설명")


# ─────────────────────────────────────────────────────────────
# 응답 모델
# ─────────────────────────────────────────────────────────────


class VisualizationHint(BaseModel):
    """결과 시각화 타입 힌트."""

    type: Literal[
        "table",
        "chart_line",
        "chart_bar",
        "chart_pie",
        "graph_highlight",
        "impact_tree",
        "3d_slab",
        "before_after_comparison",
        "text",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    alternative_views: list[str] = Field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OntologyResponse(BaseModel):
    """Section 2 → Section 3 응답."""

    model_config = ConfigDict(use_enum_values=False)

    request_id: str
    status: Status
    confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="응답 신뢰도 (0~1)"
    )
    result: dict[str, Any] | None = Field(
        None, description="status가 success/partial일 때 결과 데이터"
    )
    missing_info: MissingInfo | None = Field(
        None, description="status가 need_more_info일 때 추가 질문"
    )
    follow_up: dict[str, Any] | None = Field(
        None, description="후속 질문 제안 등"
    )
    execution_trace: list[dict[str, Any]] | None = Field(
        None, description="실행 단계 추적 (디버깅용)"
    )
    timestamp: datetime = Field(default_factory=_utcnow)


# ─────────────────────────────────────────────────────────────
# Result 데이터 형식 (intent별 권장 구조)
# ─────────────────────────────────────────────────────────────


class ImpactAnalysisResult(BaseModel):
    """intent=impact_analysis일 때의 result."""

    summary: str
    direct_impact: dict[str, Any]
    indirect_impact: dict[str, Any]
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]
    risk_factors: list[str] = Field(default_factory=list)
    visualization: VisualizationHint | None = None


class TestDataResult(BaseModel):
    """intent=simulate (test_data 모드)일 때의 result."""

    # pytest가 'Test'로 시작하는 클래스를 수집하려는 것을 방지
    __test__ = False

    test_cases: list[dict[str, Any]]
    code_skeleton: str | None = None
    data_dependencies: list[str] = Field(default_factory=list)


class LocatorResult(BaseModel):
    """intent=explain일 때의 result."""

    matched_terms: list[dict[str, Any]]
    process_locations: list[dict[str, Any]]
    source_locations: list[dict[str, Any]]
    data_locations: list[dict[str, Any]]
    related_terms: list[dict[str, Any]] = Field(default_factory=list)
    visualization: VisualizationHint | None = None


__all__ = [
    "Intent",
    "Status",
    "OntologyRequest",
    "MissingInfoQuestion",
    "MissingInfo",
    "VisualizationHint",
    "OntologyResponse",
    "ImpactAnalysisResult",
    "TestDataResult",
    "LocatorResult",
]
