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


class TestOCREngine:
    """Test EasyOCR wrapper."""

    def test_ocr_engine_init(self):
        """Verify OCREngine can be instantiated."""
        from backend.application.image.ocr_engine import OCREngine
        engine = OCREngine(languages=["en"], gpu=False)
        assert engine is not None

    @pytest.mark.asyncio
    async def test_ocr_extract_text_from_image(self, tmp_path):
        """Test OCR on a real image with text."""
        import asyncio
        from backend.application.image.ocr_engine import OCREngine
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), "Hello World 500 Error", fill="black")
        img_path = tmp_path / "test_ocr.png"
        img.save(img_path)
        engine = OCREngine(languages=["en"], gpu=False)
        text = await engine.extract_text(img_path)
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_ocr_empty_image(self, tmp_path):
        """Test OCR on blank image returns empty string."""
        from backend.application.image.ocr_engine import OCREngine
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="white")
        img_path = tmp_path / "blank.png"
        img.save(img_path)
        engine = OCREngine(languages=["en"], gpu=False)
        text = await engine.extract_text(img_path)
        assert isinstance(text, str)

    def test_ocr_extract_text_sync(self, tmp_path):
        """Test OCR on a real image with text (sync wrapper for environments without pytest-asyncio)."""
        import asyncio
        from backend.application.image.ocr_engine import OCREngine
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), "Hello World 500 Error", fill="black")
        img_path = tmp_path / "test_ocr_sync.png"
        img.save(img_path)
        engine = OCREngine(languages=["en"], gpu=False)
        text = asyncio.run(engine.extract_text(img_path))
        assert len(text) > 0

    def test_ocr_empty_image_sync(self, tmp_path):
        """Test OCR on blank image returns empty string (sync wrapper)."""
        import asyncio
        from backend.application.image.ocr_engine import OCREngine
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="white")
        img_path = tmp_path / "blank_sync.png"
        img.save(img_path)
        engine = OCREngine(languages=["en"], gpu=False)
        text = asyncio.run(engine.extract_text(img_path))
        assert isinstance(text, str)


class TestVisionProviders:
    """Test Vision LLM provider abstraction."""

    @pytest.mark.asyncio
    async def test_noop_provider_returns_empty(self, tmp_path):
        from backend.application.image.vision_provider import NoopVisionProvider
        provider = NoopVisionProvider()
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake")
        result = await provider.describe(img_path, "some ocr text")
        assert result == ""
        assert provider.provider_name == "none"

    @pytest.mark.asyncio
    async def test_ollama_provider_has_correct_name(self):
        from backend.application.image.vision_provider import OllamaVisionProvider
        provider = OllamaVisionProvider(model="llava:13b", ollama_url="http://localhost:11434")
        assert provider.provider_name == "ollama/llava:13b"

    def test_create_vision_provider_noop(self):
        from backend.application.image.vision_provider import create_vision_provider
        provider = create_vision_provider("none")
        assert provider.provider_name == "none"

    def test_create_vision_provider_ollama(self):
        from backend.application.image.vision_provider import create_vision_provider
        provider = create_vision_provider("ollama", model="llava:7b", ollama_url="http://localhost:11434")
        assert provider.provider_name == "ollama/llava:7b"


