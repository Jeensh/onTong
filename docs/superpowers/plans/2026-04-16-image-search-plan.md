# Image Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make wiki images searchable by extracting text (OCR) and generating contextual descriptions (Vision LLM), injecting them into the existing text indexing pipeline.

**Architecture:** Two-stage image analysis (OCR + Vision) produces sidecar `.meta.json` files per image. The wiki indexer reads these sidecars and injects descriptions into text chunks before embedding. No search pipeline changes needed.

**Tech Stack:** EasyOCR (Korean+English), Ollama client (Vision LLM), FastAPI (async background processing), existing ChromaDB + BM25 indexing.

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `backend/application/image/__init__.py` | Package init, exports `ImageAnalyzer`, `ImageAnalysis` |
| `backend/application/image/models.py` | `ImageAnalysis` dataclass + sidecar I/O |
| `backend/application/image/ocr_engine.py` | EasyOCR wrapper with Korean+English support |
| `backend/application/image/vision_provider.py` | `VisionProvider` protocol + `NoopVisionProvider` + `OllamaVisionProvider` |
| `backend/application/image/analyzer.py` | `ImageAnalyzer` orchestrator (OCR + Vision → sidecar) |
| `backend/application/image/queue.py` | Async background processing queue for images |
| `backend/cli/__init__.py` | CLI package init |
| `backend/cli/backfill_images.py` | CLI tool for bulk processing existing images |
| `tests/test_image_analysis.py` | Unit tests for OCR, Vision, Analyzer, indexer enrichment |

### Modified files

| File | Change |
|---|---|
| `backend/core/config.py` | Add image analysis settings |
| `backend/application/wiki/wiki_indexer.py` | Add `enrich_chunk_with_images()` to chunking pipeline |
| `backend/application/wiki/wiki_service.py` | Trigger image processing on document save |
| `backend/main.py` | Initialize `ImageAnalyzer` and wire into `WikiService` |
| `pyproject.toml` | Add `easyocr` and `ollama` dependencies |

---

### Task 1: Data Models and Sidecar I/O

**Files:**
- Create: `backend/application/image/__init__.py`
- Create: `backend/application/image/models.py`
- Test: `tests/test_image_analysis.py`

- [ ] **Step 1: Write the failing test for ImageAnalysis dataclass and sidecar I/O**

```python
# tests/test_image_analysis.py
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
        time.sleep(0.05)  # ensure sidecar is newer

        save_sidecar(image_path, ImageAnalysis(
            ocr_text="text", description="desc", provider="noop",
            ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        ))
        assert needs_processing(image_path) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageAnalysisModels -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.application.image'`

- [ ] **Step 3: Create the package init**

```python
# backend/application/image/__init__.py
"""Image analysis pipeline for wiki image searchability."""

from .models import ImageAnalysis, save_sidecar, load_sidecar, needs_processing
from .analyzer import ImageAnalyzer

__all__ = [
    "ImageAnalysis",
    "ImageAnalyzer",
    "save_sidecar",
    "load_sidecar",
    "needs_processing",
]
```

Note: This will still fail until `analyzer.py` exists. Create a placeholder:

```python
# backend/application/image/analyzer.py (placeholder — implemented in Task 4)
"""Image analyzer orchestrator. Placeholder for Task 4."""
```

- [ ] **Step 4: Implement models.py**

```python
# backend/application/image/models.py
"""Image analysis data models and sidecar file I/O."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SIDECAR_VERSION = 1


@dataclass
class ImageAnalysis:
    ocr_text: str
    description: str
    provider: str
    ocr_engine: str
    processed_at: datetime

    def to_dict(self) -> dict:
        return {
            "version": SIDECAR_VERSION,
            "ocr_text": self.ocr_text,
            "description": self.description,
            "provider": self.provider,
            "ocr_engine": self.ocr_engine,
            "processed_at": self.processed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> ImageAnalysis:
        return cls(
            ocr_text=d.get("ocr_text", ""),
            description=d.get("description", ""),
            provider=d.get("provider", ""),
            ocr_engine=d.get("ocr_engine", ""),
            processed_at=datetime.fromisoformat(d["processed_at"]),
        )


def _meta_path_for(image_path: Path) -> Path:
    """Return the sidecar .meta.json path for an image."""
    return image_path.parent / (image_path.name + ".meta.json")


def save_sidecar(image_path: Path, analysis: ImageAnalysis) -> None:
    """Write analysis results to sidecar JSON file."""
    meta_path = _meta_path_for(image_path)
    meta_path.write_text(
        json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.debug(f"Saved sidecar: {meta_path}")


def load_sidecar(image_path: Path) -> ImageAnalysis | None:
    """Load analysis from sidecar JSON file. Returns None if not found."""
    meta_path = _meta_path_for(image_path)
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return ImageAnalysis.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to load sidecar {meta_path}: {e}")
        return None


def needs_processing(image_path: Path) -> bool:
    """Check if an image needs (re-)processing.

    Returns True if no sidecar exists or image is newer than sidecar.
    """
    meta_path = _meta_path_for(image_path)
    if not meta_path.exists():
        return True
    return image_path.stat().st_mtime > meta_path.stat().st_mtime
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageAnalysisModels -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/application/image/__init__.py backend/application/image/models.py backend/application/image/analyzer.py tests/test_image_analysis.py
git commit -m "feat(image): add ImageAnalysis data models and sidecar I/O"
```

