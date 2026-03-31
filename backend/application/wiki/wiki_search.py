"""Wiki search: backlink extraction, tag index, and search index generation."""

from __future__ import annotations

from backend.core.schemas import (
    BacklinkMap,
    SearchIndexEntry,
    TagIndex,
    WikiFile,
)


class WikiSearchService:
    """Builds and maintains search indices for the frontend (MiniSearch)."""

    def build_search_index(self, files: list[WikiFile]) -> list[SearchIndexEntry]:
        """Build full-text search index entries for all wiki files."""
        entries: list[SearchIndexEntry] = []
        for f in files:
            if f.content.startswith("[Binary file:"):
                continue
            entries.append(SearchIndexEntry(
                id=f.path,
                path=f.path,
                title=f.title,
                content=f.content,
                tags=f.tags,
            ))
        return entries

    def build_backlink_map(self, files: list[WikiFile]) -> BacklinkMap:
        """Build forward and backward link maps from [[wiki-link]] syntax."""
        forward: dict[str, list[str]] = {}
        backward: dict[str, list[str]] = {}

        # Map stem -> full path for resolution
        stem_to_path: dict[str, str] = {}
        for f in files:
            stem = f.path.rsplit("/", 1)[-1].replace(".md", "")
            stem_to_path[stem] = f.path

        for f in files:
            resolved_links: list[str] = []
            for link in f.links:
                target_path = stem_to_path.get(link)
                if target_path:
                    resolved_links.append(target_path)
                    backward.setdefault(target_path, [])
                    if f.path not in backward[target_path]:
                        backward[target_path].append(f.path)

            if resolved_links:
                forward[f.path] = resolved_links

        return BacklinkMap(forward=forward, backward=backward)

    def build_tag_index(self, files: list[WikiFile]) -> TagIndex:
        """Build tag -> file paths index."""
        tags: dict[str, list[str]] = {}
        for f in files:
            for tag in f.tags:
                tags.setdefault(tag, [])
                if f.path not in tags[tag]:
                    tags[tag].append(f.path)
        return TagIndex(tags=tags)
