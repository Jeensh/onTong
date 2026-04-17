"""Tests for ImageRegistry: hash index, ref counting, and startup scan."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# TestImageEntry
# ---------------------------------------------------------------------------

class TestImageEntry:
    """Tests for the ImageEntry dataclass."""

    def test_create_entry(self):
        from backend.application.image.image_registry import ImageEntry

        entry = ImageEntry(
            filename="f8f8873a4c18.png",
            sha256="abc123def456" * 5,  # 60-char hex-like
            size_bytes=20480,
            width=800,
            height=600,
            ref_count=0,
            referenced_by=set(),
            source=None,
            created_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
        )

        assert entry.filename == "f8f8873a4c18.png"
        assert entry.size_bytes == 20480
        assert entry.width == 800
        assert entry.height == 600
        assert entry.ref_count == 0
        assert entry.referenced_by == set()
        assert entry.source is None

    def test_entry_with_source(self):
        from backend.application.image.image_registry import ImageEntry

        entry = ImageEntry(
            filename="annotated_f8f8873a4c18.png",
            sha256="deadbeef" * 8,
            size_bytes=10000,
            width=800,
            height=600,
            ref_count=0,
            referenced_by=set(),
            source="f8f8873a4c18.png",
            created_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
        )

        assert entry.source == "f8f8873a4c18.png"


# ---------------------------------------------------------------------------
# TestImageRegistry
# ---------------------------------------------------------------------------

def _make_entry(
    filename: str = "img001.png",
    sha256: str = "aabbcc",
    size: int = 1024,
    source: str | None = None,
) -> "ImageEntry":
    from backend.application.image.image_registry import ImageEntry

    return ImageEntry(
        filename=filename,
        sha256=sha256,
        size_bytes=size,
        width=100,
        height=100,
        ref_count=0,
        referenced_by=set(),
        source=source,
        created_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )


class TestImageRegistry:
    """Tests for ImageRegistry in-memory index operations."""

    def test_register_and_lookup_by_hash(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        entry = _make_entry("img001.png", sha256="hash001")
        reg.register(entry)

        found = reg.get_by_hash("hash001")
        assert found is not None
        assert found.filename == "img001.png"

    def test_lookup_missing_returns_none(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        assert reg.get_by_hash("nonexistent") is None

    def test_get_by_filename(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        entry = _make_entry("img002.png", sha256="hash002")
        reg.register(entry)

        found = reg.get_by_filename("img002.png")
        assert found is not None
        assert found.sha256 == "hash002"

    def test_get_by_filename_missing_returns_none(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        assert reg.get_by_filename("nope.png") is None

    def test_first_registered_hash_wins(self):
        """When two entries share the same hash (duplicate), first registered wins hash→filename mapping."""
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        e1 = _make_entry("first.png", sha256="same_hash")
        e2 = _make_entry("second.png", sha256="same_hash")
        reg.register(e1)
        reg.register(e2)

        # hash→filename mapping should point to first
        found = reg.get_by_hash("same_hash")
        assert found.filename == "first.png"
        # Both should be retrievable by filename
        assert reg.get_by_filename("first.png") is not None
        assert reg.get_by_filename("second.png") is not None

    def test_increment_ref(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        entry = _make_entry("img003.png")
        reg.register(entry)

        reg.increment_ref("img003.png", "docs/pageA.md")
        reg.increment_ref("img003.png", "docs/pageB.md")

        e = reg.get_by_filename("img003.png")
        assert e.ref_count == 2
        assert "docs/pageA.md" in e.referenced_by
        assert "docs/pageB.md" in e.referenced_by

    def test_increment_ref_same_doc_is_idempotent(self):
        """Adding the same doc path twice should not inflate ref_count."""
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("img004.png"))

        reg.increment_ref("img004.png", "docs/pageA.md")
        reg.increment_ref("img004.png", "docs/pageA.md")

        e = reg.get_by_filename("img004.png")
        assert e.ref_count == 1

    def test_decrement_ref(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("img005.png"))
        reg.increment_ref("img005.png", "docs/pageA.md")
        reg.increment_ref("img005.png", "docs/pageB.md")

        reg.decrement_ref("img005.png", "docs/pageA.md")

        e = reg.get_by_filename("img005.png")
        assert e.ref_count == 1
        assert "docs/pageA.md" not in e.referenced_by
        assert "docs/pageB.md" in e.referenced_by

    def test_decrement_floors_at_zero(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("img006.png"))

        # Call decrement without any prior increment
        reg.decrement_ref("img006.png", "docs/missing.md")

        e = reg.get_by_filename("img006.png")
        assert e.ref_count == 0

    def test_remove_all_refs_for_doc(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("imgA.png"))
        reg.register(_make_entry("imgB.png", sha256="hashB"))

        reg.increment_ref("imgA.png", "docs/page1.md")
        reg.increment_ref("imgB.png", "docs/page1.md")
        reg.increment_ref("imgA.png", "docs/page2.md")  # imgA also referenced by page2

        reg.remove_all_refs_for_doc("docs/page1.md")

        a = reg.get_by_filename("imgA.png")
        b = reg.get_by_filename("imgB.png")
        assert "docs/page1.md" not in a.referenced_by
        assert a.ref_count == 1  # still referenced by page2
        assert b.ref_count == 0

    def test_get_refs_for_doc(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("x.png"))
        reg.register(_make_entry("y.png", sha256="hashY"))
        reg.register(_make_entry("z.png", sha256="hashZ"))

        reg.increment_ref("x.png", "docs/mypage.md")
        reg.increment_ref("z.png", "docs/mypage.md")

        refs = reg.get_refs_for_doc("docs/mypage.md")
        assert refs == {"x.png", "z.png"}

    def test_remove_entry(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        entry = _make_entry("del.png", sha256="hashDel")
        reg.register(entry)

        reg.remove("del.png")

        assert reg.get_by_filename("del.png") is None
        # hash map should no longer return this filename
        result = reg.get_by_hash("hashDel")
        assert result is None

    def test_remove_entry_missing_is_noop(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        # Should not raise
        reg.remove("does_not_exist.png")

    def test_stats(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("a.png", sha256="h1", size=1000))
        reg.register(_make_entry("b.png", sha256="h2", size=2000))
        reg.register(_make_entry("c.png", sha256="h3", size=500, source="a.png"))  # derivative

        reg.increment_ref("a.png", "docs/page1.md")

        stats = reg.stats()
        assert stats["total"] == 3
        assert stats["unused"] == 2          # b and c have ref_count == 0
        assert stats["total_bytes"] == 3500
        assert stats["derivative_count"] == 1

    def test_list_paginated(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        for i in range(10):
            reg.register(_make_entry(f"img{i:02d}.png", sha256=f"hash{i:02d}"))

        result = reg.list_entries(page=1, size=4)
        assert result["total"] == 10
        assert result["page"] == 1
        assert result["pages"] == 3
        assert len(result["items"]) == 4

        result2 = reg.list_entries(page=3, size=4)
        assert len(result2["items"]) == 2  # 10 - 8 = 2 remaining

    def test_list_filter_unused(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("used.png", sha256="h1"))
        reg.register(_make_entry("unused1.png", sha256="h2"))
        reg.register(_make_entry("unused2.png", sha256="h3"))

        reg.increment_ref("used.png", "docs/page.md")

        result = reg.list_entries(page=1, size=10, filter="unused")
        filenames = {item["filename"] for item in result["items"]}
        assert "unused1.png" in filenames
        assert "unused2.png" in filenames
        assert "used.png" not in filenames

    def test_list_filter_used(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("used.png", sha256="h1"))
        reg.register(_make_entry("unused.png", sha256="h2"))

        reg.increment_ref("used.png", "docs/page.md")

        result = reg.list_entries(page=1, size=10, filter="used")
        filenames = {item["filename"] for item in result["items"]}
        assert "used.png" in filenames
        assert "unused.png" not in filenames

    def test_list_filter_derivative(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("original.png", sha256="h1"))
        reg.register(_make_entry("deriv.png", sha256="h2", source="original.png"))
        reg.register(_make_entry("plain.png", sha256="h3"))

        result = reg.list_entries(page=1, size=10, filter="derivative")
        filenames = {item["filename"] for item in result["items"]}
        assert "deriv.png" in filenames
        assert "original.png" not in filenames
        assert "plain.png" not in filenames

    def test_list_search_by_filename(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("screenshot_20260417.png", sha256="h1"))
        reg.register(_make_entry("chart_revenue.png", sha256="h2"))
        reg.register(_make_entry("screenshot_error.png", sha256="h3"))

        result = reg.list_entries(page=1, size=10, search="screenshot")
        filenames = {item["filename"] for item in result["items"]}
        assert "screenshot_20260417.png" in filenames
        assert "screenshot_error.png" in filenames
        assert "chart_revenue.png" not in filenames

    def test_get_unused_filenames(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("used.png", sha256="h1"))
        reg.register(_make_entry("orphan.png", sha256="h2"))

        reg.increment_ref("used.png", "docs/page.md")

        unused = reg.get_unused_filenames()
        assert "orphan.png" in unused
        assert "used.png" not in unused

    def test_get_derivatives_of(self):
        from backend.application.image.image_registry import ImageRegistry

        reg = ImageRegistry()
        reg.register(_make_entry("parent.png", sha256="h1"))
        reg.register(_make_entry("child1.png", sha256="h2", source="parent.png"))
        reg.register(_make_entry("child2.png", sha256="h3", source="parent.png"))
        reg.register(_make_entry("unrelated.png", sha256="h4"))

        derivatives = reg.get_derivatives_of("parent.png")
        assert set(derivatives) == {"child1.png", "child2.png"}


# ---------------------------------------------------------------------------
# TestImageRegistryScan
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class TestImageRegistryScan:
    """Tests for ImageRegistry.scan() startup population."""

    def test_scan_assets_dir(self, tmp_path):
        """scan() should populate registry from images and sidecar source fields + markdown refs."""
        from PIL import Image
        from backend.application.image.image_registry import ImageRegistry

        # Create wiki directory layout
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        assets_dir = wiki_dir / "assets"
        assets_dir.mkdir()

        # Create two real PNG images so PIL can open them
        for name in ["img_a.png", "img_b.png"]:
            img = Image.new("RGB", (10, 10), color="white")
            img.save(assets_dir / name)

        # Create a derivative image and write its sidecar with source field
        derivative_name = "img_b_annotated.png"
        img_d = Image.new("RGB", (10, 10), color="red")
        img_d.save(assets_dir / derivative_name)
        sidecar_data = {"source": "img_b.png"}
        (assets_dir / f"{derivative_name}.meta.json").write_text(
            json.dumps(sidecar_data), encoding="utf-8"
        )

        # Create markdown documents referencing images
        docs_dir = wiki_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "page1.md").write_text(
            "# Page 1\n![](assets/img_a.png)\n![](assets/img_b.png)\n",
            encoding="utf-8",
        )
        (docs_dir / "page2.md").write_text(
            "# Page 2\n![](assets/img_a.png)\n",
            encoding="utf-8",
        )

        reg = ImageRegistry()
        reg.scan(wiki_dir)

        # All three images should be registered
        assert reg.get_by_filename("img_a.png") is not None
        assert reg.get_by_filename("img_b.png") is not None
        assert reg.get_by_filename("img_b_annotated.png") is not None

        # Hash lookup should work
        sha_a = _sha256_file(assets_dir / "img_a.png")
        assert reg.get_by_hash(sha_a) is not None

        # ref_count for img_a should be 2 (referenced by page1 and page2)
        entry_a = reg.get_by_filename("img_a.png")
        assert entry_a.ref_count == 2
        assert "docs/page1.md" in entry_a.referenced_by
        assert "docs/page2.md" in entry_a.referenced_by

        # ref_count for img_b should be 1 (only page1)
        entry_b = reg.get_by_filename("img_b.png")
        assert entry_b.ref_count == 1

        # derivative source should be populated from sidecar
        entry_d = reg.get_by_filename("img_b_annotated.png")
        assert entry_d.source == "img_b.png"

    def test_scan_dimensions(self, tmp_path):
        """scan() should correctly record pixel dimensions."""
        from PIL import Image
        from backend.application.image.image_registry import ImageRegistry

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        assets_dir = wiki_dir / "assets"
        assets_dir.mkdir()

        img = Image.new("RGB", (320, 240), color="blue")
        img.save(assets_dir / "sized.png")

        reg = ImageRegistry()
        reg.scan(wiki_dir)

        entry = reg.get_by_filename("sized.png")
        assert entry is not None
        assert entry.width == 320
        assert entry.height == 240

    def test_scan_empty_assets_dir(self, tmp_path):
        """scan() on an empty assets dir should produce an empty registry."""
        from backend.application.image.image_registry import ImageRegistry

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        (wiki_dir / "assets").mkdir()

        reg = ImageRegistry()
        reg.scan(wiki_dir)

        stats = reg.stats()
        assert stats["total"] == 0

    def test_scan_no_assets_dir(self, tmp_path):
        """scan() when assets dir doesn't exist should not raise — just return empty."""
        from backend.application.image.image_registry import ImageRegistry

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        # No assets dir created

        reg = ImageRegistry()
        reg.scan(wiki_dir)  # should not raise

        assert reg.stats()["total"] == 0

    def test_scan_size_bytes(self, tmp_path):
        """scan() should record correct file size."""
        from PIL import Image
        from backend.application.image.image_registry import ImageRegistry

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        assets_dir = wiki_dir / "assets"
        assets_dir.mkdir()

        img = Image.new("RGB", (50, 50), color="green")
        img_path = assets_dir / "sized_bytes.png"
        img.save(img_path)
        expected_size = img_path.stat().st_size

        reg = ImageRegistry()
        reg.scan(wiki_dir)

        entry = reg.get_by_filename("sized_bytes.png")
        assert entry is not None
        assert entry.size_bytes == expected_size