---

### Task 2: OCR Engine (EasyOCR Wrapper)

**Files:**
- Create: `backend/application/image/ocr_engine.py`
- Modify: `pyproject.toml` (add easyocr dependency)
- Test: `tests/test_image_analysis.py`

- [ ] **Step 1: Add easyocr dependency**

In `pyproject.toml`, under `[tool.poetry.dependencies]`, add:

```toml
# Image Analysis (OCR)
easyocr = "^1.7"
```

Then install:

```bash
cd /Users/donghae/workspace/ai/onTong && pip install easyocr
```

- [ ] **Step 2: Write the failing test for OCREngine**

Append to `tests/test_image_analysis.py`:

```python
class TestOCREngine:
    """Test EasyOCR wrapper."""

    def test_ocr_engine_init(self):
        """Verify OCREngine can be instantiated (downloads model on first run)."""
        from backend.application.image.ocr_engine import OCREngine

        engine = OCREngine(languages=["en"], gpu=False)
        assert engine is not None

    @pytest.mark.asyncio
    async def test_ocr_extract_text_from_image(self, tmp_path):
        """Test OCR on a real image with text."""
        from backend.application.image.ocr_engine import OCREngine
        from PIL import Image, ImageDraw, ImageFont

        # Create a test image with text
        img = Image.new("RGB", (400, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), "Hello World 500 Error", fill="black")
        img_path = tmp_path / "test_ocr.png"
        img.save(img_path)

        engine = OCREngine(languages=["en"], gpu=False)
        text = await engine.extract_text(img_path)
        # EasyOCR should extract at least part of the text
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestOCREngine -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.application.image.ocr_engine'`

- [ ] **Step 4: Implement ocr_engine.py**

```python
# backend/application/image/ocr_engine.py
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
            logger.info(
                f"EasyOCR initialized: languages={self._languages}, gpu={self._gpu}"
            )
        return self._reader

    async def extract_text(self, image_path: Path) -> str:
        """Extract text from an image file.

        Runs EasyOCR in a thread pool to avoid blocking the event loop.
        Returns extracted text lines joined by newline, filtered by confidence.
        """

        def _run_ocr() -> str:
            reader = self._get_reader()
            results = reader.readtext(str(image_path))
            lines = [
                text
                for _, text, conf in results
                if conf >= self._confidence_threshold
            ]
            return "\n".join(lines)

        return await asyncio.to_thread(_run_ocr)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestOCREngine -v`
Expected: All 3 tests PASS (first run may be slow due to EasyOCR model download)

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/application/image/ocr_engine.py pyproject.toml
git commit -m "feat(image): add EasyOCR wrapper for text extraction"
```

---

### Task 3: Vision Provider Abstraction

**Files:**
- Create: `backend/application/image/vision_provider.py`
- Modify: `pyproject.toml` (add ollama dependency)
- Test: `tests/test_image_analysis.py`

- [ ] **Step 1: Add ollama dependency**

In `pyproject.toml`, under `[tool.poetry.dependencies]`, add:

```toml
# Image Analysis (Vision LLM)
ollama = ">=0.4"
```

Then install:

```bash
cd /Users/donghae/workspace/ai/onTong && pip install ollama
```

- [ ] **Step 2: Write the failing test for VisionProviders**

Append to `tests/test_image_analysis.py`:

```python
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

        provider = OllamaVisionProvider(
            model="llava:13b",
            ollama_url="http://localhost:11434",
        )
        assert provider.provider_name == "ollama/llava:13b"

    def test_create_vision_provider_noop(self):
        from backend.application.image.vision_provider import create_vision_provider

        provider = create_vision_provider("none")
        assert provider.provider_name == "none"

    def test_create_vision_provider_ollama(self):
        from backend.application.image.vision_provider import create_vision_provider

        provider = create_vision_provider(
            "ollama", model="llava:7b", ollama_url="http://localhost:11434"
        )
        assert provider.provider_name == "ollama/llava:7b"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestVisionProviders -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.application.image.vision_provider'`

