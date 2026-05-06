"""ES backend tests via mocked client."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def es_backend(monkeypatch):
    """Return ESSearchBackend with mocked client."""
    fake_es = MagicMock()
    fake_es.indices.exists_alias.return_value = False
    fake_es.indices.create.return_value = {"acknowledged": True}
    fake_es.indices.put_alias.return_value = {"acknowledged": True}
    fake_es.delete_by_query.return_value = {"deleted": 0}

    monkeypatch.setattr(
        "backend.infrastructure.search.es_backend._build_client",
        lambda url: fake_es,
    )

    from backend.infrastructure.search.es_backend import ESSearchBackend
    backend = ESSearchBackend("http://fake:9200", use_nori=True)
    return backend, fake_es


def test_init_creates_index_with_alias(es_backend):
    backend, fake_es = es_backend
    fake_es.indices.create.assert_called_once()
    fake_es.indices.put_alias.assert_called_once()


def test_search_returns_typed_hits(es_backend, monkeypatch):
    backend, fake_es = es_backend
    fake_es.search.return_value = {
        "hits": {
            "hits": [
                {"_id": "c1", "_score": 1.5, "_source": {
                    "file_path": "a.md", "chunk_id": "c1",
                    "heading": "Hello", "content": "World",
                }},
            ]
        }
    }
    hits = backend.search("hello", limit=5)
    assert len(hits) == 1
    assert hits[0].file_path == "a.md"
    assert hits[0].score == 1.5


def test_search_with_predicate_filter(es_backend):
    backend, fake_es = es_backend
    fake_es.search.return_value = {
        "hits": {
            "hits": [
                {"_id": "c1", "_score": 1.0, "_source": {
                    "file_path": "a.md", "chunk_id": "c1", "heading": "h", "content": "c",
                }},
                {"_id": "c2", "_score": 1.0, "_source": {
                    "file_path": "b.md", "chunk_id": "c2", "heading": "h", "content": "c",
                }},
                {"_id": "c3", "_score": 1.0, "_source": {
                    "file_path": "c.md", "chunk_id": "c3", "heading": "h", "content": "c",
                }},
            ]
        }
    }
    hits = backend.search("q", limit=5, file_predicate=lambda p: p == "b.md")
    assert len(hits) == 1
    assert hits[0].file_path == "b.md"


def test_alias_swap(es_backend):
    backend, fake_es = es_backend
    fake_es.indices.get_alias.return_value = {"old-index": {}}
    backend.alias_swap("new-index")
    # Verify update_aliases was called with both remove + add
    fake_es.indices.update_aliases.assert_called_once()
    call_args = fake_es.indices.update_aliases.call_args
    actions = call_args.kwargs["body"]["actions"]
    types = [list(a.keys())[0] for a in actions]
    assert "remove" in types
    assert "add" in types


def test_factory_enterprise_profile_returns_es(monkeypatch):
    """get_fulltext_search returns ESSearchBackend for enterprise profile."""
    monkeypatch.setenv("ONTONG_PROFILE", "enterprise")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.backends import _reset_for_test, get_fulltext_search
    _reset_for_test()

    from backend.core.config import settings
    profile = settings.resolve_profile()
    assert profile.fulltext_backend == "elasticsearch"

    fake_es = MagicMock()
    fake_es.indices.exists_alias.return_value = True  # Skip create
    monkeypatch.setattr(
        "backend.infrastructure.search.es_backend._build_client",
        lambda url: fake_es,
    )
    result = get_fulltext_search(profile, es_url="http://fake:9200")
    from backend.infrastructure.search.es_backend import ESSearchBackend
    assert isinstance(result, ESSearchBackend)
    _reset_for_test()


def test_factory_dev_profile_returns_bm25(monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.backends import _reset_for_test, get_fulltext_search
    _reset_for_test()
    from backend.core.config import settings
    profile = settings.resolve_profile()
    result = get_fulltext_search(profile)
    # Should be bm25_index (the global) — duck-type check
    assert hasattr(result, "add_documents")
    assert hasattr(result, "search")
    _reset_for_test()
