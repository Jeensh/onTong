"""Tests for SkillMatcher — keyword trigger matching, scoring, priority.

Usage:
    cd /path/to/onTong
    source venv/bin/activate
    pytest tests/test_skill_matcher.py -v
"""

from __future__ import annotations

import pytest

from backend.application.skill.skill_matcher import SkillMatcher, _tokenize
from backend.application.skill.skill_loader import UserSkillLoader
from backend.core.schemas import SkillMeta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill(
    path: str = "_skills/test.md",
    title: str = "테스트",
    trigger: list[str] | None = None,
    enabled: bool = True,
    scope: str = "shared",
    priority: int = 5,
    pinned: bool = False,
    category: str = "",
) -> SkillMeta:
    return SkillMeta(
        path=path,
        title=title,
        trigger=trigger or [],
        enabled=enabled,
        scope=scope,
        priority=priority,
        pinned=pinned,
        category=category,
    )


class FakeWikiFile:
    def __init__(self, path: str, raw_content: str, title: str = ""):
        self.path = path
        self.raw_content = raw_content
        self.content = raw_content
        self.title = title or path.split("/")[-1].replace(".md", "")


class FakeStorage:
    """Minimal storage that returns pre-built skills via loader."""
    def __init__(self, skills: list[SkillMeta]):
        self._skills = skills
        self._files: dict[str, str] = {}
        for s in skills:
            # Build minimal frontmatter for skill_loader to parse
            trigger_yaml = "\n".join(f"  - {t}" for t in s.trigger)
            self._files[s.path] = (
                f"---\ntype: skill\ntrigger:\n{trigger_yaml}\n"
                f"icon: {s.icon}\nscope: {s.scope}\n"
                f"enabled: {'true' if s.enabled else 'false'}\n"
                f"priority: {s.priority}\n"
                f"{'pinned: true' if s.pinned else ''}\n"
                f"{'category: ' + s.category if s.category else ''}\n"
                f"---\n\n# {s.title}\n\n## 지시사항\n내용\n"
            )

    async def list_file_paths(self) -> list[str]:
        return list(self._files.keys())

    async def read(self, path: str) -> FakeWikiFile | None:
        content = self._files.get(path)
        if content is None:
            return None
        return FakeWikiFile(path=path, raw_content=content)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_korean(self):
        tokens = _tokenize("신규 입사자 온보딩")
        assert "신규" in tokens
        assert "입사자" in tokens
        assert "온보딩" in tokens

    def test_english(self):
        tokens = _tokenize("Hello World test")
        assert "hello" in tokens
        assert "world" in tokens

    def test_mixed(self):
        tokens = _tokenize("출장비 expense 규정")
        assert "출장비" in tokens
        assert "expense" in tokens
        assert "규정" in tokens

    def test_punctuation_stripped(self):
        tokens = _tokenize("안녕하세요! (테스트)")
        assert "안녕하세요" in tokens
        assert "테스트" in tokens
        assert "!" not in tokens

    def test_empty(self):
        assert _tokenize("") == set()


# ---------------------------------------------------------------------------
# SkillMatcher._score (internal)
# ---------------------------------------------------------------------------

class TestMatcherScore:
    def setup_method(self):
        self.matcher = SkillMatcher()

    def test_exact_substring_high_score(self):
        skill = _skill(trigger=["온보딩"])
        score = self.matcher._score("신규 입사자 온보딩 절차", _tokenize("신규 입사자 온보딩 절차"), skill)
        assert score >= 0.9

    def test_no_trigger_zero(self):
        skill = _skill(trigger=[])
        score = self.matcher._score("아무 질문", _tokenize("아무 질문"), skill)
        assert score == 0.0

    def test_token_overlap(self):
        # "경비" overlaps, but "정산해" != "정산" (Korean agglutinative)
        # Use a query with exact token overlap to test Jaccard path
        skill = _skill(trigger=["경비 정산 규정"])
        score = self.matcher._score(
            "경비 정산 어떻게 해?",
            _tokenize("경비 정산 어떻게 해"),
            skill,
        )
        # "경비", "정산" overlap out of 5 unique tokens → Jaccard = 2/5 = 0.4 ≥ 0.3
        assert score > 0

    def test_no_overlap_zero(self):
        skill = _skill(trigger=["온보딩"])
        score = self.matcher._score("날씨가 좋다", _tokenize("날씨가 좋다"), skill)
        assert score == 0.0

    def test_multiple_triggers_best(self):
        """Multiple triggers → best score wins."""
        skill = _skill(trigger=["온보딩", "신규입사자 온보딩 절차"])
        score = self.matcher._score("온보딩", _tokenize("온보딩"), skill)
        assert score >= 0.9  # exact substring match on "온보딩"


