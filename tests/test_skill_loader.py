"""Tests for UserSkillLoader — frontmatter parsing, category extraction,
6-layer section extraction, cache TTL, wikilink references.

Usage:
    cd /path/to/onTong
    source venv/bin/activate
    pytest tests/test_skill_loader.py -v
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.skill.skill_loader import (
    UserSkillLoader,
    _extract_section,
    FRONTMATTER_RE,
    WIKILINK_RE,
)
from backend.core.schemas import SkillMeta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill_md(
    *,
    title: str = "테스트 스킬",
    description: str = "test skill",
    trigger: list[str] | None = None,
    icon: str = "⚡",
    scope: str = "shared",
    enabled: bool = True,
    category: str = "",
    priority: int = 5,
    pinned: bool = False,
    instructions: str = "지시사항 내용",
    role: str = "",
    workflow: str = "",
    checklist: str = "",
    output_format: str = "",
    self_regulation: str = "",
    refs: list[str] | None = None,
) -> str:
    """Build a skill markdown document with YAML frontmatter."""
    lines = ["---", "type: skill"]
    lines.append(f"description: {description}")
    if trigger:
        lines.append("trigger:")
        for t in trigger:
            lines.append(f"  - {t}")
    lines.append(f"icon: {icon}")
    lines.append(f"scope: {scope}")
    lines.append(f"enabled: {'true' if enabled else 'false'}")
    if category:
        lines.append(f"category: {category}")
    if priority != 5:
        lines.append(f"priority: {priority}")
    if pinned:
        lines.append("pinned: true")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    if role:
        lines.append("## 역할")
        lines.append(role)
        lines.append("")
    lines.append("## 지시사항")
    lines.append(instructions)
    lines.append("")
    if workflow:
        lines.append("## 워크플로우")
        lines.append(workflow)
        lines.append("")
    if checklist:
        lines.append("## 체크리스트")
        lines.append(checklist)
        lines.append("")
    if output_format:
        lines.append("## 출력 형식")
        lines.append(output_format)
        lines.append("")
    if self_regulation:
        lines.append("## 제한사항")
        lines.append(self_regulation)
        lines.append("")
    lines.append("## 참조 문서")
    if refs:
        for r in refs:
            lines.append(f"- [[{r}]]")
    else:
        lines.append("- [[sample-doc]]")
    lines.append("")
    return "\n".join(lines)


class FakeWikiFile:
    """Minimal stand-in for WikiFile returned by storage.read()."""
    def __init__(self, path: str, raw_content: str, title: str = ""):
        self.path = path
        self.raw_content = raw_content
        self.content = raw_content
        self.title = title or path.split("/")[-1].replace(".md", "")


class FakeStorage:
    """In-memory fake for the StorageBackend used by UserSkillLoader."""
    def __init__(self, files: dict[str, str] | None = None):
        self._files: dict[str, str] = files or {}

    async def list_file_paths(self) -> list[str]:
        return list(self._files.keys())

    async def read(self, path: str) -> FakeWikiFile | None:
        content = self._files.get(path)
        if content is None:
            return None
        return FakeWikiFile(path=path, raw_content=content)


# ---------------------------------------------------------------------------
# Regex unit tests
# ---------------------------------------------------------------------------

class TestFrontmatterRegex:
    def test_match_valid(self):
        raw = "---\ntype: skill\n---\n# Title"
        m = FRONTMATTER_RE.match(raw)
        assert m is not None
        assert "type: skill" in m.group(1)

    def test_no_frontmatter(self):
        raw = "# Just a title\nSome content"
        assert FRONTMATTER_RE.match(raw) is None


class TestWikilinkRegex:
    def test_single(self):
        assert WIKILINK_RE.findall("참조: [[온보딩-가이드]]") == ["온보딩-가이드"]

    def test_multiple(self):
        text = "- [[doc-a]]\n- [[doc-b.md]]"
        assert WIKILINK_RE.findall(text) == ["doc-a", "doc-b.md"]

    def test_none(self):
        assert WIKILINK_RE.findall("no links here") == []


# ---------------------------------------------------------------------------
# _extract_section
# ---------------------------------------------------------------------------

class TestExtractSection:
    BODY = (
        "## 역할\n역할 내용입니다\n\n"
        "## 지시사항\n지시사항 내용\n\n"
        "## 워크플로우\n### 1단계\n첫 단계\n\n"
        "## 참조 문서\n- [[doc]]"
    )

    def test_extract_existing(self):
        assert _extract_section(self.BODY, "역할") == "역할 내용입니다"

    def test_extract_instructions(self):
        assert _extract_section(self.BODY, "지시사항") == "지시사항 내용"

    def test_extract_workflow_multiline(self):
        result = _extract_section(self.BODY, "워크플로우")
        assert "### 1단계" in result
        assert "첫 단계" in result

    def test_extract_missing(self):
        assert _extract_section(self.BODY, "체크리스트") == ""


# ---------------------------------------------------------------------------
# _parse_skill (via loader)
# ---------------------------------------------------------------------------

class TestParseSkill:
    def setup_method(self):
        self.loader = UserSkillLoader(FakeStorage())

    def test_valid_skill(self):
        raw = _make_skill_md(title="온보딩", trigger=["온보딩", "신규입사자"])
        meta = self.loader._parse_skill("_skills/HR/onboarding.md", raw)
        assert meta is not None
        assert meta.title == "온보딩"
        assert meta.trigger == ["온보딩", "신규입사자"]
        assert meta.enabled is True

    def test_non_skill_type(self):
        raw = "---\ntype: document\n---\n# Not a skill"
        assert self.loader._parse_skill("_skills/test.md", raw) is None

    def test_no_frontmatter(self):
        raw = "# Just markdown"
        assert self.loader._parse_skill("_skills/test.md", raw) is None

    def test_invalid_yaml(self):
        raw = "---\n: invalid: yaml: {{{\n---\n# Title"
        assert self.loader._parse_skill("_skills/test.md", raw) is None

    def test_disabled_skill(self):
        raw = _make_skill_md(enabled=False)
        meta = self.loader._parse_skill("_skills/test.md", raw)
        assert meta is not None
        assert meta.enabled is False

    def test_priority_clamp_high(self):
        raw = _make_skill_md(priority=99)
        meta = self.loader._parse_skill("_skills/test.md", raw)
        assert meta.priority == 10

    def test_priority_clamp_low(self):
        raw = _make_skill_md(priority=-5)
        meta = self.loader._parse_skill("_skills/test.md", raw)
        assert meta.priority == 1

    def test_pinned(self):
        raw = _make_skill_md(pinned=True)
        meta = self.loader._parse_skill("_skills/test.md", raw)
        assert meta.pinned is True

    def test_wikilink_ref_md_appended(self):
        raw = _make_skill_md(refs=["온보딩-가이드"])
        meta = self.loader._parse_skill("_skills/test.md", raw)
        assert "온보딩-가이드.md" in meta.referenced_docs

    def test_wikilink_ref_already_md(self):
        raw = _make_skill_md(refs=["guide.md"])
        meta = self.loader._parse_skill("_skills/test.md", raw)
        assert "guide.md" in meta.referenced_docs

    def test_title_from_heading(self):
        raw = _make_skill_md(title="스킬 제목")
        meta = self.loader._parse_skill("_skills/test.md", raw)
        assert meta.title == "스킬 제목"

    def test_title_fallback_to_filename(self):
        raw = "---\ntype: skill\n---\nNo heading here"
        meta = self.loader._parse_skill("_skills/fallback.md", raw)
        assert meta.title == "fallback"


# ---------------------------------------------------------------------------
# _extract_category
# ---------------------------------------------------------------------------

class TestExtractCategory:
    def test_subfolder(self):
        assert UserSkillLoader._extract_category("_skills/HR/file.md") == "HR"

    def test_nested_subfolder(self):
        assert UserSkillLoader._extract_category("_skills/IT/Network/file.md") == "IT/Network"

    def test_root_level(self):
        assert UserSkillLoader._extract_category("_skills/file.md") == ""

    def test_personal_with_category(self):
        assert UserSkillLoader._extract_category("_skills/@user/SCM/file.md") == "SCM"

    def test_personal_root(self):
        assert UserSkillLoader._extract_category("_skills/@user/file.md") == ""

    def test_category_frontmatter_override(self):
        """Frontmatter category should override folder-derived one."""
        loader = UserSkillLoader(FakeStorage())
        raw = _make_skill_md(category="커스텀")
        meta = loader._parse_skill("_skills/HR/test.md", raw)
        assert meta.category == "커스텀"

    def test_category_from_folder(self):
        """No frontmatter category → derive from folder."""
        loader = UserSkillLoader(FakeStorage())
        raw = _make_skill_md()  # no category set
        meta = loader._parse_skill("_skills/Finance/test.md", raw)
        assert meta.category == "Finance"


# ---------------------------------------------------------------------------
# list_skills (async)
# ---------------------------------------------------------------------------

class TestListSkills:
    @pytest.fixture
    def storage(self):
        return FakeStorage({
            "_skills/HR/onboarding.md": _make_skill_md(title="온보딩", trigger=["온보딩"]),
            "_skills/Finance/expense.md": _make_skill_md(title="출장비", trigger=["출장비"]),
            "_skills/disabled.md": _make_skill_md(title="비활성", enabled=False),
            "normal-doc.md": "---\ndomain: IT\n---\n# Not a skill",
        })

    @pytest.fixture
    def loader(self, storage):
        return UserSkillLoader(storage)

    @pytest.mark.asyncio
    async def test_list_enabled_only(self, loader):
        result = await loader.list_skills()
        titles = {s.title for s in result.system}
        assert "온보딩" in titles
        assert "출장비" in titles
        assert "비활성" not in titles

    @pytest.mark.asyncio
    async def test_list_include_disabled(self, loader):
        result = await loader.list_skills(include_disabled=True)
        titles = {s.title for s in result.system}
        assert "비활성" in titles

    @pytest.mark.asyncio
    async def test_categories(self, loader):
        result = await loader.list_skills(include_disabled=True)
        assert "HR" in result.categories
        assert "Finance" in result.categories

    @pytest.mark.asyncio
    async def test_non_skill_files_excluded(self, loader):
        result = await loader.list_skills(include_disabled=True)
        all_paths = {s.path for s in result.system + result.personal}
        assert "normal-doc.md" not in all_paths

    @pytest.mark.asyncio
    async def test_get_skill(self, loader):
        skill = await loader.get_skill("_skills/HR/onboarding.md")
        assert skill is not None
        assert skill.title == "온보딩"

    @pytest.mark.asyncio
    async def test_get_skill_not_found(self, loader):
        skill = await loader.get_skill("_skills/nonexistent.md")
        assert skill is None


# ---------------------------------------------------------------------------
# load_skill_context (6-layer)
# ---------------------------------------------------------------------------

class TestLoadSkillContext:
    @pytest.mark.asyncio
    async def test_full_6layer(self):
        raw = _make_skill_md(
            title="풀 스킬",
            instructions="지시 내용",
            role="친절한 상담사",
            workflow="### 1단계\n확인",
            checklist="- 필수 항목",
            output_format="1. 요약\n2. 상세",
            self_regulation="최대 500자",
            refs=["ref-doc"],
        )
        ref_content = "---\ndomain: HR\n---\n# 참조 문서\n참조 내용"
        storage = FakeStorage({
            "_skills/test.md": raw,
            "ref-doc.md": ref_content,
        })
        loader = UserSkillLoader(storage)

        skill = await loader.get_skill("_skills/test.md")
        ctx = await loader.load_skill_context(skill)

        assert "지시 내용" in ctx.instructions
        assert "친절한 상담사" in ctx.role
        assert "1단계" in ctx.workflow
        assert "필수 항목" in ctx.checklist
        assert "요약" in ctx.output_format
        assert "500자" in ctx.self_regulation
        assert ctx.preamble_docs_found == 1
        assert ctx.preamble_docs_missing == []

    @pytest.mark.asyncio
    async def test_missing_ref_doc(self):
        raw = _make_skill_md(refs=["missing-doc"])
        storage = FakeStorage({"_skills/test.md": raw})
        loader = UserSkillLoader(storage)

        skill = await loader.get_skill("_skills/test.md")
        ctx = await loader.load_skill_context(skill)

        assert ctx.preamble_docs_found == 0
        assert "missing-doc.md" in ctx.preamble_docs_missing

    @pytest.mark.asyncio
    async def test_instructions_fallback_to_body(self):
        """If no ## 지시사항 heading, entire body becomes instructions."""
        raw = "---\ntype: skill\n---\n# 제목\n\n전체 내용이 지시사항"
        storage = FakeStorage({"_skills/test.md": raw})
        loader = UserSkillLoader(storage)

        skill = await loader.get_skill("_skills/test.md")
        ctx = await loader.load_skill_context(skill)

        assert "전체 내용이 지시사항" in ctx.instructions


# ---------------------------------------------------------------------------
# Cache TTL
# ---------------------------------------------------------------------------

class TestCache:
    @pytest.mark.asyncio
    async def test_cache_reuse(self):
        storage = FakeStorage({
            "_skills/test.md": _make_skill_md(title="캐시 테스트"),
        })
        loader = UserSkillLoader(storage)
        loader._cache_ttl = 60  # long TTL

        await loader.list_skills()
        first_ts = loader._cache_ts

        await loader.list_skills()
        assert loader._cache_ts == first_ts  # no re-scan

    @pytest.mark.asyncio
    async def test_invalidate_forces_refresh(self):
        storage = FakeStorage({
            "_skills/test.md": _make_skill_md(title="V1"),
        })
        loader = UserSkillLoader(storage)
        loader._cache_ttl = 60

        await loader.list_skills()
        first_ts = loader._cache_ts

        loader.invalidate()
        await loader.list_skills()
        assert loader._cache_ts != first_ts  # re-scanned
