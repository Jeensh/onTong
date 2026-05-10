"""Phase 6-D — OntologyBridge.

도메인 용어(한국어/영문/컬럼명) → 영향받는 sandbox step 매핑 + 자동 시나리오 생성.

목적: 운영자가 온톨로지 그래프에서 용어를 클릭하면 →
  1) 영향받는 step 목록 (sandbox 에서 시뮬 가능)
  2) 추천 시나리오 (rule override 기본값) → "샌드박스 시뮬" 패널로 핸드오프

이전 Agent 4 (온톨로지 익스플로러) 를 대체. 온톨로지 그래프 자체는 Section 2 의 책임.
Section 3 의 역할은 그래프 위에 "여기서 무엇을 시뮬할 수 있는가" 를 overlay 하는 것.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from ..client.ontology_client import OntologyClient
from ..sandbox import registry

logger = logging.getLogger(__name__)


# ─── 도메인 용어 → step 매핑 (curated) ──────────────────────────────


# (canonical_term, aliases) 쌍 + 영향받는 step_ids
_TERM_DEFINITIONS: list[tuple[str, list[str], list[str]]] = [
    (
        "실수율",
        ["productivity", "yield", "yield-rate", "공정실수율"],
        ["productivity", "second_wgt", "max_split", "split_range",
         "slab_count", "slab_weight", "pipeline", "pipeline_full"],
    ),
    (
        "두께",
        ["slab_thickness", "thickness", "slabThickness"],
        ["thickness", "second_wgt", "final_width_range",
         "final_length_range", "target_size", "pipeline_full"],
    ),
    (
        "포장단중",
        ["pkg_wgt", "pkgWgtLow", "pkgWgtHigh", "package-weight"],
        ["validator", "pipeline_full"],
    ),
    (
        "단중",
        ["slab_wgt", "slabWgt", "unit-weight", "secondWgt"],
        ["second_wgt", "split_range", "slab_count",
         "slab_weight", "max_split", "pipeline_full"],
    ),
    (
        "EDGING",
        ["edging", "edging_group", "edging_spec",
         "EDGING_GROUP", "EDGING_SPEC"],
        ["width_range", "pipeline_full"],
    ),
    (
        "폭",
        ["width", "slabWidth", "selectedHrTgtWidth", "firstWidth"],
        ["width_range", "second_wgt", "final_width_range",
         "target_size", "pipeline_full"],
    ),
    (
        "길이",
        ["length", "slabLength", "firstLength"],
        ["length_range", "final_length_range", "target_size", "pipeline_full"],
    ),
    (
        "분할",
        ["split", "splitCount", "currentSplitCount"],
        ["split_range", "max_split", "slab_count", "pipeline_full"],
    ),
    (
        "제강",
        ["sm", "smCd", "PlantMapping", "plant_mapping", "제강공장"],
        ["thickness", "width_range", "length_range",
         "plant_mapping_migrate", "pipeline_full"],
    ),
    (
        "HR_MIN_WGT",
        ["hr_min_wgt", "hrMinWgt", "압연최소단중"],
        ["second_wgt", "pipeline_full"],
    ),
    (
        "HR_MAX_WGT",
        ["hr_max_wgt", "hrMaxWgt", "압연최대단중"],
        ["second_wgt", "pipeline_full"],
    ),
    (
        "HR_SPEC",
        ["hr_spec", "hrSpec", "열연설비"],
        ["width_range", "length_range", "pipeline_full"],
    ),
    (
        "CAST_SPEC",
        ["cast_spec", "castSpec", "연주설비"],
        ["thickness", "width_range", "length_range",
         "plant_mapping_migrate", "pipeline_full"],
    ),
    (
        "주문",
        ["order", "SDOrder", "ORDER_OS", "주문단중"],
        ["validator", "split_range", "slab_count",
         "slab_weight", "pipeline_full"],
    ),
    (
        "설계대기량",
        ["designPendQty", "design-pend-qty", "designPendQtyHigh"],
        ["slab_count", "second_wgt", "validator", "pipeline_full"],
    ),
    (
        "21-step",
        ["pipeline", "21단계", "전체파이프라인", "전체알고리즘"],
        ["pipeline", "pipeline_full"],
    ),
]


def _build_index() -> tuple[dict[str, str], dict[str, list[str]]]:
    """alias → canonical, canonical → step_ids."""
    alias_to_canonical: dict[str, str] = {}
    canonical_to_steps: dict[str, list[str]] = {}
    for canonical, aliases, steps in _TERM_DEFINITIONS:
        canonical_to_steps[canonical] = steps
        alias_to_canonical[canonical.lower()] = canonical
        for a in aliases:
            alias_to_canonical[a.lower()] = canonical
    return alias_to_canonical, canonical_to_steps


_ALIAS_TO_CANONICAL, _CANONICAL_TO_STEPS = _build_index()


def _build_step_to_terms() -> dict[str, list[str]]:
    """역방향 인덱스 — step_id → 영향 용어 목록."""
    out: dict[str, list[str]] = {}
    for canonical, _, steps in _TERM_DEFINITIONS:
        for s in steps:
            out.setdefault(s, []).append(canonical)
    return out


_STEP_TO_TERMS = _build_step_to_terms()


# ─── 자동 시나리오 추천 ────────────────────────────────────────────


@dataclass
class ScenarioSuggestion:
    """OntologyBridge 가 제안하는 시뮬 시나리오 1건."""

    title: str
    step_id: str
    inputs: dict
    rationale: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "step_id": self.step_id,
            "inputs": self.inputs,
            "rationale": self.rationale,
            "tags": list(self.tags),
        }


# 용어별 추천 inputs 카탈로그.
_SUGGESTIONS: dict[str, list[ScenarioSuggestion]] = {
    "실수율": [
        ScenarioSuggestion(
            title="HR 실수율 0.95 → 0.92",
            step_id="pipeline_full",
            inputs={"rules": {"hr": "0.92"}},
            rationale="열연 실수율 0.03 하락 시 Slab 매수/단중 fan-out 측정",
            tags=["productivity", "rule-change"],
        ),
        ScenarioSuggestion(
            title="HRF 실수율 0.93 → 0.88",
            step_id="pipeline_full",
            inputs={"rules": {"hrf": "0.88"}},
            rationale="열연정정 실수율 변경. 누적 실수율 fan-out",
            tags=["productivity", "rule-change", "hrf"],
        ),
    ],
    "두께": [
        ScenarioSuggestion(
            title="A001 vs B002 품종 두께 비교",
            step_id="thickness",
            inputs={"order": {"productTypeCd": "B002"}},
            rationale="동일 주문에서 품종 변경 시 CAST_SPEC.slabThickness 룩업 결과 변동",
            tags=["thickness", "product-type"],
        ),
    ],
    "EDGING": [
        ScenarioSuggestion(
            title="EDGING_SPEC '*' fallback 누락 시나리오",
            step_id="pipeline_full",
            inputs={"rules": {"edging_wildcard": False}},
            rationale="와일드카드 row 가 누락되면 EdgingSpecMissingError → 어느 그룹에서?",
            tags=["edging", "data-integrity"],
        ),
        ScenarioSuggestion(
            title="EDGING_GROUP 매칭 미달 (selectedHrTgtWidth=1700)",
            step_id="pipeline_full",
            inputs={"order": {"selectedHrTgtWidth": "1700"}},
            rationale="등록된 그룹 범위 외 입력 → DG103",
            tags=["edging", "group-miss"],
        ),
    ],
    "제강": [
        ScenarioSuggestion(
            title="K → CC2/M2 마이그",
            step_id="plant_mapping_migrate",
            inputs={
                "smCd": "K", "productTypeCd": "A001",
                "mapping_overrides": {"K": {"castCd": "CC2", "machineCd": "M2"}},
            },
            rationale="레거시 하드코딩 → DB 마이그 시뮬. CastSpec 룩업 변동 측정",
            tags=["migration", "plant-mapping"],
        ),
    ],
    "포장단중": [
        ScenarioSuggestion(
            title="포장단중 범위 좁힘 (10~20)",
            step_id="validator",
            inputs={"order": {"pkgWgtLow": "10", "pkgWgtHigh": "20"}},
            rationale="고객 단중 제약 강화 시 DG003 검증 fan-out",
            tags=["validator", "pkg-wgt"],
        ),
    ],
    "단중": [
        ScenarioSuggestion(
            title="얇고 좁은 Slab 단중 (HR_MIN/MAX 격자 외)",
            step_id="second_wgt",
            inputs={
                "order": {"confirmedPlantCd": "KKKK    ", "productivity": "0.85"},
                "slab": {
                    "slabThickness": "180", "firstWidthLow": "1100",
                    "firstWidthHigh": "1100", "firstWgtLow": "8", "firstWgtHigh": "25",
                },
            },
            rationale="HR_MIN/MAX_WGT 2D sheet 격자 외 입력 → DG106/107",
            tags=["hr-min-wgt", "boundary"],
        ),
    ],
}


# ─── Bridge ──────────────────────────────────────────────────────────


class OntologyBridge:
    """Section 2 의 ontology client 와 결합하여 도메인 용어 시뮬 가이드 제공.

    in_process=True (기본) — Neo4j 미가용 환경에선 timeout 후 graceful fallback.
    """

    def __init__(self, client: Optional[OntologyClient] = None, *, ontology_timeout: float = 2.0):
        self._client = client
        self._ontology_timeout = ontology_timeout
        self._skip_ontology = os.getenv("SIMULATION_SKIP_ONTOLOGY", "1") == "1"

    @staticmethod
    def all_terms() -> list[dict]:
        """등록된 canonical 용어 목록 + 영향 step 미리보기."""
        return [
            {"canonical": canonical, "aliases": aliases,
             "step_count": len(steps), "steps": steps}
            for canonical, aliases, steps in _TERM_DEFINITIONS
        ]

    @staticmethod
    def step_to_terms(step_id: str) -> list[str]:
        return _STEP_TO_TERMS.get(step_id, [])

    @staticmethod
    def all_step_to_terms() -> dict[str, list[str]]:
        """모든 step → 영향 용어 인덱스."""
        return {sid: _STEP_TO_TERMS.get(sid, []) for sid in registry.list_steps()}

    @staticmethod
    def resolve(term: str) -> Optional[str]:
        """alias 포함 정규화 → canonical."""
        return _ALIAS_TO_CANONICAL.get(term.lower())

    @classmethod
    def term_to_steps(cls, term: str) -> list[str]:
        canonical = cls.resolve(term)
        if canonical is None:
            return []
        return list(_CANONICAL_TO_STEPS.get(canonical, []))

    @classmethod
    def suggest_scenarios(cls, term: str) -> list[ScenarioSuggestion]:
        canonical = cls.resolve(term)
        if canonical is None:
            return []
        return list(_SUGGESTIONS.get(canonical, []))

    async def overlay(self, term: str) -> dict:
        """용어 → 매핑 + Section 2 ontology query (graceful fallback) 결합 응답."""
        canonical = self.resolve(term)
        steps = self.term_to_steps(term)
        suggestions = [s.to_dict() for s in self.suggest_scenarios(term)]

        ontology_block: dict = {"available": False, "reason": "skipped"}
        if not self._skip_ontology and self._client is not None:
            try:
                from backend.shared.contracts.ontology import Intent, OntologyRequest
                req = OntologyRequest(
                    request_id=f"sim-bridge-{term}",
                    intent=Intent.QUERY,
                    natural_language=term,
                    parameters={"term": canonical or term},
                )
                resp = await asyncio.wait_for(
                    self._client.query(req),
                    timeout=self._ontology_timeout,
                )
                ontology_block = {
                    "available": True,
                    "status": resp.status.value if hasattr(resp.status, "value") else str(resp.status),
                    "result": resp.result if hasattr(resp, "result") else {},
                }
            except (asyncio.TimeoutError, Exception) as e:
                ontology_block = {"available": False, "reason": f"{type(e).__name__}: {e}"}

        return {
            "input_term": term,
            "canonical": canonical,
            "matched": canonical is not None,
            "impacted_steps": steps,
            "step_count": len(steps),
            "scenario_suggestions": suggestions,
            "ontology": ontology_block,
        }
