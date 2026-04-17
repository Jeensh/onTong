"""OCR engine: Tesseract (primary) with EasyOCR fallback."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class OCREngine:
    """Extract text from images using Tesseract (primary) or EasyOCR (fallback).

    Tesseract runs as a system binary via pytesseract — works on any Python version.
    Includes image preprocessing (upscale + contrast boost) for better accuracy.
    Falls back to EasyOCR if Tesseract is unavailable.
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
        self._easyocr_reader = None  # lazy init
        self._backend: str | None = None  # detected backend

    def _detect_backend(self) -> str:
        """Detect available OCR backend: tesseract > easyocr > none."""
        if self._backend is not None:
            return self._backend

        # Try tesseract first
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._backend = "tesseract"
            logger.info("OCR backend: tesseract")
            return self._backend
        except Exception:
            pass

        # Try easyocr
        try:
            import easyocr  # noqa: F401
            self._backend = "easyocr"
            logger.info("OCR backend: easyocr")
            return self._backend
        except ImportError:
            pass

        self._backend = "none"
        logger.warning("No OCR backend available (install tesseract or easyocr)")
        return self._backend

    def _run_tesseract(self, image_path: Path) -> str:
        """Run Tesseract OCR with preprocessing for better accuracy."""
        import pytesseract
        from PIL import Image, ImageEnhance

        img = Image.open(image_path)

        # Preprocess: grayscale → upscale 3x → contrast boost
        img = img.convert("L")
        img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(2.0)

        # Map language codes: ko → kor, en → eng (tesseract format)
        lang_map = {"ko": "kor", "en": "eng", "ja": "jpn", "zh": "chi_sim"}
        tess_langs = "+".join(lang_map.get(l, l) for l in self._languages)

        text = pytesseract.image_to_string(img, lang=tess_langs, config="--psm 6")
        return text.strip()

    def _run_easyocr(self, image_path: Path) -> str:
        """Run EasyOCR (requires torch, Python <3.13)."""
        if self._easyocr_reader is None:
            import easyocr
            self._easyocr_reader = easyocr.Reader(self._languages, gpu=self._gpu)
            logger.info(f"EasyOCR initialized: languages={self._languages}")

        results = self._easyocr_reader.readtext(str(image_path))
        lines = [text for _, text, conf in results if conf >= self._confidence_threshold]
        return "\n".join(lines)

    async def extract_text(self, image_path: Path) -> str:
        """Extract text from an image file.

        Runs OCR in a thread pool to avoid blocking the event loop.
        Returns empty string if no OCR backend is available.
        """
        backend = self._detect_backend()
        if backend == "none":
            return ""

        def _run() -> str:
            if backend == "tesseract":
                return self._run_tesseract(image_path)
            else:
                return self._run_easyocr(image_path)

        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            logger.warning(f"OCR ({backend}) failed for {image_path.name}: {e}")
            return ""
