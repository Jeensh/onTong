"""OD-11-D2-1 : DocxParser 검증.

- python-docx 로 heading style 기반 Section 분할
- 본문 paragraph 는 TEXT Fragment
- 제목/헤딩은 Section 타이틀

Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6.
"""
from __future__ import annotations

from pathlib import Path

from backend.modeling.manual_ingest.docx_parser import DocxParser
from backend.modeling.manuals.manual_models import ManualFormat, ManualFragmentKind

from tests._manual_ingest_fixtures import make_docx


def test_docx_parser_format_is_docx() -> None:
    assert DocxParser().format == ManualFormat.DOCX


def test_docx_parser_single_heading(tmp_path: Path) -> None:
    p = tmp_path / "simple.docx"
    make_docx(p, title="Safety Stock", headings=[(2, "Overview", "General policy text.")])
    result = DocxParser().parse(p)
    assert result.document.format == ManualFormat.DOCX
    titles = [s.title for s in result.sections]
    assert "Safety Stock" in titles or any("Safety" in t for t in titles)
    assert "Overview" in titles


def test_docx_parser_heading_hierarchy(tmp_path: Path) -> None:
    p = tmp_path / "hier.docx"
    make_docx(
        p,
        title="Manual",
        headings=[
            (2, "1. Scope", "scope body"),
            (2, "2. Formula", "formula body"),
            (3, "2.1 Variables", "z sigma L"),
            (2, "3. Notes", "notes body"),
        ],
    )
    result = DocxParser().parse(p)
    by_title = {s.title: s for s in result.sections}
    assert "2.1 Variables" in by_title
    # heading_path depth >= 2 (문서 타이틀 + h2 + h3)
    path_21 = by_title["2.1 Variables"].heading_path
    assert len(path_21) >= 2
    assert "2.1 Variables" in path_21


def test_docx_parser_emits_text_fragments(tmp_path: Path) -> None:
    p = tmp_path / "frag.docx"
    make_docx(
        p,
        title="Doc",
        headings=[(2, "Intro", "hello world intro body.")],
    )
    result = DocxParser().parse(p)
    texts = [f.text for f in result.fragments if f.kind == ManualFragmentKind.TEXT]
    assert any("hello world" in t for t in texts)


def test_docx_parser_fragments_reference_sections(tmp_path: Path) -> None:
    p = tmp_path / "ref.docx"
    make_docx(
        p,
        title="Doc",
        headings=[(2, "A", "a body"), (2, "B", "b body")],
    )
    result = DocxParser().parse(p)
    section_fqns = {s.qualified_name for s in result.sections}
    for frag in result.fragments:
        assert frag.section_fqn in section_fqns


def test_docx_parser_document_fqn_uses_stem(tmp_path: Path) -> None:
    p = tmp_path / "quality_manual_2024.docx"
    make_docx(p, title="Q", headings=[(2, "A", "x")])
    result = DocxParser().parse(p)
    assert "quality" in result.document.qualified_name.lower()