class TestImageAnalyzer:
    """Test ImageAnalyzer orchestrator (OCR + Vision → sidecar)."""

    @pytest.mark.asyncio
    async def test_analyze_creates_sidecar(self, tmp_path):
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import load_sidecar
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (300, 80), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 20), "Test OCR Text", fill="black")
        img_path = tmp_path / "test_analyze.png"
        img.save(img_path)

        analyzer = ImageAnalyzer(
            ocr=OCREngine(languages=["en"], gpu=False),
            vision=NoopVisionProvider(),
        )
        analysis = await analyzer.analyze(img_path)

        assert len(analysis.ocr_text) > 0
        assert analysis.description == ""
        assert analysis.provider == "none"
        assert analysis.ocr_engine == "easyocr"

        sidecar = load_sidecar(img_path)
        assert sidecar is not None
        assert sidecar.ocr_text == analysis.ocr_text

    @pytest.mark.asyncio
    async def test_analyze_skips_if_fresh(self, tmp_path):
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from datetime import datetime, timezone
        import time

        img_path = tmp_path / "cached.png"
        img_path.write_bytes(b"fake image")
        time.sleep(0.05)

        save_sidecar(img_path, ImageAnalysis(
            ocr_text="cached text", description="cached desc",
            provider="test", ocr_engine="test",
            processed_at=datetime.now(timezone.utc),
        ))

        analyzer = ImageAnalyzer(
            ocr=OCREngine(languages=["en"], gpu=False),
            vision=NoopVisionProvider(),
        )
        analysis = await analyzer.analyze(img_path)

        assert analysis.ocr_text == "cached text"
        assert analysis.description == "cached desc"

    @pytest.mark.asyncio
    async def test_analyze_force_reprocess(self, tmp_path):
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from PIL import Image, ImageDraw
        from datetime import datetime, timezone
        import time

        img = Image.new("RGB", (300, 80), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 20), "Fresh Text", fill="black")
        img_path = tmp_path / "force.png"
        img.save(img_path)
        time.sleep(0.05)

        save_sidecar(img_path, ImageAnalysis(
            ocr_text="old", description="old",
            provider="old", ocr_engine="old",
            processed_at=datetime.now(timezone.utc),
        ))

        analyzer = ImageAnalyzer(
            ocr=OCREngine(languages=["en"], gpu=False),
            vision=NoopVisionProvider(),
        )
        analysis = await analyzer.analyze(img_path, force=True)

        assert analysis.ocr_text != "old"
        assert analysis.provider == "none"


class TestIndexerEnrichment:
    """Test image description injection into wiki indexer chunks."""

    def test_enrich_chunk_with_image_description(self, tmp_path):
        from backend.application.wiki.wiki_indexer import enrich_chunk_with_images
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from datetime import datetime, timezone

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        img_path = assets_dir / "abc123.png"
        img_path.write_bytes(b"fake")
        save_sidecar(img_path, ImageAnalysis(
            ocr_text="500 서버 에러",
            description="결제 화면 에러 스크린샷. HTTP 500 응답.",
            provider="noop", ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        ))

        chunk_text = "# 결제 문의\n\n![](assets/abc123.png)\n\n추가 메모"
        enriched = enrich_chunk_with_images(chunk_text, tmp_path)

        assert "결제 화면 에러 스크린샷" in enriched
        assert "![](assets/abc123.png)" not in enriched
        assert "추가 메모" in enriched
        assert "[이미지:" in enriched

    def test_enrich_chunk_ocr_only_fallback(self, tmp_path):
        from backend.application.wiki.wiki_indexer import enrich_chunk_with_images
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from datetime import datetime, timezone

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        img_path = assets_dir / "def456.png"
        img_path.write_bytes(b"fake")
        save_sidecar(img_path, ImageAnalysis(
            ocr_text="에러 코드 ERR-001",
            description="",
            provider="none", ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        ))

        chunk_text = "![에러 화면](assets/def456.png)"
        enriched = enrich_chunk_with_images(chunk_text, tmp_path)

        assert "이미지 텍스트: 에러 코드 ERR-001" in enriched

    def test_enrich_chunk_no_sidecar_keeps_original(self, tmp_path):
        from backend.application.wiki.wiki_indexer import enrich_chunk_with_images

        chunk_text = "![](assets/no_meta.png)"
        enriched = enrich_chunk_with_images(chunk_text, tmp_path)

        assert enriched == chunk_text

    def test_enrich_chunk_no_images_unchanged(self, tmp_path):
        from backend.application.wiki.wiki_indexer import enrich_chunk_with_images

        chunk_text = "Plain text with no images at all."
        enriched = enrich_chunk_with_images(chunk_text, tmp_path)

        assert enriched == chunk_text

    def test_enrich_chunk_multiple_images(self, tmp_path):
        from backend.application.wiki.wiki_indexer import enrich_chunk_with_images
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from datetime import datetime, timezone

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()

        for name, desc in [("img1.png", "첫 번째 이미지"), ("img2.png", "두 번째 이미지")]:
            p = assets_dir / name
            p.write_bytes(b"fake")
            save_sidecar(p, ImageAnalysis(
                ocr_text="", description=desc,
                provider="noop", ocr_engine="easyocr",
                processed_at=datetime.now(timezone.utc),
            ))

        chunk_text = "![](assets/img1.png)\n![](assets/img2.png)"
        enriched = enrich_chunk_with_images(chunk_text, tmp_path)

        assert "첫 번째 이미지" in enriched
        assert "두 번째 이미지" in enriched


