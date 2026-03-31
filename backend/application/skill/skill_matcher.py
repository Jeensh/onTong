"""SkillMatcher — keyword-based trigger matching (no LLM call)."""

from __future__ import annotations

import re
from typing import Any

from backend.core.schemas import SkillMeta


# Simple Korean-aware tokenizer: split on whitespace and punctuation
_TOKEN_RE = re.compile(r"[\w가-힣]+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase word/Korean tokens."""
    return {t.lower() for t in _TOKEN_RE.findall(text)}


class SkillMatcher:
    """Match user query against skill triggers.

    Matching logic (no LLM, fast keyword matching):
    1. Exact substring: trigger is a substring of query → confidence 0.9
    2. Token overlap: Jaccard similarity ≥ 0.3 → confidence = overlap * 0.8
    3. Best match returned; personal skills win ties.
    4. Threshold 0.5 → return None if below.
    """

    THRESHOLD = 0.5

    async def match(
        self,
        query: str,
        username: str,
        loader: Any,  # UserSkillLoader (avoid import cycle)
    ) -> tuple[SkillMeta, float] | None:
        """Return (skill, confidence) for the best-matching skill, or None."""
        skill_list = await loader.list_skills(username)
        candidates = skill_list.personal + skill_list.system

        if not candidates:
            return None

        query_lower = query.lower()
        query_tokens = _tokenize(query)

        best: tuple[SkillMeta, float] | None = None
        best_key: tuple = ()  # (score, pinned, priority, is_personal)

        for skill in candidates:
            if not skill.enabled:
                continue

            base_score = self._score(query_lower, query_tokens, skill)
            if base_score < self.THRESHOLD:
                continue

            # Priority boost: multiplier so bad matches can't win via priority alone
            # priority 5 (default) = 1.0x, priority 10 = 1.2x, priority 1 = 0.84x
            score = base_score * (0.8 + skill.priority * 0.04)

            # Tiebreaker tuple: higher is better for all components
            key = (score, skill.pinned, skill.priority, skill.scope == "personal")

            if best is None or key > best_key:
                best = (skill, score)
                best_key = key

        return best

    def _score(self, query_lower: str, query_tokens: set[str], skill: SkillMeta) -> float:
        """Compute match score between query and skill triggers."""
        if not skill.trigger:
            return 0.0

        best_score = 0.0

        for trigger in skill.trigger:
            trigger_lower = trigger.lower()

            # 1. Exact substring match
            if trigger_lower in query_lower:
                score = 0.9
                # Bonus for longer trigger matches (more specific)
                ratio = len(trigger_lower) / max(len(query_lower), 1)
                score = min(0.95, score + ratio * 0.05)
                best_score = max(best_score, score)
                continue

            # 2. Token overlap (Jaccard)
            trigger_tokens = _tokenize(trigger)
            if not trigger_tokens:
                continue

            intersection = query_tokens & trigger_tokens
            union = query_tokens | trigger_tokens
            if not union:
                continue

            jaccard = len(intersection) / len(union)
            if jaccard >= 0.3:
                score = jaccard * 0.8
                best_score = max(best_score, score)

        return best_score
