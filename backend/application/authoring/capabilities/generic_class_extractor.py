"""Capability 1b — Generic Java Class Extractor (Sonnet, STANDARD tier).

Phase B of authoring expansion plan (see toClaude/modeling/authoring_expansion_plan.md).

Sibling of `code_extractor.extract_jpo_from_file` for non-@Entity Java classes.
Lightweight: class-level annotations + method/field outlines only, no body.
Downstream capabilities (hypothesis / interview / …) currently support only
ExtractedJpo — Generic output is the "extraction done, hypothesis on roadmap"
fallback so users can pick any class without hitting a wall.

Tier: STANDARD (per plan Q4 — Entity/Action=STANDARD, Service=HARD when
service-specific extractor lands in Phase C).

Public API:
    extract_generic_from_file(path, content, *, session_id, turn_no) -> ExtractedGenericClass
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
from backend.application.authoring.capabilities.code_extractor import (
    ExtractedJpo,
    _usage_from_result,
)
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "code_extractor_generic"
TIER = ModelTier.STANDARD
TOOL_BUDGET = 5

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "generic_extraction.md"


# ── Output schema ────────────────────────────────────────────────────


class MethodSig(BaseModel):
    """One method's signature outline. Body is intentionally excluded for cost."""

    name: str = Field(..., description="Method name as written (camelCase)")
    params: list[str] = Field(
        default_factory=list,
        description='"type name" pairs in source order, e.g. ["String orderId", "int qty"]',
    )
    return_type: str = Field(..., description='Short return type, e.g. "void", "Optional<Order>"')
    annotations: list[str] = Field(
        default_factory=list,
        description='Method-level annotations, e.g. ["@Transactional", "@RequestMapping(\\"/orders\\")"]',
    )
    javadoc_first_line: str | None = Field(
        None,
        description="First non-empty line of the method's Javadoc — Korean preserved",
    )


class FieldSig(BaseModel):
    """One field outline. Used to identify dependencies (@Autowired) and config."""

    name: str = Field(..., description="Field name (camelCase)")
    java_type: str = Field(..., description='Short Java type, e.g. "CustomerService"')
    annotations: list[str] = Field(
        default_factory=list,
        description='Field-level annotations, e.g. ["@Autowired"]',
    )


class ExtractedGenericClass(BaseModel):
    """Lightweight outline of any Java class — Entity / Service / Component / POJO.

    Discriminator field `kind="generic"` so this can be part of the
    ExtractedClass union with ExtractedJpo (kind="jpo") and future
    ExtractedService / ExtractedAction (Phase C).
    """

    kind: Literal["generic"] = "generic"
    package: str
    class_name: str
    class_annotations: list[str] = Field(
        default_factory=list,
        description='Class-level annotations, e.g. ["@Service", "@RestController"]',
    )
    methods_outline: list[MethodSig] = Field(default_factory=list)
    fields_outline: list[FieldSig] = Field(default_factory=list)
    class_docstring: str | None = Field(
        None,
        description="Class-level Javadoc block joined into one string (preserve newlines as \\n)",
    )


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, ExtractedGenericClass]:
    return Agent(
        get_authoring_model(TIER),
        output_type=ExtractedGenericClass,
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


async def extract_generic_from_file(
    path: str,
    content: str,
    *,
    session_id: str,
    turn_no: int,
    event_pump: ToolEventPump | None = None,
) -> ExtractedGenericClass:
    """Run the Sonnet extractor on one non-Entity Java file's content.

    Mirror of `extract_jpo_from_file` for any Java class. The dispatcher in
    `code_extractor.extract_from_file` picks JPO vs generic based on presence
    of `@Entity`.
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
        "authoring.generic_extractor session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


def reset_caches() -> None:
    """Test helper — drop the prompt cache."""
    _system_prompt.cache_clear()


# ── Union of all extracted class kinds ───────────────────────────────


from typing import Annotated, Union  # noqa: E402

from pydantic import Field  # noqa: E402

# Phase B union (Phase C will extend with ExtractedService / ExtractedAction).
# Pydantic v2 discriminated union — `kind` field tags the variant. Use this
# as the response type in API routes that hand back extraction output so
# the frontend can branch cleanly without sniffing fields.
ExtractedClass = Annotated[
    Union[ExtractedJpo, ExtractedGenericClass],
    Field(discriminator="kind"),
]


# ── Dispatcher ───────────────────────────────────────────────────────


import re as _re  # noqa: E402

# Match @Entity from either javax.persistence or jakarta.persistence, with or
# without a fully-qualified name. Crude on purpose: the LLM is the final arbiter,
# the dispatcher just picks which prompt + schema to use.
_ENTITY_ANNOTATION_RE = _re.compile(
    r"@(?:(?:javax|jakarta)\.persistence\.)?Entity\b"
)


def is_jpa_entity_source(content: str) -> bool:
    """True if the Java source carries an @Entity annotation."""
    return bool(_ENTITY_ANNOTATION_RE.search(content))


async def extract_from_file(
    path: str,
    content: str,
    *,
    session_id: str,
    turn_no: int,
    event_pump: ToolEventPump | None = None,
) -> "ExtractedJpo | ExtractedGenericClass":
    """Pick JPO or Generic extractor based on @Entity presence in the source.

    Phase B addition — replaces calling `extract_jpo_from_file` directly
    everywhere. Existing callers that hand-pick the JPO path keep working;
    new code should call this dispatcher so non-Entity classes don't
    silently get parsed by the JPA-specific prompt.
    """
    if is_jpa_entity_source(content):
        # Local import to keep this module's top-level imports lean and to
        # avoid loading the JPO agent infrastructure when only the generic
        # path is needed.
        from backend.application.authoring.capabilities.code_extractor import (
            extract_jpo_from_file,
        )
        return await extract_jpo_from_file(
            path,
            content,
            session_id=session_id,
            turn_no=turn_no,
            event_pump=event_pump,
        )
    return await extract_generic_from_file(
        path,
        content,
        session_id=session_id,
        turn_no=turn_no,
        event_pump=event_pump,
    )