class TestImageProcessingQueue:
    """Test async background processing queue."""

    @pytest.mark.asyncio
    async def test_queue_processes_images(self, tmp_path):
        from backend.application.image.queue import ImageProcessingQueue
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import load_sidecar
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (300, 80), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 20), "Queue Test", fill="black")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        img_path = assets_dir / "queued.png"
        img.save(img_path)

        analyzer = ImageAnalyzer(
            ocr=OCREngine(languages=["en"], gpu=False),
            vision=NoopVisionProvider(),
        )
        queue = ImageProcessingQueue(analyzer)
        await queue.process_images([img_path])

        sidecar = load_sidecar(img_path)
        assert sidecar is not None
        assert len(sidecar.ocr_text) > 0

    @pytest.mark.asyncio
    async def test_queue_processes_images_sync(self, tmp_path):
        """Async version ensuring OCR pipeline processes images end-to-end."""
        from backend.application.image.queue import ImageProcessingQueue
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import load_sidecar
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (300, 80), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 20), "Queue Test", fill="black")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        img_path = assets_dir / "queued.png"
        img.save(img_path)

        analyzer = ImageAnalyzer(
            ocr=OCREngine(languages=["en"], gpu=False),
            vision=NoopVisionProvider(),
        )
        queue = ImageProcessingQueue(analyzer)
        await queue.process_images([img_path])

        sidecar = load_sidecar(img_path)
        assert sidecar is not None
        assert len(sidecar.ocr_text) > 0

    @pytest.mark.asyncio
    async def test_queue_skips_already_processed(self, tmp_path):
        from backend.application.image.queue import ImageProcessingQueue
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from datetime import datetime, timezone
        import time

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        img_path = assets_dir / "done.png"
        img_path.write_bytes(b"fake")
        time.sleep(0.05)

        save_sidecar(img_path, ImageAnalysis(
            ocr_text="already done", description="",
            provider="none", ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        ))

        analyzer = ImageAnalyzer(
            ocr=OCREngine(languages=["en"], gpu=False),
            vision=NoopVisionProvider(),
        )
        queue = ImageProcessingQueue(analyzer)
        result = await queue.process_images([img_path])

        assert result["skipped"] == 1
        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_queue_skips_already_processed_sync(self, tmp_path):
        """Async version ensuring skip logic works when sidecar is fresh."""
        from backend.application.image.queue import ImageProcessingQueue
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from datetime import datetime, timezone
        import time

        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        img_path = assets_dir / "done.png"
        img_path.write_bytes(b"fake")
        time.sleep(0.05)

        save_sidecar(img_path, ImageAnalysis(
            ocr_text="already done", description="",
            provider="none", ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        ))

        analyzer = ImageAnalyzer(
            ocr=OCREngine(languages=["en"], gpu=False),
            vision=NoopVisionProvider(),
        )
        queue = ImageProcessingQueue(analyzer)
        result = await queue.process_images([img_path])

        assert result["skipped"] == 1
        assert result["processed"] == 0

    def test_extract_image_paths_from_markdown(self):
        from backend.application.image.queue import extract_image_paths

        content = """# Test
![](assets/img1.png)
Some text
![alt text](assets/img2.jpg)
![](https://external.com/img.png)
"""
        paths = extract_image_paths(content)
        assert paths == ["assets/img1.png", "assets/img2.jpg"]
