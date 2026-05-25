"""시뮬레이션 에이전트 — gate payload schemas.

multiturn 의 schema 를 base 로 import 하되, 5 intent 분기 (locate / explain /
hypothesis) payload 를 추가 정의.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# multiturn 의 공용 모델은 그대로 import
from backend.section3.agents.multiturn.schemas import (
    ActionCandidate,
    ActionRef,
    AffectedMethod,
    BaselineDiff,
    BusinessRuleEvidence,
    CaseResult,
    CodeLocation,
    Finding,
    FixtureRow,
    GateBundle,
    GateExecutedHypothesis,
    GateExecutedImpact,
    GateExecutedLookup,
    GateExecutedSimulation,
    GateIntentClassified,
    GateTarget,
    IdiomDiff,
    Provenance,
    SchemaField,
    SchemaSummary,
)

# multiturn 의 GatePayload 가 정의됐다면 그대로 re-export.


# ─────────────────────────────────────────────────────────────────────────────
# 시뮬레이션 전용 — locate / explain payload (multiturn 미정의분)
# ─────────────────────────────────────────────────────────────────────────────


class LocateMatch(BaseModel):
    """locate intent 의 1건 매칭 — 코드 위치."""
    file: str
    line_start: int
    line_end: int
    method_fqn: str | None = None
    snippet: str = ""
    relevance: float = Field(ge=0.0, le=1.0, default=0.5)


class GateExecutedLocate(BaseModel):
    """locate intent 결과 payload."""
    kind: Literal["executed_locate"] = "executed_locate"
    query: str
    matches: list[LocateMatch] = Field(default_factory=list)
    total_scanned: int = 0
    provenance: Provenance | None = None


class ExplainRelated(BaseModel):
    """explain intent 의 관련 ontology 객체."""
    kind: Literal["term", "action", "rule", "code_method"]
    fqn: str
    label: str
    summary: str = ""


class GateExecutedExplain(BaseModel):
    """explain intent 결과 payload."""
    kind: Literal["executed_explain"] = "executed_explain"
    query: str
    summary: str
    related: list[ExplainRelated] = Field(default_factory=list)
    provenance: Provenance | None = None


# ─────────────────────────────────────────────────────────────────────────────
# 비교 실행 (compare_runs) — simulate · hypothesis 양쪽이 사용
# ─────────────────────────────────────────────────────────────────────────────


class FieldDiff(BaseModel):
    """결과 record 1개 필드의 변경 전/후."""
    field: str
    before: object | None = None
    after: object | None = None
    changed: bool = False


class CompareRunResult(BaseModel):
    """변경 전/후 동일 fixture 로 두 번 실행한 결과."""
    method_fqn: str
    before_result: dict | None = None
    after_result: dict | None = None
    field_diffs: list[FieldDiff] = Field(default_factory=list)
    invariant_before: list[str] = Field(default_factory=list)
    invariant_after: list[str] = Field(default_factory=list)
    summary: str = ""


__all__ = [
    # multiturn re-export
    "ActionCandidate",
    "ActionRef",
    "AffectedMethod",
    "BaselineDiff",
    "BusinessRuleEvidence",
    "CaseResult",
    "CodeLocation",
    "Finding",
    "FixtureRow",
    "GateBundle",
    "GateExecutedHypothesis",
    "GateExecutedImpact",
    "GateExecutedLookup",
    "GateExecutedSimulation",
    "GateIntentClassified",
    "GateTarget",
    "IdiomDiff",
    "Provenance",
    "SchemaField",
    "SchemaSummary",
    # simulation 전용
    "CompareRunResult",
    "ExplainRelated",
    "FieldDiff",
    "GateExecutedExplain",
    "GateExecutedLocate",
    "LocateMatch",
]
