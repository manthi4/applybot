"""Provider-agnostic LLM client backed by litellm.

litellm exposes a single ``completion`` API across providers (OpenAI,
Anthropic, Google Gemini, ...). The provider is selected entirely by the model
string configured via env (see :mod:`applybot.llm.config`); this module
contains no vendor-specific code, so swapping providers is a config change,
not a code change.

Public surface: :class:`LLMClient` and the :func:`get_llm` lazy singleton.
"""

from functools import lru_cache
from typing import Literal, TypeVar

import litellm
from pydantic import BaseModel

from applybot.llm.config import settings

T = TypeVar("T", bound=BaseModel)

Tier = Literal["fast", "smart"]


def _messages(prompt: str, system: str) -> list[dict[str, str]]:
    """Build the chat message list, prepending a system message when given."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


class LLMClient:
    """Thin wrapper over litellm.

    Two call shapes:

    - :meth:`complete` -- plain text completion.
    - :meth:`structured_output` -- completion parsed into a Pydantic model via
      litellm's JSON-schema response format.

    Use :func:`get_llm` rather than instantiating directly.
    """

    def _model(self, tier: Tier) -> str:
        return settings.model_smart if tier == "smart" else settings.model_fast

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        tier: Tier = "fast",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Simple text completion -- returns the assistant's text response."""
        response = litellm.completion(
            model=self._model(tier),
            messages=_messages(prompt, system),
            max_tokens=max_tokens,
            temperature=temperature,
            num_retries=settings.max_retries,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned no text content")
        return str(content)

    def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        *,
        system: str = "",
        tier: Tier = "fast",
        max_tokens: int = 4096,
    ) -> T:
        """Return a response parsed into a Pydantic model.

        litellm passes ``output_type``'s JSON schema to the provider as a
        structured-output response format and returns JSON text, which we
        validate into the model.
        """
        response = litellm.completion(
            model=self._model(tier),
            messages=_messages(prompt, system),
            response_format=output_type,
            max_tokens=max_tokens,
            temperature=0.0,
            num_retries=settings.max_retries,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned no text content")
        return output_type.model_validate_json(content)

@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    """Return the shared :class:`LLMClient` instance, creating it on first call."""
    return LLMClient()
