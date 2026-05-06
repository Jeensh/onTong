"""OD-11-D2-1 : MarkdownParser 검증.

- heading (`#` / `##` / `###`) 기준으로 Section 분할
- 헤딩 계층 (`heading_path`) 은 부모까지 포함
- 본문 텍스트는 TEXT Fragment, 코드펜스는 독립 Fragment (kind=TEXT + text raw)
- 표 라인은 TABLE Fragment 로 별도 분리

Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6.
"""
from __future__ import annotations

from pathlib import Path

from backend.modeling.manual_ingest.md_parser import MarkdownParser
from backend.modeling.manuals.manual_models import (
    ManualFormat,
    ManualFragmentKind,
)


_MD_SAMPLE = """\
# 안전재고 정책

본 문서는 안전재고 산출 기준을 정의한다.

## 1. 범위
해당 공정 전반에 적용한다.

## 2. 공식

수식은 아래와 같다.

```
SS = z * sigma * sqrt(L)
```

### 2.1 변수
| 기호 | 설명 |
|------|------|
| z | 서비스 수준 계수 |
| sigma | 수요 표준편차 |
| L | 리드타임 |

## 3. 주의사항
리드타임 단위는 일(day) 로 통일한다.
"""


def _write_md(tmp_path: Path) -> Path:
    p = tmp_path / "safety_stock_policy.md"
    p.write_text(_MD_SAMPLE, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Basic parse
# ---------------------------------------------------------------------------
def test_md_parser_format_is_markdown() -> None:
    p = MarkdownParser()
    assert p.format == ManualFormat.MARKDOWN


def test_md_parser_returns_document_with_checksum(tmp_path: Path) -> None:
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    assert result.document.format == ManualFormat.MARKDOWN
    assert result.document.qualified_name.startswith("manual.")
    assert len(result.document.checksum) == 64
    assert result.document.title == "안전재고 정책"


def test_md_parser_splits_sections_by_headings(tmp_path: Path) -> None:
    """헤딩 4개 (`#` 1 + `##` 3 + `###` 1) → Section 5 이상."""
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    # h1 "안전재고 정책" + h2 범위/공식/주의사항 + h3 변수 = 5 섹션
    titles = [s.title for s in result.sections]
    assert "안전재고 정책" in titles
    assert "1. 범위" in titles
    assert "2. 공식" in titles
    assert "2.1 변수" in titles
    assert "3. 주의사항" in titles


def test_md_parser_preserves_heading_path_hierarchy(tmp_path: Path) -> None:
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    by_title = {s.title: s for s in result.sections}
    # h3 2.1 은 h2 "2. 공식" 아래 → heading_path = ["안전재고 정책", "2. 공식", "2.1 변수"]
    sec = by_title["2.1 변수"]
    assert sec.heading_path == ["안전재고 정책", "2. 공식", "2.1 변수"]
    # h2 "3. 주의사항" 은 h1 아래 → 부모 1 개
    sec3 = by_title["3. 주의사항"]
    assert sec3.heading_path == ["안전재고 정책", "3. 주의사항"]


def test_md_parser_section_fqn_references_document(tmp_path: Path) -> None:
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    for sec in result.sections:
        assert sec.doc_fqn == result.document.qualified_name
        assert sec.qualified_name.startswith(result.document.qualified_name + "#")


# ---------------------------------------------------------------------------
# Fragment extraction
# ---------------------------------------------------------------------------
def test_md_parser_emits_text_fragments(tmp_path: Path) -> None:
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    texts = [f.text for f in result.fragments if f.kind == ManualFragmentKind.TEXT]
    assert any("안전재고 산출 기준" in t for t in texts)
    assert any("리드타임 단위는 일" in t for t in texts)


def test_md_parser_emits_code_fence_as_text_fragment(tmp_path: Path) -> None:
    """코드 펜스는 TEXT Fragment 로 내용 그대로 보존."""
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    code_frags = [
        f for f in result.fragments
        if f.kind == ManualFragmentKind.TEXT and "SS =" in f.text
    ]
    assert len(code_frags) == 1
    assert "z * sigma * sqrt(L)" in code_frags[0].text


def test_md_parser_emits_table_fragment(tmp_path: Path) -> None:
    """파이프 테이블은 TABLE Fragment 로 독립 분리."""
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    tables = [f for f in result.fragments if f.kind == ManualFragmentKind.TABLE]
    assert len(tables) == 1
    assert "기호" in tables[0].text
    assert "리드타임" in tables[0].text


def test_md_parser_fragments_reference_sections(tmp_path: Path) -> None:
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    section_fqns = {s.qualified_name for s in result.sections}
    for frag in result.fragments:
        assert frag.section_fqn in section_fqns


def test_md_parser_fragment_order_index_starts_zero_per_section(tmp_path: Path) -> None:
    path = _write_md(tmp_path)
    result = MarkdownParser().parse(path)
    from collections import defaultdict
    idx_by_sec: dict[str, list[int]] = defaultdict(list)
    for frag in result.fragments:
        idx_by_sec[frag.section_fqn].append(frag.order_index)
    for indices in idx_by_sec.values():
        assert indices[0] == 0
        # 순번 연속
        assert indices == list(range(len(indices)))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
def test_md_parser_no_heading_creates_single_section(tmp_path: Path) -> None:
    """헤딩이 전혀 없는 MD → 문서 stem 을 제목으로 한 단일 Section."""
    p = tmp_path / "plain.md"
    p.write_text("이 문서는 제목이 없다.\n\n본문이다.\n", encoding="utf-8")
    result = MarkdownParser().parse(p)
    assert len(result.sections) == 1
    assert len(result.fragments) >= 1


def test_md_parser_empty_file_produces_document_only(tmp_path: Path) -> None:
    p = tmp_path / "empty.md"
    p.write_text("", encoding="utf-8")
    result = MarkdownParser().parse(p)
    assert result.document is not None
    assert result.sections == []
    assert result.fragments == []


# ---------------------------------------------------------------------------
# Structured Manual directive (2026-04-26) — `<!-- ontong: k=v -->`
# ---------------------------------------------------------------------------
class TestStructuredDirective:
    def test_directive_attaches_to_next_paragraph(self, tmp_path):
        from backend.modeling.manual_ingest.md_parser import MarkdownParser
        p = tmp_path / "doc.md"
        p.write_text(
            "# 강종\n\n"
            "<!-- ontong: rule=rule.gradeLength -->\n"
            "강종은 4자리 영숫자로 표현한다.\n",
            encoding="utf-8",
        )
        result = MarkdownParser().parse(p)
        # heading 다음 paragraph 가 fragment, attributes 에 rule 가짐
        assert len(result.fragments) == 1
        f = result.fragments[0]
        assert "강종은 4자리" in f.text
        assert f.attributes.get("rule") == "rule.gradeLength"

    def test_multiple_kv_in_one_directive(self, tmp_path):
        from backend.modeling.manual_ingest.md_parser import MarkdownParser
        p = tmp_path / "doc.md"
        p.write_text(
            "# H\n\n"
            "<!-- ontong: term=term.강종코드 scope=primary unit=char -->\n"
            "강종은 4자리.\n",
            encoding="utf-8",
        )
        result = MarkdownParser().parse(p)
        assert result.fragments[0].attributes == {
            "term": "term.강종코드", "scope": "primary", "unit": "char",
        }

    def test_directive_only_affects_next_chunk(self, tmp_path):
        from backend.modeling.manual_ingest.md_parser import MarkdownParser
        p = tmp_path / "doc.md"
        p.write_text(
            "# H\n\n"
            "<!-- ontong: rule=rule.A -->\n"
            "첫 단락 — directive 적용.\n\n"
            "두번째 단락 — directive 없음.\n",
            encoding="utf-8",
        )
        result = MarkdownParser().parse(p)
        assert len(result.fragments) == 2
        assert result.fragments[0].attributes == {"rule": "rule.A"}
        assert result.fragments[1].attributes == {}

    def test_no_directive_means_empty_attributes(self, tmp_path):
        from backend.modeling.manual_ingest.md_parser import MarkdownParser
        p = tmp_path / "doc.md"
        p.write_text("# H\n\n그냥 단락.\n", encoding="utf-8")
        result = MarkdownParser().parse(p)
        assert result.fragments[0].attributes == {}
