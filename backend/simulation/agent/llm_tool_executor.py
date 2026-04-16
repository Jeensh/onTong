"""SimulationToolExecutor — Anthropic claude-sonnet-4-6 tool_use 기반 ReAct 에이전트 루프.

모든 시나리오 에이전트(A/B/C)와 커스텀 에이전트가 이 executor에 위임한다.
LLM이 어떤 툴을 언제 호출할지 스스로 결정하는 진짜 에이전트 루프를 구현한다.

스트리밍 SSE 이벤트 흐름:
    thinking → tool_call → tool_result → (반복) → content_delta → done

기존 시나리오별 하드코딩 시퀀스를 대체한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Any

logger = logging.getLogger(__name__)

# 최대 tool_use 반복 횟수 (무한 루프 방지)
MAX_ITERATIONS = 10


class SimulationToolExecutor:
    """
    Anthropic claude-sonnet-4-6 API로 ReAct 에이전트 루프를 실행하고,
    각 단계를 SSE 이벤트로 스트리밍한다.

    Args:
        tool_names: 이 에이전트가 사용 가능한 툴 이름 목록
        system_prompt: 에이전트 역할을 정의하는 시스템 프롬프트 (한국어)
        scenario: 시나리오 식별자 (graph_state/slab_state 이벤트 생성 결정)
        initial_context: LLM 첫 호출 전 추가할 컨텍스트 (예: 추출된 order_id)
    """

    def __init__(
        self,
        tool_names: list[str],
        system_prompt: str,
        scenario: str = "",
        initial_context: dict | None = None,
    ) -> None:
        self.tool_names = tool_names
        self.system_prompt = system_prompt
        self.scenario = scenario
        self.initial_context = initial_context or {}

    async def run(self, message: str) -> AsyncGenerator[dict, None]:
        """
        메시지를 입력받아 SSE 이벤트를 비동기 제너레이터로 반환.

        Yields:
            {"event": str, "data": dict}
        """
        from backend.simulation.tools.tool_registry import get_registry
        from backend.core.config import settings

        registry = get_registry()

        # ── Anthropic 클라이언트 초기화 ──────────────────────────────────────
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        except (ImportError, Exception) as e:
            logger.warning(f"Anthropic SDK 사용 불가, 폴백 모드로 전환: {e}")
            async for evt in self._fallback_run(message, registry):
                yield evt
            return

        # ── 툴 스키마 준비 ───────────────────────────────────────────────────
        tool_schemas = registry.get_anthropic_schemas(self.tool_names)
        if not tool_schemas:
            logger.warning(f"No tool schemas found for: {self.tool_names}")

        # ── 초기 thinking 이벤트 ─────────────────────────────────────────────
        yield {
            "event": "thinking",
            "data": {"message": "요청을 분석하고 있습니다..."},
        }

        # ── 메시지 히스토리 초기화 ───────────────────────────────────────────
        # initial_context가 있으면 첫 메시지에 포함
        user_content = message
        if self.initial_context:
            ctx_json = json.dumps(self.initial_context, ensure_ascii=False, indent=2)
            user_content = f"{message}\n\n## 컨텍스트\n```json\n{ctx_json}\n```"

        messages: list[dict] = [{"role": "user", "content": user_content}]

        # ── ReAct 루프 ───────────────────────────────────────────────────────
        iteration = 0
        final_text = ""

        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.debug(f"[{self.scenario}] ReAct iteration {iteration}")

            # LLM 호출 (스트리밍)
            try:
                response = await client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=tool_schemas if tool_schemas else anthropic.NOT_GIVEN,
                    messages=messages,
                )
            except Exception as e:
                logger.error(f"Anthropic API 호출 실패: {e}")
                yield {
                    "event": "error",
                    "data": {"message": f"LLM 호출 오류: {str(e)}"},
                }
                yield {"event": "done", "data": {}}
                return

            # ── 응답 처리 ────────────────────────────────────────────────────
            has_tool_use = any(
                block.type == "tool_use" for block in response.content
            )
            text_blocks = [
                block for block in response.content if block.type == "text"
            ]
            tool_use_blocks = [
                block for block in response.content if block.type == "tool_use"
            ]

            # 텍스트 응답이 있으면 스트리밍
            for text_block in text_blocks:
                text = text_block.text
                if text.strip():
                    # 텍스트를 청크 단위로 스트리밍
                    for chunk in _chunk_text(text, 20):
                        yield {"event": "content_delta", "data": {"delta": chunk}}
                        await asyncio.sleep(0.015)
                    final_text += text

            # 툴 호출이 없으면 루프 종료
            if not has_tool_use or response.stop_reason == "end_turn":
                break

            # ── 툴 실행 ──────────────────────────────────────────────────────
            tool_results: list[dict] = []

            # 병렬 툴 호출: 여러 tool_use 블록을 asyncio.gather로 동시 실행
            if len(tool_use_blocks) > 1:
                yield {
                    "event": "thinking",
                    "data": {
                        "message": (
                            f"{len(tool_use_blocks)}개 툴을 병렬로 실행합니다: "
                            f"{', '.join(b.name for b in tool_use_blocks)}"
                        )
                    },
                }

                # 각 툴의 tool_call 이벤트를 먼저 emit
                for tool_block in tool_use_blocks:
                    yield {
                        "event": "tool_call",
                        "data": {
                            "tool": tool_block.name,
                            "args": tool_block.input,
                        },
                    }

                # 병렬 실행
                async def _exec_tool(tb) -> tuple[str, str, Any]:
                    try:
                        result = await registry.execute_async(tb.name, tb.input)
                        return tb.id, tb.name, result
                    except Exception as e:
                        logger.error(f"Tool {tb.name} 실행 오류: {e}")
                        return tb.id, tb.name, {"error": str(e)}

                parallel_results = await asyncio.gather(
                    *[_exec_tool(tb) for tb in tool_use_blocks]
                )

                for tool_id, tool_name, result in parallel_results:
                    yield {
                        "event": "tool_result",
                        "data": {"tool": tool_name, "result": result},
                    }
                    # 시각화 이벤트 생성
                    async for viz_evt in _make_viz_events(tool_name, result, self.scenario):
                        yield viz_evt
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            else:
                # 단일 툴 실행
                tool_block = tool_use_blocks[0]
                tool_name = tool_block.name
                tool_args = tool_block.input

                yield {
                    "event": "thinking",
                    "data": {"message": f"'{tool_name}' 툴을 실행합니다..."},
                }
                yield {
                    "event": "tool_call",
                    "data": {"tool": tool_name, "args": tool_args},
                }

                try:
                    result = await registry.execute_async(tool_name, tool_args)
                except Exception as e:
                    logger.error(f"Tool {tool_name} 실행 오류: {e}")
                    result = {"error": str(e)}

                yield {
                    "event": "tool_result",
                    "data": {"tool": tool_name, "result": result},
                }

                # 시각화 이벤트 생성 (graph_state, slab_state)
                async for viz_evt in _make_viz_events(tool_name, result, self.scenario):
                    yield viz_evt

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # ── 메시지 히스토리 업데이트 ─────────────────────────────────────
            # assistant 메시지 추가 (tool_use 블록 포함)
            messages.append({
                "role": "assistant",
                "content": [
                    _content_block_to_dict(block) for block in response.content
                ],
            })
            # tool_result 메시지 추가
            messages.append({
                "role": "user",
                "content": tool_results,
            })

        yield {
            "event": "done",
            "data": {
                "scenario": self.scenario,
                "iterations": iteration,
            },
        }

    async def _fallback_run(
        self,
        message: str,
        registry,
    ) -> AsyncGenerator[dict, None]:
        """Anthropic API 사용 불가 시 폴백: PydanticAI/Ollama 시도 후 규칙 기반 응답."""
        from backend.simulation.tools.tool_registry import get_registry
        import re

        yield {
            "event": "thinking",
            "data": {"message": "LLM 연결을 확인하고 있습니다... (오프라인 모드)"},
        }
        await asyncio.sleep(0.3)

        # PydanticAI + Ollama 시도
        try:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model

            tool_list = ", ".join(self.tool_names)
            prompt = (
                f"사용자 질문: {message}\n\n"
                f"사용 가능한 도구: {tool_list}\n\n"
                "위 맥락에서 Slab 설계 분석을 수행하고 한국어로 답변하세요."
            )
            llm_agent = Agent(get_model(), system_prompt=self.system_prompt)
            async with llm_agent.run_stream(prompt) as result:
                async for delta in result.stream_text(delta=True):
                    yield {"event": "content_delta", "data": {"delta": delta}}

        except Exception as e:
            logger.warning(f"PydanticAI 폴백도 실패: {e}")
            # 최종 폴백: 안내 메시지
            fallback_msg = (
                "⚠️ **LLM 연결 오류**\n\n"
                "Anthropic API 키를 설정하거나 Ollama를 실행해주세요.\n\n"
                "```\nexport ANTHROPIC_API_KEY=sk-ant-...\n```\n"
                "또는 `.env` 파일에 `ANTHROPIC_API_KEY`를 설정하면 "
                "AI가 툴을 선택하고 분석을 수행합니다."
            )
            for chunk in _chunk_text(fallback_msg, 20):
                yield {"event": "content_delta", "data": {"delta": chunk}}
                await asyncio.sleep(0.02)

        yield {"event": "done", "data": {"scenario": self.scenario, "fallback": True}}


# ── 헬퍼 함수들 ──────────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int = 20) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def _content_block_to_dict(block) -> dict:
    """Anthropic SDK ContentBlock → JSON 직렬화 가능 dict."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {"type": block.type}


