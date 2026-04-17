"""Agent Builder Agent — LLM 기반 대화로 Custom Agent 요구사항 수집.

사용자와 자유 대화를 통해 Slab 설계 도메인 Agent 정의를 수집하고,
충분한 정보가 모이면 [AGENT_DEFINITION]...[/AGENT_DEFINITION] 블록을 출력하여
agent_ready SSE 이벤트로 프론트엔드에 전달한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# 사용 가능한 Slab 설계 도구 설명
_TOOLS_DESCRIPTION = """
사용 가능한 Slab 설계 도구:
- get_order_info: 주문 ID로 주문 정보(폭/길이/단중/분할수 등) 조회
- simulate_width_range: 목표폭 + 열연라인으로 폭 범위 산정 가능 여부 시뮬레이션
- suggest_adjusted_width: DG320 에러 주문에 대해 가능한 폭으로 자동 조정 제안
- get_equipment_spec: 연주/열연 설비 기준 (폭/길이 범위, Edging 능력) 조회
- simulate_edging_impact: Edging 능력 변경 시 특정 주문의 폭 범위 영향 분석
- optimize_split_count: 주문에 대해 단중 만족률이 최대인 분할수 최적화
- calculate_slab_design: 목표폭/길이/두께/단중/분할수로 설계 프로세스 전체 계산 (SEQ 1~16)
"""

_SYSTEM_PROMPT = f"""당신은 POSCO Slab 설계 도메인 전문 AI Agent 설계사입니다.
사용자가 원하는 Custom Agent를 만들 수 있도록 대화를 통해 필요한 정보를 수집하세요.

{_TOOLS_DESCRIPTION}

수집해야 할 정보:
1. 해결하고 싶은 Slab 설계 문제 또는 목표
2. 필요한 도구 (위 목록에서 선택)
3. 에이전트 이름과 간단한 설명
4. 사용자가 실제로 입력할 예시 질문

대화 원칙:
- 한 번에 하나씩 자연스럽게 질문하세요
- 사용자의 답변을 바탕으로 다음 질문을 이어가세요
- 이미 파악된 정보는 다시 묻지 마세요
- 3~5회 대화 후 충분한 정보가 모이면 에이전트 정의를 생성하세요

모든 정보가 수집되면, 반드시 아래 형식으로 에이전트 정의를 출력하세요:

