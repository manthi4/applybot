import json
import logging
from typing import Any, TypeVar, cast

import anthropic
from pydantic import BaseModel

from applybot.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Thin wrapper around the Anthropic SDK with tool-use and structured output."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            max_retries=settings.anthropic_max_retries,
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
        model = model or settings.anthropic_model_fast
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
        """Get a response parsed into a Pydantic model via JSON output."""
        schema_json = json.dumps(output_type.model_json_schema(), indent=2)
        full_system = (
            f"{system}\n\n"
            f"Respond ONLY with valid JSON matching this schema:\n{schema_json}"
        ).strip()

        raw = self.complete(
            prompt, system=full_system, model=model, max_tokens=max_tokens
        )

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        return output_type.model_validate_json(cleaned)

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
        model = model or settings.anthropic_model_fast
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
