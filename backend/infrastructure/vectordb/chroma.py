"""ChromaDB wrapper for vector search."""

from __future__ import annotations

import logging
import os

import chromadb

from backend.core.config import settings

logger = logging.getLogger(__name__)


def _get_embedding_function():
    """Get embedding function based on config.

    - "default": ChromaDB built-in (all-MiniLM-L6-v2, no external API needed)
    - "openai": OpenAI text-embedding-3-small (requires OPENAI_API_KEY)
    """
    if settings.embedding_provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
            return OpenAIEmbeddingFunction(
                api_key=api_key,
                model_name="text-embedding-3-small",
            )
        logger.warning("embedding_provider=openai but OPENAI_API_KEY not set, falling back to default")
    return None


class ChromaWrapper:
    def __init__(self) -> None:
        self._client: chromadb.ClientAPI | None = None
        self._collection = None

    def connect(self) -> None:
        try:
            # Configure httpx connection pool via ChromaDB Settings
            chroma_settings = chromadb.Settings(
                chroma_server_http_host=settings.chromadb_host,
                chroma_server_http_port=str(settings.chromadb_port),
                anonymized_telemetry=False,
            )
            self._client = chromadb.HttpClient(
                host=settings.chromadb_host,
                port=settings.chromadb_port,
                settings=chroma_settings,
            )
            ef = _get_embedding_function()
            self._collection = self._client.get_or_create_collection(
                name=settings.chromadb_collection,
                metadata={"hnsw:space": "cosine"},
                embedding_function=ef,
            )
            logger.info(
                f"Connected to ChromaDB at {settings.chromadb_host}:{settings.chromadb_port} "
                f"(embedding: {'OpenAI' if ef else 'default'})"
            )
        except Exception as e:
            logger.warning(f"ChromaDB connection failed: {e}. Running without vector search.")
            self._client = None
            self._collection = None

    @property
    def is_connected(self) -> bool:
        return self._collection is not None

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict], batch_size: int = 100) -> None:
        if not self.is_connected:
            return
        # Batch upsert for large document sets
        if len(ids) <= batch_size:
            self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        else:
            for i in range(0, len(ids), batch_size):
                end = min(i + batch_size, len(ids))
                self._collection.upsert(
                    ids=ids[i:end],
                    documents=documents[i:end],
                    metadatas=metadatas[i:end],
                )
                logger.debug(f"Batch upsert {i}..{end} of {len(ids)}")

    def delete(self, ids: list[str]) -> None:
        if not self.is_connected:
            return
        self._collection.delete(ids=ids)

    def delete_where(self, where: dict) -> None:
        """Delete documents matching a metadata filter."""
        if not self.is_connected:
            return
        try:
            self._collection.delete(where=where)
        except Exception as e:
            logger.warning(f"ChromaDB delete_where failed: {e}")

    def query(self, query_text: str, n_results: int = 5) -> dict:
        if not self.is_connected:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        return self._collection.query(query_texts=[query_text], n_results=n_results)

    def query_with_filter(
        self, query_text: str, n_results: int = 5, where: dict | None = None
    ) -> dict:
        """Query with optional ChromaDB where filter."""
        empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        if not self.is_connected:
            return empty
        kwargs: dict = {"query_texts": [query_text], "n_results": n_results}
        if where:
            kwargs["where"] = where
        try:
            return self._collection.query(**kwargs)
        except Exception as e:
            logger.warning(f"ChromaDB filtered query failed: {e}")
            return empty

    def get_all_embeddings(self, batch_size: int = 1000) -> dict:
        """Retrieve all documents with embeddings and metadata in batches.

        Uses offset/limit pagination to avoid loading everything into memory at once.
        Returns dict with keys: ids, embeddings, documents, metadatas.
        Used by ConflictDetectionService for similarity clustering.
        """
        if not self.is_connected:
            return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
        try:
            all_ids: list = []
            all_embeddings: list = []
            all_documents: list = []
            all_metadatas: list = []

            total = self._collection.count()
            offset = 0

            while offset < total:
                batch = self._collection.get(
                    include=["embeddings", "documents", "metadatas"],
                    limit=batch_size,
                    offset=offset,
                )
                batch_ids = batch.get("ids", [])
                if not batch_ids:
                    break
                all_ids.extend(batch_ids)
                all_embeddings.extend(batch.get("embeddings", []))
                all_documents.extend(batch.get("documents", []))
                all_metadatas.extend(batch.get("metadatas", []))
                offset += len(batch_ids)
                logger.debug(f"Loaded embeddings batch {offset}/{total}")

            return {
                "ids": all_ids,
                "embeddings": all_embeddings,
                "documents": all_documents,
                "metadatas": all_metadatas,
            }
        except Exception as e:
            logger.warning(f"ChromaDB get_all_embeddings failed: {e}")
            return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}

    def get_file_embeddings(self, file_path: str) -> dict:
        """Get all chunk embeddings for a specific file."""
        empty = {"ids": [], "embeddings": [], "metadatas": []}
        if not self.is_connected:
            return empty
        try:
            return self._collection.get(
                where={"file_path": file_path},
                include=["embeddings", "metadatas"],
            )
        except Exception as e:
            logger.warning(f"ChromaDB get_file_embeddings failed for {file_path}: {e}")
            return empty

    def query_by_embedding(
        self, embedding: list[float], n_results: int = 10, where: dict | None = None
    ) -> dict:
        """Query using a raw embedding vector via ChromaDB HNSW native search."""
        empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        if not self.is_connected:
            return empty
        try:
            kwargs: dict = {"query_embeddings": [embedding], "n_results": n_results}
            if where:
                kwargs["where"] = where
            return self._collection.query(**kwargs)
        except Exception as e:
            logger.warning(f"ChromaDB query_by_embedding failed: {e}")
            return empty

    def count(self) -> int:
        if not self.is_connected:
            return 0
        return self._collection.count()


chroma = ChromaWrapper()
