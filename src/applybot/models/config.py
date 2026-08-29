"""Firestore-backed application configuration documents.

The ``config`` collection holds singleton documents with runtime-mutable app
settings (e.g. ``config/llm`` for the default LLM model). This module is the
single place for app-config Firestore documents -- the models component owns
all Firestore CRUD, so other components read and write these settings through
these helpers instead of touching Firestore directly.
"""

from __future__ import annotations

from .base import get_db

_CONFIG_COLLECTION = "config"


def get_config_value(doc_id: str, field: str, default: str = "") -> str:
    """Read ``field`` from ``config/<doc_id>``.

    Returns ``default`` when the document or the field is absent, or when the
    stored value is blank.
    """
    doc = get_db().collection(_CONFIG_COLLECTION).document(doc_id).get()
    if not doc.exists:
        return default
    value = str((doc.to_dict() or {}).get(field) or "")
    return value if value else default


def set_config_value(doc_id: str, field: str, value: str) -> None:
    """Write ``value`` into ``field`` on ``config/<doc_id>``.

    Uses ``set(..., merge=True)`` so sibling fields on the document survive.
    """
    get_db().collection(_CONFIG_COLLECTION).document(doc_id).set(
        {field: value}, merge=True
    )
