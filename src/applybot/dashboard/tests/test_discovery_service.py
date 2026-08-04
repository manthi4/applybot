"""Tests for the discovery HTTP service (`dashboard/services/discovery.py`).

The service must NOT import the discovery pipeline; it only speaks HTTP to the
Cloud Function. These tests mock the OIDC token fetch and the HTTP transport
so nothing network-bound runs.
"""

from __future__ import annotations

import httpx
import pytest

from applybot.dashboard.services import discovery as svc
from applybot.dashboard.services.discovery import DiscoveryResult, trigger_discovery

FAKE_TOKEN = "fake-id-token"


def _patch_http(monkeypatch, handler):
    """Replace httpx.AsyncClient in the service with one using a MockTransport."""
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(svc.httpx, "AsyncClient", factory)


def _configure(monkeypatch, url="https://discovery.example.run.app"):
    monkeypatch.setattr(svc.settings, "discovery_function_url", url)
    monkeypatch.setattr(svc, "_fetch_id_token", lambda audience: FAKE_TOKEN)
    return url


async def test_trigger_discovery_posts_bearer_token_and_parses(monkeypatch):
    url = _configure(monkeypatch)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        captured["method"] = request.method
        return httpx.Response(
            200,
            json={
                "total_scraped": 12,
                "after_dedup": 8,
                "above_threshold": 5,
                "new_jobs_saved": 3,
                "top_matches": [{"title": "Robotics Eng"}],
            },
        )

    _patch_http(monkeypatch, handler)

    result = await trigger_discovery()

    assert isinstance(result, DiscoveryResult)
    assert result.total_scraped == 12
    assert result.after_dedup == 8
    assert result.above_threshold == 5
    assert result.new_jobs_saved == 3
    assert result.top_matches == [{"title": "Robotics Eng"}]
    # The OIDC identity token must be sent as a bearer token to authorize the call.
    assert captured["auth"] == f"Bearer {FAKE_TOKEN}"
    assert captured["url"] == url
    assert captured["method"] == "POST"


async def test_trigger_discovery_raises_on_non_2xx(monkeypatch):
    _configure(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Discovery run failed"})

    _patch_http(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await trigger_discovery()


async def test_trigger_discovery_raises_when_url_unset(monkeypatch):
    monkeypatch.setattr(svc.settings, "discovery_function_url", "")

    with pytest.raises(RuntimeError, match="DISCOVERY_FUNCTION_URL"):
        await trigger_discovery()


async def test_fetch_id_token_result_is_used_as_bearer(monkeypatch):
    """The token returned by _fetch_id_token is what lands in the header."""
    _configure(monkeypatch)
    monkeypatch.setattr(svc, "_fetch_id_token", lambda audience: "custom-token")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "total_scraped": 0,
                "after_dedup": 0,
                "above_threshold": 0,
                "new_jobs_saved": 0,
                "top_matches": [],
            },
        )

    _patch_http(monkeypatch, handler)

    await trigger_discovery()
    assert captured["auth"] == "Bearer custom-token"