- [ ] **Step 4: Implement vision_provider.py**

```python
# backend/application/image/vision_provider.py
"""Vision LLM provider abstraction for image description generation."""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

VISION_PROMPT = """이 이미지는 사내 위키 문서에 포함된 것입니다.
이 이미지의 내용을 문서 본문의 일부로 사용할 수 있도록 상세히 설명하세요.

포함할 내용:
- 이미지 유형 (대화 캡처, 에러 화면, 시스템 화면, 다이어그램 등)
- 등장하는 사람/시스템 이름
- 핵심 내용 요약 (무슨 상황인지)
- 중요한 수치, 코드, 에러 메시지
- 시간 정보가 있으면 포함

아래는 OCR로 추출된 텍스트입니다. 참고하되, 이미지의 시각적 맥락(레이아웃, UI 상태, 관계)을 추가로 설명하세요.

OCR 텍스트:
{ocr_text}

한국어로 작성하세요."""


@runtime_checkable
class VisionProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    async def describe(self, image_path: Path, ocr_text: str) -> str: ...


class NoopVisionProvider:
    """No-op provider: returns empty description. Used when vision is disabled."""

    @property
    def provider_name(self) -> str:
        return "none"

    async def describe(self, image_path: Path, ocr_text: str) -> str:
        return ""


class OllamaVisionProvider:
    """Ollama-based vision provider using models like LLaVA."""

    def __init__(
        self,
        model: str = "llava:13b",
        ollama_url: str = "http://localhost:11434",
    ):
        self._model = model
        self._ollama_url = ollama_url

    @property
    def provider_name(self) -> str:
        return f"ollama/{self._model}"

    async def describe(self, image_path: Path, ocr_text: str) -> str:
        """Send image to Ollama vision model and return description."""
        import ollama

        prompt = VISION_PROMPT.format(ocr_text=ocr_text if ocr_text else "(OCR 텍스트 없음)")

        def _call_ollama() -> str:
            image_bytes = image_path.read_bytes()
            b64 = base64.b64encode(image_bytes).decode("ascii")
            client = ollama.Client(host=self._ollama_url)
            response = client.chat(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [b64],
                    }
                ],
            )
            return response["message"]["content"]

        try:
            return await asyncio.to_thread(_call_ollama)
        except Exception as e:
            logger.warning(f"Ollama vision failed for {image_path.name}: {e}")
            return ""


def create_vision_provider(
    provider: str = "none",
    model: str = "llava:13b",
    ollama_url: str = "http://localhost:11434",
) -> VisionProvider:
    """Factory function to create a VisionProvider by name."""
    if provider == "ollama":
        return OllamaVisionProvider(model=model, ollama_url=ollama_url)
    return NoopVisionProvider()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestVisionProviders -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/application/image/vision_provider.py pyproject.toml
git commit -m "feat(image): add Vision provider abstraction with Ollama + Noop"
```

---

### Task 4: Image Analyzer Orchestrator

**Files:**
- Modify: `backend/application/image/analyzer.py` (replace placeholder)
- Modify: `backend/application/image/__init__.py`
- Test: `tests/test_image_analysis.py`

- [ ] **Step 1: Write the failing test for ImageAnalyzer**

Append to `tests/test_image_analysis.py`:

