from abc import ABC, abstractmethod
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from applybot.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """Abstract base class for LLM provider backends.

    Concrete implementations: ``GeminiClient``, ``AnthropicClient``.
    Use ``get_llm()`` rather than instantiating directly —
    the provider is selected via ``settings.llm_provider``.
    """

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Simple text completion — returns the assistant's text response."""

    @abstractmethod
    def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
    ) -> T:
        """Return a response parsed into a Pydantic model."""

    def with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
    ) -> Any:
        """Send a message with tool definitions and return the raw response.

        Not supported by all providers — raises ``NotImplementedError`` by default.
        Override in subclasses that support tool use (e.g. ``AnthropicClient``).
        """
        raise NotImplementedError(
            f"with_tools() is not supported by {type(self).__name__}."
        )


class GeminiClient(LLMClient):
    """Gemini backend via the ``google-genai`` SDK (Vertex AI auth)."""

    def __init__(self) -> None:
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.vertex_region,
        )
        self._types = types

    def _model(self, tier: Literal["fast", "smart"]) -> str:
        return (
            settings.gemini_model_smart
            if tier == "smart"
            else settings.gemini_model_fast
        )

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        response = self._client.models.generate_content(
            model=self._model(tier),
            contents=prompt,
            config=self._types.GenerateContentConfig(
                system_instruction=system if system else None,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return str(response.text)

    def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
    ) -> T:
        response = self._client.models.generate_content(
            model=self._model(tier),
            contents=prompt,
            config=self._types.GenerateContentConfig(
                system_instruction=system if system else None,
                response_mime_type="application/json",
                response_schema=output_type,
                max_output_tokens=max_tokens,
            ),
        )
        return output_type.model_validate_json(str(response.text))


class AnthropicClient(LLMClient):
    """Anthropic Claude backend via the Vertex AI SDK (ADC auth)."""

    def __init__(self) -> None:
        from anthropic import AnthropicVertex

        self._client = AnthropicVertex(
            project_id=settings.gcp_project_id,
            region=settings.vertex_region,
            max_retries=settings.anthropic_max_retries,
        )

    def _model(self, tier: Literal["fast", "smart"]) -> str:
        return (
            settings.anthropic_model_smart
            if tier == "smart"
            else settings.anthropic_model_fast
        )

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model(tier),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response: Any = self._client.messages.create(**kwargs)
        return "\n".join(b.text for b in response.content if b.type == "text")

    def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
    ) -> T:
        tool_name = "structured_output"
        kwargs: dict[str, Any] = {
            "model": self._model(tier),
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [
                {
                    "name": tool_name,
                    "description": f"Return a structured {output_type.__name__} object.",
                    "strict": True,
                    "input_schema": output_type.model_json_schema(),
                }
            ],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        if system:
            kwargs["system"] = system
        response: Any = self._client.messages.create(**kwargs)

        tool_use_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_use_block is None:
            raise ValueError(
                f"structured_output: expected a tool_use block in response, got: {response.content}"
            )
        return output_type.model_validate(tool_use_block.input)

    def with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        *,
        system: str = "",
        tier: Literal["fast", "smart"] = "fast",
        max_tokens: int = 4096,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._model(tier),
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": tools,
        }
        if system:
            kwargs["system"] = system
        return self._client.messages.create(**kwargs)


def _create_client() -> LLMClient:
    if settings.llm_provider == "gemini":
        return GeminiClient()
    return AnthropicClient()


_instance: LLMClient | None = None


def get_llm() -> LLMClient:
    """Return the shared LLMClient instance, creating it on first call."""
    global _instance
    if _instance is None:
        _instance = _create_client()
    return _instance