async def _make_viz_events(
    tool_name: str,
    result: Any,
    scenario: str,
) -> AsyncGenerator[dict, None]:
    """툴 결과에서 graph_state, slab_state 시각화 이벤트를 생성.

    기존 하드코딩 에이전트가 emit하던 visualization 이벤트를 대체한다.
    """
    if not isinstance(result, dict):
        return

    # 온톨로지 그래프 순회 결과 → graph_state
    if tool_name in ("find_edging_specs_for_order", "find_orders_by_rolling_line"):
        traversal = result.get("traversal", [])
        highlighted_edges = result.get("highlighted_edges", [])
        if traversal or highlighted_edges:
            yield {
                "event": "graph_state",
                "data": {
                    "traversal": traversal,
                    "highlighted_edges": highlighted_edges,
                },
            }

    # 폭 범위 시뮬레이션 결과 → slab_state
    if tool_name == "simulate_width_range":
        order_id = result.get("order_id", "ORDER")
        feasible = result.get("feasible", True)
        yield {
            "event": "slab_state",
            "data": {
                "slabs": [
                    {
                        "id": order_id,
                        "status": "normal" if feasible else "error",
                        "label": result.get("reason", ""),
                    }
                ]
            },
        }

    # 폭 조정 제안 결과 → slab_state (조정 후 정상 상태)
    if tool_name == "suggest_adjusted_width":
        suggested = result.get("suggested_width")
        if suggested:
            yield {
                "event": "slab_state",
                "data": {
                    "slabs": [
                        {
                            "status": "adjusted",
                            "width": suggested,
                            "label": f"조정 후: {suggested}mm",
                        }
                    ]
                },
            }

    # 파급 효과 배치 분석 결과 → slab_state
    if tool_name in ("batch_simulate_width_impact", "analyze_edging_change_ripple"):
        details = result.get("details", [])
        if details:
            slabs = []
            for impact in details:
                status = "normal"
                if not impact.get("new_feasible") and impact.get("original_feasible"):
                    status = "error"
                slabs.append({
                    "id": impact.get("order_id", ""),
                    "status": status,
                    "width": impact.get("target_width"),
                    "label": (
                        f"{impact.get('order_id', '')}\n"
                        f"{impact.get('target_width')}mm\n"
                        f"{'❌' if status == 'error' else '✅'} {impact.get('impact', '')}"
                    ),
                })
            if slabs:
                yield {"event": "slab_state", "data": {"slabs": slabs}}

    # 분할수 최적화 결과 → slab_state
    if tool_name == "simulate_split_combinations":
        optimal = result.get("recommended_split_count")
        order_id = result.get("order_id", "")
        satisfaction = result.get("recommended_satisfaction_rate", 0)
        if optimal:
            yield {
                "event": "slab_state",
                "data": {
                    "slabs": [
                        {
                            "id": order_id,
                            "status": "optimal",
                            "split_count": optimal,
                            "animating": True,
                            "label": (
                                f"{order_id}\n최적 분할수 {optimal}개\n"
                                f"만족률 {satisfaction:.0%}"
                            ),
                        }
                    ]
                },
            }
