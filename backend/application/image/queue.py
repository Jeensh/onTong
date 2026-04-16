"""Async background processing queue for image analysis."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from .analyzer import ImageAnalyzer
from .models import needs_processing

logger = logging.getLogger(__name__)

IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def extract_image_paths(markdown_content: str) -> list[str]:
    """Extract local image paths from markdown content.

    Filters out external URLs (http/https). Returns relative paths
    like 'assets/abc123.png'.
    """
    paths = []
    for match in IMAGE_REF_RE.finditer(markdown_content):
        path = match.group(1)
        if not path.startswith(("http://", "https://")):
            paths.append(path)
    return paths


class ImageProcessingQueue:
    """Process a batch of images through the analysis pipeline."""

    def __init__(self, analyzer: ImageAnalyzer):
        self.analyzer = analyzer

    async def process_images(
        self, image_paths: list[Path], force: bool = False, max_concurrent: int = 1
    ) -> dict:
        """Process a list of image paths. Returns stats dict.

        Skips images that already have fresh sidecar files (unless force=True).
        Uses asyncio.Semaphore for parallel processing when max_concurrent > 1.
        """
        processed = 0
        skipped = 0
        errors = 0
        sem = asyncio.Semaphore(max_concurrent)

        async def _process_one(img_path: Path) -> str:
            if not img_path.exists():
                logger.warning(f"Image not found, skipping: {img_path}")
                return "error"
            if not force and not needs_processing(img_path):
                return "skipped"
            try:
                async with sem:
                    await self.analyzer.analyze(img_path, force=True)
                return "processed"
            except Exception as e:
                logger.warning(f"Failed to process {img_path.name}: {e}")
                return "error"

        results = await asyncio.gather(*[_process_one(p) for p in image_paths])
        for r in results:
            if r == "processed":
                processed += 1
            elif r == "skipped":
                skipped += 1
            else:
                errors += 1

        logger.info(
            f"Image processing complete: {processed} processed, "
            f"{skipped} skipped, {errors} errors"
        )
        return {"processed": processed, "skipped": skipped, "errors": errors}

    async def process_document_images(
        self, markdown_content: str, wiki_root: Path
    ) -> dict:
        """Extract image references from markdown and process them."""
        rel_paths = extract_image_paths(markdown_content)
        abs_paths = [wiki_root / p for p in rel_paths]
        return await self.process_images(abs_paths)
