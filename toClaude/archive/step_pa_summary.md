# Pydantic AI Migration Summary

## Scope
Hybrid migration: Pydantic AI for structured outputs + ReAct agent loop + streaming,
keeping existing Skill/Registry protocols and SSE event interface unchanged.

## Changes

### New Files (7)
| File | Purpose |
|------|---------|
| `llm_factory.py` | Centralized `get_model_id()` → `litellm:ollama/llama3` |
| `models.py` | 6 Pydantic models for structured LLM outputs |
| `pydantic_tools.py` | `@agent.tool` wrappers bridging skills to Pydantic AI |
| `react_agent.py` | Factory for Pydantic AI ReAct agents with wiki tools |
| `structured_agents.py` | Factory functions for cognitive/clarity/classify agents |
| `test_pydantic_ai_migration.py` | 29 migration-specific tests |
| `pyproject.toml` (modified) | Added `pydantic-ai-slim[litellm]` dependency |

### Modified Files (12)
- **rag_agent.py** — Removed `import litellm`, converted `_cognitive_reflect()` to Pydantic AI structured output, converted `_augment_query()`, replaced all inline `litellm.acompletion()` fallbacks with Pydantic AI agents
- **router.py** — Removed `import litellm`, `_llm_classify()` → Pydantic AI `IntentClassification`
- **tool_executor.py** — Rewrote `react_loop()` to use Pydantic AI `Agent.run_stream()` with `event_stream_handler`
- **skills/conflict_check.py** — Pydantic AI `ConflictCheckResult` structured output
- **skills/wiki_write.py** — Pydantic AI `WikiWriteResult` structured output
- **skills/wiki_edit.py** — Pydantic AI `WikiEditResult` structured output + document picker
- **skills/query_augment.py** — Pydantic AI `Agent(output_type=str)`
- **skills/llm_generate.py** — Retained litellm for streaming/tool-calling (only remaining litellm consumer)
- **simulator_agent.py** — Added Pydantic AI usage scaffolding in docstring
- **tracer_agent.py** — Added Pydantic AI usage scaffolding in docstring

## Design Decisions
1. **Hybrid approach** — RAG pipeline orchestration stays custom; Pydantic AI for individual LLM calls
2. **litellm retained in llm_generate.py only** — streaming chunk generator and tool_calls support not cleanly wrapped by Pydantic AI Agent
3. **`litellm:` prefix model strings** — Pydantic AI's LiteLLMProvider handles routing to Ollama/OpenAI/etc.
4. **No API contract changes** — SSE event types, frontend interface, skill protocol all unchanged

## Test Results
- **174/174 PASS** (145 existing + 29 new migration tests)
- New tests cover: model validation, factory functions, tool registration, litellm removal verification
