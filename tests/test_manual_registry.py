"""OD-11-D2-2 : ManualRegistry 검증.

Protocol 기반 메타 저장소 + `has_checksum` dedup + authoritative 토글.
InMemoryManualRegistry reference impl 검증.

Spec : `toClaude/modeling/round3-manual-gap.html` rev.2 §6-2.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.modeling.manual_ingest.manual_registry import (
    InMemoryManualRegistry,
    ManualRegistry,
    ManualRegistryEntry,
)
from backend.modeling.manuals.manual_models import (
    ManualDocument,
    ManualFormat,
    ManualFragment,
    ManualFragmentKind,
    ManualSection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_doc(
    fqn: str = "manual.spec",
    *,
    title: str = "Spec",
    checksum: str = "a" * 64,
    source_path: str = "/tmp/spec.md",
    authoritative: bool = False,
) -> ManualDocument:
    return ManualDocument(
        qualified_name=fqn,
        title=title,
        source_path=source_path,
        format=ManualFormat.MARKDOWN,
        version="",
        checksum=checksum,
        authoritative=authoritative,
        created_at=datetime.now(timezone.utc),
    )


def _make_section(fqn: str, doc_fqn: str = "manual.spec") -> ManualSection:
    return ManualSection(
        qualified_name=fqn,
        doc_fqn=doc_fqn,
        title=fqn.split("#")[-1],
        heading_path=["Root"],
        order_index=0,
        created_at=datetime.now(timezone.utc),
    )


def _make_fragment(fqn: str, section_fqn: str) -> ManualFragment:
    return ManualFragment(
        qualified_name=fqn,
        section_fqn=section_fqn,
        kind=ManualFragmentKind.TEXT,
        text="body",
        order_index=0,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_inmemory_registry_conforms_to_protocol() -> None:
    reg = InMemoryManualRegistry()
    assert isinstance(reg, ManualRegistry)


# ---------------------------------------------------------------------------
# Happy path : add + get + list + has_checksum
# ---------------------------------------------------------------------------
def test_registry_add_then_get() -> None:
    reg = InMemoryManualRegistry()
    doc = _make_doc(checksum="c" * 64)
    sec = _make_section("manual.spec#root:0")
    frag = _make_fragment("manual.spec#root:0:f0", "manual.spec#root:0")

    reg.add(doc, sections=[sec], fragments=[frag])
    entry = reg.get_by_fqn("manual.spec")
    assert entry is not None
    assert isinstance(entry, ManualRegistryEntry)
    assert entry.document.qualified_name == "manual.spec"
    assert len(entry.sections) == 1
    assert len(entry.fragments) == 1


def test_registry_has_checksum() -> None:
    reg = InMemoryManualRegistry()
    doc = _make_doc(checksum="abc123")
    reg.add(doc, sections=[], fragments=[])
    assert reg.has_checksum("abc123") is True
    assert reg.has_checksum("deadbeef") is False


def test_registry_list_all() -> None:
    reg = InMemoryManualRegistry()
    reg.add(_make_doc(fqn="manual.a", checksum="1" * 64), sections=[], fragments=[])
    reg.add(_make_doc(fqn="manual.b", checksum="2" * 64), sections=[], fragments=[])
    docs = reg.list_all()
    fqns = {d.qualified_name for d in docs}
    assert fqns == {"manual.a", "manual.b"}


def test_registry_get_missing_returns_none() -> None:
    reg = InMemoryManualRegistry()
    assert reg.get_by_fqn("manual.nonexistent") is None


# ---------------------------------------------------------------------------
# Re-add / overwrite
# ---------------------------------------------------------------------------
def test_registry_add_same_fqn_overwrites() -> None:
    reg = InMemoryManualRegistry()
    reg.add(_make_doc(title="v1", checksum="1" * 64), sections=[], fragments=[])
    reg.add(_make_doc(title="v2", checksum="2" * 64), sections=[], fragments=[])
    entry = reg.get_by_fqn("manual.spec")
    assert entry.document.title == "v2"
    assert entry.document.checksum == "2" * 64
    # Old checksum should be gone
    assert reg.has_checksum("1" * 64) is False
    assert reg.has_checksum("2" * 64) is True


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------
def test_registry_remove() -> None:
    reg = InMemoryManualRegistry()
    reg.add(_make_doc(checksum="x" * 64), sections=[], fragments=[])
    reg.remove("manual.spec")
    assert reg.get_by_fqn("manual.spec") is None
    assert reg.has_checksum("x" * 64) is False


def test_registry_remove_missing_is_noop() -> None:
    reg = InMemoryManualRegistry()
    reg.remove("manual.ghost")   # 예외 없이 조용히 무시


# ---------------------------------------------------------------------------
# Authoritative toggle (Q8=B)
# ---------------------------------------------------------------------------
def test_registry_set_authoritative_true() -> None:
    reg = InMemoryManualRegistry()
    reg.add(_make_doc(checksum="a" * 64, authoritative=False), sections=[], fragments=[])
    updated = reg.set_authoritative("manual.spec", True)
    assert updated.authoritative is True
    assert reg.get_by_fqn("manual.spec").document.authoritative is True


def test_registry_set_authoritative_false() -> None:
    reg = InMemoryManualRegistry()
    reg.add(_make_doc(checksum="a" * 64, authoritative=True), sections=[], fragments=[])
    updated = reg.set_authoritative("manual.spec", False)
    assert updated.authoritative is False


def test_registry_set_authoritative_missing_raises() -> None:
    reg = InMemoryManualRegistry()
    with pytest.raises(KeyError):
        reg.set_authoritative("manual.ghost", True)


# ---------------------------------------------------------------------------
# Checksum query edge cases
# ---------------------------------------------------------------------------
def test_registry_empty_has_no_checksums() -> None:
    reg = InMemoryManualRegistry()
    assert reg.has_checksum("anything") is False


def test_registry_list_all_empty() -> None:
    reg = InMemoryManualRegistry()
    assert reg.list_all() == []
