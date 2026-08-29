"""Provider-agnostic LLM client backed by litellm.

litellm exposes a single ``completion`` API across providers (OpenAI,
Anthropic, Google Gemini, ...). The provider is selected by the model string
prefix (litellm convention); provider definitions live in
:mod:`applybot.llm.providers`, so swapping providers is a config change, not a
code change.

Provider API keys and the default model are **mutable at runtime** -- callers
may update or delete providers and change the default model while the app is
deployed. Keys live in GCP Secret Manager and are delivered to every runtime
as volume-mounted files (``<LLM_SECRETS_DIR>/<secret_id>/latest``, refreshed
by the platform when a new version is added), so this module simply re-reads
the file on each access -- there is no key cache. Writes go through the I/O
shims in :mod:`applybot.llm._backends`. The default model lives in a Firestore
``config/llm`` document accessed via :mod:`applybot.models.config` (the models
component owns all Firestore CRUD) behind a short-TTL cache.

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
from pathlib import Path
from typing import Any, overload

import litellm
from pydantic import BaseModel

from applybot.models.config import get_config_value, set_config_value

from . import _backends
from .providers import (
    LLMProvider as LLMProvider,
)
from .providers import (
    provider_for_model as provider_for_model,
)

logger = logging.getLogger(__name__)


# How long the cached default model is trusted before re-fetching Firestore.
# Keeps per-completion latency low while still propagating updates across
# services quickly.
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
# TTL cache: in-process, short-lived, write-through
# ---------------------------------------------------------------------------


class _TTLCache[K, V]:
    """In-process TTL cache with write-through updates.

    functools.lru_cache cannot replace this: it has no TTL (cross-service
    updates would never propagate to already-warm processes) and no
    write-through invalidation.
    """

    def __init__(self, ttl: float = _CACHE_TTL_SECONDS) -> None:
        """Build a cache whose entries expire after ``ttl`` seconds."""
        self._ttl = ttl
        self._entries: dict[K, tuple[V, float]] = {}

    def get(self, key: K) -> V | None:
        """Return the cached value, or ``None`` on a miss or expired entry."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, stored_at = entry
        if time.monotonic() - stored_at >= self._ttl:
            return None
        return value

    def set(self, key: K, value: V) -> None:
        """Store ``value`` under ``key`` with a fresh TTL (write-through)."""
        self._entries[key] = (value, time.monotonic())

    def pop(self, key: K) -> None:
        """Drop ``key`` if present (no error when absent); used on delete."""
        self._entries.pop(key, None)

    def clear(self) -> None:
        """Drop every entry (test isolation)."""
        self._entries.clear()


# ---------------------------------------------------------------------------
# Key lookup: in-process override → mounted secret file → env var
# ---------------------------------------------------------------------------

# Directory where provider key secrets are volume-mounted (one subdirectory
# per secret, holding version files including a `latest` entry). Overridable
# so tests can point it at a local directory.
_SECRETS_DIR_ENV = "LLM_SECRETS_DIR"
_DEFAULT_SECRETS_DIR = "/etc/secrets"

# Keys set via update_provider()/delete_provider() in this process. They take
# effect immediately, without waiting for the platform to refresh the volume
# mount (which typically takes minutes).
_key_overrides: dict[LLMProvider, str] = {}


def _mounted_key(provider: LLMProvider) -> str:
    """Read the provider's key from the volume-mounted secret, or ``""``.

    GCP mounts each provider secret as a directory of version files with a
    ``latest`` entry and refreshes it when a new version is added, so this
    read always returns the current key. Whitespace is stripped because
    versions seeded outside Terraform can carry a trailing newline.
    """
    path = (
        Path(os.environ.get(_SECRETS_DIR_ENV, _DEFAULT_SECRETS_DIR))
        / provider.secret_id
        / "latest"
    )
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError:
        logger.warning("Failed to read mounted secret %s", path)
        return ""


def _get_provider_key(provider: LLMProvider) -> str:
    """Return the API key for ``provider``.

    Order: in-process override (set by update/delete in this process), the
    volume-mounted secret file, then the provider env var (local dev/tests,
    where no mount exists).
    """
    override = _key_overrides.get(provider)
    if override is not None:
        return override

    mounted = _mounted_key(provider)
    if mounted:
        return mounted

    return os.environ.get(provider.env_var, "")


def get_configured_providers() -> list[LLMProvider]:
    """Return the providers that currently have a non-blank API key."""
    return [p for p in LLMProvider if _get_provider_key(p)]


def update_provider(provider: LLMProvider | str, api_key: str) -> None:
    """Set ``provider``'s API key.

    Adds a new version in GCP Secret Manager -- other services pick it up when
    the platform refreshes their volume mount -- and records an in-process
    override so this process uses the new key immediately.
    """
    if not isinstance(provider, LLMProvider):
        provider = LLMProvider(provider)
    _key_overrides[provider] = api_key
    if _backends.project_id():
        try:
            _backends.write_secret(provider, api_key)
        except Exception:  # noqa: BLE001 - override is set; SM failure is non-fatal
            logger.exception("Failed to write %s key to Secret Manager", provider)


def delete_provider(provider: LLMProvider | str) -> None:
    """Delete ``provider``'s key: blank secret version + blank in-process override."""
    if not isinstance(provider, LLMProvider):
        provider = LLMProvider(provider)
    _key_overrides[provider] = ""
    if _backends.project_id():
        try:
            _backends.write_secret(provider, "")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to clear %s key in Secret Manager", provider)


# ---------------------------------------------------------------------------
# Default model store: Firestore ``config/llm`` doc, TTL cached
# ---------------------------------------------------------------------------

_MODEL_CACHE_KEY = "default_model"
_model_cache = _TTLCache[str, str]()


def get_default_model() -> str:
    """Return the default model.

    Order: TTL-cached value, then Firestore ``config/llm.default_model`` (via
    :mod:`applybot.models.config`), then the ``LLM_MODEL_DEFAULT`` env var.
    """
    cached = _model_cache.get(_MODEL_CACHE_KEY)
    if cached is not None:
        return cached

    model = ""
    if _backends.project_id():
        try:
            model = get_config_value(_DEFAULT_MODEL_DOC, _DEFAULT_MODEL_FIELD)
        except Exception:  # noqa: BLE001 - degrade to env on Firestore failure
            logger.warning(
                "Firestore read of default model failed; falling back to env"
            )

    if not model:
        model = os.environ.get("LLM_MODEL_DEFAULT", "")

    _model_cache.set(_MODEL_CACHE_KEY, model)
    return model


def set_default_model(model: str) -> None:
    """Set the default model: env var (immediate) + Firestore (cross-service)."""
    os.environ["LLM_MODEL_DEFAULT"] = model
    _model_cache.set(_MODEL_CACHE_KEY, model)
    if _backends.project_id():
        try:
            set_config_value(_DEFAULT_MODEL_DOC, _DEFAULT_MODEL_FIELD, model)
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
