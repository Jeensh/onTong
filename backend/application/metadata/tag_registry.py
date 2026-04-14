"""Semantic Tag Registry — ChromaDB-backed tag deduplication.

Uses a dedicated ChromaDB collection to store tag embeddings.
Provides semantic similarity search for tag normalization.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import chromadb

from backend.core.config import settings

logger = logging.getLogger(__name__)


class TagRegistry:
    """ChromaDB-backed semantic tag registry."""

    COLLECTION_NAME = "tag_registry"
    SIMILARITY_THRESHOLD = 0.55  # cosine distance threshold for OpenAI text-embedding-3-small on short text

    def __init__(self) -> None:
        self._collection = None

    def connect(self, client: chromadb.ClientAPI, embedding_function=None) -> None:
        """Initialize using an existing ChromaDB client."""
        try:
            self._collection = client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_function,
            )
            logger.info(f"Tag registry connected ({self._collection.count()} tags)")
        except Exception as e:
            logger.warning(f"Tag registry connection failed: {e}")
            self._collection = None

    @property
    def is_connected(self) -> bool:
        return self._collection is not None

    def register_tag(self, tag: str, count: int = 1) -> None:
        """Add or update a tag in the registry."""
        if not self.is_connected:
            return
        try:
            self._collection.upsert(
                ids=[tag],
                documents=[tag],
                metadatas=[{
                    "count": count,
                    "created": datetime.now(timezone.utc).isoformat(),
                }],
            )
        except Exception as e:
            logger.warning(f"Tag registry upsert failed for '{tag}': {e}")

    def register_tags_bulk(self, tags_with_counts: dict[str, int]) -> None:
        """Bulk register tags from metadata index."""
        if not self.is_connected or not tags_with_counts:
            return
        try:
            ids = list(tags_with_counts.keys())
            documents = list(tags_with_counts.keys())
            metadatas = [{"count": c, "created": datetime.now(timezone.utc).isoformat()}
                         for c in tags_with_counts.values()]
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                end = min(i + batch_size, len(ids))
                self._collection.upsert(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    metadatas=metadatas[i:end],
                )
            logger.info(f"Tag registry bulk registered {len(ids)} tags")
        except Exception as e:
            logger.warning(f"Tag registry bulk register failed: {e}")

    def find_similar(self, tag: str, top_k: int = 3) -> list[dict]:
        """Find similar existing tags by semantic similarity.

        Returns list of {tag, distance, count} sorted by distance asc.
        distance is cosine distance (0 = identical, 1 = opposite).
        """
        if not self.is_connected:
            return []
        try:
            results = self._collection.query(
                query_texts=[tag],
                n_results=top_k,
            )
            similar = []
            for i, tag_id in enumerate(results["ids"][0]):
                dist = results["distances"][0][i]
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                similar.append({
                    "tag": tag_id,
                    "distance": dist,
                    "count": meta.get("count", 0),
                })
            return similar
        except Exception as e:
            logger.warning(f"Tag registry query failed for '{tag}': {e}")
            return []

    def find_similar_groups(self, threshold: float = 0.55) -> list[list[dict]]:
        """Find all groups of similar tags for admin merge dashboard.

        Returns groups where each group has 2+ tags within threshold distance.
        """
        if not self.is_connected:
            return []
        try:
            all_data = self._collection.get(include=["metadatas"])
            all_tags = all_data["ids"]
            if len(all_tags) < 2:
                return []

            visited: set[str] = set()
            groups: list[list[dict]] = []

            for tag in all_tags:
                if tag in visited:
                    continue
                similar = self.find_similar(tag, top_k=10)
                group = []
                for s in similar:
                    if s["distance"] <= threshold and s["tag"] not in visited:
                        group.append(s)
                if len(group) >= 2:
                    groups.append(group)
                    for s in group:
                        visited.add(s["tag"])

            return groups
        except Exception as e:
            logger.warning(f"Tag registry group search failed: {e}")
            return []

    def delete_tag(self, tag: str) -> None:
        """Remove a tag from the registry."""
        if not self.is_connected:
            return
        try:
            self._collection.delete(ids=[tag])
        except Exception as e:
            logger.warning(f"Tag registry delete failed for '{tag}': {e}")

    def count(self) -> int:
        if not self.is_connected:
            return 0
        return self._collection.count()


tag_registry = TagRegistry()
