"""Tests for the application-preparer HTTP service
(``dashboard/services/application.py``).

The service must NOT import the application pipeline; it only speaks HTTP to
the Cloud Function. These tests mock the OIDC token fetch and the HTTP
transport so nothing network-bound runs.
"""

from __future__ import annotations

import httpx
import pytest

from applybot.dashboard.services import application as svc
from applybot.dashboard.services.application import (
    ApplicationPreparationResult,
    trigger_application_preparation,
)

FAKE_TOKEN = "fake-id-token"


def _patch_http(monkeypatch, handler):
    """Replace httpx.AsyncClient in the service with one using a MockTransport."""
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(svc.httpx, "AsyncClient", factory)


def _configure(monkeypatch, url="https://application-preparer.example.run.app"):
    monkeypatch.setattr(svc.settings, "application_preparer_function_url", url)
    monkeypatch.setattr(svc, "_fetch_id_token", lambda audience: FAKE_TOKEN)
    return url


async def test_trigger_application_preparation_posts_bearer_token_and_parses(
    monkeypatch,
):
    url = _configure(monkeypatch)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        captured["method"] = request.method
        return httpx.Response(
            200,
            json={
                "applications_built": 3,
                "profile_gaps_flagged": 5,
            },
        )

    _patch_http(monkeypatch, handler)

    result = await trigger_application_preparation()

    assert isinstance(result, ApplicationPreparationResult)
    assert result.applications_built == 3
    assert result.profile_gaps_flagged == 5
    # The OIDC identity token must be sent as a bearer token to authorize the call.
    assert captured["auth"] == f"Bearer {FAKE_TOKEN}"
    assert captured["url"] == url
    assert captured["method"] == "POST"


async def test_trigger_application_preparation_defaults_gaps_to_zero(monkeypatch):
    """profile_gaps_flagged is optional in the response (defaults to 0)."""
    _configure(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"applications_built": 1})

    _patch_http(monkeypatch, handler)

    result = await trigger_application_preparation()

    assert result.applications_built == 1
    assert result.profile_gaps_flagged == 0


async def test_trigger_application_preparation_raises_on_non_2xx(monkeypatch):
    _configure(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Preparation failed"})

    _patch_http(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await trigger_application_preparation()


async def test_trigger_application_preparation_raises_when_url_unset(monkeypatch):
    monkeypatch.setattr(svc.settings, "application_preparer_function_url", "")

    with pytest.raises(RuntimeError, match="APPLICATION_PREPARER_FUNCTION_URL"):
        await trigger_application_preparation()


async def test_fetch_id_token_result_is_used_as_bearer(monkeypatch):
    """The token returned by _fetch_id_token is what lands in the header."""
    _configure(monkeypatch)
    monkeypatch.setattr(svc, "_fetch_id_token", lambda audience: "custom-token")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={"applications_built": 0, "profile_gaps_flagged": 0},
        )

    _patch_http(monkeypatch, handler)

    await trigger_application_preparation()
    assert captured["auth"] == "Bearer custom-token"
