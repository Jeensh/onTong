"""Capability 1d — Action Extractor (Sonnet STANDARD tier).

Phase C-1b of authoring expansion plan (see toClaude/modeling/authoring_expansion_plan.md).

Method-level extractor. Unlike JPO/Service/Generic which run on a whole
class file, Action runs on ONE method picked by the user (Q1 decision: 2-stage
UX — class first in tree, then method picked in MainPanel). The schema
focuses on:

- signature + javadoc (caller-visible contract)
- callees (which other methods this method invokes — building blocks)
- side_effects (DB writes, external calls, event publishes — verification target)
- br_refs (linked BR FQNs if the user has pre-mapped any)
- anchors_hint (line-level pointers to interesting fragments for AnchorBinding)

Per plan Q4: TIER=STANDARD — Action extraction is mostly mechanical (read
body, extract calls), unlike Service hypothesis which needs dependency
graph reasoning.

The class-level dispatcher (`generic_class_extractor.extract_from_file`)
does NOT route here. Action extraction is invoked through a dedicated
endpoint that takes (class_fqn, method_name, params_signature) — UI
wiring lands in Phase C-4.

Public API:
    extract_action_from_method(
        class_fqn, method_name, content, *, session_id, turn_no
    ) -> ExtractedAction
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

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
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "code_extractor_action"
TIER = ModelTier.STANDARD
TOOL_BUDGET = 8  # higher — call-site lookup might need a few graph hops


_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "action_extraction.md"


# ── Output schema ────────────────────────────────────────────────────


class ActionParam(BaseModel):
    """One parameter of the method."""

    name: str
    type_simple: str = Field(..., description='Short Java type, e.g. "Order", "BigDecimal"')
    domain_meaning_hint: str | None = Field(
        None,
        description="One-line guess at domain meaning, drawn from Javadoc / @param / inline comment",
    )


class Callee(BaseModel):
    """One method this Action invokes inside its body."""

    receiver_type: str = Field(..., description='Short class name of the receiver, "this" if intra-class')
    method_name: str
    is_repository_call: bool = Field(
        False,
        description="True if receiver type ends with Repository/Dao/Mapper — DB side-effect hint",
    )
    is_external_call: bool = Field(
        False,
        description="True if receiver looks like HTTP/SOAP/messaging client (RestTemplate, WebClient, KafkaTemplate, …)",
    )


class SideEffect(BaseModel):
    """One classified side-effect observable from the body."""

    op: Literal["db_write", "db_read", "external_call", "event_publish", "log_only", "in_memory_only"]
    target_hint: str = Field(..., description='Free-form, e.g. "OrderRepository.save", "OrderCreated event"')


class AnchorHint(BaseModel):
    """One free-form anchor locator the user may later promote to an AnchorBinding."""

    locator: str = Field(..., description='e.g. "if-stmt@line-42", "return@line-99", "literal:0.10"')
    line: int | None = None
    note: str | None = Field(None, description="One-line reason this fragment looks anchor-worthy")


class ExtractedAction(BaseModel):
    """Structured form of one Java method analysed as a domain Action candidate.

    `kind="action"` discriminator. NOT part of the class-level ExtractedClass
    union — Action is method-scoped and invoked through a separate endpoint
    after the user picks a method from a Service/Generic class outline.
    """

    kind: Literal["action"] = "action"
    enclosing_class_fqn: str
    method_name: str
    params: list[ActionParam] = Field(default_factory=list)
    return_type: str
    return_meaning_hint: str | None = Field(
        None,
        description="One-line guess at what the return value represents, from @return / context",
    )
    method_annotations: list[str] = Field(default_factory=list)
    javadoc: str | None = Field(
        None,
        description="Method-level Javadoc joined into one string — Korean preserved verbatim",
    )
    callees: list[Callee] = Field(default_factory=list)
    side_effects: list[SideEffect] = Field(default_factory=list)
    br_refs: list[str] = Field(
        default_factory=list,
        description="Pre-existing BusinessRule FQNs the user has linked (empty on first extraction)",
    )
    anchors_hint: list[AnchorHint] = Field(default_factory=list)
    is_idempotent_guess: bool | None = Field(
        None,
        description="Best guess from body shape — null when unclear",
    )


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, ExtractedAction]:
    return Agent(
        get_authoring_model(TIER),
        output_type=ExtractedAction,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _make_combined_logger(*loggers):
    def combined(record):
        for log in loggers:
            if log is not None:
                log(record)
    return combined


# ── Public API ───────────────────────────────────────────────────────


async def extract_action_from_method(
    class_fqn: str,
    method_name: str,
    method_body_with_signature: str,
    *,
    session_id: str,
    turn_no: int,
    event_pump: ToolEventPump | None = None,
) -> ExtractedAction:
    """Run the Sonnet extractor on one Java method's signature + body.

    Caller responsibilities: hand over the exact slice (signature + Javadoc +
    body) so the LLM doesn't have to navigate the whole file. Receiver class
    FQN is passed separately so the schema's `enclosing_class_fqn` doesn't
    rely on LLM guessing.
    """
    user_prompt = (
        f"Enclosing class FQN: {class_fqn}\n"
        f"Method name: {method_name}\n\n"
        "```java\n"
        f"{method_body_with_signature.rstrip()}\n"
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
        "authoring.action_extractor session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


def reset_caches() -> None:
    """Test helper — drop the prompt cache."""
    _system_prompt.cache_clear()
