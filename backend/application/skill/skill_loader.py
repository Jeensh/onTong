"""UserSkillLoader — scan _skills/ folders, parse skill frontmatter, load referenced docs."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import yaml

from backend.core.schemas import SkillContext, SkillListResponse, SkillMeta

logger = logging.getLogger(__name__)

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _extract_section(body: str, heading: str) -> str:
    """Extract content under a ## heading until the next ## or end of file."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


class UserSkillLoader:
    """Scan _skills/ folder for skill documents and cache results."""

    def __init__(self, storage: Any) -> None:
        self.storage = storage
        self._cache: dict[str, SkillMeta] = {}
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 30.0  # seconds

    async def list_skills(self, username: str = "", include_disabled: bool = False) -> SkillListResponse:
        """Return skills accessible to the given user."""
        await self._maybe_refresh()

        system: list[SkillMeta] = []
        personal: list[SkillMeta] = []

        for skill in self._cache.values():
            if not include_disabled and not skill.enabled:
                continue
            if skill.scope == "shared":
                system.append(skill)
            elif skill.scope == "personal" and username and f"@{username}/" in skill.path:
                personal.append(skill)

        all_cats = sorted({s.category for s in self._cache.values() if s.category})
        return SkillListResponse(system=system, personal=personal, categories=all_cats)

    async def get_skill(self, path: str) -> SkillMeta | None:
        """Get a single skill by path."""
        await self._maybe_refresh()
        return self._cache.get(path)

    async def load_skill_context(self, skill: SkillMeta) -> SkillContext:
        """Build structured 6-layer context from a skill document."""
        wiki_file = await self.storage.read(skill.path)
        if not wiki_file:
            return SkillContext()

        body = wiki_file.content
        instructions = _extract_section(body, "지시사항")
        if not instructions:
            instructions = body

        ctx = SkillContext(
            instructions=instructions,
            role=_extract_section(body, "역할"),
            workflow=_extract_section(body, "워크플로우"),
            checklist=_extract_section(body, "체크리스트"),
            output_format=_extract_section(body, "출력 형식"),
            self_regulation=_extract_section(body, "제한사항"),
        )

        # Follow [[wikilinks]] and read referenced docs, track missing
        for doc_path in skill.referenced_docs:
            doc = await self.storage.read(doc_path)
            if doc:
                ctx.referenced_doc_contents.append((doc.title, doc.content))
                ctx.preamble_docs_found += 1
            else:
                ctx.preamble_docs_missing.append(doc_path)
                logger.warning(f"Skill {skill.path} references missing doc: {doc_path}")

        return ctx

    def invalidate(self) -> None:
        """Force cache refresh on next access."""
        self._cache_ts = 0.0

    async def _maybe_refresh(self) -> None:
        """Refresh cache if TTL expired."""
        now = time.monotonic()
        if now - self._cache_ts < self._cache_ttl and self._cache:
            return
        await self._scan_skills()
        self._cache_ts = now

    async def _scan_skills(self) -> None:
        """Scan _skills/ subtree and parse skill documents."""
        new_cache: dict[str, SkillMeta] = {}

        try:
            all_paths = await self.storage.list_file_paths()
        except Exception:
            logger.exception("Failed to list files for skill scan")
            return

        skill_paths = [p for p in all_paths if p.startswith("_skills/") and p.endswith(".md")]

        for path in skill_paths:
            try:
                wiki_file = await self.storage.read(path)
                if not wiki_file:
                    continue

                meta = self._parse_skill(path, wiki_file.raw_content or wiki_file.content)
                if meta:
                    new_cache[path] = meta
            except Exception:
                logger.warning(f"Failed to parse skill: {path}", exc_info=True)

        self._cache = new_cache
        logger.info(f"Skill scan complete: {len(new_cache)} skills loaded")

    def _parse_skill(self, path: str, raw_content: str) -> SkillMeta | None:
        """Parse a markdown file into SkillMeta if it has type: skill frontmatter."""
        match = FRONTMATTER_RE.match(raw_content)
        if not match:
            return None

        yaml_str = match.group(1)
        body = raw_content[match.end():]

        try:
            data = yaml.safe_load(yaml_str)
            if not isinstance(data, dict):
                return None
        except yaml.YAMLError:
            return None

        # Only process files with type: skill
        if data.get("type") != "skill":
            return None

        # Extract title from first # heading or filename
        title_match = TITLE_RE.search(body)
        title = title_match.group(1).strip() if title_match else path.split("/")[-1].replace(".md", "")

        # Extract [[wikilinks]] from body
        referenced_docs = WIKILINK_RE.findall(body)

        # Resolve wikilink names to paths (append .md if no extension)
        resolved_refs: list[str] = []
        for ref in referenced_docs:
            if not ref.endswith(".md"):
                resolved_refs.append(f"{ref}.md")
            else:
                resolved_refs.append(ref)

        # Determine scope from path
        scope = "personal" if "/@" in path or "/_skills/@" in path.replace("_skills/@", "/_skills/@") else "shared"
        # Simpler check: if path contains @username/ pattern
        if "/@" in path:
            scope = "personal"
        else:
            scope = data.get("scope", "shared")

        trigger = data.get("trigger", [])
        if isinstance(trigger, str):
            trigger = [trigger]

        # Category: frontmatter override, else derive from folder path
        category = data.get("category", "")
        if not category:
            category = self._extract_category(path)

        # Priority: clamp 1~10
        priority = int(data.get("priority", 5))
        priority = max(1, min(10, priority))

        pinned = bool(data.get("pinned", False))

        return SkillMeta(
            path=path,
            title=title,
            description=data.get("description", ""),
            trigger=trigger,
            icon=data.get("icon", "⚡"),
            scope=scope,
            enabled=data.get("enabled", True),
            created_by=data.get("created_by", ""),
            updated=str(data.get("updated", "")),
            referenced_docs=resolved_refs,
            category=category,
            priority=priority,
            pinned=pinned,
        )

    @staticmethod
    def _extract_category(path: str) -> str:
        """Derive category from folder path.

        _skills/HR/file.md           → "HR"
        _skills/@user/SCM/file.md    → "SCM"
        _skills/file.md              → ""
        _skills/@user/file.md        → ""
        """
        # Remove _skills/ prefix
        rel = path.removeprefix("_skills/")

        # Strip @username/ prefix for personal skills
        if rel.startswith("@"):
            parts = rel.split("/", 1)
            if len(parts) < 2:
                return ""
            rel = parts[1]

        # If there's a subfolder before the filename, that's the category
        parts = rel.rsplit("/", 1)
        if len(parts) > 1:
            return parts[0]
        return ""
