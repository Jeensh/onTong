"""OD-11-D2-1 : ImageParser 검증.

- OCREngine 을 injected dependency 로 받아 이미지 경로 → 텍스트 추출
- 1 이미지 = 1 Section + 1 OCR_TEXT Fragment (+ confidence)
- OCR 실패 시 빈 Fragment + warning 누적

OCR 은 외부 바이너리에 의존하므로 fake OCREngine stub 을 주입해 결정적 테스트.
Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.modeling.manual_ingest.image_parser import ImageParser
from backend.modeling.manuals.manual_models import ManualFormat, ManualFragmentKind


# ---------------------------------------------------------------------------
# Fake OCREngine — deterministic stub
# ---------------------------------------------------------------------------
@dataclass
class _FakeOCREngine:
    text: str = ""
    confidence: float = 0.9
    fail: bool = False

    async def extract_text(self, path: Path) -> dict:  # noqa: ARG002
        if self.fail:
            raise RuntimeError("tesseract unavailable")
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": "ko",
            "backend": "tesseract",
        }


def _write_fake_image(tmp_path: Path, name: str = "spec.png") -> Path:
    """테스트는 OCREngine 을 stub 으로 대체하므로 실제 이미지 내용은 중요치 않음.
    파일 존재 + 크기 > 0 만 보장."""
    p = tmp_path / name
    # PNG 최소 header (invalid 일 수 있으나 OCREngine 이 fake 라 OK)
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    return p


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_image_parser_format_is_image() -> None:
    assert ImageParser().format == ManualFormat.IMAGE


def test_image_parser_yields_single_section_and_ocr_fragment(tmp_path: Path) -> None:
    img = _write_fake_image(tmp_path)
    ocr = _FakeOCREngine(text="안전재고 수식 SS = z * sigma * sqrt(L)", confidence=0.85)
    result = ImageParser(ocr_engine=ocr).parse(img)
    assert result.document.format == ManualFormat.IMAGE
    assert len(result.sections) == 1
    ocr_frags = [f for f in result.fragments if f.kind == ManualFragmentKind.OCR_TEXT]
    assert len(ocr_frags) == 1
    assert "안전재고" in ocr_frags[0].text


def test_image_parser_fragment_references_section(tmp_path: Path) -> None:
    img = _write_fake_image(tmp_path)
    ocr = _FakeOCREngine(text="abc")
    result = ImageParser(ocr_engine=ocr).parse(img)
    section_fqn = result.sections[0].qualified_name
    assert all(f.section_fqn == section_fqn for f in result.fragments)


def test_image_parser_document_fqn_uses_stem(tmp_path: Path) -> None:
    img = _write_fake_image(tmp_path, name="annotated_diagram.png")
    ocr = _FakeOCREngine(text="x")
    result = ImageParser(ocr_engine=ocr).parse(img)
    assert "annotated" in result.document.qualified_name.lower()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
def test_image_parser_ocr_failure_produces_warning(tmp_path: Path) -> None:
    img = _write_fake_image(tmp_path)
    ocr = _FakeOCREngine(fail=True)
    result = ImageParser(ocr_engine=ocr).parse(img)
    assert len(result.sections) == 1
    # Fragment 는 생성되지 않거나 빈 text
    ocr_frags = [f for f in result.fragments if f.kind == ManualFragmentKind.OCR_TEXT]
    assert all(f.text == "" for f in ocr_frags)
    assert any("ocr" in w.lower() or "failed" in w.lower() for w in result.warnings)


def test_image_parser_empty_text_still_produces_section(tmp_path: Path) -> None:
    """OCR 이 빈 문자열 반환 → Section 은 있지만 Fragment.text 는 비어있음."""
    img = _write_fake_image(tmp_path)
    ocr = _FakeOCREngine(text="", confidence=0.0)
    result = ImageParser(ocr_engine=ocr).parse(img)
    assert len(result.sections) == 1
    # 빈 텍스트여도 Fragment 는 하나 있고 image_ref 로 원본 참조
    ocr_frags = [f for f in result.fragments if f.kind == ManualFragmentKind.OCR_TEXT]
    assert len(ocr_frags) == 1
    assert ocr_frags[0].text == ""


# ---------------------------------------------------------------------------
# Default OCREngine construction — 실제 OCREngine 인스턴스가 만들어지는지만 확인
# (tesseract 바이너리 없어도 __init__ 은 성공해야 함)
# ---------------------------------------------------------------------------
def test_image_parser_default_constructs_ocr_engine() -> None:
    parser = ImageParser()
    assert parser.ocr_engine is not None
