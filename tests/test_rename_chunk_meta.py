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
