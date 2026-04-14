"""AgentContext — runtime context passed to agents and skills per request."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.core.schemas import ChatRequest, ClarificationRequestEvent, ThinkingStepEvent
from backend.core.session import SessionStore

logger = logging.getLogger(__name__)

# Allowed skills per intent — restricts which skills can be invoked.
# Skills not in the list for the current intent are blocked at run_skill().
INTENT_ALLOWED_SKILLS: dict[str, list[str]] = {
    "question": ["wiki_search", "wiki_read", "llm_generate", "conflict_check", "query_augment"],
    "write": ["wiki_search", "wiki_read", "wiki_write", "llm_generate"],
    "edit": ["wiki_search", "wiki_read", "wiki_edit", "llm_generate"],
}


@dataclass
class AgentContext:
    """Runtime context for a single agent request.

    Constructed once per request in api/agent.py, threaded to agents and skills.
    """

    request: ChatRequest
    chroma: Any  # ChromaWrapper (avoid import cycle)
    storage: Any  # StorageProvider (avoid import cycle)
    session_store: SessionStore
    history: list[dict] = field(default_factory=list)
    attached_context: str = ""
    augmented_query: str | None = None
    user_roles: list[str] = field(default_factory=lambda: ["admin"])
    user_skill: Any = None        # SkillMeta | None — matched user-facing skill
    skill_context: Any = None     # SkillContext | None — structured 6-layer context
    conflict_store: Any = None    # ConflictStore | None — for registering detected conflicts
    intent_action: str = "question"  # current intent action for allowed-tools filtering
    username: str = ""               # authenticated user name (for per-user persona)
    meta_index: Any = None               # MetadataIndex | None — for status lookups
    # L3 Path-Aware RAG: path preferences from disambiguation
    path_preference: str | None = None       # current query's path preference
    path_preferences: list[str] = field(default_factory=list)  # session-accumulated
    # ACL domain scoping — computed from authenticated user at request time
    user_scope: list[str] | None = None      # e.g. ["@userId", "group1", "role1", "all"]

    @staticmethod
    def emit_thinking(step: str, status: str, label: str, detail: str = "") -> str:
        """Format a ThinkingStepEvent as an SSE string."""
        evt = ThinkingStepEvent(step=step, status=status, label=label, detail=detail)
        return f"event: thinking_step\ndata: {evt.model_dump_json()}\n\n"

    @staticmethod
    def sse(event: str, data: str) -> str:
        """Format a generic SSE event string."""
        return f"event: {event}\ndata: {data}\n\n"

    @staticmethod
    def emit_clarification(question: str, options: list[str] | None = None, context: str = "") -> str:
        """Format a ClarificationRequestEvent as SSE. Used when NEEDS_CONTEXT."""
        evt = ClarificationRequestEvent(
            request_id=str(uuid.uuid4()),
            question=question,
            options=options or [],
            context=context,
        )
        return f"event: clarification_request\ndata: {evt.model_dump_json()}\n\n"

    async def run_skill(self, skill_name: str, **kwargs: Any) -> Any:
        """Look up and execute a skill by name.

        Pipeline:
          1. Check allowed-tools for the current intent
          2. Check permission level vs user roles
          3. Run pre-skill hooks (can block or modify kwargs)
          4. Execute the skill
          5. Run post-skill hooks (can transform result)
        Returns SkillResult on success, or SkillResult(success=False) if blocked.
        """
        from backend.application.agent.skill import (
            CompletionStatus,
            PERMISSION_REQUIRED_ROLES,
            SKILL_PERMISSIONS,
            PermissionLevel,
            SkillResult,
            hook_registry,
            skill_registry,
        )

        # 1. Check allowed-tools: per-skill override takes precedence over intent default
        if self.user_skill and hasattr(self.user_skill, "allowed_tools") and self.user_skill.allowed_tools:
            allowed = self.user_skill.allowed_tools
        else:
            allowed = INTENT_ALLOWED_SKILLS.get(self.intent_action)
        if allowed and skill_name not in allowed:
            logger.warning(f"Skill '{skill_name}' blocked for intent '{self.intent_action}'")
            return SkillResult(
                data=None, success=False,
                error=f"Skill '{skill_name}' not allowed for intent '{self.intent_action}'",
                status=CompletionStatus.BLOCKED,
            )

        # 2. Check permission level vs user roles
        perm = SKILL_PERMISSIONS.get(skill_name, PermissionLevel.READ)
        required_roles = PERMISSION_REQUIRED_ROLES.get(perm, [])
        if required_roles and not any(r in self.user_roles for r in required_roles):
            logger.warning(
                f"Skill '{skill_name}' requires {perm.value} permission "
                f"(roles: {required_roles}), user has: {self.user_roles}"
            )
            return SkillResult(
                data=None, success=False,
                error=f"권한 부족: '{skill_name}' 스킬은 {perm.value} 권한이 필요합니다.",
                retry_hint="관리자에게 편집 권한을 요청해주세요.",
                status=CompletionStatus.BLOCKED,
            )

        skill = skill_registry.get(skill_name)
        if skill is None:
            logger.warning(f"Skill not found: {skill_name}")
            return SkillResult(data=None, success=False, error=f"Skill '{skill_name}' not found",
                               status=CompletionStatus.BLOCKED)

        # 3. Run pre-skill hooks
        pre_result = await hook_registry.run_pre_hooks(skill_name, self, kwargs)
        if not pre_result.allow:
            return SkillResult(
                data=None, success=False,
                error=pre_result.block_reason or f"Blocked by pre-hook for '{skill_name}'",
                status=CompletionStatus.BLOCKED,
            )
        if pre_result.modified_kwargs is not None:
            kwargs.update(pre_result.modified_kwargs)

        # 4. Execute
        result = await skill.execute(self, **kwargs)

        # 5. Run post-skill hooks
        result = await hook_registry.run_post_hooks(skill_name, self, result)

        return result
