"""LLMGenerateSkill — unified LLM call with semaphore concurrency control.

Uses Pydantic AI's LiteLLM provider internally while maintaining the same
SkillResult interface for backward compatibility with ctx.run_skill().
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import litellm

from backend.core.config import settings
from backend.core.schemas import TokenUsage
from backend.application.agent.skill import SkillResult

logger = logging.getLogger(__name__)

_llm_semaphore: asyncio.Semaphore | None = None


def _get_llm_semaphore() -> asyncio.Semaphore:
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(settings.llm_semaphore_limit)
    return _llm_semaphore


class LLMGenerateSkill:
    """Unified LLM call skill — retains litellm for raw message passing.

    This skill is the bridge between the old ctx.run_skill("llm_generate", ...)
    pattern and the underlying LLM. It keeps litellm for streaming and tool-calling
    support that Pydantic AI's Agent doesn't expose at the raw message level.

    Other skills and rag_agent.py have been migrated to use Pydantic AI directly
    for their specific LLM calls. This skill remains for:
    - Streaming final answers in _handle_qa() (via ctx.run_skill)
    - Any future code that needs raw message-level LLM access
    """
    name = "llm_generate"
    description = "LLM으로 텍스트를 생성합니다"

    async def execute(
        self,
        ctx: Any,
        *,
        messages: list[dict] | None = None,
        stream: bool = False,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        model: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> SkillResult:
        if not messages:
            return SkillResult(data=None, success=False, error="messages required")

        target_model = model or settings.litellm_model

        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        sem = _get_llm_semaphore()

        if stream:
            return await self._stream_call(sem, kwargs)
        else:
            return await self._blocking_call(sem, kwargs)

    async def _blocking_call(self, sem: asyncio.Semaphore, kwargs: dict) -> SkillResult:
        try:
            async with sem:
                response = await litellm.acompletion(**kwargs)

            msg = response.choices[0].message
            usage = getattr(response, "usage", None)
            token_usage = TokenUsage(
                input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            )

            data: dict[str, Any] = {
                "content": msg.content or "",
                "usage": token_usage,
            }
            # Include tool_calls if present (for ReAct loop)
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                data["tool_calls"] = msg.tool_calls
                data["message"] = msg

            return SkillResult(data=data)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return SkillResult(data=None, success=False, error=str(e))

    async def _stream_call(self, sem: asyncio.Semaphore, kwargs: dict) -> SkillResult:
        try:
            await sem.acquire()
            try:
                response = await litellm.acompletion(**kwargs)
            except Exception:
                sem.release()
                raise

            async def chunk_generator():
                total_tokens = 0
                try:
                    async for chunk in response:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            total_tokens += 1
                            yield delta.content
                finally:
                    sem.release()

            return SkillResult(data={"chunks": chunk_generator()})

        except Exception as e:
            logger.error(f"LLM stream call failed: {e}")
            return SkillResult(data=None, success=False, error=str(e))

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "description": "LLM 메시지 배열",
                            "items": {"type": "object"},
                        },
                        "max_tokens": {"type": "integer", "default": 2000},
                        "temperature": {"type": "number", "default": 0.3},
                    },
                    "required": ["messages"],
                },
            },
        }
