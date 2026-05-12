"""Section 3 — 공통 Pydantic 모델.

설계 원칙:
- Section 3 는 modeling API 의 응답 (HTTP JSON) 만 활용. Neo4j/Cypher 직접 의존 0건.
- 모든 agent 는 streaming events 또는 단일 final result 둘 다 지원.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── 요청 ──────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """온톨로지 브릿지 chat 메시지 단위."""

    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=_utcnow)


class ChatRequest(BaseModel):
    """chat agent 진입 요청."""

    model_config = ConfigDict(extra="forbid")
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    session_id: Optional[str] = None


class SandboxRequest(BaseModel):
    """샌드박스 메뉴 — 테스트 데이터 + 실행."""

    model_config = ConfigDict(extra="forbid")
    target_kind: Literal["step", "method", "class"] = "step"
    target_id: str  # e.g. "1" (step number), "calculateThickness" (method)
    case_types: list[Literal["normal", "boundary", "error"]] = Field(
        default_factory=lambda: ["normal", "boundary", "error"]
    )
    run_after_generate: bool = True
    request_id: Optional[str] = None


class CodeImpactRequest(BaseModel):
    """영향도 분석 — 코드 변경 (method/class)."""

    model_config = ConfigDict(extra="forbid")
    target_kind: Literal["method", "class", "column"]
    target_id: str
    request_id: Optional[str] = None


class DataImpactRequest(BaseModel):
    """데이터 변경 분석 (기준 / slab data)."""

    model_config = ConfigDict(extra="forbid")
    target_kind: Literal["table", "standard_value", "order"]
    target_id: str
    request_id: Optional[str] = None


# ─── 응답 / 이벤트 ─────────────────────────────────────────────────


class StreamEventType:
    """agent streaming 이벤트 타입 상수."""

    THINKING = "thinking"         # LLM 의도 분석 / 계획 시작
    MODELING_CALL = "modeling_call"  # modeling API 호출 시작
    MODELING_RESULT = "modeling_result"  # modeling 응답 수신
    LAYER_SCAN = "layer_scan"     # ontology 트리 layer 별 스캔 (workflow → step → method → ...)
    CODE_GEN = "code_gen"         # Python 코드 합성
    SANDBOX_RUN = "sandbox_run"   # sandbox 실행
    SANDBOX_RESULT = "sandbox_result"
    FINAL = "final"               # agent 최종 결과
    ERROR = "error"
    NEED_MORE_INFO = "need_more_info"  # missing_info 그대로 forward


class StreamEvent(BaseModel):
    """agent → UI 로 스트리밍되는 단일 이벤트."""

    model_config = ConfigDict(extra="forbid")
    type: str
    timestamp: datetime = Field(default_factory=_utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)
    """payload 의 shape 은 type 별로 다름. UI 가 type 으로 dispatch."""


class IntentClassification(BaseModel):
    """LLM 이 자연어 → modeling intent 변환한 결과."""

    model_config = ConfigDict(extra="forbid")
    modeling_intent: Literal["impact_analysis", "simulate", "explain"]
    """modeling 의 OntologyRequest.intent 값."""

    parameters: dict[str, Any] = Field(default_factory=dict)
    """modeling 의 OntologyRequest.parameters 값 (target.kind/id 등)."""

    confidence: float = 0.0
    reasoning: str = ""
    """LLM 이 왜 이렇게 분류했는지 — UI 가 사용자에게 표시 가능."""

    suggested_followups: list[str] = Field(default_factory=list)


class AgentFinalResult(BaseModel):
    """agent 의 최종 결과 (StreamEvent.payload 또는 단일 응답)."""

    model_config = ConfigDict(extra="forbid")
    ok: bool
    summary: str = ""
    modeling_response: Optional[dict[str, Any]] = None
    generated_python: Optional[str] = None
    sandbox_result: Optional[dict[str, Any]] = None
    visualization: Optional[dict[str, Any]] = None
    """nodes/edges/cypher 등 — modeling.ontology_trace 그대로 또는 가공."""
    error: Optional[str] = None
