"""ChromaDB chunk metadata + body prefix updater after rename."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ChunkMetaUpdater:
    """Updates ChromaDB chunk metadata when a path is renamed.

    Two-step:
      1. Update metadata.file_path (cheap, no re-embedding).
      2. If wiki_file_at_new_path is supplied, queue re-indexing of the whole
         document (chunks rebuilt with new path prefix + new embeddings).
         OQ-4=A decision: chunk body must reflect the new path even if it
         requires re-embedding.
    """

    def __init__(self, chroma, indexer) -> None:
        """
        chroma: ChromaWrapper (backend.infrastructure.vectordb.chroma.ChromaWrapper)
        indexer: WikiIndexer (backend.application.wiki.wiki_indexer.WikiIndexer)
        """
        self._chroma = chroma
        self._indexer = indexer

    async def update_for_path_rename(
        self,
        old_path: str,
        new_path: str,
        *,
        wiki_file_at_new_path: Any = None,
    ) -> dict:
        """Apply rename to chunks belonging to old_path → new_path.

        Returns: {meta_updated: int, reindex_triggered: bool, error: str | None}

        Strategy:
        - Get all chunks where metadata.file_path == old_path
        - Update metadata.file_path on each via _collection.update()
        - If wiki_file_at_new_path provided, force re-index to rebuild chunks
          with new body prefix + new embeddings (OQ-4=A)
        - Return counts
        """
        result: dict = {"meta_updated": 0, "reindex_triggered": False, "error": None}

        if not getattr(self._chroma, "is_connected", True):
            result["error"] = "chroma_disconnected"
            return result

        try:
            data = self._chroma._collection.get(
                where={"file_path": old_path},
                include=["metadatas"],
            )
            chunk_ids = data.get("ids", [])
            metas = data.get("metadatas", [])
            if not chunk_ids:
                return result

            new_metas = []
            for m in metas:
                m["file_path"] = new_path
                new_metas.append(m)
            self._chroma._collection.update(ids=chunk_ids, metadatas=new_metas)
            result["meta_updated"] = len(chunk_ids)

            # OQ-4=A: re-embed if wiki_file is available (chunk body has stale path prefix)
            if wiki_file_at_new_path is not None:
                try:
                    await self._indexer.index_file(wiki_file_at_new_path, force=True)
                    result["reindex_triggered"] = True
                except Exception as e:
                    logger.warning(f"Re-index after rename failed for {new_path}: {e}")
                    result["error"] = f"reindex_failed: {e}"

        except Exception as e:
            logger.error(f"ChunkMetaUpdater failed: {old_path} → {new_path}: {e}")
            result["error"] = str(e)

        return result
