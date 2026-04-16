# Wiki Image Management System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide content-hash dedup for images, an annotation editor, and admin-only image management — all designed for 100K+ document scale.

**Architecture:** Three independent subsystems share a single ImageRegistry (in-memory hash index + ref count). Backend changes in `files.py` and a new `image_registry.py`; frontend adds fabric.js canvas editor and admin gallery page. Event-driven ref counting hooks into the existing `event_bus.py`.

**Tech Stack:** Python (FastAPI), fabric.js (canvas annotation), React, SHA-256 content hashing, Intersection Observer (lazy load)

**Spec:** `docs/superpowers/specs/2026-04-17-image-management-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|----------------|
| `backend/application/image/image_registry.py` | `ImageEntry` dataclass + `ImageRegistry` class: in-memory hash→filename index, ref counting, startup scan |

### Backend — Modified Files

| File | Changes |
|------|---------|
| `backend/application/image/models.py` | Add `source` field to `ImageAnalysis` dataclass + sidecar serialization |
| `backend/api/files.py` | SHA-256 hash dedup on upload, admin endpoints (stats, paginated list, delete, bulk-delete), OCR inheritance endpoint |
| `backend/application/wiki/wiki_service.py` | Ref tracking on save (diff old/new image refs), ref cleanup on delete |
| `backend/main.py` | Initialize `ImageRegistry` at startup, register `tree_change` event handler for ref updates |

### Frontend — New Files

| File | Responsibility |
|------|----------------|
| `frontend/src/components/editors/ImageViewerModal.tsx` | Fullscreen viewer overlay with fabric.js annotation tools + info panel |
| `frontend/src/components/editors/ImageManagementPage.tsx` | Admin gallery: paginated grid, filters, stats badges, bulk delete |

### Frontend — Modified Files

| File | Changes |
|------|---------|
| `frontend/package.json` | Add `fabric` dependency |
| `frontend/src/types/workspace.ts` | Add `"image-management"` to `VirtualTabType` |
| `frontend/src/lib/workspace/useWorkspaceStore.ts` | Add title for `"image-management"` virtual tab |
| `frontend/src/components/workspace/FileRouter.tsx` | Route `"image-management"` to `ImageManagementPage` |
| `frontend/src/lib/tiptap/pasteHandler.ts` | Image copy: right-click context menu + Ctrl/Cmd+C keyboard shortcut |
| `frontend/src/components/editors/MarkdownEditor.tsx` | Click image → open `ImageViewerModal` |
| `frontend/src/components/TreeNav.tsx` | Add "이미지 관리" item in settings section (admin only), gate `UnusedImagesPanel` behind admin check |

### Tests

| File | What it covers |
|------|----------------|
| `tests/test_image_registry.py` | ImageEntry, ImageRegistry: hash lookup, ref counting, startup scan |
| `tests/test_image_dedup_upload.py` | Upload dedup endpoint, hash collision returns existing path |
| `tests/test_image_admin_api.py` | Admin endpoints: stats, paginated list, delete with ref guard, bulk delete |

---

## Task 1: ImageRegistry Core — Data Structure + Hash Index

**Files:**
- Create: `backend/application/image/image_registry.py`
- Test: `tests/test_image_registry.py`

- [ ] **Step 1: Write failing tests for ImageEntry and ImageRegistry**

```python
# tests/test_image_registry.py
"""Tests for ImageRegistry: in-memory hash index + ref counting."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path


class TestImageEntry:
    """Test ImageEntry dataclass."""

    def test_create_entry(self):
        from backend.application.image.image_registry import ImageEntry

        entry = ImageEntry(
            filename="f8f8873a4c18.png",
            sha256="f8f8873a4c18" + "a" * 52,
            size_bytes=51200,
            width=212,
            height=238,
            ref_count=0,
            referenced_by=set(),
            source=None,
            created_at=datetime.now(timezone.utc),
        )
        assert entry.filename == "f8f8873a4c18.png"
        assert entry.ref_count == 0
        assert entry.referenced_by == set()


class TestImageRegistry:
    """Test ImageRegistry hash index and ref counting."""

    def _make_registry(self):
        from backend.application.image.image_registry import ImageRegistry
        return ImageRegistry()

    def test_register_and_lookup_by_hash(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        entry = ImageEntry(
            filename="abc123.png",
            sha256="deadbeef" * 8,
            size_bytes=1024,
            width=100,
            height=100,
            ref_count=0,
            referenced_by=set(),
            source=None,
            created_at=datetime.now(timezone.utc),
        )
        reg.register(entry)

        found = reg.get_by_hash("deadbeef" * 8)
        assert found is not None
        assert found.filename == "abc123.png"

    def test_lookup_missing_hash_returns_none(self):
        reg = self._make_registry()
        assert reg.get_by_hash("nonexistent") is None

    def test_get_by_filename(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        entry = ImageEntry(
            filename="test.png",
            sha256="aabb" * 16,
            size_bytes=512,
            width=50,
            height=50,
            ref_count=0,
            referenced_by=set(),
            source=None,
            created_at=datetime.now(timezone.utc),
        )
        reg.register(entry)
        assert reg.get_by_filename("test.png") is not None
        assert reg.get_by_filename("missing.png") is None

    def test_increment_ref(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        entry = ImageEntry(
            filename="img.png",
            sha256="ccdd" * 16,
            size_bytes=256,
            width=10,
            height=10,
            ref_count=0,
            referenced_by=set(),
            source=None,
            created_at=datetime.now(timezone.utc),
        )
        reg.register(entry)

        reg.increment_ref("img.png", "docs/test.md")
        updated = reg.get_by_filename("img.png")
        assert updated.ref_count == 1
        assert "docs/test.md" in updated.referenced_by

    def test_decrement_ref(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        entry = ImageEntry(
            filename="img.png",
            sha256="eeff" * 16,
            size_bytes=256,
            width=10,
            height=10,
            ref_count=1,
            referenced_by={"docs/test.md"},
            source=None,
            created_at=datetime.now(timezone.utc),
        )
        reg.register(entry)

        reg.decrement_ref("img.png", "docs/test.md")
        updated = reg.get_by_filename("img.png")
        assert updated.ref_count == 0
        assert "docs/test.md" not in updated.referenced_by

    def test_decrement_ref_floors_at_zero(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        entry = ImageEntry(
            filename="img.png",
            sha256="1122" * 16,
            size_bytes=256,
            width=10,
            height=10,
            ref_count=0,
            referenced_by=set(),
            source=None,
            created_at=datetime.now(timezone.utc),
        )
        reg.register(entry)

        reg.decrement_ref("img.png", "docs/test.md")
        assert reg.get_by_filename("img.png").ref_count == 0

    def test_remove_all_refs_for_doc(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        for name, sha in [("a.png", "aa" * 32), ("b.png", "bb" * 32)]:
            reg.register(ImageEntry(
                filename=name, sha256=sha, size_bytes=100,
                width=10, height=10, ref_count=1,
                referenced_by={"docs/page.md"},
                source=None, created_at=datetime.now(timezone.utc),
            ))

        reg.remove_all_refs_for_doc("docs/page.md")
        assert reg.get_by_filename("a.png").ref_count == 0
        assert reg.get_by_filename("b.png").ref_count == 0

    def test_get_refs_for_doc(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="x.png", sha256="xx" * 32, size_bytes=100,
            width=10, height=10, ref_count=1,
            referenced_by={"docs/page.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="y.png", sha256="yy" * 32, size_bytes=100,
            width=10, height=10, ref_count=0,
            referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))

        refs = reg.get_refs_for_doc("docs/page.md")
        assert refs == {"x.png"}

    def test_remove_entry(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="del.png", sha256="dd" * 32, size_bytes=100,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.remove("del.png")
        assert reg.get_by_filename("del.png") is None
        assert reg.get_by_hash("dd" * 32) is None

    def test_stats(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="used.png", sha256="u1" * 32, size_bytes=1000,
            width=10, height=10, ref_count=2, referenced_by={"a.md", "b.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="unused.png", sha256="u2" * 32, size_bytes=500,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="deriv.png", sha256="u3" * 32, size_bytes=800,
            width=10, height=10, ref_count=1, referenced_by={"c.md"},
            source="used.png", created_at=datetime.now(timezone.utc),
        ))

        stats = reg.stats()
        assert stats["total"] == 3
        assert stats["unused"] == 1
        assert stats["total_bytes"] == 2300
        assert stats["derivative_count"] == 1

    def test_list_paginated(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        for i in range(10):
            reg.register(ImageEntry(
                filename=f"img{i:02d}.png", sha256=f"{i:02d}" * 32,
                size_bytes=100, width=10, height=10,
                ref_count=i % 3, referenced_by=set(),
                source=None, created_at=datetime.now(timezone.utc),
            ))

        result = reg.list_entries(page=1, size=3)
        assert len(result["items"]) == 3
        assert result["total"] == 10
        assert result["page"] == 1
        assert result["pages"] == 4

    def test_list_filter_unused(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="used.png", sha256="aa" * 32, size_bytes=100,
            width=10, height=10, ref_count=1, referenced_by={"a.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="unused.png", sha256="bb" * 32, size_bytes=100,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))

        result = reg.list_entries(page=1, size=50, filter="unused")
        assert len(result["items"]) == 1
        assert result["items"][0].filename == "unused.png"

    def test_list_filter_derivative(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="orig.png", sha256="oo" * 32, size_bytes=100,
            width=10, height=10, ref_count=1, referenced_by={"a.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="ann.png", sha256="an" * 32, size_bytes=100,
            width=10, height=10, ref_count=1, referenced_by={"a.md"},
            source="orig.png", created_at=datetime.now(timezone.utc),
        ))

        result = reg.list_entries(page=1, size=50, filter="derivative")
        assert len(result["items"]) == 1
        assert result["items"][0].filename == "ann.png"

    def test_list_search_by_filename(self):
        from backend.application.image.image_registry import ImageRegistry, ImageEntry

        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="chat-payment.png", sha256="cp" * 32, size_bytes=100,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="error-500.png", sha256="e5" * 32, size_bytes=100,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))

        result = reg.list_entries(page=1, size=50, search="chat")
        assert len(result["items"]) == 1
        assert result["items"][0].filename == "chat-payment.png"


class TestImageRegistryScan:
    """Test startup scanning of assets directory."""

    def test_scan_assets_dir(self, tmp_path):
        from backend.application.image.image_registry import ImageRegistry

        # Create fake assets
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "img1.png").write_bytes(b"hello world")
        (assets / "img2.png").write_bytes(b"hello world")  # same content = same hash
        (assets / "img3.jpg").write_bytes(b"different content")
        (assets / "not_image.txt").write_text("skip me")
        # Create sidecar with source field
        import json
        (assets / "img3.jpg.meta.json").write_text(json.dumps({
            "version": 1, "ocr_text": "", "description": "",
            "provider": "none", "ocr_engine": "none",
            "processed_at": "2026-01-01T00:00:00+00:00",
            "source": "img1.png",
        }))

        # Create markdown file referencing img1
        (tmp_path / "test.md").write_text("![](assets/img1.png)")

        reg = ImageRegistry()
        reg.scan(wiki_dir=tmp_path)

        # img1 and img2 have same hash — only one entry in hash map
        # but both filenames should be registered
        assert reg.get_by_filename("img1.png") is not None
        assert reg.get_by_filename("img2.png") is not None
        assert reg.get_by_filename("img3.jpg") is not None
        assert reg.get_by_filename("not_image.txt") is None

        # img1 should have ref_count=1 from test.md
        assert reg.get_by_filename("img1.png").ref_count == 1
        assert "test.md" in reg.get_by_filename("img1.png").referenced_by

        # img3 should have source from sidecar
        assert reg.get_by_filename("img3.jpg").source == "img1.png"

        # stats
        stats = reg.stats()
        assert stats["total"] == 3
        assert stats["derivative_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_registry.py -v --tb=short 2>&1 | head -30`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.application.image.image_registry'`

- [ ] **Step 3: Implement ImageRegistry**

```python
# backend/application/image/image_registry.py
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
        items = entries[start : start + size]

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
```

- [ ] **Step 4: Update `__init__.py` exports**

Add to `backend/application/image/__init__.py`:
```python
from .image_registry import ImageEntry, ImageRegistry
```

Add to `__all__`:
```python
"ImageEntry",
"ImageRegistry",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_registry.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/application/image/image_registry.py backend/application/image/__init__.py tests/test_image_registry.py
git commit -m "feat: add ImageRegistry with hash index, ref counting, and startup scan"
```

---

## Task 2: Add `source` Field to ImageAnalysis

**Files:**
- Modify: `backend/application/image/models.py:16-47` (ImageAnalysis dataclass)
- Test: `tests/test_image_analysis.py` (existing — add new test)

- [ ] **Step 1: Write failing test for source field**

Add to `tests/test_image_analysis.py` inside `TestImageAnalysisModels`:

```python
def test_image_analysis_source_field(self):
    from backend.application.image.models import ImageAnalysis

    analysis = ImageAnalysis(
        ocr_text="text",
        description="desc",
        provider="none",
        ocr_engine="tesseract",
        processed_at=datetime(2026, 4, 17, 10, 0, 0, tzinfo=timezone.utc),
        source="original.png",
    )
    d = analysis.to_dict()
    assert d["source"] == "original.png"

    loaded = ImageAnalysis.from_dict(d)
    assert loaded.source == "original.png"

def test_image_analysis_source_default_empty(self):
    from backend.application.image.models import ImageAnalysis

    analysis = ImageAnalysis(
        ocr_text="text",
        description="desc",
        provider="none",
        ocr_engine="tesseract",
        processed_at=datetime(2026, 4, 17, 10, 0, 0, tzinfo=timezone.utc),
    )
    assert analysis.source == ""
    d = analysis.to_dict()
    assert d["source"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageAnalysisModels::test_image_analysis_source_field -v --tb=short`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'source'`

- [ ] **Step 3: Add source field to ImageAnalysis**

In `backend/application/image/models.py`, add `source` field to the dataclass:

```python
@dataclass
class ImageAnalysis:
    ocr_text: str
    description: str
    provider: str           # "ollama/llava:13b" | "claude/model" | "none"
    ocr_engine: str         # "tesseract" | "easyocr" | "none"
    processed_at: datetime
    source: str = ""        # parent image filename if annotation derivative

    def to_dict(self) -> dict:
        return {
            "version": SIDECAR_VERSION,
            "ocr_text": self.ocr_text,
            "description": self.description,
            "provider": self.provider,
            "ocr_engine": self.ocr_engine,
            "processed_at": self.processed_at.isoformat(),
            "source": self.source,
        }

    @staticmethod
    def from_dict(d: dict) -> "ImageAnalysis":
        ver = d.get("version", 0)
        if ver != SIDECAR_VERSION:
            raise ValueError(f"Unsupported sidecar version {ver}, expected {SIDECAR_VERSION}")
        raw_ts = d.get("processed_at", "")
        if raw_ts:
            ts = datetime.fromisoformat(raw_ts)
        else:
            ts = datetime.now(timezone.utc)
        return ImageAnalysis(
            ocr_text=d.get("ocr_text", ""),
            description=d.get("description", ""),
            provider=d.get("provider", "unknown"),
            ocr_engine=d.get("ocr_engine", "unknown"),
            processed_at=ts,
            source=d.get("source", ""),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py -v --tb=short`
Expected: ALL PASS (including existing tests — backwards compatible since `source` defaults to `""`)

- [ ] **Step 5: Commit**

```bash
git add backend/application/image/models.py tests/test_image_analysis.py
git commit -m "feat: add source field to ImageAnalysis for annotation derivative tracking"
```

---

## Task 3: Upload Hash Dedup

**Files:**
- Modify: `backend/api/files.py:93-117` (upload_image endpoint)
- Test: `tests/test_image_dedup_upload.py`

- [ ] **Step 1: Write failing tests for dedup upload**

```python
# tests/test_image_dedup_upload.py
"""Tests for image upload with SHA-256 content-hash dedup."""

from __future__ import annotations

import hashlib
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO

from backend.application.image.image_registry import ImageRegistry, ImageEntry
from datetime import datetime, timezone


class TestUploadDedup:
    """Test SHA-256 dedup on image upload."""

    def test_duplicate_returns_existing_path(self):
        """Uploading the same image bytes should return existing filename."""
        reg = ImageRegistry()
        image_bytes = b"fake png content for dedup test"
        sha = hashlib.sha256(image_bytes).hexdigest()

        reg.register(ImageEntry(
            filename="existing123.png",
            sha256=sha,
            size_bytes=len(image_bytes),
            width=100, height=100,
            ref_count=1, referenced_by={"test.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))

        # The dedup logic: check hash, return existing
        found = reg.get_by_hash(sha)
        assert found is not None
        assert found.filename == "existing123.png"

    def test_new_image_gets_hash_filename(self):
        """New image should get filename based on sha256[:12]."""
        image_bytes = b"brand new image content"
        sha = hashlib.sha256(image_bytes).hexdigest()
        filename = f"{sha[:12]}.png"
        assert len(sha[:12]) == 12
        assert filename.endswith(".png")

    def test_registry_updated_after_new_upload(self):
        """After uploading a new image, registry should contain it."""
        reg = ImageRegistry()
        image_bytes = b"new upload test"
        sha = hashlib.sha256(image_bytes).hexdigest()

        assert reg.get_by_hash(sha) is None

        reg.register(ImageEntry(
            filename=f"{sha[:12]}.png",
            sha256=sha,
            size_bytes=len(image_bytes),
            width=0, height=0,
            ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))

        assert reg.get_by_hash(sha) is not None
        assert reg.get_by_hash(sha).filename == f"{sha[:12]}.png"
```

- [ ] **Step 2: Run tests to verify they pass (these are unit tests on registry logic)**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_dedup_upload.py -v --tb=short`
Expected: ALL PASS (these test the registry interface that upload_image will use)

- [ ] **Step 3: Modify upload_image endpoint for hash dedup**

Replace the upload endpoint in `backend/api/files.py`:

```python
# Add at top of file:
import hashlib

# Add module-level variable for registry injection:
_image_registry = None

def set_image_registry(registry) -> None:
    """Called from main.py to inject the ImageRegistry singleton."""
    global _image_registry
    _image_registry = registry

def get_image_registry():
    return _image_registry
```

Replace the `upload_image` function:

```python
@router.post("/upload/image")
async def upload_image(file: UploadFile):
    """Upload an image file to wiki/assets/ with SHA-256 content-hash dedup."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {file.content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Content-hash dedup
    sha256 = hashlib.sha256(data).hexdigest()

    if _image_registry:
        existing = _image_registry.get_by_hash(sha256)
        if existing:
            logger.info(f"Dedup hit: {file.filename} → existing {existing.filename}")
            return {
                "path": f"assets/{existing.filename}",
                "filename": existing.filename,
                "deduplicated": True,
            }

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "image.png").suffix or ".png"
    filename = f"{sha256[:12]}{ext}"
    dest = ASSETS_DIR / filename

    # Handle rare hash-prefix collision
    if dest.exists():
        existing_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        if existing_sha == sha256:
            return {
                "path": f"assets/{filename}",
                "filename": filename,
                "deduplicated": True,
            }
        # True collision (different content, same 12-char prefix) — use full hash
        filename = f"{sha256}{ext}"
        dest = ASSETS_DIR / filename

    dest.write_bytes(data)

    # Register in image registry
    if _image_registry:
        from backend.application.image.image_registry import ImageEntry
        _image_registry.register(ImageEntry(
            filename=filename,
            sha256=sha256,
            size_bytes=len(data),
            width=0,  # Populated by background image analysis
            height=0,
            ref_count=0,
            referenced_by=set(),
            source=None,
            created_at=datetime.now(timezone.utc),
        ))

    rel_path = f"assets/{filename}"
    return {"path": rel_path, "filename": filename, "deduplicated": False}
