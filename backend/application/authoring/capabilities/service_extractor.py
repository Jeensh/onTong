"""Capability 1c — Service Extractor (Sonnet HARD tier).

Phase C-1a of authoring expansion plan (see toClaude/modeling/authoring_expansion_plan.md).

Sibling of `code_extractor.extract_jpo_from_file` and
`generic_class_extractor.extract_generic_from_file` for Spring service-layer
classes (`@Service`, `@RestController`, `@Controller`, `@Component`).

The schema is richer than ExtractedGenericClass because Service hypothesis
needs to reason about: (a) what this class depends on, (b) what it exposes
to the outside world (REST/event/method-level), and (c) transactional
boundaries. Per plan Q4, TIER=HARD — Service hypothesis needs dependency
graph reasoning that benefits from the stronger model.

Per plan Q2: "Single class first" — this extractor handles ONE Service
class. Feature bundles (Service + Repository + DTO) are Phase D.

Public API:
    extract_service_from_file(path, content, *, session_id, turn_no) -> ExtractedService
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

CAPABILITY_NAME = "code_extractor_service"
TIER = ModelTier.HARD
TOOL_BUDGET = 6

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "service_extraction.md"


# ── Output schema ────────────────────────────────────────────────────


class ServiceDependency(BaseModel):
    """One @Autowired / @Inject / constructor-injected dependency."""

    field_name: str = Field(..., description='Field name (camelCase)')
    type_simple: str = Field(..., description='Dependency type short name, e.g. "OrderRepository"')
    injection_style: Literal["field", "constructor", "setter", "unknown"] = "unknown"
    is_repository: bool = Field(
        False,
        description="True if the type ends with Repository / Dao / Mapper — strong signal for data layer",
    )


class ServiceMethod(BaseModel):
    """One public method exposed by this Service class.

    Body is excluded — body-level extraction belongs to ExtractedAction.
    """

    name: str
    params: list[str] = Field(default_factory=list, description='"type name" pairs')
    return_type: str
    annotations: list[str] = Field(default_factory=list)
    javadoc_first_line: str | None = None
    is_transactional: bool = Field(False, description="@Transactional on this method or its class")


class RestEndpoint(BaseModel):
    """One HTTP entry point (@RequestMapping family) on this class."""

    http_method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "ANY"] = "ANY"
    path: str = Field(..., description="Combined class+method path, e.g. /orders/{id}")
    handler_method: str = Field(..., description="Java method name that handles this endpoint")


class ExtractedService(BaseModel):
    """Structured form of one Spring service-layer Java class.

    `kind="service"` discriminator slots into the ExtractedClass union next
    to "jpo", "generic", and (future) "action". Downstream Service
    hypothesis lives in Phase C-2.
    """

    kind: Literal["service"] = "service"
    package: str
    class_name: str
    class_annotations: list[str] = Field(
        default_factory=list,
        description='Class-level annotations, e.g. ["@Service", "@Transactional(readOnly = true)"]',
    )
    dependencies: list[ServiceDependency] = Field(
        default_factory=list,
        description="Collaborators injected into this Service — the dependency-graph signal",
    )
    exposed_methods: list[ServiceMethod] = Field(
        default_factory=list,
        description="Public methods this Service exposes (excludes inherited Object methods)",
    )
    transaction_boundary_methods: list[str] = Field(
        default_factory=list,
        description="Subset of exposed_methods that are @Transactional — write boundary signal",
    )
    rest_endpoints: list[RestEndpoint] = Field(
        default_factory=list,
        description="HTTP entry points on this class (empty when not a controller)",
    )
    publishes_events: list[str] = Field(
        default_factory=list,
        description='Event type simple names this Service publishes via ApplicationEventPublisher',
    )
    class_docstring: str | None = None


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, ExtractedService]:
    return Agent(
        get_authoring_model(TIER),
        output_type=ExtractedService,
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


async def extract_service_from_file(
    path: str,
    content: str,
    *,
    session_id: str,
    turn_no: int,
    event_pump: ToolEventPump | None = None,
) -> ExtractedService:
    """Run the HARD-tier extractor on one Spring service-layer Java file.

    Mirror of `extract_jpo_from_file`. The dispatcher in
    `code_extractor.extract_from_file` picks this path when the source carries
    `@Service`, `@RestController`, `@Controller`, or `@Component`.
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
        "authoring.service_extractor session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


def reset_caches() -> None:
    """Test helper — drop the prompt cache."""
    _system_prompt.cache_clear()
