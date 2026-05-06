"""Registry — wire selected agent tools onto a `pydantic_ai.Agent`.

Single entry point:

    from backend.application.agent_tools import register_tools, RunTracker

    tracker = RunTracker(max_calls=8, logger_fn=my_logger)
    register_tools(
        agent,
        allowed={"code_lookup", "code_search", "find_callers"},
        tracker=tracker,
        operational_session=None,
    )

Each tool name in `allowed` must exist in one of the four sub-modules
(`code_tools`, `ontology_tools`, `mapping_tools`, operational). Unknown
names raise ValueError.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from pydantic_ai import Agent

from backend.application.agent_tools import (
    code_tools,
    mapping_tools,
    ontology_tools,
    operational,
)
from backend.application.agent_tools.tracking import RunTracker, make_tracked

logger = logging.getLogger(__name__)


# All tool names known to this package.
_ALL_TOOLS: dict[str, Any] = {
    **code_tools.ALL_CODE_TOOLS,
    **ontology_tools.ALL_ONTOLOGY_TOOLS,
    **mapping_tools.ALL_MAPPING_TOOLS,
    # Operational tools are constructed at registration time so they can
    # close over the host session — listed here for the allowlist check
    # only.
}
_OPERATIONAL_NAMES = set(operational.ALL_OPERATIONAL_TOOLS)


def all_tool_names() -> set[str]:
    """All tool names supported by this registry (incl. operational)."""
    return set(_ALL_TOOLS.keys()) | _OPERATIONAL_NAMES


def validate_allowlist(allowed: Iterable[str]) -> None:
    unknown = set(allowed) - all_tool_names()
    if unknown:
        raise ValueError(
            f"Unknown agent tool name(s): {sorted(unknown)}. "
            f"Known: {sorted(all_tool_names())}"
        )


def register_tools(
    agent: Agent,
    *,
    allowed: Iterable[str],
    tracker: RunTracker,
    operational_session: operational.OperationalSession | None = None,
) -> list[str]:
    """Register the requested tools onto `agent`. Returns the list of names
    actually wired (in registration order).

    `operational_session` is required IFF an operational tool is in `allowed`.
    For pure graph-only agents pass None.
    """
    allowed_set = set(allowed)
    validate_allowlist(allowed_set)

    # Operational tools need a session.
    needs_session = bool(allowed_set & _OPERATIONAL_NAMES)
    if needs_session and operational_session is None:
        operational_session = operational.NullOperationalSession()

    registered: list[str] = []

    # Wire pure graph tools.
    for name, fn in _ALL_TOOLS.items():
        if name not in allowed_set:
            continue
        wrapped = make_tracked(fn, tool_name=name, tracker=tracker)
        agent.tool_plain(wrapped)
        registered.append(name)

    # Wire operational tools (closure over session).
    if "note_observation" in allowed_set:
        fn = operational.make_note_observation(operational_session)  # type: ignore[arg-type]
        wrapped = make_tracked(fn, tool_name="note_observation", tracker=tracker)
        agent.tool_plain(wrapped)
        registered.append("note_observation")

    if "request_user_input" in allowed_set:
        fn = operational.make_request_user_input(operational_session)  # type: ignore[arg-type]
        wrapped = make_tracked(fn, tool_name="request_user_input", tracker=tracker)
        agent.tool_plain(wrapped)
        registered.append("request_user_input")

    logger.info(
        "agent_tools registered %d/%d tools max_calls=%d",
        len(registered),
        len(allowed_set),
        tracker.max_calls,
    )
    return registered


# Recommended per-capability allowlists (Authoring AI presets).
# Cross-cutting clients can ignore these and pick their own subset.
PRESETS: dict[str, set[str]] = {
    # Cap 5 (gap_detector) + Cap 6 (option_proposer) — full graph access
    "authoring_full": (
        set(code_tools.ALL_CODE_TOOLS.keys())
        | set(ontology_tools.ALL_ONTOLOGY_TOOLS.keys())
        | set(mapping_tools.ALL_MAPPING_TOOLS.keys())
        | {"note_observation"}
    ),
    # Cap 1 (code_extractor) — minimal graph context (5 tools)
    "authoring_extract": {
        "code_lookup",
        "code_search",
        "find_related_jpos",
        "get_method_body",
        "note_observation",
    },
    # Cap 2 (hypothesize) — extract + ontology cross-checks (10 tools)
    "authoring_hypothesize": {
        "code_lookup",
        "code_search",
        "find_subclasses",
        "find_implementations",
        "find_related_jpos",
        "find_in_same_package",
        "domain_search",
        "find_terms_in_domain",
        "find_existing_mapping",
        "note_observation",
    },
    # Cap 7 (pattern_checker) — domain-only (5 tools)
    "authoring_pattern_check": {
        "domain_search",
        "term_lookup",
        "find_terms_in_domain",
        "find_term_realizations",
        "note_observation",
    },
    # Cap 11 (next_entity picker) — code-side graph + ontology dedup (6 tools)
    "authoring_pick_next": {
        "find_related_jpos",
        "find_in_same_package",
        "code_search",
        "domain_search",
        "find_existing_mapping",
        "note_observation",
    },
    # Cap 3 (interview) / Cap 8 (naming) — name-collision check only
    "authoring_naming": {
        "domain_search",
        "find_terms_in_domain",
        "term_lookup",
    },
}


__all__ = [
    "register_tools",
    "all_tool_names",
    "validate_allowlist",
    "PRESETS",
]
