"""Firestore client management — lazy singleton."""

from __future__ import annotations

from google.cloud.firestore_v1 import Client

from applybot.config import settings

_client: Client | None = None


def get_db() -> Client:
    """Return the Firestore client singleton (lazy-initialized)."""
    global _client
    if _client is None:
        kwargs = {}
        if settings.gcp_project_id:
            kwargs["project"] = settings.gcp_project_id
        _client = Client(**kwargs)
    return _client


def init_db() -> None:
    """Verify Firestore connection. No schema needed (schema-less)."""
    get_db()
