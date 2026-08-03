"""Tests for the Firestore error-page handlers in ``dashboard.frontend``.

When Firestore credentials are missing/invalid or the service is unreachable,
the dashboard must render a helpful HTML page (HTTP 503) instead of a raw 500
traceback. These tests force a real google exception out of the overview route
and assert the helpful page is rendered.
"""

from __future__ import annotations

import google.api_core.exceptions as gace
import google.auth.exceptions as gae
import pytest
from starlette.testclient import TestClient

from applybot.dashboard import frontend
from applybot.models import job as job_mod


@pytest.fixture
def client(monkeypatch):
    """A TestClient with auth bypassed so we can hit dashboard routes directly.

    Existing dashboard tests don't drive the FastHTML app over HTTP, so there is
    no established auth-bypass to reuse. The simplest deterministic approach is
    to short-circuit ``_AuthMiddleware.dispatch`` (the only thing standing
    between the TestClient and the routes) — exactly what the middleware exists
    to gate in production.
    """

    async def _passthrough(self, request, call_next):  # noqa: ARG001
        return await call_next(request)

    monkeypatch.setattr(frontend._AuthMiddleware, "dispatch", _passthrough)
    return TestClient(frontend.app)


def _force_count_by_status_to_raise(monkeypatch, exc: Exception) -> None:
    """Make ``Job.count_by_status`` raise ``exc`` (called by the overview route)."""

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise exc

    monkeypatch.setattr(job_mod.Job, "count_by_status", _raise)


def test_credentials_error_renders_helpful_page(client, monkeypatch):
    """A DefaultCredentialsError surfaces as a 503 HTML page with guidance."""
    _force_count_by_status_to_raise(
        monkeypatch, gae.DefaultCredentialsError("no creds")
    )

    resp = client.get("/")

    assert resp.status_code == 503
    assert "GOOGLE_APPLICATION_CREDENTIALS" in resp.text
    assert "Dashboard Unavailable" in resp.text


def test_connection_error_renders_helpful_page(client, monkeypatch):
    """A ServiceUnavailable surfaces as a 503 HTML page with guidance."""
    _force_count_by_status_to_raise(
        monkeypatch, gace.ServiceUnavailable("firestore down")
    )

    resp = client.get("/")

    assert resp.status_code == 503
    assert "could not reach Firestore" in resp.text
    assert "Dashboard Unavailable" in resp.text


def test_connection_error_renders_helpful_page_for_plain_connectionerror(
    client, monkeypatch
):
    """A bare ConnectionError also maps to the connection-failure page."""
    _force_count_by_status_to_raise(monkeypatch, ConnectionError("network gone"))

    resp = client.get("/")

    assert resp.status_code == 503
    assert "could not reach Firestore" in resp.text
