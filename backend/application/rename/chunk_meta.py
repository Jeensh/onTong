"""ChromaDB chunk metadata + body prefix updater after rename."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _compute_new_path_access_scope(new_path: str) -> dict[str, str] | None:
    """Resolve the access_scope (read/write principal lists) for new_path.

    Uses the global acl_store + format_scope_for_chroma so the post-rename
    chunks carry the ACL appropriate to their *new* location, not the old one
    or — worse — empty strings (which look like default-deny to non-admins).

    Returns None if the ACL machinery isn't available (e.g. dev environments
    where acl_store hasn't been wired). Caller treats None as "leave as-is".
    """
    try:
        from backend.core.auth.acl_store import acl_store
        from backend.core.auth.scope import format_scope_for_chroma
    except Exception:
        return None
    try:
        scope = acl_store.compute_access_scope(new_path)
    except Exception as e:
        logger.warning("compute_access_scope(%s) failed: %s", new_path, e)
        return None
    return {
        "read": format_scope_for_chroma(scope.get("read", [])),
        "write": format_scope_for_chroma(scope.get("write", [])),
    }


class ChunkMetaUpdater:
    """Updates ChromaDB chunk metadata when a path is renamed.

    Two-step:
      1. Update metadata.file_path + access_read + access_write (cheap, no re-embed).
         This is the first thing we do post-move so the ACL leak window —
         the gap during which ChromaDB chunks point at the old ACL — closes
         as fast as possible.
      2. If wiki_file_at_new_path is supplied, queue re-indexing of the whole
         document (chunks rebuilt with new path prefix + new embeddings).
         The re-index call must carry the new path's access_scope or non-admin
         users will lose visibility on their own document (default-deny on
         empty access_read).
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

        Returns: {meta_updated: int, reindex_triggered: bool, error: str | None,
                  access_scope_synced: bool}

        Strategy:
        - Compute access_scope for new_path (E4: ACL leak window guard)
        - Get all chunks where metadata.file_path == old_path
        - Update file_path + access_read + access_write atomically
        - If wiki_file_at_new_path provided, force re-index with the same scope
        """
        result: dict = {
            "meta_updated": 0,
            "reindex_triggered": False,
            "error": None,
            "access_scope_synced": False,
        }

        if not getattr(self._chroma, "is_connected", True):
            result["error"] = "chroma_disconnected"
            return result

        # E4: resolve the new path's ACL up-front so step 1 can stamp it
        # together with file_path. If unavailable (dev), step 1 still moves
        # file_path immediately — no regression vs prior behavior.
        new_scope = _compute_new_path_access_scope(new_path)

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
                if new_scope is not None:
                    m["access_read"] = new_scope["read"]
                    m["access_write"] = new_scope["write"]
                new_metas.append(m)
            self._chroma._collection.update(ids=chunk_ids, metadatas=new_metas)
            result["meta_updated"] = len(chunk_ids)
            result["access_scope_synced"] = new_scope is not None

            # OQ-4=A: re-embed if wiki_file is available (chunk body has stale path prefix).
            # Pass new_scope so non-admins keep visibility — empty access_read
            # would default-deny everyone except admin.
            if wiki_file_at_new_path is not None:
                try:
                    await self._indexer.index_file(
                        wiki_file_at_new_path,
                        force=True,
                        access_scope=new_scope,
                    )
                    result["reindex_triggered"] = True
                except Exception as e:
                    logger.warning(f"Re-index after rename failed for {new_path}: {e}")
                    result["error"] = f"reindex_failed: {e}"

        except Exception as e:
            logger.error(f"ChunkMetaUpdater failed: {old_path} → {new_path}: {e}")
            result["error"] = str(e)

        return result
