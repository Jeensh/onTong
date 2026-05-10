"""Phase 7-B — AI 시나리오 어시스턴트.

자연어 질의 ("HR 실수율 0.85로 줄이면?", "PlantMapping K 가 CC2 로 바뀌면 어느 주문이 깨져?")
→ scenario inputs JSON 자동 변환 + 그대로 sandbox 실행 가능한 형태.

설계:
- Pydantic AI Agent + structured output (ScenarioDraft)
- LLM 미가용 환경 자동 fallback: 키워드 기반 deterministic 매칭 (OntologyBridge 카탈로그 활용)
- LLM 사용 시 system prompt 에 step 카탈로그 + 입력 schema 주입
- 결과는 1) ScenarioDraft (저장 가능) 2) 잡 큐 즉시 등록 옵션 모두 지원
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..ontology_bridge.bridge import OntologyBridge
from ..sandbox import registry

logger = logging.getLogger(__name__)


# ─── 결과 스키마 ────────────────────────────────────────────────────


class ScenarioDraft(BaseModel):
    """LLM/fallback 가 생성한 시뮬 시나리오 초안."""

    title: str = Field(..., description="시나리오 한국어 제목 (≤30자)")
    rationale: str = Field(..., description="왜 이 시나리오를 추천하는지 — 사용자에게 보여줄 설명")
    step_id: str = Field(..., description="실행 대상 step (registry.STEP_REGISTRY 키)")
    inputs: dict = Field(default_factory=dict, description="step 에 넘길 inputs JSON")
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="추천 신뢰도 (0~1)")
    extracted_term: Optional[str] = Field(None, description="자연어에서 매칭된 도메인 용어 canonical")
    method: str = Field("fallback", description="'llm' / 'fallback' — 어떤 경로로 생성됐는지")


@dataclass
class AssistRequest:
    natural_language: str
    prefer_llm: bool = True


# ─── Fallback (키워드 기반) ──────────────────────────────────────────


def _fallback_draft(query: str) -> ScenarioDraft:
    """LLM 미가용 시: OntologyBridge 카탈로그에서 첫 매칭 term → 첫 추천 시나리오."""
    # 토큰별로 alias 매칭 시도
    tokens = [t for t in query.replace(",", " ").replace("/", " ").split() if t]
    matched_canonical = None
    for tok in tokens:
        canonical = OntologyBridge.resolve(tok)
        if canonical:
            matched_canonical = canonical
            break
    if matched_canonical is None:
        # 전체 query 한 방에 시도
        matched_canonical = OntologyBridge.resolve(query.strip())

    if matched_canonical is None:
        return ScenarioDraft(
            title="기본 thickness 검증",
            rationale=(
                f'"{query}" 에서 도메인 용어를 찾지 못했습니다. '
                "기본 step (thickness) 으로 안전한 검증을 시작해 보세요. "
                "구체 용어 (예: 실수율, 두께, EDGING) 를 포함하면 더 정확한 추천이 가능합니다."
            ),
            step_id="thickness",
            inputs={"order": {}},
            tags=["fallback", "baseline"],
            confidence=0.2,
            extracted_term=None,
            method="fallback",
        )

    suggestions = OntologyBridge.suggest_scenarios(matched_canonical)
    if not suggestions:
        # 용어는 있지만 추천 시나리오가 카탈로그에 없는 경우 — 영향 step 첫 항목 사용
        steps = OntologyBridge.term_to_steps(matched_canonical)
        first_step = steps[0] if steps else "pipeline_full"
        return ScenarioDraft(
            title=f"{matched_canonical} 기본 검증",
            rationale=(
                f'"{matched_canonical}" 용어가 인식됐지만 사전 정의된 추천이 없어 '
                f"기본 step ({first_step}) 으로 검증합니다."
            ),
            step_id=first_step,
            inputs={},
            tags=[matched_canonical, "fallback"],
            confidence=0.4,
            extracted_term=matched_canonical,
            method="fallback",
        )

    # 첫 추천 시나리오를 ScenarioDraft 로 래핑
    sug = suggestions[0]
    return ScenarioDraft(
        title=sug.title,
        rationale=(
            f'"{matched_canonical}" 용어 매칭. 카탈로그 추천: {sug.rationale}'
        ),
        step_id=sug.step_id,
        inputs=sug.inputs,
        tags=sug.tags + [matched_canonical],
        confidence=0.7,
        extracted_term=matched_canonical,
        method="fallback",
    )


# ─── LLM 경로 (Pydantic AI tool-use) ────────────────────────────────


_AVAILABLE_STEPS_DESC = """
사용 가능한 sandbox step (step_id):
- validator             — DG001~005 검증 (재고 / 사이즈 / 포장단중 / 설계대기량 / 작업기한일)
- productivity          — 활성 공정 누적 실수율 곱
- thickness             — Step 1: CAST_SPEC 룩업 → slabThickness
- width_range           — Step 2: CAST ∩ HR_SPEC ∩ EDGING 폭 범위
- length_range          — Step 3: CAST ∩ HR_SPEC 길이 범위
- second_wgt            — Step 5+6: HR_MIN/MAX_WGT 2D sheet 룩업 (단중 하/상한)
- max_split             — Step 7: A-a 루프 시작점 산정
- split_range           — Step 8: 분할수 고려 단중 범위
- slab_count            — Step 9: Slab 매수 = floor(pendQ/yield/wgt)
- slab_weight           — Step 10: Slab 단중 산정
- final_width_range     — Step 16: 최종 폭 범위
- final_length_range    — Step 17: 최종 길이 범위
- target_size           — Step 18+19: 목표 폭/길이
- pipeline              — validate → productivity → split → count → weight (간단 e2e)
- pipeline_full         — validate → step 1~19 전체 흐름 (가장 풍부)
- plant_mapping_migrate — 마이그 시뮬: 변경 전·후 thickness 룩업 비교

