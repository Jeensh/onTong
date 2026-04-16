"""Async background processing queue for image analysis."""

from __future__ import annotations

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
        self, image_paths: list[Path], force: bool = False
    ) -> dict:
        """Process a list of image paths. Returns stats dict.

        Skips images that already have fresh sidecar files (unless force=True).
        """
        processed = 0
        skipped = 0
        errors = 0

        for img_path in image_paths:
            if not img_path.exists():
                logger.warning(f"Image not found, skipping: {img_path}")
                errors += 1
                continue

            if not force and not needs_processing(img_path):
                skipped += 1
                continue

            try:
                await self.analyzer.analyze(img_path, force=force)
                processed += 1
                logger.debug(f"Processed image: {img_path.name}")
            except Exception as e:
                logger.warning(f"Failed to process {img_path.name}: {e}")
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
