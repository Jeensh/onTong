"""Wiki document chunking and ChromaDB indexing."""

from __future__ import annotations

import json
import os
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

# System directories that should NOT get path prefixes
_SYSTEM_PATH_PREFIXES = ("_skills/", "_personas/", ".ontong/")


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


def _build_path_prefix(file_path: str) -> str:
    """Build normalized path context prefix for embedding enrichment.

    Example:
        "인프라/네트워크/캐시-장애-대응.md"
        → "[분류: 인프라 > 네트워크] [문서: 캐시 장애 대응]"
    """
    if any(file_path.startswith(sp) for sp in _SYSTEM_PATH_PREFIXES):
        return ""

    cleaned = file_path.removesuffix(".md")
    parts = cleaned.split("/")
    if not parts:
        return ""

    # Normalize: hyphens/underscores → spaces
    def _norm(s: str) -> str:
        return s.replace("-", " ").replace("_", " ")

    doc_name = _norm(parts[-1])
    folders = parts[:-1]

    if folders:
        hierarchy = " > ".join(_norm(f) for f in folders)
        return f"[분류: {hierarchy}] [문서: {doc_name}]"
    return f"[문서: {doc_name}]"


def _extract_path_depths(file_path: str) -> dict[str, str]:
    """Extract structured path metadata for ChromaDB filtering.

    Returns dict with path_depth_1, path_depth_2, path_stem.
    """
    cleaned = file_path.removesuffix(".md")
    parts = cleaned.split("/")

    return {
        "path_depth_1": parts[0] if len(parts) > 1 else "",
        "path_depth_2": parts[1] if len(parts) > 2 else "",
        "path_stem": parts[-1].replace("-", " ").replace("_", " ") if parts else "",
    }


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


IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def enrich_chunk_with_images(chunk_text: str, wiki_root: Path) -> str:
    """Replace image markdown references with their text descriptions.

    Reads sidecar .meta.json files for each image reference. If a sidecar
    exists, replaces the image reference with the description text.
    Falls back to OCR text if no vision description is available.
    Keeps original reference if no sidecar exists.
    """

    def _replace_image(match: re.Match) -> str:
        image_rel_path = match.group(2)
        image_path = wiki_root / image_rel_path
        meta_path = image_path.parent / (image_path.name + ".meta.json")

        if not meta_path.exists():
            return match.group(0)

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return match.group(0)

        description = meta.get("description", "")
        ocr_text = meta.get("ocr_text", "")

        if description:
            return f"\n[이미지: {description}]\n"
        elif ocr_text:
            return f"\n[이미지 텍스트: {ocr_text}]\n"

        return match.group(0)

    return IMAGE_REF_RE.sub(_replace_image, chunk_text)


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

        # Build path prefix for embedding enrichment (L1: Path-Aware RAG)
        path_embed_enabled = os.environ.get("ONTONG_PATH_EMBED_ENABLED", "true").lower() == "true"
        path_prefix = _build_path_prefix(wiki_file.path) if path_embed_enabled else ""

        for idx, (heading, body) in enumerate(sections):
            full_text = f"{heading}\n{body}" if heading else body
            # Enrich: replace image references with their text descriptions
            wiki_root = Path(settings.wiki_dir)
            full_text = enrich_chunk_with_images(full_text, wiki_root)

            if path_prefix:
                prefixed_text = f"{path_prefix}\n{full_text}"
            else:
                prefixed_text = full_text

            tokens = _estimate_tokens(prefixed_text)

            if tokens <= MAX_CHUNK_TOKENS:
                chunks.append(Chunk(
                    id=f"{wiki_file.path}::chunk_{idx}",
                    file_path=wiki_file.path,
                    heading=heading,
                    content=prefixed_text,
                    token_estimate=tokens,
                ))
            else:
                # Split long sections with overlap
                # Only prepend path prefix to first sub-chunk to avoid duplication
                sub_texts = _split_long_text(full_text, MAX_CHUNK_TOKENS, OVERLAP_TOKENS)
                for sub_idx, sub in enumerate(sub_texts):
                    content = f"{path_prefix}\n{sub}" if path_prefix and sub_idx == 0 else sub
                    chunks.append(Chunk(
                        id=f"{wiki_file.path}::chunk_{idx}_{sub_idx}",
                        file_path=wiki_file.path,
                        heading=heading,
                        content=content,
                        token_estimate=_estimate_tokens(content),
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
    def _metadata_to_chroma(
        wiki_file: WikiFile,
        access_scope: dict[str, str] | None = None,
    ) -> dict:
        """Convert WikiFile metadata to ChromaDB-compatible flat dict.

        Auto-generated from DocumentMetadata fields so new fields are
        never accidentally omitted. list[str] fields use pipe-delimited
        format for $contains queries; str fields pass through as-is.

        Also includes structured path fields (path_depth_1/2, path_stem)
        for query-time filtering (L2: Path-Aware RAG).

        access_scope: optional {"read": "<pipe-delimited>", "write": "<pipe-delimited>"}
        stamped into access_read / access_write for per-user vector pre-filtering.
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

        # Structured path metadata for pre-filtering at scale
        result.update(_extract_path_depths(wiki_file.path))

        # Access scope metadata for per-user vector search pre-filtering
        if access_scope:
            result["access_read"] = access_scope.get("read", "")
            result["access_write"] = access_scope.get("write", "")
        else:
            result["access_read"] = ""
            result["access_write"] = ""

        return result

    async def index_file(
        self,
        wiki_file: WikiFile,
        force: bool = False,
        access_scope: dict[str, str] | None = None,
    ) -> int:
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

        chroma_meta = self._metadata_to_chroma(wiki_file, access_scope=access_scope)

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

    async def update_access_scope(
        self,
        file_path: str,
        access_scope: dict[str, str],
    ) -> int:
        """Update only access_scope metadata for existing chunks (no re-embedding).

        Used when an ACL change affects a document that is already indexed —
        avoids the cost of re-chunking and re-embedding.

        Returns the number of chunks updated (0 if ChromaDB unavailable or
        no chunks found for the path).
        """
        if not self.chroma.is_connected:
            return 0
        data = self.chroma._collection.get(
            where={"file_path": file_path},
            include=["metadatas"],
        )
        if not data["ids"]:
            return 0
        updated_metadatas = []
        for meta in data["metadatas"]:
            meta["access_read"] = access_scope.get("read", "")
            meta["access_write"] = access_scope.get("write", "")
            updated_metadatas.append(meta)
        self.chroma._collection.update(
            ids=data["ids"],
            metadatas=updated_metadatas,
        )
        logger.info(
            f"Updated access_scope for {len(data['ids'])} chunks: {file_path}"
        )
        return len(data["ids"])