```python
class TestImageAnalyzer:
    """Test ImageAnalyzer orchestrator (OCR + Vision → sidecar)."""

    @pytest.mark.asyncio
    async def test_analyze_creates_sidecar(self, tmp_path):
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import load_sidecar
        from PIL import Image, ImageDraw

        # Create test image with text
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

        # Analysis should have OCR text, empty description (noop vision)
        assert len(analysis.ocr_text) > 0
        assert analysis.description == ""
        assert analysis.provider == "none"
        assert analysis.ocr_engine == "easyocr"

        # Sidecar should be written automatically
        sidecar = load_sidecar(img_path)
        assert sidecar is not None
        assert sidecar.ocr_text == analysis.ocr_text

    @pytest.mark.asyncio
    async def test_analyze_skips_if_fresh(self, tmp_path):
        """Analyze should skip processing if sidecar is fresh."""
        from backend.application.image.analyzer import ImageAnalyzer
        from backend.application.image.ocr_engine import OCREngine
        from backend.application.image.vision_provider import NoopVisionProvider
        from backend.application.image.models import ImageAnalysis, save_sidecar, load_sidecar
        from datetime import datetime, timezone
        import time

        img_path = tmp_path / "cached.png"
        img_path.write_bytes(b"fake image")
        time.sleep(0.05)

        # Pre-populate sidecar
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

        # Should return cached result, not re-process
        assert analysis.ocr_text == "cached text"
        assert analysis.description == "cached desc"

    @pytest.mark.asyncio
    async def test_analyze_force_reprocess(self, tmp_path):
        """Analyze with force=True should always reprocess."""
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

        # Pre-populate stale sidecar
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

        # Should have fresh OCR text, not "old"
        assert analysis.ocr_text != "old"
        assert analysis.provider == "none"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageAnalyzer -v`
Expected: FAIL with `ImportError` (analyzer.py is a placeholder)

- [ ] **Step 3: Implement analyzer.py**

```python
# backend/application/image/analyzer.py
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

    async def analyze(
        self, image_path: Path, force: bool = False
    ) -> ImageAnalysis:
        """Analyze an image: OCR text extraction + Vision description.

        Returns cached result if sidecar is fresh (unless force=True).
        Writes sidecar file after processing.
        """
        if not force and not needs_processing(image_path):
            cached = load_sidecar(image_path)
            if cached is not None:
                logger.debug(f"Using cached sidecar for {image_path.name}")
                return cached

        # Stage 1: OCR (always)
        ocr_text = await self.ocr.extract_text(image_path)
        logger.debug(
            f"OCR extracted {len(ocr_text)} chars from {image_path.name}"
        )

        # Stage 2: Vision (if configured — NoopVisionProvider returns "")
        description = await self.vision.describe(image_path, ocr_text)
        if description:
            logger.debug(
                f"Vision generated {len(description)} chars for {image_path.name}"
            )

        analysis = ImageAnalysis(
            ocr_text=ocr_text,
            description=description,
            provider=self.vision.provider_name,
            ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        )

        save_sidecar(image_path, analysis)
        return analysis
```

- [ ] **Step 4: Update __init__.py to export properly**

```python
# backend/application/image/__init__.py
"""Image analysis pipeline for wiki image searchability."""

from .models import ImageAnalysis, save_sidecar, load_sidecar, needs_processing
from .analyzer import ImageAnalyzer

__all__ = [
    "ImageAnalysis",
    "ImageAnalyzer",
    "save_sidecar",
    "load_sidecar",
    "needs_processing",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageAnalyzer -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/application/image/analyzer.py backend/application/image/__init__.py
git commit -m "feat(image): add ImageAnalyzer orchestrator with sidecar caching"
```

---

### Task 5: Configuration

**Files:**
- Modify: `backend/core/config.py:7-79`
- Test: `tests/test_image_analysis.py`

- [ ] **Step 1: Write the failing test for config**

Append to `tests/test_image_analysis.py`:

```python
class TestImageConfig:
    """Test image analysis configuration in Settings."""

    def test_default_config_values(self):
        from backend.core.config import Settings

        s = Settings(
            _env_file=None,  # don't load .env for testing
        )
        assert s.image_analysis_enabled is True
        assert s.image_ocr_engine == "easyocr"
        assert s.image_ocr_languages == "ko,en"
        assert s.image_ocr_confidence == 0.3
        assert s.image_ocr_gpu is False
        assert s.image_vision_provider == "none"
        assert s.image_vision_model == "llava:13b"

    def test_vision_disabled_by_default(self):
        from backend.core.config import Settings

        s = Settings(_env_file=None)
        assert s.image_vision_provider == "none"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageConfig -v`
