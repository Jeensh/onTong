"""ChunkMetaUpdater tests with mocked Chroma + Indexer."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_chroma_and_indexer():
    chroma = MagicMock()
    chroma.is_connected = True
    chroma._collection = MagicMock()
    chroma._collection.get.return_value = {
        "ids": ["c1", "c2"],
        "metadatas": [{"file_path": "old.md", "heading": "h"}, {"file_path": "old.md", "heading": "h2"}],
    }
    indexer = MagicMock()
    indexer.index_file = AsyncMock(return_value=2)
    return chroma, indexer


@pytest.mark.asyncio
async def test_update_metadata_no_chunks():
    from backend.application.rename.chunk_meta import ChunkMetaUpdater
    chroma = MagicMock()
    chroma.is_connected = True
    chroma._collection = MagicMock()
    chroma._collection.get.return_value = {"ids": [], "metadatas": []}
    indexer = MagicMock()
    cm = ChunkMetaUpdater(chroma, indexer)
    res = await cm.update_for_path_rename("nope.md", "newer.md")
    assert res["meta_updated"] == 0
    assert res["error"] is None


@pytest.mark.asyncio
async def test_update_metadata_two_chunks(mock_chroma_and_indexer):
    chroma, indexer = mock_chroma_and_indexer
    from backend.application.rename.chunk_meta import ChunkMetaUpdater
    cm = ChunkMetaUpdater(chroma, indexer)
    res = await cm.update_for_path_rename("old.md", "new.md")
    assert res["meta_updated"] == 2
    # Verify update was called
    chroma._collection.update.assert_called_once()
    args = chroma._collection.update.call_args
    new_metas = args.kwargs["metadatas"]
    for m in new_metas:
        assert m["file_path"] == "new.md"


@pytest.mark.asyncio
async def test_reindex_triggered_when_wiki_file_provided(mock_chroma_and_indexer):
    chroma, indexer = mock_chroma_and_indexer
    from backend.application.rename.chunk_meta import ChunkMetaUpdater
    cm = ChunkMetaUpdater(chroma, indexer)
    fake_wiki_file = MagicMock()
    res = await cm.update_for_path_rename("old.md", "new.md", wiki_file_at_new_path=fake_wiki_file)
    assert res["reindex_triggered"] is True
    indexer.index_file.assert_called_once()


@pytest.mark.asyncio
async def test_chroma_disconnected():
    from backend.application.rename.chunk_meta import ChunkMetaUpdater
    chroma = MagicMock()
    chroma.is_connected = False
    cm = ChunkMetaUpdater(chroma, MagicMock())
    res = await cm.update_for_path_rename("a.md", "b.md")
    assert res["error"] == "chroma_disconnected"


# ── E4: ACL leak window guard ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chunk_meta_stamps_new_access_scope(monkeypatch, mock_chroma_and_indexer):
    """metadata.update must carry the new path's access_scope, not leave it stale.

    Regression: prior to E4 the chunks kept whatever access_read / access_write
    they had at original-index time, which is the wrong ACL when a doc is moved
    into a folder with a different policy.
    """
    chroma, indexer = mock_chroma_and_indexer

    # Stub acl_store.compute_access_scope so the updater receives a concrete scope.
    import backend.application.rename.chunk_meta as cm_mod
    def fake_compute_scope(new_path: str) -> dict[str, str] | None:
        return {"read": "|secret-team|", "write": "|secret-team|"}
    monkeypatch.setattr(cm_mod, "_compute_new_path_access_scope", fake_compute_scope)

    cm = cm_mod.ChunkMetaUpdater(chroma, indexer)
    res = await cm.update_for_path_rename("old.md", "secret/new.md")

    assert res["access_scope_synced"] is True
    args = chroma._collection.update.call_args
    new_metas = args.kwargs["metadatas"]
    for m in new_metas:
        assert m["file_path"] == "secret/new.md"
        assert m["access_read"] == "|secret-team|"
        assert m["access_write"] == "|secret-team|"


@pytest.mark.asyncio
async def test_reindex_carries_new_access_scope(monkeypatch, mock_chroma_and_indexer):
    """index_file(force=True) must pass the new path's access_scope.

    Without this, the re-embedded chunks would carry empty access_read, which
    makes the document invisible to non-admin users (default-deny on $contains).
    """
    chroma, indexer = mock_chroma_and_indexer

    import backend.application.rename.chunk_meta as cm_mod
    def fake_compute_scope(new_path: str) -> dict[str, str] | None:
        return {"read": "|infra|", "write": "|infra|"}
    monkeypatch.setattr(cm_mod, "_compute_new_path_access_scope", fake_compute_scope)

    cm = cm_mod.ChunkMetaUpdater(chroma, indexer)
    fake_wiki_file = MagicMock()
    await cm.update_for_path_rename("old.md", "infra/new.md", wiki_file_at_new_path=fake_wiki_file)

    indexer.index_file.assert_called_once()
    kwargs = indexer.index_file.call_args.kwargs
    assert kwargs.get("force") is True
    assert kwargs.get("access_scope") == {"read": "|infra|", "write": "|infra|"}


@pytest.mark.asyncio
async def test_chunk_meta_no_acl_machinery_still_updates_path(monkeypatch, mock_chroma_and_indexer):
    """If acl_store is unavailable, file_path still moves — leaving ACL fields untouched."""
    chroma, indexer = mock_chroma_and_indexer

    import backend.application.rename.chunk_meta as cm_mod
    monkeypatch.setattr(cm_mod, "_compute_new_path_access_scope", lambda p: None)

    cm = cm_mod.ChunkMetaUpdater(chroma, indexer)
    res = await cm.update_for_path_rename("old.md", "new.md")

    assert res["meta_updated"] == 2
    assert res["access_scope_synced"] is False
    args = chroma._collection.update.call_args
    new_metas = args.kwargs["metadatas"]
    for m in new_metas:
        assert m["file_path"] == "new.md"
        # ACL keys NOT injected since compute returned None
        assert "access_read" not in m
        assert "access_write" not in m
