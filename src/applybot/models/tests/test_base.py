"""Tests for the Firestore client management module (base.py)."""

from __future__ import annotations

from applybot.models import base


def test_get_db_returns_singleton():
    """get_db() must return the same Client instance across calls."""
    base.get_db.cache_clear()  # isolate from any previously-cached client
    first = base.get_db()
    second = base.get_db()
    assert first is second


def test_init_db_initializes_client():
    """init_db() must initialize the cached client without raising."""
    base.get_db.cache_clear()  # force re-init of the lru_cache singleton
    base.init_db()
    assert base.get_db() is not None
