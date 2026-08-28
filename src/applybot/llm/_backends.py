"""GCP backing stores for the LLM client.

Secret Manager holds API keys; Firestore holds the default model. These are
pure I/O shims over the GCP SDKs -- all caching and policy lives in
:mod:`applybot.llm.client`. Outside GCP (no ``GCP_PROJECT_ID``) the client does
not engage these helpers, so local dev/tests run env-only.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from .providers import LLMProvider

logger = logging.getLogger(__name__)


def project_id() -> str | None:
    """GCP project id, or ``None`` when running outside GCP (local dev/tests)."""
    pid = os.environ.get("GCP_PROJECT_ID")
    return pid or None


# ---------------------------------------------------------------------------
# Secret Manager (API keys)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def secret_client() -> Any:
    """Lazily build the Secret Manager client (cached for the process)."""
    from google.cloud import secretmanager

    return secretmanager.SecretManagerServiceClient()


def _secret_name(provider: LLMProvider) -> str:
    return f"projects/{project_id()}/secrets/{provider.secret_id}"


def ensure_secret_exists(provider: LLMProvider) -> None:
    """Create the secret shell if it does not yet exist (idempotent)."""
    from google.api_core import exceptions

    client = secret_client()
    try:
        client.get_secret(request={"name": _secret_name(provider)})
    except exceptions.NotFound:
        client.create_secret(
            request={
                "parent": f"projects/{project_id()}",
                "secret_id": provider.secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )


def read_secret(provider: LLMProvider) -> str:
    """Read the latest secret version, returning ``""`` if absent/empty."""
    from google.api_core import exceptions

    client = secret_client()
    try:
        resp = client.access_secret_version(
            request={"name": f"{_secret_name(provider)}/versions/latest"}
        )
        return str(resp.payload.data.decode("utf-8"))
    except exceptions.NotFound:
        return ""
    except Exception:  # noqa: BLE001 - degrade to env-only on any SM failure
        logger.warning(
            "Secret Manager read failed for %s; falling back to env", provider
        )
        return os.environ.get(provider.env_var, "")


def write_secret(provider: LLMProvider, value: str) -> None:
    """Add a new secret version with ``value`` (creates the secret if needed)."""
    ensure_secret_exists(provider)
    client = secret_client()
    client.add_secret_version(
        request={
            "parent": _secret_name(provider),
            "payload": {"data": value.encode("utf-8")},
        }
    )


# ---------------------------------------------------------------------------
# Firestore (default model)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def firestore() -> Any:
    """Lazily build the Firestore client (cached for the process)."""
    from google.cloud.firestore_v1 import Client

    kwargs: dict[str, Any] = {}
    pid = project_id()
    if pid:
        kwargs["project"] = pid
    return Client(**kwargs)
