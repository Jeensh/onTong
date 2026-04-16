"""Tests for image analysis pipeline."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone


class TestImageAnalysisModels:
    """Test ImageAnalysis dataclass and sidecar file I/O."""

    def test_image_analysis_to_dict(self):
        from backend.application.image.models import ImageAnalysis

        analysis = ImageAnalysis(
            ocr_text="결제가 안 돼요\n500 서버 에러",
            description="카카오톡 대화 캡처. 고객이 결제 실패를 보고.",
            provider="ollama/llava:13b",
            ocr_engine="easyocr",
            processed_at=datetime(2026, 4, 16, 10, 30, 0, tzinfo=timezone.utc),
        )
        d = analysis.to_dict()
        assert d["version"] == 1
        assert d["ocr_text"] == "결제가 안 돼요\n500 서버 에러"
        assert d["description"] == "카카오톡 대화 캡처. 고객이 결제 실패를 보고."
        assert d["provider"] == "ollama/llava:13b"
        assert d["ocr_engine"] == "easyocr"
        assert d["processed_at"] == "2026-04-16T10:30:00+00:00"

    def test_image_analysis_from_dict(self):
        from backend.application.image.models import ImageAnalysis

        d = {
            "version": 1,
            "ocr_text": "hello",
            "description": "a greeting",
            "provider": "noop",
            "ocr_engine": "easyocr",
            "processed_at": "2026-04-16T10:30:00+00:00",
        }
        analysis = ImageAnalysis.from_dict(d)
        assert analysis.ocr_text == "hello"
        assert analysis.description == "a greeting"
        assert analysis.provider == "noop"

    def test_sidecar_save_and_load(self, tmp_path):
        from backend.application.image.models import ImageAnalysis, save_sidecar, load_sidecar

        image_path = tmp_path / "test.png"
        image_path.write_bytes(b"fake png")

        analysis = ImageAnalysis(
            ocr_text="OCR text here",
            description="Description here",
            provider="noop",
            ocr_engine="easyocr",
            processed_at=datetime(2026, 4, 16, 10, 0, 0, tzinfo=timezone.utc),
        )
        save_sidecar(image_path, analysis)

        meta_path = tmp_path / "test.png.meta.json"
        assert meta_path.exists()

        loaded = load_sidecar(image_path)
        assert loaded is not None
        assert loaded.ocr_text == "OCR text here"
        assert loaded.description == "Description here"

    def test_load_sidecar_missing(self, tmp_path):
        from backend.application.image.models import load_sidecar

        image_path = tmp_path / "missing.png"
        assert load_sidecar(image_path) is None

    def test_needs_processing_no_sidecar(self, tmp_path):
        from backend.application.image.models import needs_processing

        image_path = tmp_path / "new.png"
        image_path.write_bytes(b"fake")
        assert needs_processing(image_path) is True

    def test_needs_processing_fresh_sidecar(self, tmp_path):
        from backend.application.image.models import (
            ImageAnalysis, save_sidecar, needs_processing,
        )
        import time

        image_path = tmp_path / "old.png"
        image_path.write_bytes(b"fake")
        time.sleep(0.05)

        save_sidecar(image_path, ImageAnalysis(
            ocr_text="text", description="desc", provider="noop",
            ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        ))
        assert needs_processing(image_path) is False