inputs schema (자주 쓰는 키):
- order: { confirmedPlantCd, productTypeCd, gradeCd, customerCd,
           pkgWgtLow/High, orderWgtLow/High, designPendQty/Low/High,
           selectedHrTgtWidth, productivity, stockCode, ... }
- slab:  { currentSplitCount, slabThickness, firstWidthLow/High, firstWgtLow/High, ... }
- rules: { hr: "0.92", hrf: "0.88", anl1: "0.90", edging_wildcard: bool }
- mapping_overrides (plant_mapping_migrate 전용): { "K": {"castCd":"CC2","machineCd":"M2"} }
"""


_SYSTEM_PROMPT = f"""당신은 Slab 설계 시스템 (slab-design Java 21-step 알고리즘) 의 시뮬레이션 시나리오 어시스턴트입니다.

사용자의 한국어 자연어 질의 ("HR 실수율 0.85로 줄이면?", "EDGING wildcard 가 사라지면?") 를 받아
**바로 sandbox 에서 실행 가능한 시나리오** 로 변환합니다.

규칙:
1. step_id 는 반드시 아래 목록에서 선택. 모르면 가장 풍부한 'pipeline_full' 사용.
2. inputs 는 dict 형태. 숫자는 문자열로 (예: "0.85"). 사용자가 명시하지 않은 키는 비워둘 것.
3. 룰 변경 (실수율, edging) → rules 키 사용. 마이그레이션 → plant_mapping_migrate + mapping_overrides.
4. title 은 한국어 ≤30자. rationale 은 1~2문장으로 사용자에게 왜 이 시나리오를 추천하는지 설명.
5. confidence: 모호할수록 낮게 (0.3~0.5), 명확할수록 높게 (0.8~0.95).
6. tags 에는 관련 키워드 2~4개.

{_AVAILABLE_STEPS_DESC}

예시:
- "HR 실수율 0.85" → step_id=pipeline_full, inputs={{rules: {{hr: "0.85"}}}}, tags=[productivity, hr]
- "PlantMapping K → CC2" → step_id=plant_mapping_migrate, inputs={{smCd: "K", productTypeCd: "A001",
   mapping_overrides: {{K: {{castCd: "CC2", machineCd: "M2"}}}}}}
- "포장단중을 10~20으로 좁히면 어떤 주문이 fail?" → step_id=validator,
   inputs={{order: {{pkgWgtLow: "10", pkgWgtHigh: "20"}}}}, tags=[validator, pkg-wgt]
"""


async def _llm_draft(query: str) -> Optional[ScenarioDraft]:
    """LLM 호출. 실패 시 None (caller 가 fallback)."""
    try:
        from pydantic_ai import Agent
        from backend.application.agent.llm_factory import get_model
    except Exception as e:
        logger.warning(f"pydantic_ai unavailable: {e}")
        return None

    try:
        model = get_model()
    except Exception as e:
        logger.warning(f"LLM model not configured: {e}")
        return None

    try:
        agent = Agent(
            model,
            output_type=ScenarioDraft,
            system_prompt=_SYSTEM_PROMPT,
        )
        result = await agent.run(query)
        draft = result.output
        # step_id 안전 검증
        if draft.step_id not in registry.STEP_REGISTRY:
            logger.warning(f"LLM produced invalid step_id={draft.step_id}, falling back")
            return None
        draft.method = "llm"
        # confidence 미설정 보정
        if draft.confidence is None or draft.confidence == 0:
            draft.confidence = 0.8
        return draft
    except Exception as e:
        logger.warning(f"LLM scenario draft failed: {e}")
        return None


# ─── 진입점 ─────────────────────────────────────────────────────────


async def assist(request: AssistRequest) -> ScenarioDraft:
    """자연어 → ScenarioDraft. LLM 우선 + fallback graceful."""
    if request.prefer_llm and os.getenv("SIMULATION_DISABLE_LLM_ASSIST", "0") != "1":
        draft = await _llm_draft(request.natural_language)
        if draft is not None:
            return draft
    return _fallback_draft(request.natural_language)
