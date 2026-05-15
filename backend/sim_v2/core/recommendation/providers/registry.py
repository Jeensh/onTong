"""Provider registry — ADR-012 의 plugin manifest 기반 provider lookup."""
from __future__ import annotations

from .base import LLMProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider


class ProviderRegistry:
    """Provider name → instance. Plugin manifest 의 default_provider 가 lookup key."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Provider {provider.name!r} already registered")
        self._providers[provider.name] = provider

    def get(self, name: str) -> LLMProvider:
        if name not in self._providers:
            raise KeyError(f"No provider registered for {name!r}")
        return self._providers[name]

    def has(self, name: str) -> bool:
        return name in self._providers

    def names(self) -> list[str]:
        return sorted(self._providers.keys())


_default_registry: ProviderRegistry | None = None


def get_default_registry() -> ProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ProviderRegistry()
        _default_registry.register(ClaudeProvider())
        _default_registry.register(OpenAIProvider())
        _default_registry.register(GeminiProvider())
    return _default_registry


def reset_default_registry() -> None:
    global _default_registry
    _default_registry = None


__all__ = ["ProviderRegistry", "get_default_registry", "reset_default_registry"]
