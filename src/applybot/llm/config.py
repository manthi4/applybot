"""LLM configuration, sourced from environment variables.

litellm routes to the correct provider based on the model string prefix
(``gpt-4o`` -> OpenAI, ``claude-3-5-sonnet`` -> Anthropic,
``gemini/gemini-2.0-flash`` -> Google, ...). Each provider's API key is read
from its standard environment variable (``OPENAI_API_KEY``,
``ANTHROPIC_API_KEY``, ``GEMINI_API_KEY``, ...) by litellm itself -- no
vendor-specific auth code lives anywhere in this package.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM settings. All fields use the ``LLM_`` env prefix."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # litellm model strings. The prefix selects the provider, so swapping
    # providers is purely a config change (no code edit required).
    model_fast: str = "gpt-4o-mini"
    model_smart: str = "gpt-4o"

    # Number of times litellm retries transient provider failures.
    max_retries: int = 3


settings = LLMSettings()
