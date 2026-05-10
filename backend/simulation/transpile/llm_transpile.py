"""LLM 기반 Java → Python step 함수 변환.

Pydantic AI Agent + structured output (PythonStepDraft).
LLM 미가용 시 deterministic stub 반환 (graceful fallback).

scenario_assistant.py 의 LLM 호출 패턴을 미러.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .parser import JavaMethodInfo, summarize_for_llm

logger = logging.getLogger(__name__)


# ─── 라인별 신뢰도 영역 (Phase J) ──────────────────────────────────


class LineOrigin(BaseModel):
    """파이썬 소스의 한 라인이 어디서 왔는지 + 신뢰도.

    UI 색상 매핑 (제안):
      - det  (≥0.9, 결정적)        : 🟢 녹색 — 자바 원본을 1:1 변환
      - llm  (0.5~0.9, LLM 추론)   : 🟡 황색 — AI 가 의미 추측한 부분
      - llm  (0.2~0.5)             : 🟠 주황 — 신뢰도 낮음, 검토 권장
      - stub (<0.2)                : 🔴 빨강 — TODO / 사람 수정 필요
      - human                      : ⚪ 회색 — 사람이 손으로 보정
    """

    line: int = Field(..., description="1-based 라인 번호 (python_source 기준)")
    kind: Literal["det", "llm", "stub", "human"] = Field(
        ..., description="det=결정적 변환, llm=AI 추론, stub=미완성 placeholder, human=사람 보정"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="라인 단위 신뢰도 0~1")
    note: Optional[str] = Field(None, description="이유/주의사항 (예: '외부 서비스 stub')")


class PythonStepDraft(BaseModel):
    """LLM 이 생성한 파이썬 step 함수 초안."""

    step_id: str = Field(..., description="snake_case 권장 step ID (예: 'thickness')")
    function_name: str = Field(..., description="파이썬 함수명 (대개 step_id 와 동일)")
    python_source: str = Field(
        ...,
        description=(
            "독립 실행 가능한 파이썬 함수 정의. inputs: dict → outputs: dict 시그니처."
            " 표준 라이브러리 + Decimal/datetime/dataclasses 만 사용."
        ),
    )
    imports: list[str] = Field(default_factory=list, description="필요한 import 라인 (from x import y).")
    rationale: str = Field(..., description="변환 시 적용한 매핑 결정 1~3문장 설명 (한국어 OK).")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="변환 신뢰도 — 메서드 전체 평균 (0~1).")
    method: str = Field("fallback", description="'llm' 또는 'fallback'.")
    line_origins: list[LineOrigin] = Field(
        default_factory=list,
        description=(
            "라인별 신뢰도 영역 (Phase J). LLM 출력 후 # [det] / # [llm:0.85] / # [stub] "
            "주석을 parse 해서 채움. 비어있으면 라인 단위 시각화 불가 → confidence 1개만 사용."
        ),
    )


@dataclass
class TranspileRequest:
    info: JavaMethodInfo
    target_step_id: Optional[str] = None  # None → LLM 이 추천
    prefer_llm: bool = True


_SYSTEM_PROMPT = """당신은 자바 메서드를 파이썬 step 함수로 변환하는 전문가입니다.
대상은 Slab 설계 (slab-design) 같은 제조업 비즈니스 룰 메서드입니다.

규칙:
1. 출력 시그니처는 반드시 `def <function_name>(inputs: dict) -> dict:` 형태.
2. 입력 inputs 는 dict 로 받고, 자바 매개변수 (entity / DTO) 를 dict 키로 매핑.
   - 예: order.getConfirmedPlantCd() → inputs["order"]["confirmedPlantCd"]
3. 자바 의존 서비스 (ex. CastSpecService.lookup) 는 파이썬에서 inputs 의 stub 필드로 받거나
   주석으로 "TODO: lookup 함수 주입 필요" 명시.
