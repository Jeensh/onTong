"""AG-3-3: PreSkill/PostSkill hook system tests."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass
from typing import Any


def _import_skill_module():
    """Import skill module with stubs to avoid heavy dependencies."""
    import sys
    # Stub out heavy deps if not available
    for mod in [
        "pydantic_settings",
        "backend.core.config",
        "backend.infrastructure.vectordb.chroma",
    ]:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()

    import importlib
    import backend.application.agent.skill as mod
    importlib.reload(mod)
    return mod


class TestCompletionStatus:
    """Test CompletionStatus enum and auto-derivation in SkillResult."""

    def test_status_values(self):
        mod = _import_skill_module()
        assert mod.CompletionStatus.DONE == "done"
        assert mod.CompletionStatus.BLOCKED == "blocked"
        assert mod.CompletionStatus.NEEDS_CONTEXT == "needs_context"
        assert mod.CompletionStatus.DONE_WITH_CONCERNS == "concerns"

    def test_auto_derive_blocked_on_failure(self):
        mod = _import_skill_module()
        result = mod.SkillResult(success=False, error="permission denied")
        assert result.status == mod.CompletionStatus.BLOCKED

    def test_auto_derive_concerns_on_feedback(self):
        mod = _import_skill_module()
        result = mod.SkillResult(success=True, feedback="2 deprecated docs")
        assert result.status == mod.CompletionStatus.DONE_WITH_CONCERNS

    def test_explicit_status_preserved(self):
        mod = _import_skill_module()
        result = mod.SkillResult(
            success=True,
            status=mod.CompletionStatus.NEEDS_CONTEXT,
        )
        assert result.status == mod.CompletionStatus.NEEDS_CONTEXT

    def test_default_done(self):
        mod = _import_skill_module()
        result = mod.SkillResult(data="ok")
        assert result.status == mod.CompletionStatus.DONE


class TestHookRegistry:
    """Test HookRegistry pre/post hook execution."""

    def test_register_and_list(self):
        mod = _import_skill_module()
        registry = mod.HookRegistry()

        class FakePre:
            name = "test_pre"
            def should_run(self, skill_name, ctx): return True
            async def before(self, skill_name, ctx, kwargs): return mod.PreHookResult()

        class FakePost:
            name = "test_post"
            def should_run(self, skill_name, ctx): return True
            async def after(self, skill_name, ctx, result): return result

        registry.register_pre(FakePre())
        registry.register_post(FakePost())

        hooks = registry.list_hooks()
        assert "test_pre" in hooks["pre"]
        assert "test_post" in hooks["post"]

    def test_pre_hook_blocks_execution(self):
        mod = _import_skill_module()
        registry = mod.HookRegistry()

        class BlockHook:
            name = "blocker"
            def should_run(self, skill_name, ctx): return True
            async def before(self, skill_name, ctx, kwargs):
                return mod.PreHookResult(allow=False, block_reason="blocked by test")

        registry.register_pre(BlockHook())

        result = asyncio.get_event_loop().run_until_complete(
            registry.run_pre_hooks("wiki_search", None, {})
        )
        assert not result.allow
        assert "blocked by test" in result.block_reason

    def test_pre_hook_modifies_kwargs(self):
        mod = _import_skill_module()
        registry = mod.HookRegistry()

        class ModifyHook:
            name = "modifier"
            def should_run(self, skill_name, ctx): return True
            async def before(self, skill_name, ctx, kwargs):
                return mod.PreHookResult(allow=True, modified_kwargs={"query": "modified"})

        registry.register_pre(ModifyHook())

        kwargs = {"query": "original"}
        asyncio.get_event_loop().run_until_complete(
            registry.run_pre_hooks("wiki_search", None, kwargs)
        )
        assert kwargs["query"] == "modified"

    def test_post_hook_transforms_result(self):
        mod = _import_skill_module()
        registry = mod.HookRegistry()

        class FeedbackHook:
            name = "feedback_injector"
            def should_run(self, skill_name, ctx): return True
            async def after(self, skill_name, ctx, result):
                result.feedback = "injected warning"
                result.status = mod.CompletionStatus.DONE_WITH_CONCERNS
                return result

        registry.register_post(FeedbackHook())

        original = mod.SkillResult(data="test")
        result = asyncio.get_event_loop().run_until_complete(
            registry.run_post_hooks("wiki_search", None, original)
        )
        assert result.feedback == "injected warning"
        assert result.status == mod.CompletionStatus.DONE_WITH_CONCERNS

    def test_hook_should_run_filtering(self):
        mod = _import_skill_module()
        registry = mod.HookRegistry()

        class SelectiveHook:
            name = "selective"
            def should_run(self, skill_name, ctx):
                return skill_name == "wiki_search"
            async def before(self, skill_name, ctx, kwargs):
                return mod.PreHookResult(allow=False, block_reason="selective block")

        registry.register_pre(SelectiveHook())

        # Should block wiki_search
        result = asyncio.get_event_loop().run_until_complete(
            registry.run_pre_hooks("wiki_search", None, {})
        )
        assert not result.allow

        # Should pass llm_generate
        result = asyncio.get_event_loop().run_until_complete(
            registry.run_pre_hooks("llm_generate", None, {})
        )
        assert result.allow

    def test_failing_hook_does_not_crash(self):
        mod = _import_skill_module()
        registry = mod.HookRegistry()

        class CrashHook:
            name = "crasher"
            def should_run(self, skill_name, ctx): return True
            async def before(self, skill_name, ctx, kwargs):
                raise RuntimeError("hook exploded")

        registry.register_pre(CrashHook())

        # Should not raise, just log warning
        result = asyncio.get_event_loop().run_until_complete(
            registry.run_pre_hooks("wiki_search", None, {})
        )
        assert result.allow


class TestBuiltinHooks:
    """Test built-in QuerySanitizeHook and DeprecatedDocHook."""

    def test_query_sanitize_strips_whitespace(self):
        from backend.application.agent.hooks import QuerySanitizeHook
        mod = _import_skill_module()

        hook = QuerySanitizeHook()
        assert hook.should_run("wiki_search", None)
        assert not hook.should_run("llm_generate", None)

        kwargs = {"query": "  hello   world  "}
        result = asyncio.get_event_loop().run_until_complete(
            hook.before("wiki_search", None, kwargs)
        )
        assert result.allow
        assert result.modified_kwargs == {"query": "hello world"}

    def test_query_sanitize_blocks_empty(self):
        from backend.application.agent.hooks import QuerySanitizeHook

        hook = QuerySanitizeHook()
        result = asyncio.get_event_loop().run_until_complete(
            hook.before("wiki_search", None, {"query": "   "})
        )
        assert not result.allow

    def test_deprecated_doc_hook_flags_deprecated(self):
        from backend.application.agent.hooks import DeprecatedDocHook
        mod = _import_skill_module()

        hook = DeprecatedDocHook()
        assert hook.should_run("wiki_search", None)

        result = mod.SkillResult(
            data=[
                {"title": "doc1", "metadata": {"status": "approved"}},
                {"title": "doc2", "metadata": {"status": "deprecated"}},
            ],
            success=True,
        )
        updated = asyncio.get_event_loop().run_until_complete(
            hook.after("wiki_search", None, result)
        )
        assert "deprecated" in updated.feedback.lower() or "폐기" in updated.feedback
        assert updated.status == mod.CompletionStatus.DONE_WITH_CONCERNS
