import logging
from typing import Any, TypeVar, cast

import anthropic
from anthropic import AnthropicVertex
from pydantic import BaseModel

from applybot.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Thin wrapper around the Anthropic SDK with tool-use and structured output."""

    def __init__(self) -> None:
        self._client = AnthropicVertex(
            project_id=settings.gcp_project_id,
            region=settings.vertex_region,
            max_retries=settings.vertex_max_retries,
        )

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Simple text completion — returns the assistant's text response."""
        model = model or settings.vertex_model_fast
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return self._extract_text(response)

    def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> T:
        """Get a response parsed into a Pydantic model via forced tool use.

        Forces Claude to call a tool whose input_schema matches the Pydantic
        model, guaranteeing schema-valid JSON without any prompt hacks or
        markdown-fence stripping.
        """
        model = model or settings.vertex_model_fast
        tool_name = "structured_output"
        tools: list[dict[str, Any]] = [
            {
                "name": tool_name,
                "description": f"Return a structured {output_type.__name__} object.",
                "strict": True,
                "input_schema": output_type.model_json_schema(),
            }
        ]
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": tools,
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        if system:
            kwargs["system"] = system
        response = cast(anthropic.types.Message, self._client.messages.create(**kwargs))

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
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> anthropic.types.Message:
        """Send a message with tool definitions, returning the full Message
        so callers can inspect tool_use blocks and continue the conversation."""
        model = model or settings.vertex_model_fast
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "tools": tools,
        }
        if system:
            kwargs["system"] = system
        return cast(anthropic.types.Message, self._client.messages.create(**kwargs))

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)


# Module-level singleton for convenience
llm = LLMClient()