4. AlgorithmException → ValueError 또는 dict 반환 ({"error": {"code": ..., "message": ...}}).
5. 자료형: 자바 BigDecimal → Decimal, java.time.LocalDate → datetime.date.
6. 부동소수점 비교 / division 은 반드시 Decimal 사용. 매직 넘버는 그대로 유지 (legacy DNA 보존).
7. Python 코드는 표준 라이브러리만 사용. 외부 패키지 금지.
8. 주석은 한국어 OK. 자바 javadoc 은 docstring 으로 옮길 것.
9. step_id 는 snake_case 권장. function_name 은 보통 step_id 와 동일.
10. confidence: 자바가 단순할수록 높게 (0.85+), 외부 서비스 의존 많을수록 낮게 (0.3~0.6).
11. rationale 에는 어떤 자바 호출을 어떻게 stub 으로 옮겼는지 1~3문장 설명.
12. ★ 각 코드 라인 끝에 origin 주석 부착 (라인별 신뢰도 시각화용):
    - 자바 원본을 1:1 직역한 라인          → `# [det]`
    - LLM 이 의미를 추론한 라인            → `# [llm:0.85]`  (점수 0~1, 추론 확신도)
    - 외부 서비스 stub / TODO 라인         → `# [stub]`
    - 짧은 라인 (def, return, 빈 줄, docstring 시작/끝 따옴표 등) 은 주석 생략 OK.
    - 예:
        def thickness(inputs: dict) -> dict:                  # [det]
            order = inputs["order"]                            # [det]
            sm = order["smPlantCd"]                            # [det]
            cast_cd = LOOKUP_PLANT_MAPPING.get(sm)             # [llm:0.7]   (Java 의 PlantMappingService 호출 매핑)
            if cast_cd is None:                                # [llm:0.7]
                raise ValueError("DG101")                      # [det]
            slab_thickness = inputs.get("cast_spec", {}).get(  # [stub]    (CastSpecRepo 주입 필요)
                "slabThickness"
            )
            return {"slab": {"slabThickness": slab_thickness}} # [det]
"""


async def _llm_transpile(request: TranspileRequest) -> Optional[PythonStepDraft]:
    """LLM 호출. 실패 시 None."""
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

    summary = summarize_for_llm(request.info)
    target = request.target_step_id or _guess_step_id(request.info)
    user_prompt = (
        f"다음 자바 메서드를 파이썬 step 함수로 변환하세요.\n\n"
        f"권장 step_id: {target}\n\n"
        f"{summary}"
    )

    try:
        agent = Agent(
            model,
            output_type=PythonStepDraft,
            system_prompt=_SYSTEM_PROMPT,
        )
        result = await agent.run(user_prompt)
        draft = result.output
        draft.method = "llm"
        if not draft.step_id:
            draft.step_id = target
        if not draft.function_name:
            draft.function_name = draft.step_id
        if draft.confidence is None or draft.confidence == 0:
            draft.confidence = 0.7
        return draft
    except Exception as e:
        logger.warning(f"LLM transpile failed: {e}")
        return None


def _guess_step_id(info: JavaMethodInfo) -> str:
    """클래스/메서드 이름에서 step_id 추론. 'SdThicknessAction.execute' → 'thickness'."""
    base = info.class_name
    if base.startswith("Sd"):
        base = base[2:]
    if base.endswith("Action"):
        base = base[: -len("Action")]
    elif base.endswith("Service"):
        base = base[: -len("Service")]
    # CamelCase → snake_case
    out: list[str] = []
    for i, ch in enumerate(base):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out) or info.method_name.lower()


def _fallback_draft(request: TranspileRequest) -> PythonStepDraft:
    """LLM 미가용 시 deterministic stub. 자바 본문은 주석으로 보존."""
    info = request.info
    step = request.target_step_id or _guess_step_id(info)
    body_lines = info.body_source.splitlines()
    body_comment = "\n    ".join(f"# {ln}" for ln in body_lines[:60])
    src = (
        f'def {step}(inputs: dict) -> dict:\n'
        f'    """LLM fallback — 자바 원본은 아래 주석 참조.\n'
        f'\n'
        f'    원본: {info.file_path}:{info.signature_line}\n'
        f'    클래스/메서드: {info.class_name}.{info.method_name}\n'
        f'    """\n'
        f'    # === 자바 원본 본문 (자동 변환 미완) ===\n'
        f'    {body_comment}\n'
        f'    # === 자동 변환 미완 — 수작업 미러링 필요 ===\n'
        f'    return {{"transpile": "fallback", "step_id": "{step}",\n'
        f'            "java_class": "{info.class_name}",\n'
        f'            "java_method": "{info.method_name}",\n'
        f'            "note": "LLM 미가용 — 수작업 변환 필요"}}\n'
    )
    return PythonStepDraft(
        step_id=step,
        function_name=step,
        python_source=src,
        imports=[],
        rationale=(
            "LLM 미가용 환경 — 자바 본문을 파이썬 주석으로 그대로 보존한 stub 생성."
            " 실제 구현은 운영자가 수작업 미러링 후 sandbox/steps/ 에 저장 필요."
        ),
        confidence=0.15,
        method="fallback",
    )


