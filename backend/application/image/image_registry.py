"""Image Registry: in-memory hash index + ref counting for wiki assets.

Single source of truth for all image metadata in wiki/assets/.
Initialized at server startup by scanning the assets directory.
Updated at runtime via event-driven hooks (file_saved, file_deleted, image_uploaded).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\((assets/[^)]+)\)")


@dataclass
class ImageEntry:
    filename: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    ref_count: int
    referenced_by: set[str]
    source: str | None
    created_at: datetime


class ImageRegistry:
    """In-memory registry of all images in wiki/assets/."""

    def __init__(self) -> None:
        self._by_filename: dict[str, ImageEntry] = {}
        self._by_hash: dict[str, str] = {}  # sha256 → filename (first registered wins)

    # ── Lookup ──────────────────────────────────────────────────────

    def get_by_hash(self, sha256: str) -> ImageEntry | None:
        fn = self._by_hash.get(sha256)
        return self._by_filename.get(fn) if fn else None

    def get_by_filename(self, filename: str) -> ImageEntry | None:
        return self._by_filename.get(filename)

    # ── Register / Remove ───────────────────────────────────────────

    def register(self, entry: ImageEntry) -> None:
        self._by_filename[entry.filename] = entry
        if entry.sha256 not in self._by_hash:
            self._by_hash[entry.sha256] = entry.filename

    def remove(self, filename: str) -> None:
        entry = self._by_filename.pop(filename, None)
        if entry and self._by_hash.get(entry.sha256) == filename:
            del self._by_hash[entry.sha256]

    # ── Ref Counting ────────────────────────────────────────────────

    def increment_ref(self, filename: str, doc_path: str) -> None:
        entry = self._by_filename.get(filename)
        if not entry:
            return
        entry.referenced_by.add(doc_path)
        entry.ref_count = len(entry.referenced_by)

    def decrement_ref(self, filename: str, doc_path: str) -> None:
        entry = self._by_filename.get(filename)
        if not entry:
            return
        entry.referenced_by.discard(doc_path)
        entry.ref_count = len(entry.referenced_by)

    def remove_all_refs_for_doc(self, doc_path: str) -> None:
        for entry in self._by_filename.values():
            if doc_path in entry.referenced_by:
                entry.referenced_by.discard(doc_path)
                entry.ref_count = len(entry.referenced_by)

    def get_refs_for_doc(self, doc_path: str) -> set[str]:
        return {
            fn for fn, entry in self._by_filename.items()
            if doc_path in entry.referenced_by
        }

    # ── Stats & Listing ─────────────────────────────────────────────

    def stats(self) -> dict:
        total = len(self._by_filename)
        unused = sum(1 for e in self._by_filename.values() if e.ref_count == 0)
        total_bytes = sum(e.size_bytes for e in self._by_filename.values())
        derivative_count = sum(1 for e in self._by_filename.values() if e.source)
        return {
            "total": total,
            "unused": unused,
            "total_bytes": total_bytes,
            "derivative_count": derivative_count,
        }

    def list_entries(
        self,
        page: int = 1,
        size: int = 50,
        filter: str = "all",
        search: str = "",
    ) -> dict:
        entries = list(self._by_filename.values())

        if filter == "unused":
            entries = [e for e in entries if e.ref_count == 0]
        elif filter == "used":
            entries = [e for e in entries if e.ref_count > 0]
        elif filter == "derivative":
            entries = [e for e in entries if e.source]

        if search:
            entries = [e for e in entries if search.lower() in e.filename.lower()]

        entries.sort(key=lambda e: e.filename)

        total = len(entries)
        pages = max(1, math.ceil(total / size))
        start = (page - 1) * size
        page_entries = entries[start : start + size]

        # Serialize to dicts for consistent API interface
        items = [
            {
                "filename": e.filename,
                "sha256": e.sha256,
                "size_bytes": e.size_bytes,
                "width": e.width,
                "height": e.height,
                "ref_count": e.ref_count,
                "referenced_by": sorted(e.referenced_by),
                "source": e.source,
                "created_at": e.created_at.isoformat(),
            }
            for e in page_entries
        ]

        return {"items": items, "total": total, "page": page, "pages": pages}

    def get_unused_filenames(self) -> list[str]:
        return [fn for fn, e in self._by_filename.items() if e.ref_count == 0]

    def get_derivatives_of(self, filename: str) -> list[str]:
        return [fn for fn, e in self._by_filename.items() if e.source == filename]

    # ── Startup Scan ────────────────────────────────────────────────

    def scan(self, wiki_dir: Path) -> None:
        """Scan wiki/assets/ and all *.md files to build the registry."""
        assets_dir = wiki_dir / "assets"
        if not assets_dir.exists():
            logger.info("No assets directory found, skipping image registry scan")
            return

        # 1. Register all image files
        for f in assets_dir.iterdir():
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                data = f.read_bytes()
                sha256 = hashlib.sha256(data).hexdigest()
                size_bytes = len(data)
                width, height = _get_dimensions(f)

                # Check sidecar for source field
                source = None
                sidecar = f.parent / f"{f.name}.meta.json"
                if sidecar.exists():
                    try:
                        meta = json.loads(sidecar.read_text(encoding="utf-8"))
                        source = meta.get("source") or None
                    except Exception:
                        pass

                self.register(ImageEntry(
                    filename=f.name,
                    sha256=sha256,
                    size_bytes=size_bytes,
                    width=width,
                    height=height,
                    ref_count=0,
                    referenced_by=set(),
                    source=source,
                    created_at=datetime.fromtimestamp(f.stat().st_ctime, tz=timezone.utc),
                ))
            except Exception as e:
                logger.warning(f"Failed to register {f.name}: {e}")

        # 2. Scan all markdown files for image references
        for md_file in wiki_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            doc_path = str(md_file.relative_to(wiki_dir))
            for match in IMAGE_REF_RE.finditer(content):
                asset_path = match.group(1)  # e.g. "assets/abc123.png"
                filename = asset_path.split("/")[-1]
                self.increment_ref(filename, doc_path)

        total = len(self._by_filename)
        used = sum(1 for e in self._by_filename.values() if e.ref_count > 0)
        logger.info(f"Image registry initialized: {total} images ({used} referenced)")


def _get_dimensions(image_path: Path) -> tuple[int, int]:
    """Get pixel dimensions of an image file. Returns (0, 0) on failure."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except Exception:
        return (0, 0)
