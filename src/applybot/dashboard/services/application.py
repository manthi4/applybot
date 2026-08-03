"""Application preparer service — HTTP client for the application-preparer
Cloud Function.

The dashboard triggers the deployed ``applybot-application-preparer`` Cloud
Function over HTTP, passing an OIDC identity token so the function's invoker
IAM authorizes the call (the Cloud Run service account holds
``roles/cloudfunctions.invoker`` on the function).

Local development: point ``APPLICATION_PREPARER_FUNCTION_URL`` at a locally
running ``functions-framework`` instance (or the deployed function). An unset
URL is a hard error — there is no in-process fallback, by design.

This mirrors ``services/discovery.py``; the dashboard must not import the
``application`` pipeline directly.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from applybot.dashboard.config import settings

logger = logging.getLogger(__name__)

# The preparer makes several LLM calls per approved job; match a generous
# Cloud Function timeout (cf. discovery's 300s).
_REQUEST_TIMEOUT = 300.0


class ApplicationPreparationResult(BaseModel):
    """Summary of an application-preparation run, mirrored from the Cloud
    Function response."""

    applications_built: int
    profile_gaps_flagged: int = 0


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
            "Failed to fetch OIDC identity token for the application-preparer function"
        )
    return token


async def trigger_application_preparation() -> ApplicationPreparationResult:
    """Trigger the application-preparer Cloud Function and return its summary.

    Raises:
        RuntimeError: if ``APPLICATION_PREPARER_FUNCTION_URL`` is not
            configured or no identity token could be obtained.
        httpx.HTTPStatusError: if the function returns a non-2xx response.
    """
    url = settings.application_preparer_function_url
    if not url:
        raise RuntimeError(
            "APPLICATION_PREPARER_FUNCTION_URL is not set; cannot build "
            "applications. Configure it to the deployed function URL or a "
            "local functions-framework instance."
        )

    token = _fetch_id_token(url)
    headers = {"Authorization": f"Bearer {token}"}

    logger.info("Triggering application-preparer Cloud Function at %s", url)
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        response = await client.post(url, headers=headers)
        response.raise_for_status()

    return ApplicationPreparationResult.model_validate(response.json())
