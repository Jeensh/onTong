"""Skill system — composable, reusable agent capabilities.

Each Skill is an independent building block that agents can invoke.
Skills support two consumption patterns:
  1. Code orchestration: agent calls ctx.run_skill("name", ...) directly
  2. LLM tool-use: agent passes skill.to_tool_schema() to LLM function calling

Hook system (PreSkill / PostSkill):
  Hooks intercept skill execution for validation, transformation, and feedback injection.
  - PreSkill hooks run before execute(): can modify kwargs or block execution
  - PostSkill hooks run after execute(): can transform results or inject feedback
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    """Permission level required to execute a skill."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


class CompletionStatus(str, Enum):
    """Completion status for skill results (bible-aligned)."""
    DONE = "done"                      # successful, no issues
    DONE_WITH_CONCERNS = "concerns"    # successful but with warnings
    BLOCKED = "blocked"                # cannot proceed (permission, missing data)
    NEEDS_CONTEXT = "needs_context"    # needs user clarification before proceeding


# Maps each skill to its required permission level.
# Skills not listed default to READ.
SKILL_PERMISSIONS: dict[str, PermissionLevel] = {
    "wiki_search": PermissionLevel.READ,
    "wiki_read": PermissionLevel.READ,
    "llm_generate": PermissionLevel.READ,
    "query_augment": PermissionLevel.READ,
    "conflict_check": PermissionLevel.READ,
    "wiki_write": PermissionLevel.WRITE,
    "wiki_edit": PermissionLevel.WRITE,
}

# Maps permission levels to required user roles.
# A user must have at least one of the listed roles.
PERMISSION_REQUIRED_ROLES: dict[PermissionLevel, list[str]] = {
    PermissionLevel.READ: [],  # all users
    PermissionLevel.WRITE: ["admin", "editor"],
    PermissionLevel.EXECUTE: ["admin"],
}


@dataclass
class SkillResult:
    """Unified return type from any skill execution."""

    data: Any = None
    success: bool = True
    error: str = ""
    feedback: str = ""      # non-fatal warnings (e.g., deprecated docs, partial results)
    retry_hint: str = ""    # suggested retry action for the user
    status: CompletionStatus = CompletionStatus.DONE  # bible-aligned completion protocol

    def __post_init__(self) -> None:
        """Auto-derive status from success/feedback if not explicitly set."""
        if not self.success and self.status == CompletionStatus.DONE:
            self.status = CompletionStatus.BLOCKED
        elif self.success and self.feedback and self.status == CompletionStatus.DONE:
            self.status = CompletionStatus.DONE_WITH_CONCERNS


# ── Hook System ──────────────────────────────────────────────────────


@dataclass
class PreHookResult:
    """Result from a pre-skill hook."""
    allow: bool = True        # False = block execution
    modified_kwargs: dict[str, Any] | None = None  # replace kwargs if set
    block_reason: str = ""    # reason for blocking (shown in SkillResult.error)


@runtime_checkable
class SkillHook(Protocol):
    """Interface for pre/post skill hooks."""

    name: str

    def should_run(self, skill_name: str, ctx: Any) -> bool:
        """Return True if this hook applies to the given skill invocation."""
        ...


@runtime_checkable
class PreSkillHook(SkillHook, Protocol):
    """Runs before skill.execute(). Can validate/transform input or block execution."""

    async def before(self, skill_name: str, ctx: Any, kwargs: dict[str, Any]) -> PreHookResult:
        ...


@runtime_checkable
class PostSkillHook(SkillHook, Protocol):
    """Runs after skill.execute(). Can transform result or inject feedback."""

    async def after(self, skill_name: str, ctx: Any, result: SkillResult) -> SkillResult:
        ...


class HookRegistry:
    """Central registry for pre/post skill hooks."""

    def __init__(self) -> None:
        self._pre_hooks: list[PreSkillHook] = []
        self._post_hooks: list[PostSkillHook] = []

    def register_pre(self, hook: PreSkillHook) -> None:
        self._pre_hooks.append(hook)
        logger.info(f"Registered pre-skill hook: {hook.name}")

    def register_post(self, hook: PostSkillHook) -> None:
        self._post_hooks.append(hook)
        logger.info(f"Registered post-skill hook: {hook.name}")

    async def run_pre_hooks(self, skill_name: str, ctx: Any, kwargs: dict[str, Any]) -> PreHookResult:
        """Run all applicable pre-hooks. First block wins."""
        for hook in self._pre_hooks:
            if not hook.should_run(skill_name, ctx):
                continue
            try:
                result = await hook.before(skill_name, ctx, kwargs)
                if not result.allow:
                    logger.info(f"Pre-hook '{hook.name}' blocked skill '{skill_name}': {result.block_reason}")
                    return result
                if result.modified_kwargs is not None:
                    kwargs.update(result.modified_kwargs)
            except Exception:
                logger.warning(f"Pre-hook '{hook.name}' failed for skill '{skill_name}'", exc_info=True)
        return PreHookResult(allow=True)

    async def run_post_hooks(self, skill_name: str, ctx: Any, result: SkillResult) -> SkillResult:
        """Run all applicable post-hooks. Each can transform the result."""
        for hook in self._post_hooks:
            if not hook.should_run(skill_name, ctx):
                continue
            try:
                result = await hook.after(skill_name, ctx, result)
            except Exception:
                logger.warning(f"Post-hook '{hook.name}' failed for skill '{skill_name}'", exc_info=True)
        return result

    def list_hooks(self) -> dict[str, list[str]]:
        return {
            "pre": [h.name for h in self._pre_hooks],
            "post": [h.name for h in self._post_hooks],
        }


hook_registry = HookRegistry()


# ── Skill Protocol & Registry ───────────────────────────────────────


@runtime_checkable
class Skill(Protocol):
    """Interface every skill must implement."""

    name: str
    description: str  # human-readable, also used in LLM tool schemas

    async def execute(self, ctx: Any, **kwargs: Any) -> SkillResult:
        """Run the skill and return a structured result."""
        ...

    def to_tool_schema(self) -> dict:
        """Return OpenAI function-calling compatible tool schema."""
        ...


class SkillRegistry:
    """Central registry for all skills. Singleton at module level."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def to_tool_schemas(self) -> list[dict]:
        """Return all skills as OpenAI function-calling tool schemas."""
        return [s.to_tool_schema() for s in self._skills.values()]


skill_registry = SkillRegistry()