```

Add `from datetime import datetime, timezone` to the imports at top of `files.py`.

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_dedup_upload.py tests/test_image_analysis.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/files.py tests/test_image_dedup_upload.py
git commit -m "feat: add SHA-256 content-hash dedup to image upload endpoint"
```

---

## Task 4: Registry Initialization + Event Handlers in main.py

**Files:**
- Modify: `backend/main.py:154-173` (image analysis init block)
- Modify: `backend/main.py:188-214` (event registrations)

- [ ] **Step 1: Add ImageRegistry initialization after image analysis setup**

In `backend/main.py`, after the existing image analysis initialization block (around line 173), add:

```python
# Image Registry — in-memory hash index + ref counting
from backend.application.image.image_registry import ImageRegistry
_image_registry = ImageRegistry()
_image_registry.scan(Path(settings.wiki_dir))

# Inject registry into files API
from backend.api.files import set_image_registry
set_image_registry(_image_registry)
```

- [ ] **Step 2: Register event handler for ref count updates**

In the event registration section of `backend/main.py` (after the existing `tree_change` handler), add:

```python
# Image ref count updates on file save/delete
def _on_tree_change_image_refs(data: dict) -> None:
    """Update image registry ref counts when documents change."""
    action = data.get("action")
    path = data.get("path", "")
    if not path.endswith(".md"):
        return
    if action == "remove":
        _image_registry.remove_all_refs_for_doc(path)
        logger.debug(f"Image refs cleared for deleted doc: {path}")

event_bus.on("tree_change", _on_tree_change_image_refs)
```

