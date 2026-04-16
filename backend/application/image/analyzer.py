"""Image analyzer orchestrator: OCR + Vision → sidecar."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import ImageAnalysis, save_sidecar, load_sidecar, needs_processing
from .ocr_engine import OCREngine
from .vision_provider import VisionProvider

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """Coordinates OCR + Vision for full image analysis.

    Manages sidecar cache: skips processing for images with fresh metadata.
    """

    def __init__(self, ocr: OCREngine, vision: VisionProvider):
        self.ocr = ocr
        self.vision = vision

    async def analyze(self, image_path: Path, force: bool = False) -> ImageAnalysis:
        """Analyze an image: OCR text extraction + Vision description.

        Returns cached result if sidecar is fresh (unless force=True).
        Writes sidecar file after processing.
        """
        if not force and not needs_processing(image_path):
            cached = load_sidecar(image_path)
            if cached is not None:
                logger.debug(f"Using cached sidecar for {image_path.name}")
                return cached

        ocr_text = await self.ocr.extract_text(image_path)
        logger.debug(f"OCR extracted {len(ocr_text)} chars from {image_path.name}")

        description = await self.vision.describe(image_path, ocr_text)
        if description:
            logger.debug(f"Vision generated {len(description)} chars for {image_path.name}")

        analysis = ImageAnalysis(
            ocr_text=ocr_text,
            description=description,
            provider=self.vision.provider_name,
            ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        )

        save_sidecar(image_path, analysis)
        return analysis