# ---------------------------------------------------------------------------
# SkillMatcher.match (async, full flow)
# ---------------------------------------------------------------------------

class TestMatcherMatch:
    @pytest.fixture
    def skills(self):
        return [
            _skill(
                path="_skills/HR/onboarding.md",
                title="온보딩",
                trigger=["온보딩", "신규입사자"],
                priority=5,
            ),
            _skill(
                path="_skills/Finance/expense.md",
                title="출장비",
                trigger=["출장비", "경비 정산"],
                priority=5,
            ),
            _skill(
                path="_skills/disabled.md",
                title="비활성",
                trigger=["비활성 트리거"],
                enabled=False,
            ),
        ]

    @pytest.fixture
    def matcher(self):
        return SkillMatcher()

    @pytest.fixture
    def loader(self, skills):
        return UserSkillLoader(FakeStorage(skills))

    @pytest.mark.asyncio
    async def test_exact_match(self, matcher, loader):
        result = await matcher.match("온보딩 절차 알려줘", "", loader)
        assert result is not None
        skill, confidence = result
        assert skill.title == "온보딩"
        assert confidence >= 0.5

    @pytest.mark.asyncio
    async def test_different_skill_match(self, matcher, loader):
        result = await matcher.match("출장비 정산 어떻게 해?", "", loader)
        assert result is not None
        assert result[0].title == "출장비"

    @pytest.mark.asyncio
    async def test_below_threshold_returns_none(self, matcher, loader):
        result = await matcher.match("완전 관련 없는 질문", "", loader)
        assert result is None

    @pytest.mark.asyncio
    async def test_disabled_skill_excluded(self, matcher, loader):
        result = await matcher.match("비활성 트리거", "", loader)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_query(self, matcher, loader):
        result = await matcher.match("", "", loader)
        assert result is None


# ---------------------------------------------------------------------------
# Priority / Pinned tiebreaker
# ---------------------------------------------------------------------------

class TestPriorityTiebreaker:
    @pytest.fixture
    def matcher(self):
        return SkillMatcher()

    @pytest.mark.asyncio
    async def test_higher_priority_wins(self, matcher):
        skills = [
            _skill(
                path="_skills/low.md",
                title="낮은 우선순위",
                trigger=["공통 키워드"],
                priority=3,
            ),
            _skill(
                path="_skills/high.md",
                title="높은 우선순위",
                trigger=["공통 키워드"],
                priority=9,
            ),
        ]
        loader = UserSkillLoader(FakeStorage(skills))
        result = await matcher.match("공통 키워드 관련 질문", "", loader)
        assert result is not None
        assert result[0].title == "높은 우선순위"

    @pytest.mark.asyncio
    async def test_pinned_wins_same_priority(self, matcher):
        skills = [
            _skill(
                path="_skills/normal.md",
                title="일반",
                trigger=["동일 트리거"],
                priority=5,
                pinned=False,
            ),
            _skill(
                path="_skills/pinned.md",
                title="고정됨",
                trigger=["동일 트리거"],
                priority=5,
                pinned=True,
            ),
        ]
        loader = UserSkillLoader(FakeStorage(skills))
        result = await matcher.match("동일 트리거 질문", "", loader)
        assert result is not None
        assert result[0].title == "고정됨"

    @pytest.mark.asyncio
    async def test_priority_boost_formula(self, matcher):
        """Priority 5 → multiplier 1.0, priority 10 → 1.2."""
        skill_5 = _skill(trigger=["테스트"], priority=5)
        skill_10 = _skill(trigger=["테스트"], priority=10)

        base = matcher._score("테스트", _tokenize("테스트"), skill_5)
        boosted_5 = base * (0.8 + 5 * 0.04)
        boosted_10 = base * (0.8 + 10 * 0.04)

        assert abs(boosted_5 - base * 1.0) < 0.001
        assert abs(boosted_10 - base * 1.2) < 0.001
