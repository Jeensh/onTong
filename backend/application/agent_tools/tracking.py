"""Per-run state for graph tools — budget, dedup, logging, reflection.

`RunTracker` is meant to be created **once per agent run** and passed into
`register_tools(...)`. It enforces:

- `max_calls` — hard cap. Once exceeded, every subsequent tool returns a
  short string nudging the agent to stop and produce its final answer.
- dedup — identical (tool_name, kwargs) pairs return the cached result so
  the agent can re-ask cheaply during reflection.
- logger callbacks — `start_logger_fn` fires *before* a tool runs (for SSE
  progress UX) and `logger_fn` fires *after* with the result/duration.
- `reflect_every` — every Nth call, the tool result is wrapped with a
  `_system_note` nudging the agent to summarize-and-decide before its next
  step (R6 Q1 = B forced reflection).

Note on `RunTracker.exceeded` — pydantic_ai retries on tool errors, so we
don't raise; instead we return a short string the LLM treats as an
observation. This keeps the loop graceful.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
from typing import Any, Callable, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolCallRecord(BaseModel):
    """One tool invocation. Logged + (optionally) persisted by the host."""

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    duration_ms: int = 0
    error: str | None = None
    cached: bool = False


class ToolCallLogger(Protocol):
    """Host callback. Authoring impl writes to `authoring_tool_call_log`."""

    def __call__(self, record: ToolCallRecord) -> None: ...


class ToolStartLogger(Protocol):
    """Host callback fired *before* a tool runs. Powers SSE progress events."""

    def __call__(self, *, tool_name: str, args: dict[str, Any]) -> None: ...


class RunTracker:
    """Per-run budget + dedup + logger plumbing + forced reflection."""

    BUDGET_EXCEEDED_MARKER = (
        "⛔ TOOL_BUDGET_EXCEEDED. You have used your full tool call budget. "
        "DO NOT call any more tools — further calls will raise an exception "
        "and abort this run. Produce your final structured output IMMEDIATELY "
        "with whatever you've gathered. If you genuinely lacked enough info, "
        "lower your confidence accordingly and note the budget limit in "
        "`concerns` (or whatever 'limitations' field your schema has)."
    )

    REFLECT_NOTE = (
        "You've made {n} tool calls so far. Before your next step, write a "
        "1-2 sentence reflection in your reasoning summarizing what you've "
        "learned. Then either produce your final structured output (if you "
        "have enough), or call ONE more tool that closes the biggest gap. "
        "Avoid drift."
    )

    def __init__(
        self,
        *,
        max_calls: int,
        logger_fn: ToolCallLogger | None = None,
        start_logger_fn: ToolStartLogger | None = None,
        dedup: bool = True,
        reflect_every: int | None = 5,
    ) -> None:
        self.max_calls = max_calls
        self.calls = 0
        self._dedup_enabled = dedup
        self._dedup_cache: dict[tuple, Any] = {}
        self._logger_fn = logger_fn
        self._start_logger_fn = start_logger_fn
        self._reflect_every = reflect_every
        self.records: list[ToolCallRecord] = []

    @property
    def exceeded(self) -> bool:
        return self.calls >= self.max_calls

    def make_dedup_key(self, tool_name: str, kwargs: dict[str, Any]) -> tuple:
        try:
            normalized = json.dumps(kwargs, sort_keys=True, default=str)
        except (TypeError, ValueError):
            normalized = repr(kwargs)
        return (tool_name, normalized)

    def get_cached(self, tool_name: str, kwargs: dict[str, Any]) -> tuple[bool, Any]:
        if not self._dedup_enabled:
            return False, None
        key = self.make_dedup_key(tool_name, kwargs)
        if key in self._dedup_cache:
            return True, self._dedup_cache[key]
        return False, None

    def cache(self, tool_name: str, kwargs: dict[str, Any], value: Any) -> None:
        if self._dedup_enabled:
            key = self.make_dedup_key(tool_name, kwargs)
            self._dedup_cache[key] = value

    def record(self, rec: ToolCallRecord) -> None:
        self.calls += 1
        self.records.append(rec)
        if self._logger_fn is not None:
            try:
                self._logger_fn(rec)
            except Exception:  # noqa: BLE001 — logging failures must not break the agent
                logger.exception("agent_tools logger raised; ignoring")

    def emit_start(self, *, tool_name: str, args: dict[str, Any]) -> None:
        if self._start_logger_fn is None:
            return
        try:
            self._start_logger_fn(tool_name=tool_name, args=args)
        except Exception:  # noqa: BLE001
            logger.exception("agent_tools start_logger raised; ignoring")

    def should_reflect_after(self, calls_so_far: int) -> bool:
        """True iff this call lands on a reflection boundary."""
        n = self._reflect_every
        if not n or n <= 0:
            return False
        return calls_so_far > 0 and calls_so_far % n == 0

    def wrap_with_reflect(self, value: Any, calls_so_far: int) -> Any:
        """Return `value` unchanged, OR a {result, _system_note} dict."""
        if not self.should_reflect_after(calls_so_far):
            return value
        return {
            "result": value,
            "_system_note": self.REFLECT_NOTE.format(n=calls_so_far),
        }


def usage_limits_for(max_calls: int, cushion: int = 2):
    """Build a `UsageLimits` matching the run's tool budget — enforced by
    pydantic_ai itself rather than relying on LLM compliance with the soft
    BUDGET_EXCEEDED marker.

    `max_calls` is the **soft** budget (BUDGET_EXCEEDED marker fires on the
    next tool result after this count). `cushion` adds extra calls before
    pydantic_ai raises `UsageLimitExceeded` — gives the LLM a chance to see
    the marker and stop voluntarily before hard abort. Default cushion=2.

    Why a cushion: R6-VAL v2 (2026-05-05) showed cap 6 hitting hard abort
    at call 11 because the LLM committed to one more tool call before
    seeing the marker. Without the cushion the agent run failed entirely;
    with the cushion the LLM gets the marker, then has 1-2 more calls to
    wrap up gracefully if it ignores the marker.

    Imported lazily to keep this module pydantic_ai-version-agnostic at
    import time.
    """
    from pydantic_ai.usage import UsageLimits

    return UsageLimits(tool_calls_limit=max_calls + cushion)


def summarize(value: Any, max_len: int = 200) -> str:
    """Compact human-readable summary used in trace records."""
    if value is None:
        return "null"
    if isinstance(value, str):
        return value[:max_len]
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        keys = ", ".join(list(value.keys())[:5])
        return f"dict({keys})"
    s = repr(value)
    return s[:max_len]


def make_tracked(
    fn: Callable[..., Any], *, tool_name: str, tracker: RunTracker
) -> Callable[..., Any]:
    """Wrap a plain (sync) tool fn with budget / dedup / start+end logging /
    forced reflection.

    The wrapper preserves `fn`'s `__signature__` and `__annotations__` so
    pydantic_ai can derive the JSON schema for the LLM (it needs to know
    the parameter names + types). Without this, the LLM sees `**kwargs`
    and never passes any arguments.

    Tools are sync because all our graph stores are sync SQLite reads.
    pydantic_ai accepts both sync and async tool callables.
    """
    import time

    sig = inspect.signature(fn)
    annotations = dict(getattr(fn, "__annotations__", {}))

    def wrapper(**kwargs: Any) -> Any:
        if tracker.exceeded:
            tracker.record(
                ToolCallRecord(
                    tool_name=tool_name,
                    args=kwargs,
                    result_summary="(budget exceeded)",
                    duration_ms=0,
                    cached=False,
                )
            )
            return tracker.BUDGET_EXCEEDED_MARKER

        # Fire start event (powers SSE progress UX) BEFORE doing any work
        # so the user sees the tool spinner the moment the LLM commits to
        # a call.
        tracker.emit_start(tool_name=tool_name, args=kwargs)

        cached_hit, cached_val = tracker.get_cached(tool_name, kwargs)
        if cached_hit:
            tracker.record(
                ToolCallRecord(
                    tool_name=tool_name,
                    args=kwargs,
                    result_summary=summarize(cached_val) + " (cached)",
                    duration_ms=0,
                    cached=True,
                )
            )
            # Wrap with reflection nudge if we landed on a boundary.
            return tracker.wrap_with_reflect(cached_val, tracker.calls)

        started = time.perf_counter()
        try:
            value = fn(**kwargs)
            duration_ms = int((time.perf_counter() - started) * 1000)
            tracker.cache(tool_name, kwargs, value)
            tracker.record(
                ToolCallRecord(
                    tool_name=tool_name,
                    args=kwargs,
                    result_summary=summarize(value),
                    duration_ms=duration_ms,
                )
            )
            return tracker.wrap_with_reflect(value, tracker.calls)
        except Exception as exc:  # noqa: BLE001 — surface error to the LLM as observation
            duration_ms = int((time.perf_counter() - started) * 1000)
            tracker.record(
                ToolCallRecord(
                    tool_name=tool_name,
                    args=kwargs,
                    result_summary="(error)",
                    duration_ms=duration_ms,
                    error=str(exc),
                )
            )
            return f"[TOOL_ERROR {tool_name}] {exc}"

    # Preserve original signature so pydantic_ai derives a real JSON schema.
    functools.update_wrapper(wrapper, fn)
    wrapper.__name__ = tool_name
    wrapper.__qualname__ = tool_name
    wrapper.__signature__ = sig  # type: ignore[attr-defined]
    wrapper.__annotations__ = annotations
    return wrapper


__all__ = [
    "RunTracker",
    "ToolCallLogger",
    "ToolCallRecord",
    "ToolStartLogger",
    "make_tracked",
    "summarize",
    "usage_limits_for",
]
