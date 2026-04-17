# Image Search Design — Wiki Image Searchability

**Date:** 2026-04-16
**Author:** donghae + Claude
**Status:** Approved
**Scope:** Section 1 Wiki — Image Search Enhancement

---

## Goal

Make images in wiki documents searchable. Currently, images (screenshots, conversation captures, error screens) are stored as binary files and invisible to the search pipeline. Support inquiries and operational records heavily use images, but they contribute nothing to search or agent answers.

The system should extract text and generate contextual descriptions from images, index them alongside document text, and enable both keyword search and contextual search through the existing RAG agent.

## Product Context

From real operational use: recording support inquiries in the wiki produces documents where 60-70% of content is screenshots (Kakao/Slack conversations, error screens, system UIs). These documents are effectively unsearchable today.

Target user query examples:
- "지난달 결제 관련 서버 에러 문의 건이 있었는데?" — needs contextual search
- "500 에러 스크린샷" — needs OCR keyword search
- "김OO 매니저가 보낸 문의" — needs contextual search of conversation captures

Image type distribution (estimated):
- ~65% text-heavy screenshots (chat captures, error messages, terminal logs)
- ~35% visual state screenshots (UI bugs, graphs, system diagrams)

## Architecture

Two-stage image analysis pipeline + indexing integration. No changes to the search pipeline itself.

```
Document save
  → Detect new/changed image references
  → Queue for background processing

Background worker
  → Stage 1: Local OCR (always, fast, free)
  → Stage 2: Vision LLM description (if configured, slower)
  → Save results to sidecar .meta.json file

Indexing (wiki_indexer.py)
  → Chunking encounters ![](assets/...)
  → Load sidecar .meta.json if exists
  → Inject image description into chunk text
  → Index as normal text (ChromaDB + BM25)

Search / Agent (no changes)
  → Hybrid search hits image descriptions naturally
  → Agent sees descriptions in retrieved chunks
```

No new databases. No changes to ChromaDB, BM25, or RAG agent search logic.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Storage format | Sidecar `.meta.json` per image | Survives re-indexing, cacheable, inspectable, no DB changes |
| OCR engine | EasyOCR | Korean built-in support, pure Python, no system dependency |
| Vision abstraction | Protocol-based provider | Swap between Ollama/OpenAI/Claude without code changes |
| Default vision | Ollama + LLaVA | Free, local, no data leaves the server, good enough quality |
| Processing timing | Async background on document save | No user-facing latency, progressive quality |
| Indexing strategy | Inject description into existing text chunks | Zero search pipeline changes, works with existing vector + BM25 + RRF |
| Paid API dependency | None required | System works with OCR-only. Vision is an optional enhancement |

## File Structure

### New files

```
backend/
  application/
    image/
      __init__.py
      image_analyzer.py        # ImageAnalyzer protocol + ImageAnalysis dataclass
      ocr_engine.py            # EasyOCR wrapper
      vision_providers/
        __init__.py
        base.py                # VisionProvider protocol
        ollama_vision.py       # Ollama + LLaVA implementation
        openai_vision.py       # OpenAI Vision implementation (optional)
        noop.py                # No-op fallback (OCR only mode)
      image_processing_queue.py  # Async background job queue
  cli/
    backfill_images.py         # CLI command for bulk processing existing images
```

### Modified files

```
backend/
  application/wiki/wiki_indexer.py   # Inject image descriptions into chunks
  application/wiki/wiki_service.py   # Trigger image processing on document save
  core/config.py                     # Image analysis configuration
```

### Storage

```
wiki/assets/
  {uuid}.png
  {uuid}.png.meta.json    # NEW: sidecar metadata file per image
```

## Sidecar File Format

`{image_filename}.meta.json`:

```json
{
  "version": 1,
  "ocr_text": "김OO: 결제가 안 돼요\n박OO: 어떤 에러가 나오시나요?\n김OO: 500 서버 에러라고 뜹니다",
  "description": "카카오톡 대화 캡처. 김OO(고객)과 박OO(CS팀) 간 대화. 고객이 앱 결제 버튼 클릭 시 에러 발생을 보고. CS팀이 에러 화면 확인 요청. 14:32~14:36 사이 3건의 메시지 교환.",
  "provider": "ollama/llava:13b",
  "ocr_engine": "easyocr",
  "processed_at": "2026-04-16T10:30:00Z"
}
```