Note: The save-time ref tracking (diffing old vs new refs) goes in wiki_service.py (Task 5), not here. This handler only covers the delete case where we need to clear all refs for a removed document.

- [ ] **Step 3: Verify server starts correctly**

Run: `cd /Users/donghae/workspace/ai/onTong && timeout 10 python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 2>&1 | tail -20 || true`
Expected: Server starts without errors, logs show "Image registry initialized: N images"

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: initialize ImageRegistry at startup, register event handler for ref tracking"
```

---

## Task 5: Ref Tracking on Document Save

**Files:**
- Modify: `backend/application/wiki/wiki_service.py:164-172` (save_file, after indexing task)

- [ ] **Step 1: Add ref tracking to save_file flow**

In `backend/application/wiki/wiki_service.py`, add image ref tracking in the `save_file` method, right before the `event_bus.publish("tree_change", ...)` line (around line 170):

```python
# Image ref tracking — update registry ref counts on save
self._update_image_refs(path, wiki_file.content)
```

Add the helper method to the `WikiService` class:

```python
def _update_image_refs(self, doc_path: str, content: str) -> None:
    """Diff image refs in new content vs registry, update ref counts."""
    from backend.api.files import get_image_registry
    import re

    registry = get_image_registry()
    if not registry:
        return

    image_ref_re = re.compile(r"!\[[^\]]*\]\((assets/[^)]+)\)")
    new_refs: set[str] = set()
    for match in image_ref_re.finditer(content):
        asset_path = match.group(1)
        filename = asset_path.split("/")[-1]
        new_refs.add(filename)

    old_refs = registry.get_refs_for_doc(doc_path)

    added = new_refs - old_refs
    removed = old_refs - new_refs

    for img in added:
        registry.increment_ref(img, doc_path)
    for img in removed:
        registry.decrement_ref(img, doc_path)

    if added or removed:
        logger.debug(f"Image refs updated for {doc_path}: +{len(added)} -{len(removed)}")
```

- [ ] **Step 2: Verify with a manual test**

Run: `cd /Users/donghae/workspace/ai/onTong && python -c "
from backend.application.image.image_registry import ImageRegistry, ImageEntry
from datetime import datetime, timezone
import re

reg = ImageRegistry()
reg.register(ImageEntry(
    filename='test.png', sha256='aa'*32, size_bytes=100,
    width=10, height=10, ref_count=0, referenced_by=set(),
    source=None, created_at=datetime.now(timezone.utc),
))

# Simulate adding a ref
content = '# Test\n![](assets/test.png)'
image_ref_re = re.compile(r'!\[[^\]]*\]\((assets/[^)]+)\)')
refs = set()
for m in image_ref_re.finditer(content):
    refs.add(m.group(1).split('/')[-1])

for r in refs:
    reg.increment_ref(r, 'docs/test.md')

entry = reg.get_by_filename('test.png')
print(f'ref_count={entry.ref_count}, referenced_by={entry.referenced_by}')
assert entry.ref_count == 1
print('OK')
"`
Expected: `ref_count=1, referenced_by={'docs/test.md'}` then `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/application/wiki/wiki_service.py
git commit -m "feat: add image ref tracking on document save (diff old/new refs)"
```

---

## Task 6: Admin API Endpoints

**Files:**
- Modify: `backend/api/files.py` (add new endpoints)
- Test: `tests/test_image_admin_api.py`

- [ ] **Step 1: Write failing tests for admin endpoints**

