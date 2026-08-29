"""Tests for the Firestore-backed app-config helpers (config.py)."""

from __future__ import annotations

from applybot.models.config import get_config_value, set_config_value


class TestGetConfigValue:
    def test_returns_default_when_doc_absent(self):
        assert get_config_value("llm", "default_model") == ""
        assert get_config_value("llm", "default_model", default="gpt-4o") == "gpt-4o"

    def test_returns_default_when_field_blank(self):
        set_config_value("llm", "default_model", "")
        assert get_config_value("llm", "default_model", default="gpt-4o") == "gpt-4o"


class TestSetConfigValue:
    def test_set_then_get_roundtrip(self):
        set_config_value("llm", "default_model", "claude-3-5-sonnet-20241022")
        assert get_config_value("llm", "default_model") == "claude-3-5-sonnet-20241022"

    def test_merge_preserves_sibling_field(self):
        set_config_value("llm", "default_model", "gpt-4o")
        set_config_value("llm", "max_tokens", "8192")
        assert get_config_value("llm", "default_model") == "gpt-4o"
        assert get_config_value("llm", "max_tokens") == "8192"