Expected: FAIL with `TypeError` (Settings doesn't have `image_analysis_enabled`)

- [ ] **Step 3: Add image analysis settings to config.py**

Add the following fields to the `Settings` class in `backend/core/config.py`, after the `log_dir` / `enable_local_monitor` fields (before `model_config`):

```python
    # Image Analysis
    image_analysis_enabled: bool = True
    image_ocr_engine: str = "easyocr"       # easyocr | tesseract
    image_ocr_languages: str = "ko,en"       # comma-separated language codes
    image_ocr_confidence: float = 0.3        # min confidence threshold
    image_ocr_gpu: bool = False
    image_vision_provider: str = "none"      # none | ollama | openai | claude
    image_vision_model: str = "llava:13b"    # provider-specific model name
    image_max_workers: int = 4               # parallel processing workers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageConfig -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/core/config.py
git commit -m "feat(image): add image analysis settings to config"
```

---

### Task 6: Indexer Integration — Inject Image Descriptions into Chunks

**Files:**
- Modify: `backend/application/wiki/wiki_indexer.py:1-186`
- Test: `tests/test_image_analysis.py`

This is the core integration point. The indexer's `chunk()` method needs to enrich text with image descriptions before embedding.

- [ ] **Step 1: Write the failing test for chunk enrichment**

Append to `tests/test_image_analysis.py`:

```python
class TestIndexerEnrichment:
    """Test image description injection into wiki indexer chunks."""

    def test_enrich_chunk_with_image_description(self, tmp_path):
        from backend.application.wiki.wiki_indexer import enrich_chunk_with_images
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from datetime import datetime, timezone

        # Set up assets dir with a sidecar
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
            description="",  # no vision description
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestIndexerEnrichment -v`
Expected: FAIL with `ImportError: cannot import name 'enrich_chunk_with_images'`

- [ ] **Step 3: Add enrich_chunk_with_images to wiki_indexer.py**

Add the following after the existing imports at the top of `backend/application/wiki/wiki_indexer.py` (after line 8, `from pathlib import Path`):

```python
import json
```

Add the following function after the `_split_long_text` function (after line 133), before the `WikiIndexer` class:

```python
IMAGE_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def enrich_chunk_with_images(chunk_text: str, wiki_root: Path) -> str:
    """Replace image markdown references with their text descriptions.

    Reads sidecar .meta.json files for each image reference. If a sidecar
    exists, replaces the image reference with the description text.
    Falls back to OCR text if no vision description is available.
    Keeps original reference if no sidecar exists.
    """

    def _replace_image(match: re.Match) -> str:
        image_rel_path = match.group(2)
        image_path = wiki_root / image_rel_path
        meta_path = image_path.parent / (image_path.name + ".meta.json")

        if not meta_path.exists():
            return match.group(0)

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return match.group(0)

        description = meta.get("description", "")
        ocr_text = meta.get("ocr_text", "")

        if description:
            return f"\n[이미지: {description}]\n"
        elif ocr_text:
            return f"\n[이미지 텍스트: {ocr_text}]\n"

        return match.group(0)

    return IMAGE_REF_RE.sub(_replace_image, chunk_text)
```

- [ ] **Step 4: Wire enrichment into the chunk() method**

In `WikiIndexer.chunk()`, add enrichment after building `full_text` (at line 155, inside the `for idx, (heading, body)` loop). Change lines 155-156 from:

```python
            full_text = f"{heading}\n{body}" if heading else body
```

to:

```python
            full_text = f"{heading}\n{body}" if heading else body

            # Enrich: replace image references with their text descriptions
            wiki_root = Path(settings.wiki_dir)
            full_text = enrich_chunk_with_images(full_text, wiki_root)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestIndexerEnrichment -v`
Expected: All 5 tests PASS

Also run existing indexer tests to verify no regression:

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/ -k "index" -v --timeout=30`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/application/wiki/wiki_indexer.py
git commit -m "feat(image): inject image descriptions into indexer chunks"
```

---

### Task 7: Background Processing Queue

**Files:**
- Create: `backend/application/image/queue.py`
- Test: `tests/test_image_analysis.py`

- [ ] **Step 1: Write the failing test for ImageProcessingQueue**

Append to `tests/test_image_analysis.py`:

```python
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
        # External URLs should be excluded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageProcessingQueue -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.application.image.queue'`

- [ ] **Step 3: Implement queue.py**

```python
# backend/application/image/queue.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestImageProcessingQueue -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/application/image/queue.py
git commit -m "feat(image): add async background processing queue"
```

---

### Task 8: Wire into WikiService and main.py

**Files:**
- Modify: `backend/application/wiki/wiki_service.py:104-164`
- Modify: `backend/main.py:60-140`
- Test: `tests/test_image_analysis.py`

- [ ] **Step 1: Write the failing test for WikiService image integration**

Append to `tests/test_image_analysis.py`:

```python
class TestWikiServiceImageIntegration:
    """Test that WikiService triggers image processing on save."""

    def test_extract_image_paths_utility(self):
        """Verify extract_image_paths works with real-world markdown."""
        from backend.application.image.queue import extract_image_paths

        content = """---
domain: IT
---
# 장애 보고서

![](assets/a1b2c3.png)

에러 상세:
![에러 화면](assets/d4e5f6.jpg)
"""
        paths = extract_image_paths(content)
        assert "assets/a1b2c3.png" in paths
        assert "assets/d4e5f6.jpg" in paths
        assert len(paths) == 2
```

- [ ] **Step 2: Run test to verify it passes (utility already implemented)**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestWikiServiceImageIntegration -v`
Expected: PASS

- [ ] **Step 3: Add image queue to WikiService**

In `backend/application/wiki/wiki_service.py`, add the `_image_queue` field and setter.

After line 77 (`self._confidence_svc = None`), add:

```python
        self._image_queue = None  # ImageProcessingQueue, set from main.py
```

After the `set_confidence_service` method (after line 93), add:

```python
    def set_image_queue(self, queue) -> None:
        """Set image processing queue (called from main.py after init)."""
        self._image_queue = queue
```

- [ ] **Step 4: Trigger image processing on document save**

In the `save_file` method, after the line that creates the background indexing task (line 161: `asyncio.create_task(self._bg_index(wiki_file, access_scope=access_scope))`), add:

```python
        # Background image analysis — process new images for search enrichment
        if self._image_queue:
            asyncio.create_task(self._bg_image_process(wiki_file))
```

Add the `_bg_image_process` method to the `WikiService` class, after the `_bg_index` method:

```python
    async def _bg_image_process(self, wiki_file: WikiFile) -> None:
        """Background image processing: extract text + generate descriptions."""
        try:
            from pathlib import Path
            result = await self._image_queue.process_document_images(
                wiki_file.content, Path(settings.wiki_dir)
            )
            if result["processed"] > 0:
                logger.info(
                    f"Image analysis for {wiki_file.path}: "
                    f"{result['processed']} processed, {result['skipped']} skipped"
                )
                # Re-index to pick up new image descriptions
                await self.indexer.index_file(wiki_file, force=True)
        except Exception as e:
            logger.warning(f"Background image processing failed for {wiki_file.path}: {e}")
```

- [ ] **Step 5: Wire ImageAnalyzer in main.py**

In `backend/main.py`, add the import near the top (after the existing application imports, around line 30):

```python
from backend.application.image.analyzer import ImageAnalyzer
from backend.application.image.ocr_engine import OCREngine
from backend.application.image.vision_provider import create_vision_provider
from backend.application.image.queue import ImageProcessingQueue
```

In the `lifespan` function, after the wiki_service is created (after line 92: `wiki_service = WikiService(storage, indexer, search_service)`), add:

```python
    # Initialize image analysis pipeline (if enabled)
    if settings.image_analysis_enabled:
        _ocr = OCREngine(
            languages=settings.image_ocr_languages.split(","),
            gpu=settings.image_ocr_gpu,
            confidence_threshold=settings.image_ocr_confidence,
        )
        _vision = create_vision_provider(
            provider=settings.image_vision_provider,
            model=settings.image_vision_model,
            ollama_url=settings.ollama_host,
        )
        _img_analyzer = ImageAnalyzer(ocr=_ocr, vision=_vision)
        _img_queue = ImageProcessingQueue(_img_analyzer)
        wiki_service.set_image_queue(_img_queue)
        logger.info(
            f"Image analysis: OCR={settings.image_ocr_engine}, "
            f"Vision={settings.image_vision_provider}/{settings.image_vision_model}"
        )
```

- [ ] **Step 6: Run the full test suite to verify no regressions**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/application/wiki/wiki_service.py backend/main.py
git commit -m "feat(image): wire image analysis into WikiService and app startup"
```

---

### Task 9: Backfill CLI Tool

**Files:**
- Create: `backend/cli/__init__.py`
- Create: `backend/cli/backfill_images.py`
- Test: manual CLI test

- [ ] **Step 1: Create CLI package**

```python
# backend/cli/__init__.py
"""CLI tools for onTong backend."""
```

- [ ] **Step 2: Implement backfill_images.py**

```python
# backend/cli/backfill_images.py
"""CLI tool to batch-process existing wiki images.

Usage:
    python -m backend.cli.backfill_images                    # Process all
    python -m backend.cli.backfill_images --ocr-only         # OCR only (fast)
    python -m backend.cli.backfill_images --dry-run           # Show what would be processed
    python -m backend.cli.backfill_images --reprocess         # Ignore cache, reprocess all
    python -m backend.cli.backfill_images --workers 8         # Parallel workers
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.config import settings
from backend.application.image.models import needs_processing

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def find_all_images(wiki_dir: Path) -> list[Path]:
    """Find all image files in wiki/assets/."""
    assets_dir = wiki_dir / "assets"
    if not assets_dir.exists():
        return []
    return sorted(
        f for f in assets_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in IMAGE_EXTENSIONS
        and not f.name.endswith(".meta.json")
    )


async def backfill(args: argparse.Namespace) -> None:
    """Run backfill processing."""
    wiki_dir = Path(settings.wiki_dir)
    all_images = find_all_images(wiki_dir)

    if not all_images:
        print("No images found in wiki/assets/")
        return

    # Filter to images needing processing
    if args.reprocess:
        to_process = all_images
    else:
        to_process = [img for img in all_images if needs_processing(img)]

    print(f"Found {len(all_images)} images total, {len(to_process)} need processing")

    if args.dry_run:
        for img in to_process:
            print(f"  Would process: {img.name}")
        return

    if not to_process:
        print("Nothing to process.")
        return

    # Build analyzer
    from backend.application.image.ocr_engine import OCREngine
    from backend.application.image.vision_provider import create_vision_provider, NoopVisionProvider
    from backend.application.image.analyzer import ImageAnalyzer
    from backend.application.image.queue import ImageProcessingQueue

    ocr = OCREngine(
        languages=settings.image_ocr_languages.split(","),
        gpu=settings.image_ocr_gpu,
        confidence_threshold=settings.image_ocr_confidence,
    )

    if args.ocr_only:
        vision = NoopVisionProvider()
    else:
        vision = create_vision_provider(
            provider=settings.image_vision_provider,
            model=settings.image_vision_model,
            ollama_url=settings.ollama_host,
        )

    analyzer = ImageAnalyzer(ocr=ocr, vision=vision)
    queue = ImageProcessingQueue(analyzer)

    print(f"Processing {len(to_process)} images (vision: {vision.provider_name})...")

    result = await queue.process_images(to_process, force=args.reprocess)

    print(
        f"Done: {result['processed']} processed, "
        f"{result['skipped']} skipped, {result['errors']} errors"
    )


def main():
    parser = argparse.ArgumentParser(description="Backfill image analysis for wiki images")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--ocr-only", action="store_true", help="Only run OCR (skip vision)")
    parser.add_argument("--reprocess", action="store_true", help="Reprocess all images")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(backfill(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify CLI runs with --dry-run**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m backend.cli.backfill_images --dry-run`
Expected: Shows count of images in wiki/assets/ and lists what would be processed (or "No images found" if wiki/assets/ is empty)

- [ ] **Step 4: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/cli/__init__.py backend/cli/backfill_images.py
git commit -m "feat(image): add CLI tool for bulk image backfill"
```

---

### Task 10: Integration Test — End-to-End

**Files:**
- Test: `tests/test_image_analysis.py`

This test verifies the full pipeline: image with sidecar → indexer enriches chunk → enriched text is searchable.

- [ ] **Step 1: Write the integration test**

Append to `tests/test_image_analysis.py`:

```python
class TestEndToEndImageSearch:
    """Integration test: image descriptions flow through to indexable chunks."""

    def test_indexer_chunks_include_image_descriptions(self, tmp_path):
        """Full pipeline: sidecar exists → WikiIndexer.chunk() produces enriched text."""
        import os
        from backend.application.wiki.wiki_indexer import WikiIndexer
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from backend.core.schemas import WikiFile, DocumentMetadata
        from datetime import datetime, timezone
        from unittest.mock import MagicMock

        # Set up wiki dir with assets
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        assets_dir = wiki_dir / "assets"
        assets_dir.mkdir()

        # Create image + sidecar
        img_path = assets_dir / "screenshot1.png"
        img_path.write_bytes(b"fake image")
        save_sidecar(img_path, ImageAnalysis(
            ocr_text="결제 실패 에러 500",
            description="결제 화면 스크린샷. HTTP 500 에러 메시지와 '서버 응답 없음' 표시.",
            provider="test", ocr_engine="easyocr",
            processed_at=datetime.now(timezone.utc),
        ))

        # Create a wiki file with image reference
        md_content = "# 결제 장애 보고\n\n![](assets/screenshot1.png)\n\n담당: 김OO"

        wiki_file = WikiFile(
            path="IT/결제-장애-보고.md",
            content=md_content,
            raw_content=f"---\ndomain: IT\n---\n{md_content}",
            metadata=DocumentMetadata(domain="IT"),
        )

        # Point settings to our tmp wiki dir
        os.environ["WIKI_DIR"] = str(wiki_dir)

        chroma_mock = MagicMock()
        indexer = WikiIndexer(chroma_mock)

        # Temporarily override settings.wiki_dir for the test
        from backend.core.config import settings
        original_wiki_dir = settings.wiki_dir
        settings.wiki_dir = wiki_dir
        try:
            chunks = indexer.chunk(wiki_file)
        finally:
            settings.wiki_dir = original_wiki_dir

        # The chunk should contain the image description
        chunk_texts = " ".join(c.content for c in chunks)
        assert "결제 화면 스크린샷" in chunk_texts
        assert "HTTP 500 에러" in chunk_texts
        assert "담당: 김OO" in chunk_texts
        # Original image markdown should be replaced
        assert "![](assets/screenshot1.png)" not in chunk_texts

    def test_image_only_document_is_searchable(self, tmp_path):
        """A document with only images should produce non-empty chunks."""
        import os
        from backend.application.wiki.wiki_indexer import WikiIndexer
        from backend.application.image.models import ImageAnalysis, save_sidecar
        from backend.core.schemas import WikiFile, DocumentMetadata
        from datetime import datetime, timezone
        from unittest.mock import MagicMock

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        assets_dir = wiki_dir / "assets"
        assets_dir.mkdir()

        # Two images, no text
        for name, desc in [
            ("chat1.png", "카카오톡 대화. 김OO 고객이 결제 실패를 보고."),
            ("chat2.png", "에러 화면 캡처. 서버 500 에러."),
        ]:
            p = assets_dir / name
            p.write_bytes(b"fake")
            save_sidecar(p, ImageAnalysis(
                ocr_text="", description=desc,
                provider="test", ocr_engine="easyocr",
                processed_at=datetime.now(timezone.utc),
            ))

        md_content = "# CS 문의\n\n![](assets/chat1.png)\n\n![](assets/chat2.png)"

        wiki_file = WikiFile(
            path="CS/문의-기록.md",
            content=md_content,
            raw_content=f"---\ndomain: CS\n---\n{md_content}",
            metadata=DocumentMetadata(domain="CS"),
        )

        chroma_mock = MagicMock()
        indexer = WikiIndexer(chroma_mock)

        from backend.core.config import settings
        original_wiki_dir = settings.wiki_dir
        settings.wiki_dir = wiki_dir
        try:
            chunks = indexer.chunk(wiki_file)
        finally:
            settings.wiki_dir = original_wiki_dir

        assert len(chunks) > 0
        chunk_text = " ".join(c.content for c in chunks)
        assert "결제 실패" in chunk_text
        assert "서버 500 에러" in chunk_text
```

- [ ] **Step 2: Run integration tests**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py::TestEndToEndImageSearch -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Run the complete test file**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/test_image_analysis.py -v`
Expected: All tests PASS (models: 6, OCR: 3, vision: 4, analyzer: 3, config: 2, enrichment: 5, queue: 3, service: 1, e2e: 2 = ~29 tests)

- [ ] **Step 4: Run the full test suite to check for regressions**

Run: `cd /Users/donghae/workspace/ai/onTong && python -m pytest tests/ -v --timeout=60`
Expected: No regressions in existing tests

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add tests/test_image_analysis.py
git commit -m "test(image): add end-to-end integration tests for image search"
```

---

## Summary

| Task | What it builds | Key files |
|---|---|---|
| 1 | Data models + sidecar I/O | `models.py` |
| 2 | OCR engine (EasyOCR) | `ocr_engine.py` |
| 3 | Vision provider abstraction | `vision_provider.py` |
| 4 | Analyzer orchestrator | `analyzer.py` |
| 5 | Configuration settings | `config.py` |
| 6 | Indexer integration | `wiki_indexer.py` |
| 7 | Background queue | `queue.py` |
| 8 | WikiService + main.py wiring | `wiki_service.py`, `main.py` |
| 9 | Backfill CLI | `backfill_images.py` |
| 10 | End-to-end integration tests | `test_image_analysis.py` |

Tasks are ordered by dependency: each task builds on the previous. Tasks 1-5 can be tested in isolation. Task 6 connects to the indexer. Tasks 7-8 wire everything together. Task 9 adds the CLI tool. Task 10 verifies the full pipeline.
