"""Tests for the Firestore client management module (base.py)."""

from __future__ import annotations

from applybot.models import base


def test_get_db_returns_singleton():
    """get_db() must return the same Client instance across calls."""
    first = base.get_db()
    second = base.get_db()
    assert first is second


def test_init_db_initializes_client():
    """init_db() must initialize the client without raising."""
    base._client = None  # force re-init
    base.init_db()
    assert base._client is not None
