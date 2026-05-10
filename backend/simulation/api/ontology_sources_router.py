"""Section 3 의 dual ontology source 명시적 endpoint (STEP 3d-E6).

Section 3 는 두 가지 ontology source 를 사용:
1. SQLite (`backend.modeling.api.ontology_query.OntologyQueryClientImpl`)
   - Schema: Action / CodeType / BusinessTerm / Realization / AnchorBinding (관계형)
   - 용도: spec 03/04/05 신경로 — RunPlanBuilder / sandbox / runner core
   - data: 1514 actions (Phase D)

2. Neo4j (`backend.modeling.ontology.client.OntologyClient`)
   - Schema: Step / Standard / Method / Class / Term (그래프)
   - 용도: agents_router 의 ontology_graph / impact / test_data / locator / explorer
   - relationships: USES_STANDARD / CALCULATES / REFERS_TO_PROCESS / CONTAINS

두 schema 가 다르므로 단순 adapter 로 통합 불가. 본 endpoint 는:
- 두 source 의 health 명시적 보고
- 데이터 카운트 (각 source 의 entity 수)
- cross-reference 가능한 항목 (action_fqn / method_fqn 매칭) 안내
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation", tags=["simulation-ontology-sources"])


# ─── Pydantic 응답 모델 ─────────────────────────────────────────────


class OntologySourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str  # "sqlite" / "neo4j"
    available: bool
    schema_kind: str  # "relational" / "graph"
    purpose: str  # 한국어 사용 의미
    entity_counts: dict[str, int] = Field(default_factory=dict)
    error: Optional[str] = None


class OntologySourcesReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[OntologySourceStatus]
    cross_references: list[str] = Field(default_factory=list)
    """두 source 가 공유하는 것으로 보이는 항목 (예: method_fqn 매칭 가능)."""


# ─── 두 source 점검 ─────────────────────────────────────────────────


def _check_sqlite() -> OntologySourceStatus:
    """SQLite OntologyQueryClientImpl 점검."""
    try:
        from backend.modeling.api.ontology_query import OntologyQueryClientImpl

        ont = OntologyQueryClientImpl()
        actions = ont.list_actions() or []
        terms = ont.list_terms() or []
        code_types = ont.list_code_types() or []
        return OntologySourceStatus(
            name="sqlite",
            available=True,
            schema_kind="relational",
            purpose="spec 03/04/05 신경로 — RunPlanBuilder / sandbox / runner core",
            entity_counts={
                "actions": len(actions),
                "terms": len(terms),
                "code_types": len(code_types),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return OntologySourceStatus(
            name="sqlite",
            available=False,
            schema_kind="relational",
            purpose="spec 03/04/05 신경로",
            error=str(exc),
        )


def _check_neo4j() -> OntologySourceStatus:
    """Neo4j OntologyClient 점검."""
    try:
        from backend.modeling.ontology.client import get_client

        client = get_client()
        health = client.verify()
        if health.get("status") != "healthy":
            return OntologySourceStatus(
                name="neo4j",
                available=False,
                schema_kind="graph",
                purpose="agents_router — ontology_graph / impact / locator",
                error=health.get("error", "unhealthy"),
            )
        # 노드 카운트 (Cypher)
        counts: dict[str, int] = {}
        for label in ("Step", "Standard", "Method", "Class", "Term"):
            try:
                rows = client.query(f"MATCH (n:{label}) RETURN count(n) AS c")
                counts[label.lower()] = int(rows[0]["c"]) if rows else 0
            except Exception:  # noqa: BLE001
                counts[label.lower()] = -1
        return OntologySourceStatus(
            name="neo4j",
            available=True,
            schema_kind="graph",
            purpose="agents_router — ontology_graph / impact / locator / explorer",
            entity_counts=counts,
        )
    except Exception as exc:  # noqa: BLE001
        return OntologySourceStatus(
            name="neo4j",
            available=False,
            schema_kind="graph",
            purpose="agents_router",
            error=str(exc),
        )


def _derive_cross_references(sqlite: OntologySourceStatus, neo4j: OntologySourceStatus) -> list[str]:
    """두 source 가 공유하는 것으로 보이는 항목 안내 (heuristic)."""
    refs: list[str] = []
    if sqlite.available and neo4j.available:
        # 방법: method_fqn 이 SQLite Realization.code_method_fqn 과 Neo4j Method.name 사이 매칭 가능
        refs.append(
            "method_fqn — SQLite Realization.code_method_fqn ↔ Neo4j Method.name "
            "(class_fqn + method name 매칭)"
        )
        refs.append(
            "action 흐름 — SQLite Action.sub_actions BFS ↔ Neo4j Step.step_number 시퀀스 "
            "(action_fqn 끝 토큰과 step_name 매칭)"
        )
        refs.append(
            "term — SQLite BusinessTerm.fqn ↔ Neo4j Term.korean_name "
            "(domain entity 식별)"
        )
    return refs


# ─── Endpoint ─────────────────────────────────────────────────────


@router.get("/ontology-sources", response_model=OntologySourcesReport)
def get_ontology_sources() -> OntologySourcesReport:
    """spec 외 추가 endpoint — Section 3 의 두 ontology source 상태 + cross-reference 안내.

    GET /api/simulation/ontology-sources

    용도:
    - 시뮬 UI 의 source 상태 패널
    - 디버그 — 두 source 중 어느 쪽이 살아있는지 / 데이터 양 비교
    - dual source 사용 시 어느 항목이 공유 가능한지 안내
    """
    sqlite = _check_sqlite()
    neo4j = _check_neo4j()
    cross = _derive_cross_references(sqlite, neo4j)
    return OntologySourcesReport(sources=[sqlite, neo4j], cross_references=cross)


__all__ = ["router"]
