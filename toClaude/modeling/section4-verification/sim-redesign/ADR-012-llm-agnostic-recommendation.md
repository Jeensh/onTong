# ADR-012: LLM-agnostic Recommendation Engine API

작성일: 2026-05-13
상태: 확정 (사용자 결정, 2026-05-13)
선행: ADR-002 (Two-Engine + plugin), ADR-005 (Recommendation LLM defenses — sibling)
관련 결정: D5 (LLM-agnostic)

## 컨텍스트

DECISIONS-CONFIRMED.md 의 D5 는 Recommendation Engine 의 LLM provider 선택을:
- 추천 (`SYNTHESIS-ROUND2.html`): Claude (단일 provider, simplicity)
- D5 결정: **LLM-agnostic (다중 지원)** (추천 X, non-default)

근거 (`DECISIONS-CONFIRMED.md` 인용):
> Per-call LLM provider abstraction layer. Manifest 확장: model_version 외 LLM_provider field 추가. Prompt template 의 model-specific 회피. 설계 복잡도 ↑, ecosystem flexibility ↑ — Claude / GPT / Gemini swap 가능

이 ADR 은 LLM-agnostic abstraction 의 구체적 API + manifest 구조 명세.

## 결정

**Recommendation Engine 의 LLM 호출은 abstract `LLMProvider` interface 를 거치며, prompt template 은 provider-specific feature (tool use, structured output 등) 회피.**

### 1. `LLMProvider` interface

```python
# core/recommendation/llm_provider.py

from typing import Protocol, Literal
from pydantic import BaseModel

class LLMRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    response_schema: dict  # JSON schema (generic) — not Claude's input_schema or OpenAI function calling
    temperature: float = 0.0
    max_tokens: int = 4096
    metadata: dict = {}  # plugin-specific (system_name, version, etc.)

class LLMResponse(BaseModel):
    content: dict       # JSON conforming to response_schema
    provider: str       # "claude" | "openai" | "gemini" | ...
    model: str          # specific model id
    raw_response: dict  # for debugging
    usage: dict         # tokens / cost

class LLMProvider(Protocol):
    name: str                       # "claude" | "openai" | "gemini"
    supported_models: list[str]

    def invoke(self, request: LLMRequest) -> LLMResponse:
        """Single round LLM call. Synchronous."""
        ...

    def supports_feature(self, feature: str) -> bool:
        """e.g., 'structured_output', 'long_context', 'vision'. Default False if unknown."""
        ...
```

### 2. Provider implementation

```python
# core/recommendation/providers/claude_provider.py
class ClaudeProvider:
    name = "claude"
    supported_models = ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"]

    def invoke(self, request):
        # Anthropic SDK
        # response_schema → tool use input_schema (internal), but result still generic JSON
        ...

# core/recommendation/providers/openai_provider.py
class OpenAIProvider:
    name = "openai"
    supported_models = ["gpt-5", "gpt-4o"]

    def invoke(self, request):
        # OpenAI SDK
        # response_schema → function calling schema, result generic JSON
        ...

# core/recommendation/providers/gemini_provider.py
class GeminiProvider:
    name = "gemini"
    supported_models = ["gemini-2.5-pro", "gemini-2.0-pro"]

    def invoke(self, request):
        # Google AI SDK
        ...
```

### 3. Manifest 확장 (plugin 단위)

Plugin 의 `manifest.toml`:
```toml
[plugin]
name = "v2-slab-design"
version = "0.1.0"

[recommendation]
default_provider = "claude"
default_model = "claude-opus-4-7"
allowed_providers = ["claude", "openai", "gemini"]
require_features = []  # 비워두면 기본 feature set 만 요구
```

System-level override 가능:
```python
# core/recommendation/engine.py
def get_provider(plugin_manifest, override=None) -> LLMProvider:
    name = override or plugin_manifest.recommendation.default_provider
    return REGISTRY[name]
```

### 4. Prompt template 의 provider-agnostic 원칙

Bad (Claude-specific):
```python
prompt = """
Use the recommend tool. Input schema:
{
  "type": "object",
  "properties": {...}
}
"""
# Claude tool use 의존, OpenAI function calling 으로 transliterate 어려움
```

Good (generic):
```python
prompt = """
Output a JSON object matching:
{
  "type": "object",
  "properties": {...}
}
"""
# Provider 가 알아서 native feature (tool use, function calling, structured output) 으로 lower
```

Provider implementation 안에서 transliterate:
```python
class ClaudeProvider:
    def invoke(self, request):
        # request.response_schema → tool_use 의 input_schema 로 wrap
        result = anthropic.messages.create(
            tools=[{"name": "respond", "input_schema": request.response_schema}],
            tool_choice={"name": "respond"},
            ...
        )
        return LLMResponse(content=result.content[0].input, ...)
```

### 5. Cross-provider test contract

매 prompt template 은 `tests/cross_provider_test_<template>.py` 에서 3 provider 모두에서 동등 quality:
```python
@pytest.mark.parametrize("provider", ["claude", "openai", "gemini"])
def test_recommendation_quality_for_template_X(provider):
    request = LLMRequest(...)
    response = REGISTRY[provider].invoke(request)

    # Cross-provider quality gate:
    # - response.content conforms to schema (strict)
    # - response.content 의 핵심 field 가 expected range 안
    # - 같은 input 에서 3 provider 가 동일 카테고리 result
    assert response.content["category"] == expected_category
    assert response.usage["total_tokens"] < 4096
```

ADR-011 의 G3 gate (Month 3) 에서 3 system × 3 provider 매트릭스로 검증.

## Risk + mitigation

| Risk | Mitigation |
|---|---|
| Quality 격차 (Claude > GPT > Gemini 가능) | Per-template quality gate. Sub-threshold provider 는 `allowed_providers` 에서 자동 제외 |
| Provider 별 feature gap | `supports_feature()` check + fallback prompt pattern |
| Cost 격차 (provider 별 token 가격 차이) | Usage tracking + cost-aware routing (optional, phase 2) |
| Provider API 변경 (SDK upgrade) | Provider adapter 의 isolated test suite. Manifest 의 `default_model` 명시로 silent drift 방지 |
| 한 provider 가 ToS 제약으로 자동화 금지 | Manifest 의 `allowed_providers` 에서 제외, 다른 provider fallback |

## 결과 / 영향

- Ecosystem flexibility — Anthropic / OpenAI / Google 의 provider lock-in 회피
- Cost optimization 가능성 (provider 별 routing)
- 설계 복잡도 ↑ — abstraction layer + cross-provider test
- 향후 추가 provider (Mistral, Cohere 등) 추가 cost = adapter 1개

## Phase 2 (future) — 비core 항목

- Cost-aware routing — token 비용 기반 provider 선택
- Quality-aware routing — template 별 quality gate 통계 기반
- Caching — provider 별 prompt cache (Anthropic 의 cache_control 등)

## 참조

- DECISIONS-CONFIRMED.md (D5)
- ADR-002 (plugin + manifest)
- ADR-005 (Recommendation Engine 의 4 defense mechanism — sibling)
- ADR-011 (3 systems — G3 gate 에서 cross-provider 검증)
- `core/recommendation/` (구현 directory, implementation phase 에서)
