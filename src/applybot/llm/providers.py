"""LLM provider definitions.

A provider is selected by the model-string prefix (litellm convention). Each
provider knows its API-key env var, its GCP Secret Manager secret id, and the
prefixes that route a model string to it. This module is a leaf: it depends on
no other applybot code and carries no runtime-mutable state, so adding a new
provider is a one-place edit here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class LLMProvider(StrEnum):
    """LLM providers supported by this project.

    The value is the litellm model-string prefix that selects the provider.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"

    @property
    def env_var(self) -> str:
        """Environment variable holding this provider's API key."""
        return _PROVIDER_META[self]["env_var"]

    @property
    def secret_id(self) -> str:
        """GCP Secret Manager secret id holding this provider's API key."""
        return _PROVIDER_META[self]["secret_id"]

    @property
    def prefixes(self) -> tuple[str, ...]:
        """Model-string prefixes (litellm convention) that select this provider."""
        return _PROVIDER_META[self]["prefixes"]


class _ProviderInfo(TypedDict):
    env_var: str
    secret_id: str
    prefixes: tuple[str, ...]


_PROVIDER_META: dict[LLMProvider, _ProviderInfo] = {
    LLMProvider.OPENAI: {
        "env_var": "OPENAI_API_KEY",
        "secret_id": "openai-api-key",
        "prefixes": ("gpt-", "o1", "o3", "o4"),
    },
    LLMProvider.ANTHROPIC: {
        "env_var": "ANTHROPIC_API_KEY",
        "secret_id": "anthropic-api-key",
        "prefixes": ("claude-",),
    },
    LLMProvider.GEMINI: {
        "env_var": "GEMINI_API_KEY",
        "secret_id": "gemini-api-key",
        "prefixes": ("gemini/", "gemini-"),
    },
}


def provider_for_model(model: str) -> LLMProvider:
    """Derive the provider from the model string prefix (litellm convention)."""
    lowered = model.lower()
    for provider in LLMProvider:
        if lowered.startswith(provider.prefixes):
            return provider
    raise ValueError(
        f"Could not infer LLM provider from model {model!r}; pass `provider` explicitly."
    )