```python
# tests/test_image_admin_api.py
"""Tests for admin image management API endpoints."""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.application.image.image_registry import ImageRegistry, ImageEntry


class TestAdminStats:
    """Test GET /api/files/assets/stats."""

    def test_stats_returns_correct_counts(self):
        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="used.png", sha256="aa" * 32, size_bytes=1000,
            width=100, height=100, ref_count=2, referenced_by={"a.md", "b.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="unused.png", sha256="bb" * 32, size_bytes=500,
            width=50, height=50, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="deriv.png", sha256="cc" * 32, size_bytes=800,
            width=100, height=100, ref_count=1, referenced_by={"c.md"},
            source="used.png", created_at=datetime.now(timezone.utc),
        ))

        stats = reg.stats()
        assert stats == {
            "total": 3,
            "unused": 1,
            "total_bytes": 2300,
            "derivative_count": 1,
        }


class TestAdminList:
    """Test GET /api/files/assets paginated listing."""

    def _make_registry_with_entries(self, count=10):
        reg = ImageRegistry()
        for i in range(count):
            reg.register(ImageEntry(
                filename=f"img{i:03d}.png",
                sha256=f"{i:03d}" + "0" * 61,
                size_bytes=100 * (i + 1),
                width=10 * (i + 1), height=10 * (i + 1),
                ref_count=i % 2,
                referenced_by={"doc.md"} if i % 2 else set(),
                source="img000.png" if i == 5 else None,
                created_at=datetime.now(timezone.utc),
            ))
        return reg

    def test_pagination(self):
        reg = self._make_registry_with_entries(10)
        result = reg.list_entries(page=1, size=3)
        assert len(result["items"]) == 3
        assert result["total"] == 10
        assert result["pages"] == 4

    def test_last_page(self):
        reg = self._make_registry_with_entries(10)
        result = reg.list_entries(page=4, size=3)
        assert len(result["items"]) == 1  # 10 items, 3 pages of 3, last page has 1

    def test_filter_unused(self):
        reg = self._make_registry_with_entries(10)
        result = reg.list_entries(page=1, size=50, filter="unused")
        for item in result["items"]:
            assert item.ref_count == 0

    def test_filter_used(self):
        reg = self._make_registry_with_entries(10)
        result = reg.list_entries(page=1, size=50, filter="used")
        for item in result["items"]:
            assert item.ref_count > 0


class TestAdminDelete:
    """Test DELETE /api/files/assets/{filename}."""

    def test_cannot_delete_referenced_image(self):
        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="referenced.png", sha256="rr" * 32, size_bytes=100,
            width=10, height=10, ref_count=1, referenced_by={"doc.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))
        entry = reg.get_by_filename("referenced.png")
        assert entry.ref_count > 0  # Cannot delete — would return 409

    def test_can_delete_unreferenced_image(self):
        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="orphan.png", sha256="oo" * 32, size_bytes=100,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))
        entry = reg.get_by_filename("orphan.png")
        assert entry.ref_count == 0

        reg.remove("orphan.png")
        assert reg.get_by_filename("orphan.png") is None


class TestBulkDelete:
    """Test POST /api/files/assets/bulk-delete."""

    def test_bulk_delete_unused(self):
        reg = ImageRegistry()
        reg.register(ImageEntry(
            filename="used.png", sha256="aa" * 32, size_bytes=1000,
            width=10, height=10, ref_count=1, referenced_by={"a.md"},
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="orphan1.png", sha256="bb" * 32, size_bytes=500,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))
        reg.register(ImageEntry(
            filename="orphan2.png", sha256="cc" * 32, size_bytes=300,
            width=10, height=10, ref_count=0, referenced_by=set(),
            source=None, created_at=datetime.now(timezone.utc),
        ))

        unused = reg.get_unused_filenames()
        assert len(unused) == 2
        total_freed = sum(reg.get_by_filename(fn).size_bytes for fn in unused)
        assert total_freed == 800

        for fn in unused:
            reg.remove(fn)

        assert reg.get_by_filename("used.png") is not None
        assert reg.get_by_filename("orphan1.png") is None
        assert reg.get_by_filename("orphan2.png") is None
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_admin_api.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 3: Add admin endpoints to files.py**

Add these endpoints to `backend/api/files.py`, replacing the old unused-image endpoints:

```python
from backend.core.auth import User, get_current_user
from backend.core.auth.permission import require_admin

# ── Admin Image Management ──────────────────────────────────────────

@router.get("/assets/stats", tags=["assets"])
async def get_asset_stats(user: User = Depends(require_admin)):
    """Get image asset statistics (admin only)."""
    if not _image_registry:
        raise HTTPException(status_code=503, detail="Image registry not initialized")
    return _image_registry.stats()


@router.get("/assets", tags=["assets"])
async def list_assets(
    page: int = 1,
    size: int = 50,
    filter: str = "all",
    search: str = "",
    user: User = Depends(require_admin),
):
    """List image assets with pagination, filtering, search (admin only)."""
    if not _image_registry:
        raise HTTPException(status_code=503, detail="Image registry not initialized")
    if size > 100:
        size = 100

    result = _image_registry.list_entries(page=page, size=size, filter=filter, search=search)

    # Serialize ImageEntry objects to dicts for JSON response
    items = []
    for entry in result["items"]:
        items.append({
            "filename": entry.filename,
            "size_bytes": entry.size_bytes,
            "width": entry.width,
            "height": entry.height,
            "ref_count": entry.ref_count,
            "referenced_by": sorted(entry.referenced_by),
            "source": entry.source,
            "derivatives": _image_registry.get_derivatives_of(entry.filename),
            "has_ocr": _has_ocr(entry.filename),
            "created_at": entry.created_at.isoformat(),
        })

    return {
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "pages": result["pages"],
    }


def _has_ocr(filename: str) -> bool:
    """Check if an image has OCR text in its sidecar."""
    sidecar = ASSETS_DIR / f"{filename}.meta.json"
    if not sidecar.exists():
        return False
    try:
        import json
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return bool(data.get("ocr_text") or data.get("description"))
    except Exception:
        return False


@router.delete("/assets/{filename}", tags=["assets"])
async def delete_asset(filename: str, user: User = Depends(require_admin)):
    """Delete a single image asset. Returns 409 if still referenced by documents."""
    if not _image_registry:
        raise HTTPException(status_code=503, detail="Image registry not initialized")

    entry = _image_registry.get_by_filename(filename)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Image not found: {filename}")
    if entry.ref_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Image still referenced by {entry.ref_count} document(s): {sorted(entry.referenced_by)}",
        )

    # Delete file + sidecar
    image_path = ASSETS_DIR / filename
    if image_path.exists():
        image_path.unlink()
    sidecar_path = ASSETS_DIR / f"{filename}.meta.json"
    if sidecar_path.exists():
        sidecar_path.unlink()

    freed = entry.size_bytes
    _image_registry.remove(filename)
    logger.info(f"Deleted image asset: {filename} ({freed} bytes)")
    return {"deleted": filename, "freed_bytes": freed}


@router.post("/assets/bulk-delete", tags=["assets"])
async def bulk_delete_assets(
    user: User = Depends(require_admin),
):
    """Delete ALL unreferenced (ref_count==0) images. Returns count + freed space."""
    if not _image_registry:
        raise HTTPException(status_code=503, detail="Image registry not initialized")

    unused = _image_registry.get_unused_filenames()
    deleted_count = 0
    freed_bytes = 0

    for filename in unused:
        entry = _image_registry.get_by_filename(filename)
        if not entry:
            continue

        image_path = ASSETS_DIR / filename
        if image_path.exists():
            image_path.unlink()
        sidecar_path = ASSETS_DIR / f"{filename}.meta.json"
        if sidecar_path.exists():
            sidecar_path.unlink()

        freed_bytes += entry.size_bytes
        _image_registry.remove(filename)
        deleted_count += 1

    logger.info(f"Bulk deleted {deleted_count} unused images ({freed_bytes} bytes freed)")
    return {"deleted": deleted_count, "freed_bytes": freed_bytes}
```

Update the existing unused image endpoints to use `require_admin`:

```python
@router.get("/assets/unused", tags=["assets"])
async def list_unused_images(user: User = Depends(require_admin)):
    """List image files in assets/ that are not referenced by any markdown file."""
    unused = _find_unused_images()
    return {"unused": unused, "count": len(unused)}


@router.delete("/assets/unused", tags=["assets"])
async def delete_unused_images(user: User = Depends(require_admin)):
    """Delete all image files in assets/ that are not referenced by any markdown file."""
    unused = _find_unused_images()
    deleted = []
    for item in unused:
        full = ASSETS_DIR / item["filename"]
        try:
            full.unlink()
            deleted.append(item["path"])
            logger.info(f"Deleted unused image: {item['path']}")
        except Exception as e:
            logger.warning(f"Failed to delete {item['path']}: {e}")
    return {"deleted": deleted, "count": len(deleted)}
```

**IMPORTANT:** The new `/assets/stats`, `/assets`, and `/assets/bulk-delete` routes must be defined BEFORE the catch-all `GET /{path:path}` route at line 240. Move the admin endpoints above the PPTX and binary CRUD sections, or FastAPI will match `/assets/stats` as a path parameter.

- [ ] **Step 4: Run all tests**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_admin_api.py tests/test_image_registry.py tests/test_image_dedup_upload.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/files.py tests/test_image_admin_api.py
git commit -m "feat: add admin image management endpoints (stats, paginated list, delete, bulk-delete)"
```

---

## Task 7: OCR Inheritance Endpoint

**Files:**
- Modify: `backend/api/files.py` (new endpoint)

- [ ] **Step 1: Add OCR inheritance endpoint**

Add to `backend/api/files.py` (before the catch-all routes):

```python
from pydantic import BaseModel

class InheritOCRRequest(BaseModel):
    source_filename: str

@router.post("/assets/{filename}/inherit-ocr", tags=["assets"])
async def inherit_ocr(filename: str, req: InheritOCRRequest):
    """Copy OCR text + description from source image sidecar to target. Sets source field."""
    target_path = ASSETS_DIR / filename
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Target image not found: {filename}")

    source_sidecar = ASSETS_DIR / f"{req.source_filename}.meta.json"
    if not source_sidecar.exists():
        raise HTTPException(status_code=404, detail=f"Source sidecar not found: {req.source_filename}")

    import json
    try:
        source_data = json.loads(source_sidecar.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read source sidecar: {e}")

    # Build target sidecar with inherited OCR + source field
    from backend.application.image.models import ImageAnalysis, save_sidecar

    analysis = ImageAnalysis(
        ocr_text=source_data.get("ocr_text", ""),
        description=source_data.get("description", ""),
        provider=source_data.get("provider", "inherited"),
        ocr_engine=source_data.get("ocr_engine", "inherited"),
        processed_at=datetime.now(timezone.utc),
        source=req.source_filename,
    )
    save_sidecar(target_path, analysis)

    # Update registry source field if available
    if _image_registry:
        entry = _image_registry.get_by_filename(filename)
        if entry:
            entry.source = req.source_filename

    return {"filename": filename, "source": req.source_filename, "inherited": True}
```