[AGENT_DEFINITION]
{{
  "name": "에이전트 이름 (간결하게)",
  "description": "1-2줄 설명",
  "icon": "관련 이모지 하나",
  "color": "#hex색상 (예: #6366f1)",
  "system_prompt": "이 에이전트의 역할과 동작 방식에 대한 LLM 지시문 (한국어, 3-5문장)",
  "available_tools": ["tool_id1", "tool_id2"],
  "example_prompt": "사용자가 실제로 입력할 예시 질문"
}}
[/AGENT_DEFINITION]
"""


async def run_agent_builder(
    message: str,
    history: list[dict],
) -> AsyncGenerator[dict, None]:
    """
    LLM 기반 에이전트 빌더 대화.
    agent_ready 이벤트로 완성된 에이전트 정의를 전달한다.
    """
    try:
        from pydantic_ai import Agent
        from backend.application.agent.llm_factory import get_model

        # 대화 컨텍스트 구성
        conversation = ""
        for msg in history:
            role = "사용자" if msg.get("role") == "user" else "어시스턴트"
            conversation += f"{role}: {msg.get('content', '')}\n\n"
        conversation += f"사용자: {message}\n\n어시스턴트:"

        yield {
            "event": "thinking",
            "data": {"message": "요청을 분석하고 에이전트 요구사항을 파악하고 있습니다..."},
        }
        await asyncio.sleep(0.2)

        agent = Agent(get_model(), system_prompt=_SYSTEM_PROMPT)

        full_text = ""
        async with agent.run_stream(conversation) as result:
            async for delta in result.stream_text(delta=True):
                full_text += delta
                # [AGENT_DEFINITION] 블록 이전까지만 실시간 전송
                if "[AGENT_DEFINITION]" not in full_text:
                    yield {"event": "content_delta", "data": {"delta": delta}}
                elif "[/AGENT_DEFINITION]" not in full_text:
                    # 블록 시작 이후는 전송 보류 (완성 대기)
                    pass

        # agent_ready 이벤트 추출
        agent_def = _extract_agent_definition(full_text)
        if agent_def:
            # 블록 이전 텍스트 전송
            before_block = full_text.split("[AGENT_DEFINITION]")[0].strip()
            if before_block and not history:
                pass  # 이미 stream으로 전송됨

            yield {
                "event": "content_delta",
                "data": {"delta": "\n\n✅ **에이전트 정의가 완성되었습니다!** 아래에서 확인 후 등록하세요."},
            }
            yield {
                "event": "agent_ready",
                "data": {"agent": agent_def},
            }
        else:
            # 정의 블록 없으면 전체 텍스트가 대화 응답
            if "[AGENT_DEFINITION]" in full_text:
                pass  # 블록 추출 실패 - 이미 부분 전송됨

        yield {"event": "done", "data": {}}

    except ImportError:
        # LLM 미설정 시 스크립트 방식으로 폴백
        async for evt in _fallback_script_builder(message, history):
            yield evt


def _extract_agent_definition(text: str) -> dict | None:
    """텍스트에서 [AGENT_DEFINITION]...[/AGENT_DEFINITION] 블록 파싱."""
    pattern = r"\[AGENT_DEFINITION\](.*?)\[/AGENT_DEFINITION\]"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    try:
        raw = match.group(1).strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"Agent definition JSON parse error: {e}")
        return None


async def _fallback_script_builder(
    message: str,
    history: list[dict],
) -> AsyncGenerator[dict, None]:
    """LLM 미사용 시 단계별 스크립트 방식 폴백."""
    step = len([m for m in history if m.get("role") == "user"])

    if step == 0:
        response = (
            "안녕하세요! Slab 설계 Custom Agent를 만들어 드리겠습니다. 😊\n\n"
            "**어떤 Slab 설계 문제를 해결하고 싶으신가요?**\n\n"
            "예시:\n"
            "- 특정 주문의 폭 범위 에러를 자동으로 진단하고 싶다\n"
            "- Edging 기준 변경 시 영향받는 주문을 빠르게 파악하고 싶다\n"
            "- 단중 만족률이 낮은 주문의 최적 분할수를 찾고 싶다"
        )
    elif step == 1:
        response = (
            f"'{message}'라는 목적을 파악했습니다! 👍\n\n"
            "**어떤 도구가 필요할 것 같으신가요?** (여러 개 선택 가능)\n\n"
            "| 도구 | 설명 |\n|------|------|\n"
            "| get_order_info | 주문 정보 조회 |\n"
            "| simulate_width_range | 폭 범위 시뮬레이션 |\n"
            "| suggest_adjusted_width | 폭 조정 제안 |\n"
            "| get_equipment_spec | 설비 기준 조회 |\n"
            "| simulate_edging_impact | Edging 파급효과 |\n"
            "| optimize_split_count | 분할수 최적화 |\n"
            "| calculate_slab_design | 설계 전체 계산 |\n\n"
            "잘 모르겠다면 '전부' 또는 목적에 맞는 것을 말씀해주세요."
        )
    elif step == 2:
        response = (
            "좋습니다! 마지막으로 **실제로 사용할 예시 질문**을 한 가지 알려주세요.\n\n"
            "예시: '주문 ORD-2024-0042의 폭 범위 에러 원인을 찾아줘'"
        )
    else:
        # 충분한 정보 수집 → 에이전트 정의 생성
        user_msgs = [m["content"] for m in history if m.get("role") == "user"]
        goal = user_msgs[0] if user_msgs else message
        tools_msg = user_msgs[1] if len(user_msgs) > 1 else ""
        example = message

        # 도구 파싱
        all_tools = [
            "get_order_info", "simulate_width_range", "suggest_adjusted_width",
            "get_equipment_spec", "simulate_edging_impact", "optimize_split_count",
            "calculate_slab_design",
        ]
        selected_tools = [t for t in all_tools if t in tools_msg.lower().replace("-", "_")] or all_tools[:3]

        agent_def = {
            "name": f"Custom Agent — {goal[:20]}",
            "description": goal[:80],
            "icon": "🤖",
            "color": "#6366f1",
            "system_prompt": (
                f"당신은 POSCO Slab 설계 전문 AI 에이전트입니다. "
                f"목표: {goal}. "
                f"사용자의 질문에 대해 선택된 Slab 설계 도구를 활용하여 정확하고 실용적인 답변을 제공하세요. "
                f"결과는 한국어로 명확하게 설명하고, 구체적인 수치와 근거를 포함하세요."
            ),
            "available_tools": selected_tools,
            "example_prompt": example,
            "created_by": "chat",
        }

        response = "✅ **에이전트 정의가 완성되었습니다!** 아래에서 확인 후 등록하세요."

        async for delta in _stream_text(response):
            yield {"event": "content_delta", "data": {"delta": delta}}

        yield {"event": "agent_ready", "data": {"agent": agent_def}}
        yield {"event": "done", "data": {}}
        return

    async for delta in _stream_text(response):
        yield {"event": "content_delta", "data": {"delta": delta}}
    yield {"event": "done", "data": {}}


async def _stream_text(text: str, chunk_size: int = 8) -> AsyncGenerator[str, None]:
    """텍스트를 청크 단위로 스트리밍."""
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
        await asyncio.sleep(0.02)
