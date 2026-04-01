"""Pydantic models for structured LLM outputs.

These models replace manual json.loads() + .get() patterns throughout the agent code.
Pydantic AI validates outputs automatically and retries on parse failure.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CognitiveReflection(BaseModel):
    """Hidden first-pass LLM analysis — used in RAGAgent._cognitive_reflect()."""

    internal_thought: str = ""
    draft_response: str = ""
    self_critique: str = ""
    has_conflict: bool = False
    conflict_details: str = ""


class ClarityCheck(BaseModel):
    """Determine if a user query is specific enough to answer directly."""

    clear: bool = True
    response: str = ""


class IntentClassification(BaseModel):
    """Router LLM classification output."""

    agent: Literal["WIKI_QA", "SIMULATION", "DEBUG_TRACE"] = "WIKI_QA"


class UserIntent(BaseModel):
    """Unified intent classification — replaces all keyword-based routing.

    Determines both the target agent AND the action type in a single LLM call.
    """

    agent: Literal["WIKI_QA", "SIMULATION", "DEBUG_TRACE"] = "WIKI_QA"
    action: Literal["question", "write", "edit"] = "question"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class WikiEditResult(BaseModel):
    """LLM-generated document edit output."""

    content: str
    summary: str = "문서가 수정되었습니다."


class WikiWriteResult(BaseModel):
    """LLM-generated new document output."""

    path: str = "new-document.md"
    content: str


class ConflictCheckResult(BaseModel):
    """Conflict detection between documents."""

    has_conflict: bool = False
    details: str = ""
    conflicting_docs: list[str] = Field(default_factory=list)
