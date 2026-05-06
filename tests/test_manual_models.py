"""OD-11-D1.5 TDD — Phase D manual/gap DTOs.

`backend/modeling/manuals/manual_models.py` 의 Pydantic DTO 검증:

- `ManualDocument` / `ManualSection` / `ManualFragment` (노드 3종)
- `DescribedInBinding` (DESCRIBED_IN 엣지)
- `ConflictBinding` (CONFLICTS_WITH 엣지)
- `MissingBinding` (MISSING_IN 엣지)

Spec: `toClaude/modeling/round3-manual-gap.html` rev.2 §2, §3.
결정 근거: Q4=C+A (gap_mode 선택지), Q8=B (authoritative 기본 False).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.modeling.manuals.manual_models import (
    ConflictBinding,
    DescribedInBinding,
    DescribedInTargetKind,
    GapDetectedBy,
    GapDirection,
    GapMode,
    GapSeverity,
    ManualDocument,
    ManualFormat,
    ManualFragment,
    ManualFragmentKind,
    ManualSection,
    MissingBinding,
)

_NOW = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
def test_manual_format_values() -> None:
    assert ManualFormat.MARKDOWN.value == "markdown"
    assert ManualFormat.PDF.value == "pdf"
    assert ManualFormat.DOCX.value == "docx"
    assert ManualFormat.PPTX.value == "pptx"
    assert ManualFormat.IMAGE.value == "image"


def test_manual_fragment_kind_values() -> None:
    assert ManualFragmentKind.TEXT.value == "text"
    assert ManualFragmentKind.IMAGE.value == "image"
    assert ManualFragmentKind.TABLE.value == "table"
    assert ManualFragmentKind.FORMULA.value == "formula"
    assert ManualFragmentKind.OCR_TEXT.value == "ocr_text"


def test_gap_enum_values() -> None:
    assert GapSeverity.HARD.value == "hard"
    assert GapSeverity.SOFT.value == "soft"
    # D3-2-a : CONFLICTS_WITH severity 4 단계 확장 (LLM 제안, Q5=A).
    assert GapSeverity.LOW.value == "low"
    assert GapSeverity.MEDIUM.value == "medium"
    assert GapSeverity.HIGH.value == "high"
    assert GapSeverity.CRITICAL.value == "critical"

    assert GapDetectedBy.HIERARCHICAL.value == "hierarchical"
    assert GapDetectedBy.LLM_ONLY.value == "llm_only"
    assert GapDetectedBy.MANUAL.value == "manual"

    assert GapMode.HIERARCHICAL.value == "hierarchical"
    assert GapMode.LLM_ONLY.value == "llm_only"

    assert GapDirection.CODE_ONLY.value == "code_only"
    assert GapDirection.MANUAL_ONLY.value == "manual_only"


def test_described_in_target_kind_values() -> None:
    assert DescribedInTargetKind.MANUAL_SECTION.value == "manual_section"
    assert DescribedInTargetKind.MANUAL_FRAGMENT.value == "manual_fragment"


# ---------------------------------------------------------------------------
# ManualDocument
# ---------------------------------------------------------------------------
def _doc(qn: str = "manual.inventory.safety_stock_policy", **over: object) -> ManualDocument:
    base: dict[str, object] = {
        "qualified_name": qn,
        "title": "안전재고 관리 기준서",
        "source_path": "/manuals/inventory/safety_stock_policy.md",
        "format": ManualFormat.MARKDOWN,
        "checksum": "a" * 64,
        "created_at": _NOW,
    }
    base.update(over)
    return ManualDocument(**base)  # type: ignore[arg-type]


def test_manual_document_defaults_non_authoritative() -> None:
    """Q8=B: 기본값 authoritative=False. 사람이 명시적으로 승격."""
    d = _doc()
    assert d.authoritative is False
    assert d.version == ""


def test_manual_document_accepts_all_formats() -> None:
    for fmt in (
        ManualFormat.MARKDOWN,
        ManualFormat.PDF,
        ManualFormat.DOCX,
        ManualFormat.PPTX,
        ManualFormat.IMAGE,
    ):
        d = _doc(format=fmt)
        assert d.format is fmt


def test_manual_document_format_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _doc(format="xml")  # type: ignore[arg-type]


def test_manual_document_checksum_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _doc(checksum="")


def test_manual_document_qualified_name_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _doc(qn="")


def test_manual_document_title_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _doc(title="")


def test_manual_document_authoritative_bool_promotion() -> None:
    d = _doc(authoritative=True, version="2026.Q2")
    assert d.authoritative is True
    assert d.version == "2026.Q2"


def test_manual_document_json_round_trip() -> None:
    d = _doc(authoritative=True, version="1.0.3")
    s = d.model_dump_json()
    u = ManualDocument.model_validate_json(s)
    assert u == d


# ---------------------------------------------------------------------------
# ManualSection
# ---------------------------------------------------------------------------
def _section(
    qn: str = "manual.inventory.safety_stock_policy#3.2",
    **over: object,
) -> ManualSection:
    base: dict[str, object] = {
        "qualified_name": qn,
        "doc_fqn": "manual.inventory.safety_stock_policy",
        "title": "3.2 안전재고 산정 기준",
        "created_at": _NOW,
    }
    base.update(over)
    return ManualSection(**base)  # type: ignore[arg-type]


def test_manual_section_defaults() -> None:
    s = _section()
    assert s.heading_path == []
    assert s.order_index == 0


def test_manual_section_accepts_heading_path() -> None:
    s = _section(heading_path=["3. 재고", "3.2 안전재고 산정"])
    assert s.heading_path == ["3. 재고", "3.2 안전재고 산정"]


def test_manual_section_doc_fqn_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _section(doc_fqn="")


def test_manual_section_title_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _section(title="")


def test_manual_section_json_round_trip() -> None:
    s = _section(heading_path=["a", "b"], order_index=3)
    raw = s.model_dump_json()
    u = ManualSection.model_validate_json(raw)
    assert u == s


# ---------------------------------------------------------------------------
# ManualFragment
# ---------------------------------------------------------------------------
def _fragment(
    qn: str = "manual.inventory.safety_stock_policy#3.2:f0",
    kind: ManualFragmentKind = ManualFragmentKind.TEXT,
    **over: object,
) -> ManualFragment:
    base: dict[str, object] = {
        "qualified_name": qn,
        "section_fqn": "manual.inventory.safety_stock_policy#3.2",
        "kind": kind,
        "text": "안전재고 = 평균수요 × 조달리드타임 × 안전계수",
        "created_at": _NOW,
    }
    base.update(over)
    return ManualFragment(**base)  # type: ignore[arg-type]


def test_manual_fragment_text_kind_basic() -> None:
    f = _fragment()
    assert f.kind is ManualFragmentKind.TEXT
    assert f.image_ref is None
    assert f.embedding is None
    assert f.order_index == 0


def test_manual_fragment_image_kind_accepts_image_ref() -> None:
    f = _fragment(
        kind=ManualFragmentKind.IMAGE,
        text="",
        image_ref="/manuals/inventory/figs/flow.png",
    )
    assert f.kind is ManualFragmentKind.IMAGE
    assert f.image_ref == "/manuals/inventory/figs/flow.png"


def test_manual_fragment_ocr_text_kind() -> None:
    """IMAGE 파싱 후 추출된 OCR 텍스트는 kind=ocr_text 로 저장."""
    f = _fragment(
        kind=ManualFragmentKind.OCR_TEXT,
        text="재고 흐름도 — 발주 → 입고 → 검사",
        image_ref="/manuals/inventory/figs/flow.png",
    )
    assert f.kind is ManualFragmentKind.OCR_TEXT


def test_manual_fragment_table_kind() -> None:
    f = _fragment(kind=ManualFragmentKind.TABLE, text="표: 안전계수 표")
    assert f.kind is ManualFragmentKind.TABLE


def test_manual_fragment_formula_kind() -> None:
    f = _fragment(kind=ManualFragmentKind.FORMULA, text="SS = μ·L·k")
    assert f.kind is ManualFragmentKind.FORMULA


def test_manual_fragment_embedding_optional() -> None:
    f = _fragment(embedding=[0.1, 0.2, 0.3])
    assert f.embedding == [0.1, 0.2, 0.3]


def test_manual_fragment_kind_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _fragment(kind="audio")  # type: ignore[arg-type]


def test_manual_fragment_section_fqn_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _fragment(section_fqn="")


def test_manual_fragment_json_round_trip() -> None:
    f = _fragment(embedding=[0.5, 0.5], order_index=2)
    raw = f.model_dump_json()
    u = ManualFragment.model_validate_json(raw)
    assert u == f


# ---------------------------------------------------------------------------
# DescribedInBinding
# ---------------------------------------------------------------------------
def _described_in(
    source_fqn: str = "com.acme.inventory.SafetyStockCalculator.compute",
    target_fqn: str = "manual.inventory.safety_stock_policy#3.2",
    target_kind: DescribedInTargetKind = DescribedInTargetKind.MANUAL_SECTION,
    **over: object,
) -> DescribedInBinding:
    base: dict[str, object] = {
        "source_fqn": source_fqn,
        "target_fqn": target_fqn,
        "target_kind": target_kind,
        "confidence": 0.92,
        "source": "embedding",
        "created_at": _NOW,
    }
    base.update(over)
    return DescribedInBinding(**base)  # type: ignore[arg-type]


def test_described_in_binding_section_target() -> None:
    b = _described_in()
    assert b.target_kind is DescribedInTargetKind.MANUAL_SECTION


def test_described_in_binding_fragment_target() -> None:
    b = _described_in(
        target_fqn="manual.inventory.safety_stock_policy#3.2:f0",
        target_kind=DescribedInTargetKind.MANUAL_FRAGMENT,
    )
    assert b.target_kind is DescribedInTargetKind.MANUAL_FRAGMENT


def test_described_in_binding_confidence_bounded() -> None:
    with pytest.raises(ValidationError):
        _described_in(confidence=-0.1)
    with pytest.raises(ValidationError):
        _described_in(confidence=1.5)


def test_described_in_binding_target_kind_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _described_in(target_kind="manual_chunk")  # type: ignore[arg-type]


def test_described_in_binding_fqns_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _described_in(source_fqn="")
    with pytest.raises(ValidationError):
        _described_in(target_fqn="")


# ---------------------------------------------------------------------------
# ConflictBinding
# ---------------------------------------------------------------------------
def _conflict(**over: object) -> ConflictBinding:
    base: dict[str, object] = {
        "code_fqn": "com.acme.inventory.SafetyStockCalculator.compute",
        "manual_section_fqn": "manual.inventory.safety_stock_policy#3.2",
        "severity": GapSeverity.HARD,
        "detected_by": GapDetectedBy.HIERARCHICAL,
        "gap_mode": GapMode.HIERARCHICAL,
        "description": "코드는 안전계수 1.65 고정, 기준서는 1.96 요구",
        "confidence": 0.78,
        "created_at": _NOW,
    }
    base.update(over)
    return ConflictBinding(**base)  # type: ignore[arg-type]


def test_conflict_binding_basic() -> None:
    c = _conflict()
    assert c.severity is GapSeverity.HARD
    assert c.detected_by is GapDetectedBy.HIERARCHICAL
    assert c.gap_mode is GapMode.HIERARCHICAL


def test_conflict_binding_llm_only_mode() -> None:
    """Q4=A: gap_mode=llm_only 경로."""
    c = _conflict(
        detected_by=GapDetectedBy.LLM_ONLY,
        gap_mode=GapMode.LLM_ONLY,
        severity=GapSeverity.SOFT,
    )
    assert c.gap_mode is GapMode.LLM_ONLY


def test_conflict_binding_severity_enum_validates() -> None:
    # "critical" 은 D3-2-a 에서 정식 값으로 등록됐으므로, 진짜 invalid 문자열 사용.
    with pytest.raises(ValidationError):
        _conflict(severity="apocalyptic")  # type: ignore[arg-type]


def test_conflict_binding_detected_by_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _conflict(detected_by="gut_feeling")  # type: ignore[arg-type]


def test_conflict_binding_gap_mode_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _conflict(gap_mode="full_llm")  # type: ignore[arg-type]


def test_conflict_binding_confidence_bounded() -> None:
    with pytest.raises(ValidationError):
        _conflict(confidence=1.5)


def test_conflict_binding_description_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _conflict(description="")


def test_conflict_binding_json_round_trip() -> None:
    c = _conflict()
    raw = c.model_dump_json()
    u = ConflictBinding.model_validate_json(raw)
    assert u == c


# ---------------------------------------------------------------------------
# MissingBinding
# ---------------------------------------------------------------------------
def _missing(**over: object) -> MissingBinding:
    base: dict[str, object] = {
        "target_fqn": "com.acme.inventory.SafetyStockCalculator.compute",
        "direction": GapDirection.CODE_ONLY,
        "detected_by": GapDetectedBy.HIERARCHICAL,
        "gap_mode": GapMode.HIERARCHICAL,
        "description": "코드에는 구현됐지만 기준서에 언급 없음",
        "created_at": _NOW,
    }
    base.update(over)
    return MissingBinding(**base)  # type: ignore[arg-type]


def test_missing_binding_code_only_direction() -> None:
    m = _missing()
    assert m.direction is GapDirection.CODE_ONLY


def test_missing_binding_manual_only_direction() -> None:
    m = _missing(
        target_fqn="manual.inventory.safety_stock_policy#5.1",
        direction=GapDirection.MANUAL_ONLY,
        description="기준서에 있지만 구현 안됨",
    )
    assert m.direction is GapDirection.MANUAL_ONLY


def test_missing_binding_direction_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _missing(direction="neither")  # type: ignore[arg-type]


def test_missing_binding_target_fqn_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _missing(target_fqn="")


def test_missing_binding_json_round_trip() -> None:
    m = _missing()
    raw = m.model_dump_json()
    u = MissingBinding.model_validate_json(raw)
    assert u == m
