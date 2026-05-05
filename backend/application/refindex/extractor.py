"""ReferenceExtractor — pure-function extractor for wiki document references.

Parses raw_content (YAML frontmatter + markdown body) and returns a list of
Reference records with kind + exact byte/character offset. Used by Phase 3's
RenameOrchestrator to patch only the precise location without naive str.replace().
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

# Import _parse_frontmatter from local_fs — do not duplicate frontmatter parsing logic.
# Adjust sys.path if needed, but prefer direct import via the package.
from backend.infrastructure.storage.local_fs import _parse_frontmatter


class RefKind:
    FM_SUPERSEDES    = 1   # frontmatter.supersedes (string)
    FM_SUPERSEDED_BY = 2   # frontmatter.superseded_by (string)
    FM_RELATED       = 3   # frontmatter.related[i] (list element, multiple)
    BODY_WIKILINK    = 4   # body [[stem]]
    BODY_MD_LINK     = 5   # body [text](path.md or relative)


@dataclass(frozen=True)
class Reference:
    source_path: str          # the document containing this reference
    target_path: str          # the document being referenced
    kind: int                 # one of RefKind constants
    location: dict            # { "offset": int, "length": int, "raw": str }


# ── Compiled regexes ──────────────────────────────────────────────────────────

# Fenced code blocks: ```...``` or ~~~...~~~ (multi-line, non-greedy)
_FENCE_RE = re.compile(
    r"(?P<fence>```|~~~)[^\n]*\n(?P<inner>.*?)(?P=fence)",
    re.DOTALL,
)

# Inline code spans: `...` (single backtick, no newline)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

# Markdown link: [text](href) — negative lookbehind to skip images ![...]
_MD_LINK_RE = re.compile(r"(?<!\!)\[([^\]]*)\]\(([^)]+)\)")

# Wikilink: [[stem]] or [[stem|Alias]] — captures stem only, ignores alias
_WIKILINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")

# External href prefixes — these should be skipped for BODY_MD_LINK
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


# ── Helper: mask code regions ─────────────────────────────────────────────────

def _mask_code_regions(text: str) -> str:
    """Replace content inside fenced code blocks and inline code spans with spaces.

    Preserves the surrounding markers (```/~~~/`) so all character offsets remain
    identical to the original. The masked string can then be safely searched with
    regex without matching links or wikilinks inside code.
    """
    result = list(text)

    # Mask fenced code block interiors (the 'inner' group content)
    for m in _FENCE_RE.finditer(text):
        inner_start = m.start("inner")
        inner_end = m.end("inner")
        for i in range(inner_start, inner_end):
            result[i] = " "

    # Mask inline code span content
    for m in _INLINE_CODE_RE.finditer(text):
        for i in range(m.start(1), m.end(1)):
            result[i] = " "

    return "".join(result)


# ── ReferenceExtractor ────────────────────────────────────────────────────────

class ReferenceExtractor:
    """Pure-function extractor. Stateless; safe to call from multiple threads."""

    def extract(self, source_path: str, raw_content: str) -> list[Reference]:
        """Parse raw_content and return all references with absolute offsets.

        Args:
            source_path: Logical path of the document (e.g. 'docs/foo.md').
            raw_content: Full file content including YAML frontmatter + body.

        Returns:
            List of Reference records sorted by offset.
        """
        if not raw_content:
            return []

        meta, body = _parse_frontmatter(raw_content)
        frontmatter_length = len(raw_content) - len(body)

        refs: list[Reference] = []

        # ── Frontmatter references ────────────────────────────────────────────
        refs.extend(self._extract_fm_scalar(
            source_path, raw_content, "supersedes", meta.supersedes or "", RefKind.FM_SUPERSEDES
        ))
        refs.extend(self._extract_fm_scalar(
            source_path, raw_content, "superseded_by", meta.superseded_by or "", RefKind.FM_SUPERSEDED_BY
        ))
        refs.extend(self._extract_fm_related(
            source_path, raw_content, meta.related or []
        ))

        # ── Body references ───────────────────────────────────────────────────
        refs.extend(self._extract_body_links(
            source_path, body, frontmatter_length
        ))
        refs.extend(self._extract_wikilinks(
            source_path, body, frontmatter_length
        ))

        # Sort by offset for deterministic output
        refs.sort(key=lambda r: r.location["offset"])
        return refs

    # ── Frontmatter scalar fields ─────────────────────────────────────────────

    def _extract_fm_scalar(
        self,
        source_path: str,
        raw_content: str,
        yaml_key: str,
        value: str,
        kind: int,
    ) -> list[Reference]:
        """Find a single-value frontmatter field (supersedes / superseded_by)."""
        if not value:
            return []

        # Search for the YAML key first, then the value right after it.
        key_pattern = re.compile(
            r"^" + re.escape(yaml_key) + r"\s*:\s*",
            re.MULTILINE,
        )
        key_match = key_pattern.search(raw_content)
        if key_match is None:
            return []

        # Value starts after the key+colon+spaces
        search_start = key_match.end()
        idx = raw_content.find(value, search_start)
        if idx == -1:
            return []

        return [Reference(
            source_path=source_path,
            target_path=value,
            kind=kind,
            location={"offset": idx, "length": len(value), "raw": value},
        )]

    # ── Frontmatter related[] list ────────────────────────────────────────────

    def _extract_fm_related(
        self,
        source_path: str,
        raw_content: str,
        related: list[str],
    ) -> list[Reference]:
        """Find each entry in frontmatter.related[]."""
        if not related:
            return []

        # Find the 'related:' key first — subsequent entries must come after it.
        key_pattern = re.compile(r"^related\s*:", re.MULTILINE)
        key_match = key_pattern.search(raw_content)
        if key_match is None:
            return []

        refs: list[Reference] = []
        search_from = key_match.end()

        for entry in related:
            if not entry:
                continue
            # Each entry appears as "  - <entry>" in YAML; find the value text
            # after the 'related:' key, starting from after the previous match.
            idx = raw_content.find(entry, search_from)
            if idx == -1:
                continue
            refs.append(Reference(
                source_path=source_path,
                target_path=entry,
                kind=RefKind.FM_RELATED,
                location={"offset": idx, "length": len(entry), "raw": entry},
            ))
            # Advance past this match to avoid matching the same position twice
            # for identical paths.
            search_from = idx + len(entry)

        return refs

    # ── Body markdown links ───────────────────────────────────────────────────

    def _extract_body_links(
        self,
        source_path: str,
        body: str,
        fm_length: int,
    ) -> list[Reference]:
        """Extract [text](href) links from body, skipping code and external URLs."""
        if not body:
            return []

        masked = _mask_code_regions(body)
        refs: list[Reference] = []

        for m in _MD_LINK_RE.finditer(masked):
            href = m.group(2)
            # Skip external / fragment-only URLs
            if href.startswith(_EXTERNAL_PREFIXES):
                continue

            href_start_in_body = m.start(2)
            absolute_offset = fm_length + href_start_in_body

            # Verify against original body (not masked) — should be identical
            actual = body[href_start_in_body: href_start_in_body + len(href)]

            refs.append(Reference(
                source_path=source_path,
                target_path=href,
                kind=RefKind.BODY_MD_LINK,
                location={
                    "offset": absolute_offset,
                    "length": len(href),
                    "raw": actual,
                },
            ))

        return refs

    # ── Body wikilinks ────────────────────────────────────────────────────────

    def _extract_wikilinks(
        self,
        source_path: str,
        body: str,
        fm_length: int,
    ) -> list[Reference]:
        """Extract [[stem]] and [[stem|Alias]] wikilinks, skipping code regions."""
        if not body:
            return []

        masked = _mask_code_regions(body)
        refs: list[Reference] = []

        for m in _WIKILINK_RE.finditer(masked):
            stem = m.group(1)
            if not stem.strip():
                continue  # skip [[]] or [[  ]]

            # group(1) starts at m.start(1) — that's the stem within the body
            stem_start_in_body = m.start(1)
            absolute_offset = fm_length + stem_start_in_body

            actual = body[stem_start_in_body: stem_start_in_body + len(stem)]

            refs.append(Reference(
                source_path=source_path,
                target_path=stem,
                kind=RefKind.BODY_WIKILINK,
                location={
                    "offset": absolute_offset,
                    "length": len(stem),
                    "raw": actual,
                },
            ))

        return refs
