"""OD-11-D2-1 : parser_protocol 헬퍼 / DTO 검증.

- slugify / FQN 생성기 동작
- checksum : 같은 내용은 같은 SHA256, 다른 내용은 다른 해시
- ManualParseResult : 필수 필드 동작, frozen 불변

Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.modeling.manual_ingest.parser_protocol import (
    ManualParseResult,
    compute_checksum,
    make_document_fqn,
    make_fragment_fqn,
    make_section_fqn,
)
from backend.modeling.manuals.manual_models import (
    ManualDocument,
    ManualFormat,
    ManualFragment,
    ManualFragmentKind,
    ManualSection,
)


_NOW = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# FQN / slug helpers
# ---------------------------------------------------------------------------
def test_make_document_fqn_from_plain_stem() -> None:
    assert make_document_fqn("/manuals/safety_stock_policy.md") == "manual.safety-stock-policy"


def test_make_document_fqn_handles_korean_and_spaces() -> None:
    """한글 + 공백 + 대문자 → 슬러그화."""
    out = make_document_fqn("/manuals/안전재고 Policy V3.PDF")
    assert out.startswith("manual.")
    # 한글은 영숫자가 아니라 `-` 로 치환됨. 정확한 문자열이 아닌 정규화 형태 확인.
    assert "pdf" not in out   # 확장자는 stem 에 포함 안 됨
    assert " " not in out
    assert "policy" in out


def test_make_section_fqn_with_heading_path() -> None:
    doc = "manual.safety-stock-policy"
    fqn = make_section_fqn(doc, ["Chapter 3", "3.2 Safety Stock"], order_index=0)
    assert fqn == f"{doc}#chapter-3/3-2-safety-stock:0"


def test_make_section_fqn_without_heading_path() -> None:
    fqn = make_section_fqn("manual.x", heading_path=[], order_index=5)
    assert fqn == "manual.x#5"


def test_make_fragment_fqn() -> None:
    sec = "manual.x#chapter-3:0"
    assert make_fragment_fqn(sec, order_index=2) == "manual.x#chapter-3:0:f2"


# ---------------------------------------------------------------------------
# checksum
# ---------------------------------------------------------------------------
def test_compute_checksum_is_deterministic(tmp_path: Path) -> None:
    p1 = tmp_path / "a.txt"
    p1.write_text("hello world", encoding="utf-8")
    p2 = tmp_path / "b.txt"
    p2.write_text("hello world", encoding="utf-8")
    assert compute_checksum(p1) == compute_checksum(p2)


def test_compute_checksum_differs_for_different_content(tmp_path: Path) -> None:
    p1 = tmp_path / "a.txt"
    p1.write_text("hello world", encoding="utf-8")
    p2 = tmp_path / "b.txt"
    p2.write_text("hello worlds", encoding="utf-8")
    assert compute_checksum(p1) != compute_checksum(p2)


def test_compute_checksum_is_sha256_hex(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_bytes(b"")
    h = compute_checksum(p)
    # SHA-256 hex = 64 chars
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
    # 빈 파일의 SHA-256
    assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ---------------------------------------------------------------------------
# ManualParseResult DTO
# ---------------------------------------------------------------------------
def _make_doc() -> ManualDocument:
    return ManualDocument(
        qualified_name="manual.x",
        title="X",
        source_path="/manuals/x.md",
        format=ManualFormat.MARKDOWN,
        version="",
        checksum="0" * 64,
        authoritative=False,
        created_at=_NOW,
    )


def test_manual_parse_result_defaults_to_empty_lists() -> None:
    result = ManualParseResult(document=_make_doc())
    assert result.sections == []
    assert result.fragments == []
    assert result.warnings == []


def test_manual_parse_result_is_frozen() -> None:
    result = ManualParseResult(document=_make_doc())
    with pytest.raises(Exception):   # ValidationError or TypeError depending on Pydantic
        result.sections = [ManualSection(   # type: ignore[misc]
            qualified_name="manual.x#1", doc_fqn="manual.x", title="T", created_at=_NOW,
        )]


def test_manual_parse_result_with_sections_and_fragments() -> None:
    sec = ManualSection(
        qualified_name="manual.x#intro:0",
        doc_fqn="manual.x",
        title="Intro",
        heading_path=["Intro"],
        order_index=0,
        created_at=_NOW,
    )
    frag = ManualFragment(
        qualified_name="manual.x#intro:0:f0",
        section_fqn="manual.x#intro:0",
        kind=ManualFragmentKind.TEXT,
        text="hello",
        order_index=0,
        created_at=_NOW,
    )
    result = ManualParseResult(
        document=_make_doc(),
        sections=[sec],
        fragments=[frag],
        warnings=["no image found"],
    )
    assert result.sections[0].title == "Intro"
    assert result.fragments[0].text == "hello"
    assert result.warnings == ["no image found"]