Fields:
- `version`: Schema version for future changes
- `ocr_text`: Raw text extracted by OCR. Always present.
- `description`: Contextual description from Vision LLM. Empty string if vision not configured.
- `provider`: Which vision provider generated the description. `"none"` if OCR only.
- `ocr_engine`: Which OCR engine was used.
- `processed_at`: ISO 8601 timestamp.

## Image Analysis Pipeline

### Stage 1: OCR (always runs)

```python
class OCREngine:
    """EasyOCR wrapper for text extraction from images."""

    def __init__(self, languages: list[str] = ["ko", "en"]):
        self.reader = easyocr.Reader(languages, gpu=False)

    async def extract_text(self, image_path: Path) -> str:
        results = self.reader.readtext(str(image_path))
        return "\n".join(text for _, text, conf in results if conf > 0.3)
```

- Languages: Korean + English (configurable)
- Confidence threshold: 0.3 (low to catch partial text)
- GPU: optional, works without

### Stage 2: Vision LLM (when configured)

```python
class VisionProvider(Protocol):
    async def describe(self, image_path: Path, ocr_text: str) -> str:
        """Generate contextual description of an image.

        Args:
            image_path: Path to image file
            ocr_text: Pre-extracted OCR text (so vision can focus on context)

        Returns:
            Detailed contextual description in Korean
        """
        ...
```

Vision prompt (critical for quality):

```
이 이미지는 사내 위키 문서에 포함된 것입니다.
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

한국어로 작성하세요.
```

### Orchestrator

```python
class ImageAnalyzer:
    """Coordinates OCR + Vision for full image analysis."""

    def __init__(self, ocr: OCREngine, vision: VisionProvider):
        self.ocr = ocr
        self.vision = vision

    async def analyze(self, image_path: Path) -> ImageAnalysis:
        ocr_text = await self.ocr.extract_text(image_path)
        description = await self.vision.describe(image_path, ocr_text)
        return ImageAnalysis(
            ocr_text=ocr_text,
            description=description,
            provider=self.vision.provider_name,
            ocr_engine="easyocr",
            processed_at=datetime.utcnow(),
        )
```

### Sidecar cache logic

```python
def needs_processing(image_path: Path) -> bool:
    meta_path = image_path.with_suffix(image_path.suffix + ".meta.json")
    if not meta_path.exists():
        return True
    meta = json.loads(meta_path.read_text())
    # Re-process if image is newer than metadata
    return image_path.stat().st_mtime > meta_path.stat().st_mtime
```

## Indexing Integration

In `wiki_indexer.py`, during the chunking phase:

```python
IMAGE_REF_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

def enrich_chunk_with_images(chunk_text: str, wiki_root: Path) -> str:
    """Replace image references with their text descriptions."""
    def replace_image(match: re.Match) -> str:
        alt_text = match.group(1)
        image_rel_path = match.group(2)
        image_path = wiki_root / image_rel_path
        meta_path = image_path.with_suffix(image_path.suffix + ".meta.json")

        if not meta_path.exists():
            return match.group(0)  # keep original if no metadata

        meta = json.loads(meta_path.read_text())
        parts = []
        if meta.get("description"):
            parts.append(meta["description"])
        elif meta.get("ocr_text"):
            parts.append(f"이미지 텍스트: {meta['ocr_text']}")

        if not parts:
            return match.group(0)

        return f"\n[이미지: {' '.join(parts)}]\n"

    return IMAGE_REF_PATTERN.sub(replace_image, chunk_text)
```

This runs after markdown splitting and before vector embedding. The `[이미지: ...]` block becomes part of the chunk text, indexed by both ChromaDB and BM25.

## Processing Triggers

### On document save (new images)

In `wiki_service.py`, after saving a document:

1. Scan markdown for image references
2. Check which images lack `.meta.json` (or have stale metadata)
3. Queue those images for background processing
4. Document is indexed immediately with whatever metadata exists
5. When processing completes, sidecar is written, next re-index picks it up

### Backfill CLI (existing images)

```bash
python -m backend.cli.backfill_images --workers 4 --vision-only
python -m backend.cli.backfill_images --workers 8 --ocr-only
python -m backend.cli.backfill_images --dry-run
```

Options:
- `--workers N`: Parallel processing workers (default: 4)
- `--ocr-only`: Only run OCR stage (fast first pass)
- `--vision-only`: Only run Vision on images that already have OCR
- `--dry-run`: Report what would be processed
- `--reprocess`: Ignore existing sidecar files, reprocess everything

Supports interrupt/resume: images with up-to-date `.meta.json` are skipped.

## Performance

### Per-image processing time

| Stage | Time | Cost |
|---|---|---|
| OCR (EasyOCR, CPU) | ~1-2 sec | Free |
| Vision (Ollama LLaVA, local) | ~5-10 sec | Free |
| Vision (Claude/GPT-4V, API) | ~2-3 sec | ~$0.01-0.03 |

### Scale estimate (100K documents)

Assuming 30% have images, 3 images per doc = ~90K images.

| Strategy | Time (4 workers) | Cost |
|---|---|---|
| OCR only | ~6-12 hours | Free |
| OCR + Ollama Vision | ~30-60 hours | Free |
| OCR + API Vision | ~6-12 hours | ~$900-2,700 |

**Recommended backfill strategy:**
1. Run OCR-only pass first (~6-12 hours). Keyword search works immediately.
2. Run Vision pass incrementally. Context search improves over time.
3. New images processed in real-time as they're uploaded.

### Progressive quality

```
Upload moment:     alt text only (if provided)
After ~2 seconds:  OCR text indexed → keyword search works
After ~10 seconds: Vision description indexed → context search works
```

User never waits. Quality improves automatically in the background.

## Configuration

In `backend/core/config.py` or equivalent settings:

```yaml
image_analysis:
  enabled: true
  ocr:
    engine: "easyocr"           # easyocr | tesseract
    languages: ["ko", "en"]
    confidence_threshold: 0.3
    gpu: false
  vision:
    provider: "ollama"          # ollama | openai | claude | none
    model: "llava:13b"          # provider-specific model name
    ollama_url: "http://localhost:11434"
    # openai_api_key: "..."     # only if provider is openai
    # claude_api_key: "..."     # only if provider is claude
  processing:
    max_workers: 4
    max_image_size_mb: 10
    queue_batch_size: 20
```

`vision.provider: "none"` = OCR-only mode. System fully functional without any LLM.

## Agent Integration

No changes to the RAG agent search logic. Image descriptions are part of text chunks, so the agent naturally retrieves and cites them.

One optional enhancement: when onTalk's answer references a chunk that contains `[이미지: ...]`, the agent can mention that visual evidence exists in the source document.

## Dependencies

### New Python packages

```
easyocr          # OCR engine (includes PyTorch)
ollama           # Ollama client library (if using Ollama vision)
```

### Optional

```
openai           # Already in project (if using OpenAI vision)
anthropic        # Already in project (if using Claude vision)
```

### System requirements

- Ollama installed locally (if using Ollama vision): `brew install ollama`
- LLaVA model pulled: `ollama pull llava:13b`
- No GPU required (CPU works, GPU is faster)

## Testing Strategy

1. **Unit tests**: OCR extraction accuracy on sample screenshots (Korean chat, error screens)
2. **Unit tests**: Vision provider returns well-formed descriptions
3. **Integration test**: Image upload → sidecar generated → chunk enriched → search finds document
4. **E2E test**: Upload a document with only images → search by contextual query → document returned
5. **Agent test**: Ask onTalk about image content → agent cites the document with image descriptions

## Out of Scope

- Real-time image analysis in the browser (all processing is server-side)
- Image similarity search (visual search, reverse image search)
- Automatic image tagging/categorization UI
- Image editing or annotation
- Video processing
