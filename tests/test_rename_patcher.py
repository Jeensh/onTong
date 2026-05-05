"""patch_references — surgical replacements via RefIndex offsets."""
from __future__ import annotations
import pytest
from backend.application.refindex.extractor import Reference, RefKind
from backend.application.rename.patcher import patch_references, PatchResult


def make_ref(source, target, kind, offset, length, raw):
    return Reference(
        source_path=source, target_path=target, kind=kind,
        location={"offset": offset, "length": length, "raw": raw},
    )


def test_empty_inputs():
    r = patch_references("hello", [], {})
    assert r.new_content == "hello"
    assert r.applied == 0


def test_single_replace():
    raw = "see [link](old.md) for details"
    refs = [make_ref("a.md", "old.md", RefKind.BODY_MD_LINK, offset=11, length=6, raw="old.md")]
    r = patch_references(raw, refs, {"old.md": "new.md"})
    assert r.applied == 1
    assert "new.md" in r.new_content
    assert "old.md" not in r.new_content


def test_multiple_replaces_descending_order():
    """Two refs in same content, applied right-to-left so offsets stay valid."""
    raw = "[a](aa.md) and then [b](bb.md)"
    refs = [
        make_ref("x.md", "aa.md", RefKind.BODY_MD_LINK, offset=4, length=5, raw="aa.md"),
        make_ref("x.md", "bb.md", RefKind.BODY_MD_LINK, offset=24, length=5, raw="bb.md"),
    ]
    r = patch_references(raw, refs, {"aa.md": "AA.md", "bb.md": "BB.md"})
    assert r.applied == 2
    assert "AA.md" in r.new_content
    assert "BB.md" in r.new_content


def test_skip_when_raw_mismatch():
    """Stale index: offset points to something else."""
    raw = "[link](current.md) here"
    refs = [make_ref("x.md", "stale.md", RefKind.BODY_MD_LINK, offset=7, length=8, raw="stale.md")]
    r = patch_references(raw, refs, {"stale.md": "fresh.md"})
    assert r.applied == 0
    assert r.skipped == 1
    assert raw == r.new_content   # unchanged


def test_skip_when_target_not_in_remap():
    """Ref whose target isn't in remap is silently kept."""
    raw = "[link](kept.md)"
    refs = [make_ref("x.md", "kept.md", RefKind.BODY_MD_LINK, offset=7, length=7, raw="kept.md")]
    r = patch_references(raw, refs, {"other.md": "new.md"})  # no kept.md
    assert r.applied == 0
    assert r.skipped == 0  # not skipped — just irrelevant
    assert "kept.md" in r.new_content


def test_korean_path():
    raw = "이전 문서: [참조](데모/A.md) 그리고"
    refs = [make_ref("x.md", "데모/A.md", RefKind.BODY_MD_LINK,
                     offset=raw.index("데모/A.md"), length=len("데모/A.md"), raw="데모/A.md")]
    r = patch_references(raw, refs, {"데모/A.md": "데모2/A_renamed.md"})
    assert r.applied == 1
    assert "데모2/A_renamed.md" in r.new_content
    assert "데모/A.md" not in r.new_content


def test_wikilink_stem_replace():
    """[[A]] → [[A_renamed]] using stem remap."""
    raw = "see [[A]] there"
    refs = [make_ref("x.md", "A", RefKind.BODY_WIKILINK, offset=6, length=1, raw="A")]
    r = patch_references(raw, refs, {"A": "A_renamed"})
    assert r.applied == 1
    assert "[[A_renamed]]" in r.new_content


def test_overlapping_offsets():
    """Two refs at non-overlapping but adjacent offsets — both apply."""
    raw = "abc.md|def.md"
    refs = [
        make_ref("x.md", "abc.md", RefKind.FM_RELATED, offset=0, length=6, raw="abc.md"),
        make_ref("x.md", "def.md", RefKind.FM_RELATED, offset=7, length=6, raw="def.md"),
    ]
    r = patch_references(raw, refs, {"abc.md": "AAA.md", "def.md": "DDD.md"})
    assert r.applied == 2
    assert r.new_content == "AAA.md|DDD.md"


def test_partial_remap_partial_apply():
    """Some refs in remap, some not — apply selectively."""
    raw = "[a](one.md) [b](two.md) [c](three.md)"
    refs = [
        make_ref("x.md", "one.md", RefKind.BODY_MD_LINK, offset=4, length=6, raw="one.md"),
        make_ref("x.md", "two.md", RefKind.BODY_MD_LINK, offset=16, length=6, raw="two.md"),
        make_ref("x.md", "three.md", RefKind.BODY_MD_LINK, offset=28, length=8, raw="three.md"),
    ]
    r = patch_references(raw, refs, {"one.md": "ONE.md", "three.md": "THREE.md"})
    assert r.applied == 2
    assert "ONE.md" in r.new_content
    assert "two.md" in r.new_content   # untouched
    assert "THREE.md" in r.new_content
