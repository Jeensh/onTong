"""AG-3-2: Skill permission mapping — unit tests.

Uses importlib.reload for cross-test compatibility.
"""

import importlib
import sys
import types
from pathlib import Path


def _ensure_stubs():
    for mod_name in [
        "chromadb", "chromadb.config", "pydantic_ai", "pydantic_ai.models",
        "pydantic_ai.models.openai", "pydantic_settings",
        "litellm", "httpx",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)
    _ps = sys.modules["pydantic_settings"]
    if not hasattr(_ps, "BaseSettings"):
        _ps.BaseSettings = type("BaseSettings", (), {"model_config": {}})


def _reload_modules():
    """Reload agent modules to get fresh class definitions."""
    _ensure_stubs()
    import backend.core.session as _sess
    import backend.application.agent.skill as _skill
    import backend.application.agent.context as _ctx
    importlib.reload(_sess)
    importlib.reload(_skill)
    importlib.reload(_ctx)
    return _skill, _ctx


def test_permission_level_enum():
    _skill, _ = _reload_modules()
    assert _skill.PermissionLevel.READ == "read"
    assert _skill.PermissionLevel.WRITE == "write"
    assert _skill.PermissionLevel.EXECUTE == "execute"


def test_skill_permissions_mapping():
    _skill, _ = _reload_modules()
    assert _skill.SKILL_PERMISSIONS["wiki_write"] == _skill.PermissionLevel.WRITE
    assert _skill.SKILL_PERMISSIONS["wiki_edit"] == _skill.PermissionLevel.WRITE
    assert _skill.SKILL_PERMISSIONS["wiki_search"] == _skill.PermissionLevel.READ


def test_write_skill_blocked_for_viewer():
    import asyncio
    from unittest.mock import MagicMock
    _skill, _ctx = _reload_modules()

    ctx = _ctx.AgentContext(
        request=MagicMock(), chroma=MagicMock(), storage=MagicMock(),
        session_store=MagicMock(), user_roles=["viewer"], intent_action="edit",
    )
    result = asyncio.run(ctx.run_skill("wiki_edit"))
    assert result.success is False
    assert "권한 부족" in result.error


def test_write_skill_allowed_for_editor():
    import asyncio
    from unittest.mock import MagicMock, AsyncMock, patch
    _skill, _ctx = _reload_modules()

    mock_skill = MagicMock()
    mock_skill.execute = AsyncMock(return_value=_skill.SkillResult(data="ok"))

    ctx = _ctx.AgentContext(
        request=MagicMock(), chroma=MagicMock(), storage=MagicMock(),
        session_store=MagicMock(), user_roles=["editor"], intent_action="edit",
    )
    with patch.object(_skill.skill_registry, "get", return_value=mock_skill):
        result = asyncio.run(ctx.run_skill("wiki_edit"))
    assert result.success is True


def test_read_skill_allowed_for_all():
    import asyncio
    from unittest.mock import MagicMock, AsyncMock, patch
    _skill, _ctx = _reload_modules()

    mock_skill = MagicMock()
    mock_skill.execute = AsyncMock(return_value=_skill.SkillResult(data="results"))

    ctx = _ctx.AgentContext(
        request=MagicMock(), chroma=MagicMock(), storage=MagicMock(),
        session_store=MagicMock(), user_roles=["viewer"], intent_action="question",
    )
    with patch.object(_skill.skill_registry, "get", return_value=mock_skill):
        result = asyncio.run(ctx.run_skill("wiki_search", query="test"))
    assert result.success is True


def test_write_blocked_has_retry_hint():
    import asyncio
    from unittest.mock import MagicMock
    _skill, _ctx = _reload_modules()

    ctx = _ctx.AgentContext(
        request=MagicMock(), chroma=MagicMock(), storage=MagicMock(),
        session_store=MagicMock(), user_roles=["viewer"], intent_action="write",
    )
    result = asyncio.run(ctx.run_skill("wiki_write"))
    assert result.retry_hint != ""
