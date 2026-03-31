"""LLM-powered metadata suggestion service."""

from __future__ import annotations

import json
import logging

import litellm

from backend.core.config import settings
from backend.core.schemas import MetadataSuggestion

logger = logging.getLogger(__name__)

SUGGEST_SYSTEM_PROMPT = """\
You are a metadata tagging assistant for a manufacturing SCM knowledge base.
Given a document's content, suggest appropriate metadata tags.

Respond with ONLY a JSON object (no markdown fences) with these fields:
- "domain": one of ["SCM", "QC", "LOGISTICS", "PRODUCTION", "MAINTENANCE", "IT", "GENERAL"] or empty string
- "process": a short process name (e.g., "주문처리", "재고관리", "장애대응") or empty string
- "error_codes": list of error codes mentioned (e.g., ["DG320", "ERR-001"]) or empty list
- "tags": list of 3-7 descriptive keyword tags in Korean or English (e.g., ["캐시", "Redis", "장애대응"])
- "confidence": float 0-1 indicating how confident you are
- "reasoning": brief Korean explanation of why you chose these tags
"""


async def suggest_metadata(
    content: str, existing_tags: list[str] | None = None
) -> MetadataSuggestion:
    """Use LLM to suggest metadata for a document."""
    existing = existing_tags or []
    user_prompt = f"Document content:\n\n{content[:3000]}"
    if existing:
        user_prompt += f"\n\nAlready assigned tags (exclude from suggestions): {existing}"

    try:
        response = await litellm.acompletion(
            model=settings.litellm_model,
            messages=[
                {"role": "system", "content": SUGGEST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)

        # Filter out existing tags
        suggested_tags = [t for t in data.get("tags", []) if t not in existing]

        return MetadataSuggestion(
            domain=data.get("domain", ""),
            process=data.get("process", ""),
            error_codes=data.get("error_codes", []),
            tags=suggested_tags,
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning", ""),
        )

    except Exception as e:
        logger.error(f"Metadata suggestion failed: {e}")
        return MetadataSuggestion(
            confidence=0.0,
            reasoning=f"추천 실패: {e}",
        )
