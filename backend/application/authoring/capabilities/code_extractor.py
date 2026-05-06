"""Capability 1 — Code Extractor (Sonnet, STANDARD tier).

Round 5 Step 13 §1: "코드 추출 (JPO/Service/Action 자동 분석)".

This S2 implementation covers JPO files only. Service and Action extraction
will be added as sibling functions when their downstream capabilities need them.

Public API:
    extract_jpo_from_file(path, content, *, session_id, turn_no) -> ExtractedJpo
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.application.agent_tools import RunTracker, ToolEventPump, register_tools
from backend.application.agent_tools.registry import PRESETS
from backend.application.agent_tools.tracking import usage_limits_for
from backend.application.authoring import cost as cost_mod
from backend.application.authoring.agent_tool_adapter import (
    AuthoringOperationalSession,
    AuthoringToolLogger,
)
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier, TokenUsage

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "code_extractor"
TIER = ModelTier.STANDARD
TOOL_BUDGET = 5  # cap 1 max_calls (HTML §3 권장 = minimal context)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "code_extraction.md"


# ── Output schema ────────────────────────────────────────────────────


class CodeColumn(BaseModel):
    """One Java field that maps to a DB column."""

    name: str = Field(..., description="Java field name (camelCase)")
    db_column: str = Field(..., description='Value of @Column(name="...")')
    java_type: str = Field(..., description='Short Java type, e.g. "BigDecimal"')
    db_length: int | None = None
    db_precision: int | None = None
    db_scale: int | None = None
    is_pk: bool = False
    comment: str | None = Field(
        None,
        description="Verbatim inline comment on the field line — Korean preserved",
    )


class ExtractedJpo(BaseModel):
    """Structured form of one JPA entity Java file."""

    package: str
    class_name: str
    table_name: str
    pk_class: str | None = None
    pk_columns: list[CodeColumn] = Field(default_factory=list)
    regular_columns: list[CodeColumn] = Field(default_factory=list)
    class_docstring: str | None = None


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, ExtractedJpo]:
    """Per-call agent — needed so each run gets its own tool wrappers
    (closures over RunTracker / session)."""
    return Agent(
        get_authoring_model(TIER),
        output_type=ExtractedJpo,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    """Cache the system prompt (Layer 1 per design §12.3)."""
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _make_combined_logger(*loggers):
    def combined(record):
        for log in loggers:
            if log is not None:
                log(record)
    return combined


def _usage_from_result(result_usage) -> TokenUsage:
    """Convert pydantic_ai RunUsage → our TokenUsage.

    pydantic_ai exposes details via `details` dict on `RunUsage`; cache hits/writes
    arrive as `cache_read_tokens` / `cache_creation_tokens` in Anthropic responses.
    """
    details = getattr(result_usage, "details", None) or {}
    return TokenUsage(
        input_tokens=int(getattr(result_usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(result_usage, "output_tokens", 0) or 0),
        cache_read_tokens=int(details.get("cache_read_input_tokens", 0) or 0),
        cache_write_tokens=int(details.get("cache_creation_input_tokens", 0) or 0),
    )


# ── Public API ───────────────────────────────────────────────────────


async def extract_jpo_from_file(
    path: str,
    content: str,
    *,
    session_id: str,
    turn_no: int,
    event_pump: ToolEventPump | None = None,
) -> ExtractedJpo:
    """Run the Sonnet extractor on one Java JPO file's content.

    `path` is informational (kept for logging / future error context); the LLM
    sees `content` plus a small graph tool budget for context (R6 §3 cap 1
    = 5 tools, minimal). When `event_pump` is supplied, tool start/end events
    are forwarded for SSE streaming UX.
    """
    user_prompt = (
        f"File: {path}\n\n"
        "```java\n"
        f"{content.rstrip()}\n"
        "```\n"
    )

    agent = _build_agent()
    db_logger = AuthoringToolLogger(
        session_id=session_id, turn_no=turn_no, capability=CAPABILITY_NAME
    )
    tracker = RunTracker(
        max_calls=TOOL_BUDGET,
        logger_fn=_make_combined_logger(
            db_logger, event_pump.end if event_pump else None
        ),
        start_logger_fn=event_pump.start if event_pump else None,
        # Cap 1's call budget is small (5); reflection is overhead.
        reflect_every=None,
    )
    op_session = AuthoringOperationalSession(
        session_id=session_id, turn_no=turn_no, capability=CAPABILITY_NAME
    )
    register_tools(
        agent,
        allowed=PRESETS["authoring_extract"],
        tracker=tracker,
        operational_session=op_session,
    )

    with cost_mod.measure() as t:
        result = await agent.run(
            user_prompt,
            model_settings=_settings(),
            usage_limits=usage_limits_for(TOOL_BUDGET),
        )

    usage = _usage_from_result(result.usage())
    cost_mod.log_call(
        session_id=session_id,
        turn_no=turn_no,
        capability=CAPABILITY_NAME,
        tier=TIER,
        model_id=get_model_id(TIER),
        usage=usage,
        duration_ms=t["elapsed_ms"],
    )
    logger.info(
        "authoring.code_extractor session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


def reset_caches() -> None:
    """Test helper — drop the prompt cache."""
    _system_prompt.cache_clear()
