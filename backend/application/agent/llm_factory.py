"""Centralized model factory for Pydantic AI agents.

Usage:
    from backend.application.agent.llm_factory import get_model
    agent = Agent(get_model(), output_type=str, ...)

Model string format: "provider/model-name"
    openai/gpt-4o-mini       → OpenAI API
    anthropic/claude-sonnet-4-20250514 → Anthropic API
    ollama/llama3             → Local Ollama
    google/gemini-2.0-flash   → Google Gemini
    azure/gpt-4o              → Azure OpenAI
    groq/llama-3.3-70b        → Groq
    deepseek/deepseek-chat    → DeepSeek

To add a new provider:
    1. Add env vars to config.py (api key, endpoint, etc.)
    2. Add a _build_<provider>() function below
    3. Register it in PROVIDER_BUILDERS
"""

from __future__ import annotations

import logging
import os
from typing import Any

from backend.core.config import settings

logger = logging.getLogger(__name__)

_cached_model = None


def get_model_id() -> str:
    """Return the raw model string as configured (e.g. 'openai/gpt-4o-mini')."""
    return settings.litellm_model


def get_model() -> Any:
    """Return a configured Pydantic AI Model instance (cached singleton)."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    provider_name, model_name = _parse_model_string(settings.litellm_model)

    builder = PROVIDER_BUILDERS.get(provider_name)
    if builder is None:
        raise ValueError(
            f"Unsupported LLM provider: '{provider_name}'. "
            f"Supported: {', '.join(sorted(PROVIDER_BUILDERS.keys()))}"
        )

    _cached_model = builder(model_name)
    logger.info(f"LLM initialized: provider={provider_name}, model={model_name}")
    return _cached_model


def reset_model() -> None:
    """Clear the cached model (useful for tests or dynamic reconfiguration)."""
    global _cached_model
    _cached_model = None


# ── Model string parsing ────────────────────────────────────────────


def _parse_model_string(model_str: str) -> tuple[str, str]:
    """Parse 'provider/model-name' into (provider, model_name)."""
    if "/" in model_str:
        provider, model = model_str.split("/", 1)
        return provider.lower(), model
    return "openai", model_str


# ── Provider builders ────────────────────────────────────────────────
# Each builder takes a model_name and returns a Pydantic AI Model instance.


def _build_openai(model_name: str) -> Any:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    api_key = settings.litellm_api_key or os.environ.get("OPENAI_API_KEY") or ""
    return OpenAIChatModel(model_name=model_name, provider=OpenAIProvider(api_key=api_key))


def _build_anthropic(model_name: str) -> Any:
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
    return AnthropicModel(model_name=model_name, provider=AnthropicProvider(api_key=api_key))


def _build_ollama(model_name: str) -> Any:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    base_url = f"{settings.ollama_host}/v1"
    return OpenAIChatModel(
        model_name=model_name,
        provider=OpenAIProvider(base_url=base_url, api_key="ollama"),
    )


def _build_google(model_name: str) -> Any:
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google_gla import GoogleGLAProvider

    api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY") or ""
    return GoogleModel(model_name=model_name, provider=GoogleGLAProvider(api_key=api_key))


def _build_azure(model_name: str) -> Any:
    from openai import AsyncAzureOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.azure import AzureProvider

    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        api_key=settings.azure_api_key or os.environ.get("AZURE_OPENAI_API_KEY", ""),
        api_version=settings.azure_api_version,
    )
    return OpenAIChatModel(model_name=model_name, provider=AzureProvider(openai_client=client))


def _build_groq(model_name: str) -> Any:
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    api_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY") or ""
    return GroqModel(model_name=model_name, provider=GroqProvider(api_key=api_key))


def _build_deepseek(model_name: str) -> Any:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY") or ""
    return OpenAIChatModel(
        model_name=model_name,
        provider=OpenAIProvider(base_url="https://api.deepseek.com", api_key=api_key),
    )


# ── Registry ─────────────────────────────────────────────────────────

PROVIDER_BUILDERS: dict[str, Any] = {
    "openai": _build_openai,
    "anthropic": _build_anthropic,
    "ollama": _build_ollama,
    "google": _build_google,
    "gemini": _build_google,      # alias
    "azure": _build_azure,
    "groq": _build_groq,
    "deepseek": _build_deepseek,
}
