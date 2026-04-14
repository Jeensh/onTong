"""Prompt loader — read skill prompts from markdown files.

Loads .md files from the prompts/ directory next to this module.
Cached after first read to avoid repeated disk I/O.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=16)
def load_prompt(skill_name: str) -> str:
    """Load a skill prompt from prompts/{skill_name}.md.

    Returns the file content, or empty string if not found.
    """
    path = _PROMPTS_DIR / f"{skill_name}.md"
    try:
        content = path.read_text(encoding="utf-8")
        logger.debug(f"Loaded prompt: {path.name} ({len(content)} chars)")
        return content
    except FileNotFoundError:
        logger.warning(f"Prompt file not found: {path}")
        return ""
