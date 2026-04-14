"""AG-2-3: SkillResult feedback field — unit tests."""

import sys
import types
from pathlib import Path

# ── Module stubs (avoid heavy deps) ─────────────────────────────
for mod_name in [
    "chromadb", "chromadb.config", "pydantic_ai", "pydantic_ai.models",
    "pydantic_ai.models.openai", "pydantic_settings",
    "litellm", "httpx",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# Stub pydantic_settings.BaseSettings → plain class
_ps = sys.modules["pydantic_settings"]
if not hasattr(_ps, "BaseSettings"):
    _ps.BaseSettings = type("BaseSettings", (), {"model_config": {}})

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_skill_result_feedback_field():
    """SkillResult has feedback and retry_hint fields."""
    from backend.application.agent.skill import SkillResult

    r = SkillResult(data="ok", feedback="문서 2건 폐기됨", retry_hint="다시 검색")
    assert r.feedback == "문서 2건 폐기됨"
    assert r.retry_hint == "다시 검색"
    assert r.success is True


def test_skill_result_default_empty():
    """Feedback and retry_hint default to empty string."""
    from backend.application.agent.skill import SkillResult

    r = SkillResult()
    assert r.feedback == ""
    assert r.retry_hint == ""


def _make_search_mocks(chroma_return):
    """Helper: create all mocks needed for WikiSearchSkill tests."""
    from unittest.mock import MagicMock

    mock_chroma = MagicMock()
    # query_with_filter is used when exclude_deprecated=True (deprecated filter)
    mock_chroma.query_with_filter.return_value = chroma_return
    mock_chroma.query.return_value = chroma_return

    mock_ctx = MagicMock()
    mock_ctx.chroma = mock_chroma
    mock_ctx.user_roles = ["admin"]

    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = []

    mock_acl = MagicMock()
    mock_acl.check_permission.return_value = True

    mock_cache = MagicMock()
    mock_cache.get.return_value = None

    return mock_ctx, mock_bm25, mock_acl, mock_cache


def test_wiki_search_deprecated_feedback():
    """WikiSearchSkill sets feedback when deprecated docs are filtered."""
    import asyncio
    from unittest.mock import patch
    from backend.application.agent.skills.wiki_search import WikiSearchSkill

    skill = WikiSearchSkill()
    mock_ctx, mock_bm25, mock_acl, mock_cache = _make_search_mocks({
        "documents": [["active doc content", "deprecated doc content"]],
        "metadatas": [[
            {"path": "/wiki/active.md", "status": "active"},
            {"path": "/wiki/old.md", "status": "deprecated"},
        ]],
        "distances": [[0.1, 0.5]],
    })

    with patch("backend.application.agent.skills.wiki_search.bm25_index", mock_bm25), \
         patch("backend.application.agent.skills.wiki_search.acl_store", mock_acl), \
         patch("backend.application.agent.skills.wiki_search.query_cache", mock_cache), \
         patch("backend.application.agent.skills.wiki_search.settings") as ms, \
         patch("backend.application.agent.skills.wiki_search.extract_metadata_filter", return_value=None):
        ms.enable_reranker = False
        result = asyncio.run(skill.execute(
            mock_ctx, query="test query", n_results=8, user_roles=["admin"]
        ))

    assert len(result.data["documents"]) == 1
    assert result.data["documents"][0] == "active doc content"
    assert "폐기" in result.feedback
    assert "/wiki/old.md" in result.feedback


def test_wiki_search_no_deprecated_no_feedback():
    """WikiSearchSkill returns empty feedback when no deprecated docs."""
    import asyncio
    from unittest.mock import patch
    from backend.application.agent.skills.wiki_search import WikiSearchSkill

    skill = WikiSearchSkill()
    mock_ctx, mock_bm25, mock_acl, mock_cache = _make_search_mocks({
        "documents": [["doc1", "doc2"]],
        "metadatas": [[
            {"path": "/wiki/a.md", "status": "active"},
            {"path": "/wiki/b.md", "status": "active"},
        ]],
        "distances": [[0.1, 0.2]],
    })

    with patch("backend.application.agent.skills.wiki_search.bm25_index", mock_bm25), \
         patch("backend.application.agent.skills.wiki_search.acl_store", mock_acl), \
         patch("backend.application.agent.skills.wiki_search.query_cache", mock_cache), \
         patch("backend.application.agent.skills.wiki_search.settings") as ms, \
         patch("backend.application.agent.skills.wiki_search.extract_metadata_filter", return_value=None):
        ms.enable_reranker = False
        result = asyncio.run(skill.execute(
            mock_ctx, query="test", n_results=8, user_roles=["admin"]
        ))

    assert result.feedback == ""
    assert len(result.data["documents"]) == 2
