"""Discovery service — HTTP client for the discovery Cloud Function.

The dashboard triggers the deployed ``applybot-discovery`` Cloud Function over HTTP, passing
an OIDC identity token so the function's invoker IAM authorizes the call (the
Cloud Run service account holds ``roles/cloudfunctions.invoker`` on the
function — see ``infra/cloud_functions.tf``).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel

from applybot.dashboard.config import settings

logger = logging.getLogger(__name__)

# Match the Cloud Function's timeout (infra/cloud_functions.tf: timeout_seconds = 300).
_REQUEST_TIMEOUT = 300.0


class DiscoveryResult(BaseModel):
    """Summary of a discovery run, mirrored from the Cloud Function response."""

    total_scraped: int
    after_dedup: int
    above_threshold: int
    new_jobs_saved: int
    top_matches: list[dict[str, Any]] = []


def _fetch_id_token(audience: str) -> str:
    """Fetch an OIDC identity token for ``audience`` using default credentials.

    On Cloud Run this uses the attached service account. Locally it uses
    ``gcloud auth application-default`` credentials.
    """
    import google.auth.transport.requests
    from google.oauth2 import id_token

    request = google.auth.transport.requests.Request()
    token: str | None = id_token.fetch_id_token(request, audience)  # type: ignore[no-untyped-call]
    if not token:
        raise RuntimeError(
            "Failed to fetch OIDC identity token for the discovery function"
        )
    return token


async def trigger_discovery() -> DiscoveryResult:
    """Trigger the discovery Cloud Function and return its result summary.

    Raises:
        RuntimeError: if ``DISCOVERY_FUNCTION_URL`` is not configured or no
            identity token could be obtained.
        httpx.HTTPStatusError: if the function returns a non-2xx response.
    """
    url = settings.discovery_function_url
    if not url:
        raise RuntimeError(
            "DISCOVERY_FUNCTION_URL is not set; cannot trigger discovery. "
            "Configure it to the deployed function URL or a local "
            "functions-framework instance."
        )

    token = _fetch_id_token(url)
    headers = {"Authorization": f"Bearer {token}"}

    logger.info("Triggering discovery Cloud Function at %s", url)
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        response = await client.post(url, headers=headers)
        response.raise_for_status()

    return DiscoveryResult.model_validate(response.json())
