"""OD-11-D2-1 : PptxParser 검증.

- python-pptx 로 슬라이드 1장 = 1 Section
- 슬라이드 타이틀 = Section 타이틀
- 슬라이드 본문 텍스트 = TEXT Fragment

Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6.
"""
from __future__ import annotations

from pathlib import Path

from backend.modeling.manual_ingest.pptx_parser import PptxParser
from backend.modeling.manuals.manual_models import ManualFormat, ManualFragmentKind

from tests._manual_ingest_fixtures import make_pptx


def test_pptx_parser_format_is_pptx() -> None:
    assert PptxParser().format == ManualFormat.PPTX


def test_pptx_parser_one_slide(tmp_path: Path) -> None:
    p = tmp_path / "one.pptx"
    make_pptx(p, [("Agenda", "Overview of safety stock policy.")])
    result = PptxParser().parse(p)
    assert result.document.format == ManualFormat.PPTX
    assert len(result.sections) == 1
    assert result.sections[0].title == "Agenda"


def test_pptx_parser_multiple_slides_create_sections(tmp_path: Path) -> None:
    p = tmp_path / "multi.pptx"
    make_pptx(
        p,
        [
            ("Introduction", "overview body"),
            ("Formula", "SS = z * sigma * sqrt(L)"),
            ("Summary", "stay aware of lead time variability"),
        ],
    )
    result = PptxParser().parse(p)
    assert len(result.sections) == 3
    titles = [s.title for s in result.sections]
    assert titles == ["Introduction", "Formula", "Summary"]


def test_pptx_parser_emits_body_fragment(tmp_path: Path) -> None:
    p = tmp_path / "body.pptx"
    make_pptx(p, [("Title", "hello slide body text")])
    result = PptxParser().parse(p)
    texts = [f.text for f in result.fragments if f.kind == ManualFragmentKind.TEXT]
    assert any("hello slide body" in t for t in texts)


def test_pptx_parser_fragments_reference_sections(tmp_path: Path) -> None:
    p = tmp_path / "ref.pptx"
    make_pptx(p, [("A", "a body"), ("B", "b body")])
    result = PptxParser().parse(p)
    section_fqns = {s.qualified_name for s in result.sections}
    for frag in result.fragments:
        assert frag.section_fqn in section_fqns


def test_pptx_parser_section_order_matches_slide_order(tmp_path: Path) -> None:
    p = tmp_path / "order.pptx"
    make_pptx(p, [("First", "1"), ("Second", "2"), ("Third", "3")])
    result = PptxParser().parse(p)
    indices = [s.order_index for s in result.sections]
    assert indices == [0, 1, 2]
