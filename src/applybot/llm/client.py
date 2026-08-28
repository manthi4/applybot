"""Provider-agnostic LLM client backed by litellm.

litellm exposes a single ``completion`` API across providers (OpenAI,
Anthropic, Google Gemini, ...). The provider is selected by the model string
prefix (litellm convention); provider definitions live in
:mod:`applybot.llm.providers`, so swapping providers is a config change, not a
code change.

Provider API keys and the default model are **mutable at runtime** -- callers
may update or delete providers and change the default model while the app is
deployed. Keys live in GCP Secret Manager; the default model lives in a
Firestore ``config/llm`` document. The GCP I/O lives in
:mod:`applybot.llm._backends`; this module owns the short-TTL in-process caches
so every service importing it picks up changes within seconds without a
redeploy.

There is deliberately no ``config.py`` / settings object: every value is read
fresh from the environment or the backing store on each access, because these
values change while the app is running.

Public surface: :func:`complete`, :func:`get_configured_providers`,
:func:`update_provider`, :func:`delete_provider`, :func:`get_default_model`,
:func:`set_default_model`, and the :class:`LLMProvider` enum.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, overload

import litellm
from pydantic import BaseModel

from . import _backends
from .providers import (
    LLMProvider as LLMProvider,
)
from .providers import (
    provider_for_model as provider_for_model,
)

logger = logging.getLogger(__name__)


# How long a cached value (key / model) is trusted before re-fetching the
# backing store. Keeps per-completion latency low while still propagating
# updates across services within seconds.
_CACHE_TTL_SECONDS = 30.0

_DEFAULT_MODEL_DOC = "llm"
_DEFAULT_MODEL_FIELD = "default_model"


def _max_retries() -> int:
    """Litellm retry count for transient provider failures."""
    try:
        return int(os.environ.get("LLM_MAX_RETRIES", "3"))
    except ValueError:
        return 3


# ---------------------------------------------------------------------------
# Key store: env var (in-process) + Secret Manager (cross-service), TTL cached
# ---------------------------------------------------------------------------

_key_cache: dict[LLMProvider, tuple[str, float]] = {}


def _cache_valid(ts: float) -> bool:
    return (time.monotonic() - ts) < _CACHE_TTL_SECONDS


def _get_provider_key(provider: LLMProvider) -> str:
    """Return the API key for ``provider``.

    Serves from the TTL cache, else from the env var, else from Secret Manager
    (which populates both the cache and the env var so litellm can also find it).
    """
    cached = _key_cache.get(provider)
    if cached and _cache_valid(cached[1]):
        return cached[0]

    key = os.environ.get(provider.env_var, "")
    if not key and _backends.project_id():
        key = _backends.read_secret(provider)
        if key:
            os.environ[provider.env_var] = key

    _key_cache[provider] = (key, time.monotonic())
    return key


def get_configured_providers() -> list[LLMProvider]:
    """Return the providers that currently have a non-blank API key."""
    return [p for p in LLMProvider if _get_provider_key(p)]


def update_provider(provider: LLMProvider | str, api_key: str) -> None:
    """Set ``provider``'s API key.

    Writes the key to the process env var (immediate effect locally) and to
    GCP Secret Manager so other services pick it up within the cache TTL.
    """
    if not isinstance(provider, LLMProvider):
        provider = LLMProvider(provider)
    os.environ[provider.env_var] = api_key
    _key_cache[provider] = (api_key, time.monotonic())
    if _backends.project_id():
        try:
            _backends.write_secret(provider, api_key)
        except Exception:  # noqa: BLE001 - env is set; SM failure is non-fatal
            logger.exception("Failed to write %s key to Secret Manager", provider)


def delete_provider(provider: LLMProvider | str) -> None:
    """Delete ``provider``'s key: clear the env var and set the secret to blank."""
    if not isinstance(provider, LLMProvider):
        provider = LLMProvider(provider)
    os.environ.pop(provider.env_var, None)
    _key_cache.pop(provider, None)
    if _backends.project_id():
        try:
            _backends.write_secret(provider, "")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to clear %s key in Secret Manager", provider)


# ---------------------------------------------------------------------------
# Default model store: Firestore ``config/llm`` doc, TTL cached
# ---------------------------------------------------------------------------

_model_cache: tuple[str, float] | None = None


def get_default_model() -> str:
    """Return the default model.

    Order: TTL-cached value, then Firestore ``config/llm.default_model``, then
    the ``LLM_MODEL_DEFAULT`` env var.
    """
    global _model_cache
    if _model_cache and _cache_valid(_model_cache[1]):
        return _model_cache[0]

    model = ""
    if _backends.project_id():
        try:
            doc = (
                _backends.firestore()
                .collection("config")
                .document(_DEFAULT_MODEL_DOC)
                .get()
            )
            if doc.exists:
                model = (doc.to_dict() or {}).get(_DEFAULT_MODEL_FIELD, "") or ""
        except Exception:  # noqa: BLE001 - degrade to env on Firestore failure
            logger.warning(
                "Firestore read of default model failed; falling back to env"
            )

    if not model:
        model = os.environ.get("LLM_MODEL_DEFAULT", "")

    _model_cache = (model, time.monotonic())
    return model


def set_default_model(model: str) -> None:
    """Set the default model: env var (immediate) + Firestore (cross-service)."""
    global _model_cache
    os.environ["LLM_MODEL_DEFAULT"] = model
    _model_cache = (model, time.monotonic())
    if _backends.project_id():
        try:
            _backends.firestore().collection("config").document(_DEFAULT_MODEL_DOC).set(
                {_DEFAULT_MODEL_FIELD: model}
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist default model to Firestore")


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


def _messages(prompt: str, system: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


@overload
def complete(
    provider: LLMProvider | str | None,
    model: str | None,
    prompt: str,
    *,
    system: str = ...,
    max_tokens: int = ...,
    temperature: float = ...,
    output_type: None = ...,
) -> str: ...


@overload
def complete[T: BaseModel](
    provider: LLMProvider | str | None,
    model: str | None,
    prompt: str,
    *,
    system: str = ...,
    max_tokens: int = ...,
    temperature: float = ...,
    output_type: type[T],
) -> T: ...


def complete[T: BaseModel](
    provider: LLMProvider | str | None,
    model: str | None,
    prompt: str,
    *,
    system: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.0,
    output_type: type[T] | None = None,
) -> str | T:
    """Run an LLM completion.

    ``model`` defaults to :func:`get_default_model`. ``provider`` defaults to
    the provider inferred from the model-string prefix; supply it explicitly to
    override. If ``output_type`` is given, the response is parsed into that
    Pydantic model via litellm's structured-output response format; otherwise
    the assistant's text is returned.
    """
    resolved_model = model or get_default_model()
    if not resolved_model:
        raise ValueError(
            "No model specified and no default model is configured "
            "(set one via set_default_model() or LLM_MODEL_DEFAULT)."
        )

    if provider is None:
        resolved_provider = provider_for_model(resolved_model)
    else:
        resolved_provider = (
            provider if isinstance(provider, LLMProvider) else LLMProvider(provider)
        )

    api_key = _get_provider_key(resolved_provider)
    if not api_key:
        raise ValueError(
            f"No API key configured for provider {resolved_provider.value!r} "
            f"(set one via update_provider())."
        )

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "messages": _messages(prompt, system),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "num_retries": _max_retries(),
        "api_key": api_key,
    }
    if output_type is not None:
        kwargs["response_format"] = output_type

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned no text content")
    if output_type is not None:
        return output_type.model_validate_json(content)
    return str(content)