- [ ] **Step 2: Test manually**

Run: `cd /Users/donghae/workspace/ai/onTong && python -c "
from backend.application.image.models import ImageAnalysis, save_sidecar, load_sidecar
from pathlib import Path
from datetime import datetime, timezone
import tempfile, json

with tempfile.TemporaryDirectory() as td:
    p = Path(td)
    # Create source sidecar
    src = p / 'source.png'
    src.write_bytes(b'fake')
    save_sidecar(src, ImageAnalysis(
        ocr_text='카카오 고객센터', description='대화 캡처',
        provider='tesseract', ocr_engine='tesseract',
        processed_at=datetime.now(timezone.utc), source='',
    ))
    # Create target
    tgt = p / 'target.png'
    tgt.write_bytes(b'fake annotated')
    # Inherit
    src_data = json.loads((p / 'source.png.meta.json').read_text())
    inherited = ImageAnalysis(
        ocr_text=src_data['ocr_text'],
        description=src_data['description'],
        provider='inherited', ocr_engine='inherited',
        processed_at=datetime.now(timezone.utc),
        source='source.png',
    )
    save_sidecar(tgt, inherited)
    loaded = load_sidecar(tgt)
    assert loaded.ocr_text == '카카오 고객센터'
    assert loaded.source == 'source.png'
    print('OK: OCR inheritance works')
"`
Expected: `OK: OCR inheritance works`

- [ ] **Step 3: Commit**

```bash
git add backend/api/files.py
git commit -m "feat: add OCR inheritance endpoint for annotation derivatives"
```

---

## Task 8: Frontend — Install fabric.js + Image Copy from Editor

**Files:**
- Modify: `frontend/package.json` (add fabric dependency)
- Modify: `frontend/src/lib/tiptap/pasteHandler.ts` (add image copy)

- [ ] **Step 1: Install fabric.js**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npm install fabric
```

- [ ] **Step 2: Add image copy context menu + keyboard shortcut to pasteHandler.ts**

In `frontend/src/lib/tiptap/pasteHandler.ts`, add a new Tiptap extension for image copying. Add at the end of the file (or as a separate export alongside `PasteHandlerExtension`):

```typescript
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey, NodeSelection } from "@tiptap/pm/state";

export const ImageCopyExtension = Extension.create({
  name: "imageCopy",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey("imageCopy"),
        props: {
          handleKeyDown(view, event) {
            // Ctrl+C / Cmd+C when image node is selected
            if ((event.ctrlKey || event.metaKey) && event.key === "c") {
              const { selection } = view.state;
              if (selection instanceof NodeSelection && selection.node.type.name === "image") {
                const src = selection.node.attrs.src;
                if (src) {
                  copyImageToClipboard(src);
                  event.preventDefault();
                  return true;
                }
              }
            }
            return false;
          },
          handleDOMEvents: {
            contextmenu(view, event) {
              const pos = view.posAtCoords({ left: event.clientX, top: event.clientY });
              if (!pos) return false;

              const node = view.state.doc.nodeAt(pos.pos);
              if (node?.type.name === "image") {
                event.preventDefault();
                showImageContextMenu(event.clientX, event.clientY, node.attrs.src);
                return true;
              }
              return false;
            },
          },
        },
      }),
    ];
  },
});

async function copyImageToClipboard(src: string): Promise<void> {
  try {
    const res = await fetch(src);
    const blob = await res.blob();
    const pngBlob = blob.type === "image/png" ? blob : await convertToPng(blob);
    await navigator.clipboard.write([
      new ClipboardItem({ "image/png": pngBlob }),
    ]);
  } catch (err) {
    console.error("Failed to copy image:", err);
  }
}

function convertToPng(blob: Blob): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("No canvas context"));
      ctx.drawImage(img, 0, 0);
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png");
    };
    img.onerror = reject;
    img.src = URL.createObjectURL(blob);
  });
}

let _menuEl: HTMLDivElement | null = null;

function showImageContextMenu(x: number, y: number, src: string): void {
  removeImageContextMenu();

  _menuEl = document.createElement("div");
  _menuEl.style.cssText = `
    position: fixed; left: ${x}px; top: ${y}px; z-index: 9999;
    background: white; border: 1px solid #ddd; border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15); padding: 4px 0;
    font-size: 13px; min-width: 160px;
  `;

  const copyItem = document.createElement("div");
  copyItem.textContent = "이미지 복사";
  copyItem.style.cssText = "padding: 6px 12px; cursor: pointer;";
  copyItem.onmouseenter = () => (copyItem.style.background = "#f0f0f0");
  copyItem.onmouseleave = () => (copyItem.style.background = "transparent");
  copyItem.onclick = () => {
    copyImageToClipboard(src);
    removeImageContextMenu();
  };
  _menuEl.appendChild(copyItem);

  document.body.appendChild(_menuEl);

  const dismiss = (e: MouseEvent) => {
    if (_menuEl && !_menuEl.contains(e.target as Node)) {
      removeImageContextMenu();
      document.removeEventListener("mousedown", dismiss);
    }
  };
  setTimeout(() => document.addEventListener("mousedown", dismiss), 0);
}

function removeImageContextMenu(): void {
  if (_menuEl) {
    _menuEl.remove();
    _menuEl = null;
  }
}
```

- [ ] **Step 3: Register extension in MarkdownEditor**

In `frontend/src/components/editors/MarkdownEditor.tsx`, import and add the extension:

```typescript
import { ImageCopyExtension } from "@/lib/tiptap/pasteHandler";
```

Add `ImageCopyExtension` to the `extensions` array in `useEditor()`:

```typescript
extensions: [
  // ... existing extensions
  PasteHandlerExtension,
  ImageCopyExtension,  // <-- add this
  MarkdownShortcuts,
],
```

- [ ] **Step 4: Test manually in browser**

1. Start dev servers
2. Open a document with an image
3. Right-click the image → verify "이미지 복사" menu appears
4. Click "이미지 복사" → paste in another app → verify image is copied
5. Click image to select → Ctrl+C → paste → verify image is copied

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong && git add frontend/package.json frontend/package-lock.json frontend/src/lib/tiptap/pasteHandler.ts frontend/src/components/editors/MarkdownEditor.tsx
git commit -m "feat: add image copy (context menu + Ctrl+C) and install fabric.js"
```

---

## Task 9: Frontend — ImageViewerModal (Fullscreen Viewer + Annotation)

**Files:**
- Create: `frontend/src/components/editors/ImageViewerModal.tsx`
- Modify: `frontend/src/components/editors/MarkdownEditor.tsx` (click handler)

- [ ] **Step 1: Create ImageViewerModal component**

