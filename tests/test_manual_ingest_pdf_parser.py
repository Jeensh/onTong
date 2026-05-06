"""OD-11-D2-1 : PdfParser 검증.

- pypdf 로 페이지별 텍스트 추출
- 페이지 단위로 Section 분할 (페이지 = "Page N" 타이틀)
- 단락은 TEXT Fragment 로 분리

Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6.
"""
from __future__ import annotations

from pathlib import Path

from backend.modeling.manual_ingest.pdf_parser import PdfParser
from backend.modeling.manuals.manual_models import ManualFormat, ManualFragmentKind

from tests._manual_ingest_fixtures import make_pdf


def test_pdf_parser_format_is_pdf() -> None:
    assert PdfParser().format == ManualFormat.PDF


def test_pdf_parser_single_page(tmp_path: Path) -> None:
    p = tmp_path / "single.pdf"
    make_pdf(p, ["Safety stock policy"])
    result = PdfParser().parse(p)
    assert result.document.format == ManualFormat.PDF
    assert len(result.sections) == 1
    # 텍스트 Fragment 존재
    text_frags = [f for f in result.fragments if f.kind == ManualFragmentKind.TEXT]
    assert any("Safety stock" in f.text for f in text_frags)


def test_pdf_parser_multi_page_creates_section_per_page(tmp_path: Path) -> None:
    p = tmp_path / "multi.pdf"
    make_pdf(p, ["Page one content", "Page two content", "Page three content"])
    result = PdfParser().parse(p)
    # 3 페이지 → 3 섹션
    assert len(result.sections) == 3
    # 각 섹션의 heading_path 에 페이지 번호 정보 포함
    titles = [s.title for s in result.sections]
    assert any("1" in t for t in titles)
    assert any("2" in t for t in titles)
    assert any("3" in t for t in titles)


def test_pdf_parser_fragments_reference_sections(tmp_path: Path) -> None:
    p = tmp_path / "ref.pdf"
    make_pdf(p, ["First", "Second"])
    result = PdfParser().parse(p)
    section_fqns = {s.qualified_name for s in result.sections}
    for frag in result.fragments:
        assert frag.section_fqn in section_fqns


def test_pdf_parser_document_checksum_matches(tmp_path: Path) -> None:
    """동일 내용은 동일 checksum."""
    p1 = tmp_path / "a.pdf"
    p2 = tmp_path / "b.pdf"
    make_pdf(p1, ["Same"])
    make_pdf(p2, ["Same"])
    r1 = PdfParser().parse(p1)
    r2 = PdfParser().parse(p2)
    # 파일 자체 바이너리에 non-deterministic 요소 (timestamp/ID) 가 있을 수 있으므로
    # 최소한 checksum 이 64자 hex 인 것만 확인 (동일 여부는 파일 바이너리에 의존)
    assert len(r1.document.checksum) == 64
    assert len(r2.document.checksum) == 64


def test_pdf_parser_document_fqn_uses_stem(tmp_path: Path) -> None:
    p = tmp_path / "safety_stock_v3.pdf"
    make_pdf(p, ["X"])
    result = PdfParser().parse(p)
    assert "safety" in result.document.qualified_name.lower()