import re

# `# [det]` / `# [llm:0.85]` / `# [llm]` / `# [stub]` 형태 origin 주석 매칭
_ORIGIN_RE = re.compile(r"#\s*\[(det|llm|stub|human)(?::([0-9]*\.?[0-9]+))?\]")


def parse_line_origins(python_source: str) -> list[LineOrigin]:
    """python_source 의 라인별 # [origin] 주석 → LineOrigin 리스트 추출.

    주석 없는 라인은 추가하지 않음 (UI 가 default 처리).
    fallback stub 의 자바 주석 라인은 자동으로 stub 으로 분류.
    """
    origins: list[LineOrigin] = []
    for idx, line in enumerate(python_source.splitlines(), start=1):
        m = _ORIGIN_RE.search(line)
        if m is None:
            continue
        kind = m.group(1)
        score_raw = m.group(2)
        try:
            score = float(score_raw) if score_raw else None
        except ValueError:
            score = None

        if kind == "det":
            confidence = 1.0
        elif kind == "stub":
            confidence = 0.0
        elif kind == "human":
            confidence = 1.0
        else:  # llm
            confidence = score if score is not None else 0.7

        # 주석 텍스트의 [태그] 뒷부분을 note 로
        note = None
        tail = line[m.end():].strip()
        if tail:
            note = tail.lstrip("#").strip(" ()").strip() or None

        origins.append(LineOrigin(line=idx, kind=kind, confidence=confidence, note=note))
    return origins


def _attach_fallback_origins(draft: PythonStepDraft) -> None:
    """fallback stub 의 자바 주석 라인을 모두 stub origin 으로 분류.

    fallback 은 LLM 호출 안 했으므로 주석 없음 → 자바 본문 영역만 stub 표식.
    """
    if draft.line_origins:
        return  # 이미 채워졌으면 노터치
    origins: list[LineOrigin] = []
    in_java_block = False
    for idx, line in enumerate(draft.python_source.splitlines(), start=1):
        if "=== 자바 원본 본문" in line:
            in_java_block = True
            origins.append(LineOrigin(line=idx, kind="stub", confidence=0.0,
                                       note="자바 원본 (수작업 변환 필요)"))
            continue
        if "=== 자동 변환 미완" in line:
            in_java_block = False
            origins.append(LineOrigin(line=idx, kind="stub", confidence=0.0))
            continue
        if in_java_block:
            origins.append(LineOrigin(line=idx, kind="stub", confidence=0.0))
    draft.line_origins = origins


async def transpile_method(request: TranspileRequest) -> PythonStepDraft:
    """자바 메서드 → 파이썬 step 초안. LLM 우선 + fallback graceful.

    Phase J: line_origins 자동 추출 — LLM 응답의 # [origin] 주석을 파싱.
    """
    draft: Optional[PythonStepDraft] = None
    if request.prefer_llm and os.getenv("SIMULATION_DISABLE_LLM_TRANSPILE", "0") != "1":
        draft = await _llm_transpile(request)

    if draft is None:
        draft = _fallback_draft(request)
        _attach_fallback_origins(draft)
        return draft

    # LLM 출력은 # [origin] 주석을 포함 — 파싱해서 line_origins 채움
    if not draft.line_origins:
        draft.line_origins = parse_line_origins(draft.python_source)
    return draft
