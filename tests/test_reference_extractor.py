"""ReferenceExtractor tests — pure function over raw markdown."""
from __future__ import annotations

import pytest
from backend.application.refindex.extractor import ReferenceExtractor, Reference, RefKind


@pytest.fixture
def extractor():
    return ReferenceExtractor()


def test_empty_content(extractor):
    refs = extractor.extract("a.md", "")
    assert refs == []


def test_no_frontmatter_no_links(extractor):
    refs = extractor.extract("a.md", "# Hello\n\nplain body.")
    assert refs == []


def test_frontmatter_supersedes(extractor):
    raw = "---\nsupersedes: docs/old.md\n---\n# A\nbody"
    refs = extractor.extract("a.md", raw)
    assert len(refs) == 1
    r = refs[0]
    assert r.kind == RefKind.FM_SUPERSEDES
    assert r.target_path == "docs/old.md"
    assert r.location["raw"] == "docs/old.md"
    assert raw[r.location["offset"]:r.location["offset"] + r.location["length"]] == "docs/old.md"


def test_frontmatter_superseded_by(extractor):
    raw = "---\nsuperseded_by: docs/new.md\n---\n# A\n"
    refs = extractor.extract("a.md", raw)
    assert any(r.kind == RefKind.FM_SUPERSEDED_BY and r.target_path == "docs/new.md" for r in refs)


def test_frontmatter_related_multiple(extractor):
    raw = "---\nrelated:\n  - docs/a.md\n  - docs/b.md\n  - docs/c.md\n---\n# Doc\n"
    refs = extractor.extract("doc.md", raw)
    related = [r for r in refs if r.kind == RefKind.FM_RELATED]
    assert sorted(r.target_path for r in related) == ["docs/a.md", "docs/b.md", "docs/c.md"]
    # Each location should accurately point to that path
    for r in related:
        assert raw[r.location["offset"]:r.location["offset"] + r.location["length"]] == r.target_path


def test_body_wikilink(extractor):
    raw = "# Doc\nSee [[other-stem]] and [[another]] but not [[]].\n"
    refs = extractor.extract("doc.md", raw)
    wikilinks = [r for r in refs if r.kind == RefKind.BODY_WIKILINK]
    assert sorted(r.target_path for r in wikilinks) == ["another", "other-stem"]
    for r in wikilinks:
        assert raw[r.location["offset"]:r.location["offset"] + r.location["length"]] == r.target_path


def test_body_wikilink_with_alias_strips_pipe(extractor):
    """[[stem|Display Text]] → target_path is 'stem', not the full string."""
    raw = "# Doc\n[[stem|Display Name]] is fine.\n"
    refs = extractor.extract("doc.md", raw)
    wikilinks = [r for r in refs if r.kind == RefKind.BODY_WIKILINK]
    assert len(wikilinks) == 1
    assert wikilinks[0].target_path == "stem"


def test_body_markdown_link_local(extractor):
    raw = "# Doc\n[click](docs/other.md) and [also](../sibling.md).\n"
    refs = extractor.extract("doc.md", raw)
    md_links = [r for r in refs if r.kind == RefKind.BODY_MD_LINK]
    assert sorted(r.target_path for r in md_links) == ["../sibling.md", "docs/other.md"]


def test_body_markdown_link_external_skipped(extractor):
    raw = "# Doc\n[external](https://example.com) and [mail](mailto:x@y.z) and [anchor](#hello).\n"
    refs = extractor.extract("doc.md", raw)
    md_links = [r for r in refs if r.kind == RefKind.BODY_MD_LINK]
    assert md_links == []


def test_body_image_link_skipped(extractor):
    """Images are Layer 4 (ImageRegistry), not L3."""
    raw = "# Doc\n![alt](assets/pic.png) and [link](docs/x.md).\n"
    refs = extractor.extract("doc.md", raw)
    md_links = [r for r in refs if r.kind == RefKind.BODY_MD_LINK]
    assert len(md_links) == 1
    assert md_links[0].target_path == "docs/x.md"


def test_links_inside_code_block_skipped(extractor):
    """Fenced code blocks should not produce links."""
    raw = '''# Doc
[real](docs/real.md) is real.

```
[fake](docs/fake.md)  # this is in code
[[fakelink]]
```

`[inline](docs/inline.md)` and `[[inlinelink]]` in inline code.
'''
    refs = extractor.extract("doc.md", raw)
    md = [r.target_path for r in refs if r.kind == RefKind.BODY_MD_LINK]
    wl = [r.target_path for r in refs if r.kind == RefKind.BODY_WIKILINK]
    assert md == ["docs/real.md"]
    assert wl == []


def test_offset_is_absolute_in_raw_content(extractor):
    """Ensure body offsets account for frontmatter length."""
    raw = "---\nrelated:\n  - x.md\n---\n[[stem]]\n[link](y.md)\n"
    refs = extractor.extract("doc.md", raw)
    for r in refs:
        actual = raw[r.location["offset"]:r.location["offset"] + r.location["length"]]
        assert actual == r.location["raw"], f"offset mismatch for {r}"


def test_combined_complex_document(extractor):
    """End-to-end: frontmatter + multiple body links."""
    raw = """---
supersedes: docs/old.md
related:
  - docs/r1.md
  - docs/r2.md
---
# Combined

See [[stem-a]] and [link to r1](docs/r1.md).
Also [[stem-b|Alias]] and [outside link](https://example.com).
"""
    refs = extractor.extract("doc.md", raw)
    by_kind = {}
    for r in refs:
        by_kind.setdefault(r.kind, []).append(r.target_path)
    assert by_kind.get(RefKind.FM_SUPERSEDES) == ["docs/old.md"]
    assert sorted(by_kind.get(RefKind.FM_RELATED, [])) == ["docs/r1.md", "docs/r2.md"]
    assert sorted(by_kind.get(RefKind.BODY_WIKILINK, [])) == ["stem-a", "stem-b"]
    assert by_kind.get(RefKind.BODY_MD_LINK) == ["docs/r1.md"]