```typescript
// frontend/src/components/editors/ImageViewerModal.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X, Square, Circle, ArrowRight, Type, ZoomIn, ZoomOut, Save } from "lucide-react";
import { uploadImage } from "@/lib/clipboard/imagePaste";

type AnnotationTool = "select" | "rect" | "ellipse" | "arrow" | "text";

interface ImageViewerModalProps {
  src: string;            // Full URL: /api/files/assets/abc123.png
  filename: string;       // Just the filename: abc123.png
  onClose: () => void;
  onReplace?: (newSrc: string) => void;  // Callback to replace image in editor
}

interface ImageMeta {
  filename: string;
  size_bytes: number;
  width: number;
  height: number;
  ref_count: number;
  referenced_by: string[];
  source: string | null;
  has_ocr: boolean;
  ocr_text?: string;
  description?: string;
}

export function ImageViewerModal({ src, filename, onClose, onReplace }: ImageViewerModalProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fabricRef = useRef<any>(null);
  const [editing, setEditing] = useState(false);
  const [activeTool, setActiveTool] = useState<AnnotationTool>("select");
  const [color, setColor] = useState("#e94560");
  const [meta, setMeta] = useState<ImageMeta | null>(null);
  const [saving, setSaving] = useState(false);

  // Load image metadata
  useEffect(() => {
    fetch(`/api/files/assets/${filename}.meta.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          setMeta((prev) => ({
            ...prev,
            filename,
            ocr_text: data.ocr_text || "",
            description: data.description || "",
            source: data.source || null,
            has_ocr: !!(data.ocr_text || data.description),
          } as ImageMeta));
        }
      })
      .catch(() => {});

    // Also try admin stats for this image
    fetch(`/api/files/assets?search=${encodeURIComponent(filename)}&size=1`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.items?.[0]) {
          setMeta((prev) => ({ ...prev, ...data.items[0] }));
        }
      })
      .catch(() => {});
  }, [filename]);

  // Initialize fabric.js canvas
  useEffect(() => {
    if (!canvasRef.current) return;

    let mounted = true;

    (async () => {
      const fabricModule = await import("fabric");
      const { Canvas, FabricImage } = fabricModule;

      if (!mounted || !canvasRef.current) return;

      const container = canvasRef.current.parentElement;
      if (!container) return;

      const canvas = new Canvas(canvasRef.current, {
        width: container.clientWidth,
        height: container.clientHeight,
        selection: editing,
      });

      fabricRef.current = canvas;

      // Load the image
      const img = await FabricImage.fromURL(src, { crossOrigin: "anonymous" });

      // Fit image to canvas
      const scaleX = canvas.width! / (img.width || 1);
      const scaleY = canvas.height! / (img.height || 1);
      const scale = Math.min(scaleX, scaleY, 1) * 0.9;

      img.set({
        scaleX: scale,
        scaleY: scale,
        left: (canvas.width! - (img.width || 0) * scale) / 2,
        top: (canvas.height! - (img.height || 0) * scale) / 2,
        selectable: false,
        evented: false,
      });

      canvas.add(img);
      canvas.sendObjectToBack(img);
      canvas.renderAll();
    })();

    return () => {
      mounted = false;
      if (fabricRef.current) {
        fabricRef.current.dispose();
        fabricRef.current = null;
      }
    };
  }, [src, editing]);

  // Handle tool changes
  useEffect(() => {
    const canvas = fabricRef.current;
    if (!canvas || !editing) return;

    canvas.isDrawingMode = false;
    canvas.selection = activeTool === "select";

    // Remove previous mouse handlers
    canvas.off("mouse:down");
    canvas.off("mouse:move");
    canvas.off("mouse:up");

    if (activeTool === "rect") {
      let startX = 0, startY = 0, rect: any = null;
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        startX = pointer.x;
        startY = pointer.y;
        import("fabric").then(({ Rect }) => {
          rect = new Rect({
            left: startX, top: startY, width: 0, height: 0,
            fill: "transparent", stroke: color, strokeWidth: 3,
          });
          canvas.add(rect);
        });
      });
      canvas.on("mouse:move", (opt: any) => {
        if (!rect) return;
        const pointer = canvas.getScenePoint(opt.e);
        rect.set({
          width: Math.abs(pointer.x - startX),
          height: Math.abs(pointer.y - startY),
          left: Math.min(startX, pointer.x),
          top: Math.min(startY, pointer.y),
        });
        canvas.renderAll();
      });
      canvas.on("mouse:up", () => { rect = null; });
    }

    if (activeTool === "ellipse") {
      let startX = 0, startY = 0, ellipse: any = null;
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        startX = pointer.x;
        startY = pointer.y;
        import("fabric").then(({ Ellipse }) => {
          ellipse = new Ellipse({
            left: startX, top: startY, rx: 0, ry: 0,
            fill: "transparent", stroke: color, strokeWidth: 3,
          });
          canvas.add(ellipse);
        });
      });
      canvas.on("mouse:move", (opt: any) => {
        if (!ellipse) return;
        const pointer = canvas.getScenePoint(opt.e);
        ellipse.set({
          rx: Math.abs(pointer.x - startX) / 2,
          ry: Math.abs(pointer.y - startY) / 2,
          left: Math.min(startX, pointer.x),
          top: Math.min(startY, pointer.y),
        });
        canvas.renderAll();
      });
      canvas.on("mouse:up", () => { ellipse = null; });
    }

    if (activeTool === "arrow") {
      let startX = 0, startY = 0, line: any = null;
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        startX = pointer.x;
        startY = pointer.y;
        import("fabric").then(({ Line }) => {
          line = new Line([startX, startY, startX, startY], {
            stroke: color, strokeWidth: 3,
          });
          canvas.add(line);
        });
      });
      canvas.on("mouse:move", (opt: any) => {
        if (!line) return;
        const pointer = canvas.getScenePoint(opt.e);
        line.set({ x2: pointer.x, y2: pointer.y });
        canvas.renderAll();
      });
      canvas.on("mouse:up", () => { line = null; });
    }

    if (activeTool === "text") {
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        import("fabric").then(({ IText }) => {
          const text = new IText("텍스트", {
            left: pointer.x, top: pointer.y,
            fontSize: 20, fill: color,
            fontFamily: "sans-serif",
          });
          canvas.add(text);
          canvas.setActiveObject(text);
          text.enterEditing();
        });
      });
    }
  }, [activeTool, color, editing]);

  const handleSave = useCallback(async () => {
    const canvas = fabricRef.current;
    if (!canvas) return;
    setSaving(true);

    try {
      // Export canvas as PNG blob
      const dataUrl = canvas.toDataURL({ format: "png", multiplier: 1 });
      const res = await fetch(dataUrl);
      const blob = await res.blob();
      const file = new File([blob], "annotated.png", { type: "image/png" });

      // Upload
      const path = await uploadImage(file);

      // Ask about OCR inheritance
      const newFilename = path.split("/").pop() || "";
      const inheritOcr = window.confirm(
        "원본 OCR 텍스트를 상속하시겠습니까?\n\n" +
        "확인: 원본 OCR 상속\n취소: 새로 OCR 처리 (저장 후 자동 실행)"
      );

      if (inheritOcr) {
        await fetch(`/api/files/assets/${newFilename}/inherit-ocr`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_filename: filename }),
        });
      }

      // Replace image in editor
      if (onReplace) {
        onReplace(`/api/files/${path}`);
      }
      onClose();
    } catch (err) {
      console.error("Failed to save annotation:", err);
      alert("저장 실패: " + (err as Error).message);
    } finally {
      setSaving(false);
    }
  }, [filename, onClose, onReplace]);

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex" onClick={(e) => e.target === e.currentTarget && onClose()}>
      {/* Left toolbar */}
      <div className="w-11 bg-gray-900 flex flex-col items-center py-3 gap-2">
        {editing && (
          <>
            {([
              ["select", "↖", "선택"],
              ["rect", null, "사각형"],
              ["ellipse", null, "타원"],
              ["arrow", null, "화살표"],
              ["text", null, "텍스트"],
            ] as const).map(([tool, icon, label]) => (
              <button
                key={tool}
                onClick={() => setActiveTool(tool as AnnotationTool)}
                className={`w-8 h-8 rounded flex items-center justify-center text-xs ${
                  activeTool === tool ? "bg-red-500 text-white" : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
                title={label}
              >
                {tool === "rect" && <Square size={14} />}
                {tool === "ellipse" && <Circle size={14} />}
                {tool === "arrow" && <ArrowRight size={14} />}
                {tool === "text" && <Type size={14} />}
                {tool === "select" && <span>↖</span>}
              </button>
            ))}
            <div className="my-1 border-t border-gray-700 w-6" />
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="w-7 h-7 rounded cursor-pointer border-0"
              title="색상"
            />
          </>
        )}
        <div className="flex-1" />
        <button
          onClick={() => {
            const canvas = fabricRef.current;
            if (canvas) canvas.setZoom(canvas.getZoom() * 1.2);
          }}
          className="w-8 h-8 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 flex items-center justify-center"
          title="확대"
        >
          <ZoomIn size={14} />
        </button>
        <button
          onClick={() => {
            const canvas = fabricRef.current;
            if (canvas) canvas.setZoom(canvas.getZoom() / 1.2);
          }}
          className="w-8 h-8 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 flex items-center justify-center"
          title="축소"
        >
          <ZoomOut size={14} />
        </button>
      </div>

      {/* Center canvas */}
      <div className="flex-1 flex items-center justify-center relative">
        <canvas ref={canvasRef} />
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-8 h-8 rounded-full bg-gray-800/80 text-white flex items-center justify-center hover:bg-gray-700"
        >
          <X size={16} />
        </button>
      </div>

      {/* Right info panel */}
      <div className="w-52 bg-gray-900 text-gray-300 p-3 text-xs overflow-y-auto">
        <div className="text-red-400 font-bold mb-2">이미지 정보</div>
        <div className="space-y-1 mb-4">
          <div>파일: {filename}</div>
          {meta && (
            <>
              <div>크기: {meta.width} x {meta.height}</div>
              <div>용량: {formatBytes(meta.size_bytes)}</div>
              <div>참조: {meta.ref_count ?? "?"}개 문서</div>
              {meta.source && <div className="text-purple-400">원본: {meta.source}</div>}
            </>
          )}
        </div>

        {meta?.ocr_text && (
          <>
            <div className="text-red-400 font-bold mb-2">OCR 텍스트</div>
            <div className="text-gray-400 text-[10px] leading-relaxed mb-4 max-h-40 overflow-y-auto">
              {meta.ocr_text}
            </div>
          </>
        )}

        {meta?.description && (
          <>
            <div className="text-red-400 font-bold mb-2">설명</div>
            <div className="text-gray-400 text-[10px] leading-relaxed mb-4 max-h-40 overflow-y-auto">
              {meta.description}
            </div>
          </>
        )}

        {meta?.referenced_by && meta.referenced_by.length > 0 && (
          <>
            <div className="text-red-400 font-bold mb-2">참조 문서</div>
            <div className="space-y-1 mb-4">
              {meta.referenced_by.map((doc) => (
                <div key={doc} className="text-blue-400 text-[10px] truncate">{doc}</div>
              ))}
            </div>
          </>
        )}

        <div className="mt-4 space-y-2">
          {!editing ? (
            <button
              onClick={() => setEditing(true)}
              className="w-full py-1.5 bg-red-500 text-white rounded text-xs hover:bg-red-600"
            >
              편집
            </button>
          ) : (
            <>
              <button
                onClick={handleSave}
                disabled={saving}
                className="w-full py-1.5 bg-red-500 text-white rounded text-xs hover:bg-red-600 disabled:opacity-50 flex items-center justify-center gap-1"
              >
                <Save size={12} />
                {saving ? "저장 중..." : "새 이미지로 저장"}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="w-full py-1.5 bg-gray-700 text-gray-300 rounded text-xs hover:bg-gray-600"
              >
                취소
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (!bytes) return "?";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}
```

- [ ] **Step 2: Add click-to-open handler in MarkdownEditor**

In `frontend/src/components/editors/MarkdownEditor.tsx`:

1. Import the modal:
```typescript
import { ImageViewerModal } from "@/components/editors/ImageViewerModal";
```

2. Add state:
```typescript
const [viewerImage, setViewerImage] = useState<{ src: string; filename: string } | null>(null);
```

3. Add a click handler in `editorProps`:
```typescript
editorProps: {
  attributes: { class: "prose max-w-none focus:outline-none..." },
  handleClickOn(view, pos, node, nodePos, event) {
    if (node.type.name === "image") {
      const src = node.attrs.src as string;
      const filename = src.split("/").pop() || "";
      setViewerImage({ src, filename });
      return true;
    }
    return false;
  },
},
```

4. Add the `onReplace` callback:
```typescript
const handleImageReplace = useCallback((newSrc: string) => {
  if (!editor || !viewerImage) return;
  // Find and replace the image node
  editor.state.doc.descendants((node, pos) => {
    if (node.type.name === "image" && node.attrs.src === viewerImage.src) {
      editor.chain().focus().setNodeSelection(pos).run();
      editor.commands.updateAttributes("image", { src: newSrc });
      return false;
    }
  });
}, [editor, viewerImage]);
```

5. Render the modal in the JSX (before closing `</div>`):
```tsx
{viewerImage && (
  <ImageViewerModal
    src={viewerImage.src}
    filename={viewerImage.filename}
    onClose={() => setViewerImage(null)}
    onReplace={handleImageReplace}
  />
)}
```

- [ ] **Step 3: Test in browser**

1. Start dev servers
2. Open a document with an image
3. Click on the image → verify fullscreen modal opens
4. Verify image info panel shows metadata
5. Click "편집" → draw a rectangle → click "새 이미지로 저장"
6. Verify new image uploaded and replaced in editor
7. Press Escape → verify modal closes

- [ ] **Step 4: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong && git add frontend/src/components/editors/ImageViewerModal.tsx frontend/src/components/editors/MarkdownEditor.tsx
git commit -m "feat: add fullscreen image viewer modal with fabric.js annotation editor"
```

---

## Task 10: Frontend — ImageManagementPage (Admin Gallery)

**Files:**
- Create: `frontend/src/components/editors/ImageManagementPage.tsx`

- [ ] **Step 1: Create the admin gallery component**

```typescript
// frontend/src/components/editors/ImageManagementPage.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Trash2, Search, Image as ImageIcon, ChevronLeft, ChevronRight } from "lucide-react";

interface ImageAsset {
  filename: string;
  size_bytes: number;
  width: number;
  height: number;
  ref_count: number;
  referenced_by: string[];
  source: string | null;
  derivatives: string[];
  has_ocr: boolean;
  created_at: string;
}

interface AssetStats {
  total: number;
  unused: number;
  total_bytes: number;
  derivative_count: number;
}

type FilterType = "all" | "used" | "unused" | "derivative";

export function ImageManagementPage() {
  const [stats, setStats] = useState<AssetStats | null>(null);
  const [items, setItems] = useState<ImageAsset[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<FilterType>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<ImageAsset | null>(null);
  const [loading, setLoading] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout>>();

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/files/assets/stats");
      if (res.ok) setStats(await res.json());
    } catch {}
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        size: "50",
        filter,
        ...(search && { search }),
      });
      const res = await fetch(`/api/files/assets?${params}`);
      if (res.ok) {
        const data = await res.json();
        setItems(data.items);
        setTotalPages(data.pages);
        setTotal(data.total);
      }
    } catch {} finally {
      setLoading(false);
    }
  }, [page, filter, search]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleSearch = (value: string) => {
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setSearch(value);
      setPage(1);
    }, 300);
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`"${filename}" 을(를) 삭제하시겠습니까?`)) return;
    const res = await fetch(`/api/files/assets/${filename}`, { method: "DELETE" });
    if (res.ok) {
      fetchItems();
      fetchStats();
      setDetail(null);
    } else {
      const err = await res.json();
      alert(err.detail || "삭제 실패");
    }
  };

  const handleBulkDelete = async () => {
    if (!stats) return;
    const msg = `미사용 이미지 ${stats.unused}개 (${formatBytes(
      items.filter((i) => i.ref_count === 0).reduce((s, i) => s + i.size_bytes, 0) || 0
    )}) 를 삭제하시겠습니까?`;
    if (!confirm(msg)) return;

    const res = await fetch("/api/files/assets/bulk-delete", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      alert(`${data.deleted}개 삭제 완료 (${formatBytes(data.freed_bytes)} 확보)`);
      setSelected(new Set());
      fetchItems();
      fetchStats();
    }
  };

  const toggleSelect = (filename: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const selectAllUnused = () => {
    const unused = items.filter((i) => i.ref_count === 0).map((i) => i.filename);
    setSelected(new Set(unused));
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-3">
          <span className="font-bold text-sm">이미지 관리</span>
          {stats && (
            <>
              <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">
                전체 {stats.total}개
              </span>
              <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full">
                미사용 {stats.unused}개
              </span>
              <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full">
                {formatBytes(stats.total_bytes)}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="파일명 검색..."
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-7 pr-3 py-1.5 text-xs border rounded-md w-44 bg-background"
            />
          </div>
          <select
            value={filter}
            onChange={(e) => { setFilter(e.target.value as FilterType); setPage(1); }}
            className="px-2 py-1.5 text-xs border rounded-md bg-background"
          >
            <option value="all">전체</option>
            <option value="used">사용 중</option>
            <option value="unused">미사용</option>
            <option value="derivative">파생본</option>
          </select>
        </div>
      </div>

      {/* Gallery grid */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">로딩 중...</div>
        ) : items.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            <ImageIcon size={20} className="mr-2" />
            이미지가 없습니다
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {items.map((item) => (
              <ImageCard
                key={item.filename}
                item={item}
                isSelected={selected.has(item.filename)}
                onToggleSelect={() => toggleSelect(item.filename)}
                onClick={() => setDetail(item)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-t bg-muted/30">
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {selected.size > 0
              ? `${selected.size}개 선택됨`
              : `${total}개 중 ${items.length}개 표시`}
          </span>
          {/* Pagination */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 rounded hover:bg-muted disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-xs text-muted-foreground px-1">{page}/{totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1 rounded hover:bg-muted disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={selectAllUnused}
            className="px-3 py-1.5 text-xs border rounded-md hover:bg-muted"
          >
            전체 미사용 선택
          </button>
          <button
            onClick={handleBulkDelete}
            disabled={!stats || stats.unused === 0}
            className="px-3 py-1.5 text-xs bg-red-500 text-white rounded-md hover:bg-red-600 disabled:opacity-50"
          >
            <Trash2 size={12} className="inline mr-1" />
            미사용 전체 삭제
          </button>
        </div>
      </div>

      {/* Detail modal */}
      {detail && (
        <DetailModal
          item={detail}
          onClose={() => setDetail(null)}
          onDelete={() => handleDelete(detail.filename)}
        />
      )}
    </div>
  );
}


function ImageCard({
  item,
  isSelected,
  onToggleSelect,
  onClick,
}: {
  item: ImageAsset;
  isSelected: boolean;
  onToggleSelect: () => void;
  onClick: () => void;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);

  // Intersection Observer for lazy loading
  useEffect(() => {
    const el = imgRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.src = `/api/files/assets/${item.filename}`;
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [item.filename]);

  const borderColor = item.ref_count > 0
    ? "border-green-300"
    : "border-orange-400 border-2";

  return (
    <div
      className={`rounded-lg overflow-hidden bg-card cursor-pointer hover:shadow-md transition-shadow ${borderColor} border`}
      onClick={onClick}
    >
      {/* Thumbnail */}
      <div className="h-24 bg-muted/30 flex items-center justify-center relative">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          alt={item.filename}
          onLoad={() => setLoaded(true)}
          className={`max-h-full max-w-full object-contain transition-opacity ${loaded ? "opacity-100" : "opacity-0"}`}
          draggable={false}
        />
        {!loaded && (
          <ImageIcon size={20} className="absolute text-muted-foreground" />
        )}
        {/* Badges */}
        <div className="absolute top-1 right-1 flex gap-1">
          {item.ref_count > 0 ? (
            <span className="bg-green-500 text-white text-[9px] px-1.5 py-0.5 rounded">
              참조 {item.ref_count}
            </span>
          ) : (
            <span className="bg-orange-500 text-white text-[9px] px-1.5 py-0.5 rounded">미사용</span>
          )}
        </div>
        {item.source && (
          <span className="absolute top-1 left-1 bg-purple-500 text-white text-[9px] px-1.5 py-0.5 rounded">
            파생
          </span>
        )}
        {item.derivatives.length > 0 && (
          <span className="absolute bottom-1 left-1 bg-purple-500 text-white text-[9px] px-1.5 py-0.5 rounded">
            파생 {item.derivatives.length}
          </span>
        )}
        {/* Checkbox for unused */}
        {item.ref_count === 0 && (
          <div className="absolute bottom-1 right-1" onClick={(e) => e.stopPropagation()}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={onToggleSelect}
              className="w-4 h-4 cursor-pointer"
            />
          </div>
        )}
      </div>
      {/* Info */}
      <div className="p-2">
        <div className="text-[11px] font-medium truncate">{item.filename}</div>
        <div className="text-[10px] text-muted-foreground">
          {formatBytes(item.size_bytes)} &middot; {item.width}x{item.height}
        </div>
      </div>
    </div>
  );
}


function DetailModal({
  item,
  onClose,
  onDelete,
}: {
  item: ImageAsset;
  onClose: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-card rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-sm">{item.filename}</h3>
            <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg">&times;</button>
          </div>

          {/* Preview */}
          <div className="bg-muted/30 rounded-lg p-4 flex items-center justify-center mb-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/files/assets/${item.filename}`} alt={item.filename} className="max-h-60 max-w-full object-contain" />
          </div>

          {/* Info grid */}
          <div className="grid grid-cols-2 gap-2 text-xs mb-4">
            <div className="text-muted-foreground">크기</div>
            <div>{item.width} x {item.height}</div>
            <div className="text-muted-foreground">용량</div>
            <div>{formatBytes(item.size_bytes)}</div>
            <div className="text-muted-foreground">참조 수</div>
            <div>{item.ref_count}</div>
            <div className="text-muted-foreground">OCR</div>
            <div>{item.has_ocr ? "있음" : "없음"}</div>
            {item.source && (
              <>
                <div className="text-muted-foreground">원본</div>
                <div className="text-purple-600">{item.source}</div>
              </>
            )}
            <div className="text-muted-foreground">생성일</div>
            <div>{new Date(item.created_at).toLocaleDateString("ko-KR")}</div>
          </div>

          {/* Referenced by */}
          {item.referenced_by.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-bold mb-1">참조 문서</div>
              <div className="space-y-0.5">
                {item.referenced_by.map((doc) => (
                  <div key={doc} className="text-xs text-blue-600 truncate">{doc}</div>
                ))}
              </div>
            </div>
          )}

          {/* Derivatives */}
          {item.derivatives.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-bold mb-1">파생 이미지</div>
              <div className="space-y-0.5">
                {item.derivatives.map((d) => (
                  <div key={d} className="text-xs text-purple-600 truncate">{d}</div>
                ))}
              </div>
            </div>
          )}

          {/* Delete button (only for unused) */}
          {item.ref_count === 0 && (
            <button
              onClick={onDelete}
              className="w-full py-2 bg-red-500 text-white text-xs rounded-md hover:bg-red-600"
            >
              <Trash2 size={12} className="inline mr-1" />
              삭제
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


function formatBytes(bytes: number): string {
  if (!bytes) return "0B";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}
```

- [ ] **Step 2: Test in browser (after routing is wired up in Task 11)**

This component is tested as part of Task 11 after routing is connected.

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong && git add frontend/src/components/editors/ImageManagementPage.tsx
git commit -m "feat: add admin image management gallery page with pagination and bulk delete"
```

---

## Task 11: Frontend — Routing, Types, and Admin Gate

**Files:**
- Modify: `frontend/src/types/workspace.ts:25-33` (add VirtualTabType)
- Modify: `frontend/src/lib/workspace/useWorkspaceStore.ts:49-58` (add title)
- Modify: `frontend/src/components/workspace/FileRouter.tsx` (add route)
- Modify: `frontend/src/components/TreeNav.tsx` (add settings item + admin gate)

- [ ] **Step 1: Add "image-management" to VirtualTabType**

In `frontend/src/types/workspace.ts`:

```typescript
export type VirtualTabType =
  | "metadata-templates"
  | "untagged-dashboard"
  | "conflict-dashboard"
  | "document-compare"
  | "document-graph"
  | "permission-editor"
  | "scoring-dashboard"
  | "maintenance-digest"
  | "image-management";  // <-- add this
```

- [ ] **Step 2: Add title in workspace store**

In `frontend/src/lib/workspace/useWorkspaceStore.ts`, add to `VIRTUAL_TAB_TITLES`:

```typescript
const VIRTUAL_TAB_TITLES: Record<VirtualTabType, string> = {
  "metadata-templates": "메타데이터 템플릿 관리",
  "untagged-dashboard": "미태깅 문서 대시보드",
  "conflict-dashboard": "관련 문서 관리",
  "document-compare": "문서 비교",
  "document-graph": "문서 관계 그래프",
  "permission-editor": "접근 권한 관리",
  "scoring-dashboard": "신뢰도 설정",
  "maintenance-digest": "관리가 필요한 문서",
  "image-management": "이미지 관리",  // <-- add this
};
```

- [ ] **Step 3: Add route in FileRouter**

In `frontend/src/components/workspace/FileRouter.tsx`:

1. Import:
```typescript
import { ImageManagementPage } from "@/components/editors/ImageManagementPage";
```

2. Add case before `default`:
```typescript
case "image-management":
  return <ImageManagementPage />;
```

- [ ] **Step 4: Add "이미지 관리" to TreeNav settings section + admin gate on UnusedImagesPanel**

In `frontend/src/components/TreeNav.tsx`, find the `SettingsSection` and add a new item. Also wrap the existing `UnusedImagesPanel` behind an admin check.

In the settings items list (around line 1337), add:

```typescript
{user?.roles.includes("admin") && (
  <button
    onClick={() => openVirtualTab("image-management")}
    className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-accent"
  >
    <ImageIcon size={16} />
    이미지 관리
  </button>
)}
```

Import `Image as ImageIcon` from `lucide-react` if not already imported.

For the existing `UnusedImagesPanel` (around line 1401), wrap it:

```typescript
{user?.roles.includes("admin") && <UnusedImagesPanel />}
```

- [ ] **Step 5: Test in browser**

1. Start dev servers
2. Click Settings in TreeNav sidebar → verify "이미지 관리" appears (if admin)
3. Click "이미지 관리" → verify gallery page opens in workspace
4. Verify pagination, filtering, search work
5. Verify unused images show checkboxes
6. Verify bulk delete works
7. Click on a card → verify detail modal opens

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong && git add frontend/src/types/workspace.ts frontend/src/lib/workspace/useWorkspaceStore.ts frontend/src/components/workspace/FileRouter.tsx frontend/src/components/TreeNav.tsx
git commit -m "feat: wire up image management page routing, admin gate on unused images panel"
```

---

## Spec Coverage Check

| Spec Section | Task |
|---|---|
| 1.1 Image Registry | Task 1 |
| 1.2 Upload Dedup | Task 3 |
| 1.3 Editor Image Copy | Task 8 |
| 1.4 Image Reference Tracking on Save | Task 5 |
| 2.1 Viewer Modal | Task 9 |
| 2.2 Annotation Save Flow | Task 9 |
| 2.3 Sidecar Extension (source field) | Task 2 |
| 2.4 Canvas Library (fabric.js) | Task 8 (install), Task 9 (usage) |
| 3.1 Backend API Extensions | Task 6 |
| 3.2 Frontend Page | Task 10 |
| 3.3 Access Control | Task 6 (backend), Task 11 (frontend) |
| OCR Inheritance | Task 7 |
| Registry init + events | Task 4 |

All spec sections covered. No gaps.
