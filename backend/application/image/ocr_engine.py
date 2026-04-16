"""EasyOCR wrapper for text extraction from images."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class OCREngine:
    """Extract text from images using EasyOCR.

    EasyOCR model is loaded lazily on first use to avoid startup cost.
    """

    def __init__(
        self,
        languages: list[str] | None = None,
        gpu: bool = False,
        confidence_threshold: float = 0.3,
    ):
        self._languages = languages or ["ko", "en"]
        self._gpu = gpu
        self._confidence_threshold = confidence_threshold
        self._reader = None  # lazy init

    def _get_reader(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(self._languages, gpu=self._gpu)
            logger.info(f"EasyOCR initialized: languages={self._languages}, gpu={self._gpu}")
        return self._reader

    async def extract_text(self, image_path: Path) -> str:
        """Extract text from an image file.

        Runs EasyOCR in a thread pool to avoid blocking the event loop.
        """
        def _run_ocr() -> str:
            reader = self._get_reader()
            results = reader.readtext(str(image_path))
            lines = [text for _, text, conf in results if conf >= self._confidence_threshold]
            return "\n".join(lines)

        return await asyncio.to_thread(_run_ocr)
