"""Wiki document chunking and ChromaDB indexing."""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from pathlib import Path

from backend.core.config import settings
from backend.core.schemas import WikiFile
from backend.infrastructure.vectordb.chroma import ChromaWrapper
from backend.infrastructure.search.bm25 import BM25Document, bm25_index, tokenize
from backend.infrastructure.storage.file_hash import FileHashStore
from backend.infrastructure.cache.query_cache import query_cache

logger = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
MAX_CHUNK_TOKENS = 500  # approximate token limit per chunk
OVERLAP_TOKENS = 50


@dataclass
class Chunk:
    id: str
    file_path: str
    heading: str
    content: str
    token_estimate: int


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1.5 chars per token for mixed Korean/English."""
    return max(1, len(text) // 3)


def _split_by_headings(content: str) -> list[tuple[str, str]]:
    """Split markdown content by headings, returning (heading, body) pairs."""
    sections: list[tuple[str, str]] = []
    parts = HEADING_RE.split(content)

    # Before first heading
    preamble = parts[0].strip()
    if preamble:
        sections.append(("", preamble))

    # Heading groups: (level, title, body)
    i = 1
    while i < len(parts) - 1:
        _level = parts[i]
        title = parts[i + 1].strip()
        # Body is everything until next heading split
        body = parts[i + 2].strip() if i + 2 < len(parts) else ""
        sections.append((title, body))
        i += 3

    return sections


def _split_long_text(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """Split text that exceeds max_tokens into overlapping chunks."""
    words = text.split()
    chunks: list[str] = []
    start = 0

    while start < len(words):
        # Estimate how many words fit in max_tokens
        end = start
        current = ""
        while end < len(words) and _estimate_tokens(current + " " + words[end]) <= max_tokens:
            current = current + " " + words[end] if current else words[end]
            end += 1

        if not current:
            # Single word exceeds limit, take it anyway
            current = words[end]
            end += 1

        chunks.append(current)

        # Overlap: step back by overlap_tokens worth of words
        overlap_words = max(1, overlap_tokens // 3)
        start = max(start + 1, end - overlap_words)

    return chunks


class WikiIndexer:
    def __init__(self, chroma: ChromaWrapper) -> None:
        self.chroma = chroma
        hash_path = Path(settings.wiki_dir) / ".ontong" / "index_hashes.json"
        self.hash_store = FileHashStore(hash_path)

    def chunk(self, wiki_file: WikiFile) -> list[Chunk]:
        """Chunk a wiki file into indexable pieces."""
        if wiki_file.content.startswith("[Binary file:"):
            return []

        sections = _split_by_headings(wiki_file.content)
        chunks: list[Chunk] = []

        # For short documents (likely structured data like personnel info),
        # prepend file path as context to improve embedding quality
        total_content = wiki_file.content.strip()
        is_short_doc = _estimate_tokens(total_content) < 150

        for idx, (heading, body) in enumerate(sections):
            full_text = f"{heading}\n{body}" if heading else body
            # Enrich short structured docs with file context for better embedding
            if is_short_doc and not heading:
                file_label = wiki_file.path.replace("/", " > ").replace(".md", "")
                full_text = f"[문서: {file_label}]\n{full_text}"
            tokens = _estimate_tokens(full_text)

            if tokens <= MAX_CHUNK_TOKENS:
                chunks.append(Chunk(
                    id=f"{wiki_file.path}::chunk_{idx}",
                    file_path=wiki_file.path,
                    heading=heading,
                    content=full_text,
                    token_estimate=tokens,
                ))
            else:
                # Split long sections with overlap
                sub_texts = _split_long_text(full_text, MAX_CHUNK_TOKENS, OVERLAP_TOKENS)
                for sub_idx, sub in enumerate(sub_texts):
                    chunks.append(Chunk(
                        id=f"{wiki_file.path}::chunk_{idx}_{sub_idx}",
                        file_path=wiki_file.path,
                        heading=heading,
                        content=sub,
                        token_estimate=_estimate_tokens(sub),
                    ))

        return chunks

    @staticmethod
    def _ensure_bm25(file_path: str, chunks: list) -> None:
        """Add chunks to BM25 index if not already present."""
        with bm25_index._lock:
            already = any(d.file_path == file_path for d in bm25_index._documents)
        if not already:
            bm25_docs = [
                BM25Document(
                    id=c.id, file_path=c.file_path, heading=c.heading,
                    content=c.content, tokens=tokenize(c.content),
                )
                for c in chunks
            ]
            bm25_index.add_documents(bm25_docs)

    @staticmethod
    def _metadata_to_chroma(wiki_file: WikiFile) -> dict:
        """Convert WikiFile metadata to ChromaDB-compatible flat dict.

        Auto-generated from DocumentMetadata fields so new fields are
        never accidentally omitted. list[str] fields use pipe-delimited
        format for $contains queries; str fields pass through as-is.
        """
        meta = wiki_file.metadata
        result = {}
        for field_name, field_info in type(meta).model_fields.items():
            value = getattr(meta, field_name)
            if isinstance(value, list):
                # Pipe-delimited: "|a|b|c|" for $contains queries
                result[field_name] = f"|{'|'.join(value)}|" if value else ""
            else:
                # str, int, float, bool — ChromaDB supports natively
                result[field_name] = value
        return result

    async def index_file(self, wiki_file: WikiFile, force: bool = False) -> int:
        """Index a single wiki file into ChromaDB + BM25. Returns chunk count.

        Skips indexing if content hash is unchanged (unless force=True).
        """
        chunks = self.chunk(wiki_file)
        if not chunks:
            return 0

        # Incremental: skip ChromaDB if content unchanged (use raw_content to detect frontmatter changes like status)
        hash_input = wiki_file.raw_content or wiki_file.content
        chroma_skip = not force and not self.hash_store.has_changed(wiki_file.path, hash_input)

        if chroma_skip:
            # BM25 is in-memory — must repopulate after server restart even if ChromaDB is up-to-date
            self._ensure_bm25(wiki_file.path, chunks)
            logger.debug(f"Skipped indexing (unchanged): {wiki_file.path}")
            return 0

        chroma_meta = self._metadata_to_chroma(wiki_file)

        try:
            self.chroma.upsert(
                ids=[c.id for c in chunks],
                documents=[c.content for c in chunks],
                metadatas=[
                    {"file_path": c.file_path, "heading": c.heading, **chroma_meta}
                    for c in chunks
                ],
            )
            logger.info(f"Indexed {len(chunks)} chunks for {wiki_file.path}")
        except Exception as e:
            logger.warning(f"ChromaDB indexing failed for {wiki_file.path}: {e}. File saved without indexing.")

        # Sync BM25 index
        bm25_index.remove_by_file(wiki_file.path)
        bm25_docs = [
            BM25Document(
                id=c.id, file_path=c.file_path, heading=c.heading,
                content=c.content, tokens=tokenize(c.content),
            )
            for c in chunks
        ]
        bm25_index.add_documents(bm25_docs)

        # Update content hash + invalidate search cache
        self.hash_store.update(wiki_file.path, hash_input)
        query_cache.invalidate_by_file(wiki_file.path)

        return len(chunks)

    async def remove_file(self, path: str) -> None:
        """Remove all chunks for a given file from ChromaDB + BM25 + hash store."""
        try:
            self.chroma.delete_where({"file_path": path})
            bm25_index.remove_by_file(path)
            self.hash_store.remove(path)
            logger.info(f"Removed chunks for {path}")
        except Exception as e:
            logger.warning(f"Failed to remove chunks for {path}: {e}")

    async def reindex_all(self, files: list[WikiFile], force: bool = False) -> int:
        """Reindex all files. force=True clears everything and reindexes from scratch."""
        if force:
            # Clear all existing documents
            try:
                existing = self.chroma.count()
                if existing > 0:
                    result = self.chroma._collection.get(limit=existing + 100)
                    if result and result.get("ids"):
                        self.chroma.delete(ids=result["ids"])
                        logger.info(f"Cleared {len(result['ids'])} existing chunks before reindex")
            except Exception as e:
                logger.warning(f"Failed to clear collection before reindex: {e}")
            bm25_index.clear()
            self.hash_store.clear()

        total = 0
        skipped = 0
        for f in files:
            count = await self.index_file(f, force=force)
            if count > 0:
                total += count
            else:
                skipped += 1

        logger.info(
            f"Reindexed {len(files)} files: {total} chunks indexed, "
            f"{skipped} skipped (unchanged), BM25: {bm25_index.size}"
        )
        return total
