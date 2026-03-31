"""Built-in skills for the onTong agent system."""

from backend.application.agent.skill import skill_registry
from .query_augment import QueryAugmentSkill
from .wiki_search import WikiSearchSkill
from .wiki_read import WikiReadSkill
from .wiki_write import WikiWriteSkill
from .wiki_edit import WikiEditSkill
from .llm_generate import LLMGenerateSkill
from .conflict_check import ConflictCheckSkill


def register_all_skills() -> None:
    """Register all built-in skills. Called from main.py lifespan."""
    skill_registry.register(QueryAugmentSkill())
    skill_registry.register(WikiSearchSkill())
    skill_registry.register(WikiReadSkill())
    skill_registry.register(WikiWriteSkill())
    skill_registry.register(WikiEditSkill())
    skill_registry.register(LLMGenerateSkill())
    skill_registry.register(ConflictCheckSkill())
