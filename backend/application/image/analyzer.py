"""Image analyzer orchestrator: OCR (free) → Vision fallback (paid)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import ImageAnalysis, save_sidecar, load_sidecar, needs_processing
from .ocr_engine import OCREngine
from .vision_provider import VisionProvider, NoopVisionProvider

logger = logging.getLogger(__name__)

# Minimum OCR chars to consider "sufficient" — skip Vision if OCR exceeds this
MIN_OCR_CHARS = 20


class ImageAnalyzer:
    """Coordinates OCR + Vision for full image analysis.

    Cost-optimized strategy:
    1. Run OCR first (Tesseract — free, local)
    2. If OCR extracts enough text (>= MIN_OCR_CHARS), skip Vision (saves API cost)
    3. If OCR returns empty/insufficient, fall back to Vision LLM (paid)

    Manages sidecar cache: skips processing for images with fresh metadata.
    """

    def __init__(self, ocr: OCREngine, vision: VisionProvider):
        self.ocr = ocr
        self.vision = vision

    async def analyze(self, image_path: Path, force: bool = False) -> ImageAnalysis:
        """Analyze an image: OCR first, Vision only if OCR is insufficient.

        Returns cached result if sidecar is fresh (unless force=True).
        Writes sidecar file after processing.
        """
        if not force and not needs_processing(image_path):
            cached = load_sidecar(image_path)
            if cached is not None:
                logger.debug(f"Using cached sidecar for {image_path.name}")
                return cached

        # Step 1: OCR (free, local)
        ocr_text = await self.ocr.extract_text(image_path)
        if ocr_text:
            logger.info(f"OCR extracted {len(ocr_text)} chars from {image_path.name}")

        # Step 2: Vision — only if OCR is insufficient AND vision is configured
        description = ""
        vision_used = False
        if len(ocr_text) < MIN_OCR_CHARS and not isinstance(self.vision, NoopVisionProvider):
            logger.info(f"OCR insufficient ({len(ocr_text)} chars < {MIN_OCR_CHARS}) — calling Vision for {image_path.name}")
            description = await self.vision.describe(image_path, ocr_text)
            vision_used = True
            if description:
                logger.info(f"Vision generated {len(description)} chars for {image_path.name}")
        elif len(ocr_text) >= MIN_OCR_CHARS:
            logger.info(f"OCR sufficient ({len(ocr_text)} chars) — skipping Vision for {image_path.name}")

        analysis = ImageAnalysis(
            ocr_text=ocr_text,
            description=description,
            provider=self.vision.provider_name if vision_used else "none",
            ocr_engine=self.ocr._detect_backend(),
            processed_at=datetime.now(timezone.utc),
        )

        save_sidecar(image_path, analysis)
        return analysis
