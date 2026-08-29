"""Tests for the litellm-backed LLM client.

litellm itself is mocked, and GCP is disabled (no ``GCP_PROJECT_ID``) so the
client runs in env-only mode. These tests assert the client's contract: model
selection, message building, response parsing, provider inference, key
lookup (in-process override → mounted secret file → env var), and the
runtime-mutable provider/default-model state -- all without network calls.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

import applybot.llm.client as llm_client
from applybot.llm.client import (
    LLMProvider,
    complete,
    delete_provider,
    get_configured_providers,
    get_default_model,
    set_default_model,
    update_provider,
)


class _Quote(BaseModel):
    text: str
    length: int


def _fake_response(content: str | None) -> Any:
    """Build an object shaped like a litellm completion response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.fixture(autouse=True)
def _env_only(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run in env-only mode (no GCP, no mount) and isolate state per test."""
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("LLM_SECRETS_DIR", raising=False)
    for p in LLMProvider:
        monkeypatch.delenv(p.env_var, raising=False)
    monkeypatch.delenv("LLM_MODEL_DEFAULT", raising=False)
    llm_client._key_overrides.clear()
    llm_client._model_cache.clear()
    yield
    llm_client._key_overrides.clear()
    llm_client._model_cache.clear()


class TestComplete:
    @patch("applybot.llm.client.litellm")
    def test_returns_text_content(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response("hello world")
        update_provider(LLMProvider.OPENAI, "sk-test")
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")

        result = complete(None, None, "hi", system="be nice", temperature=0.5)

        assert result == "hello world"
        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["model"] == "gpt-4o-mini"

    @patch("applybot.llm.client.litellm")
    def test_structured_output_parsed(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response(
            '{"text": "hi", "length": 2}'
        )
        update_provider(LLMProvider.OPENAI, "sk-test")
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")

        result = complete(None, None, "hi", output_type=_Quote)

        assert result == _Quote(text="hi", length=2)
        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["response_format"] is _Quote

    @patch("applybot.llm.client.litellm")
    def test_system_message_prepended(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        update_provider(LLMProvider.OPENAI, "sk-test")
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")

        complete(None, None, "hi", system="sys")

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["messages"][0] == {"role": "system", "content": "sys"}

    @patch("applybot.llm.client.litellm")
    def test_no_system_message_when_blank(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        update_provider(LLMProvider.OPENAI, "sk-test")
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")

        complete(None, None, "hi")

        _, kwargs = mock_litellm.completion.call_args
        assert all(m["role"] != "system" for m in kwargs["messages"])

    @patch("applybot.llm.client.litellm")
    def test_no_content_raises(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response(None)
        update_provider(LLMProvider.OPENAI, "sk-test")
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")

        with pytest.raises(ValueError, match="no text content"):
            complete(None, None, "hi")

    def test_no_default_model_raises(self) -> None:
        update_provider(LLMProvider.OPENAI, "sk-test")
        with pytest.raises(ValueError, match="no default model"):
            complete(None, None, "hi")

    def test_no_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")
        with pytest.raises(ValueError, match="No API key configured"):
            complete(None, None, "hi")

    @patch("applybot.llm.client.litellm")
    def test_explicit_model_overrides_default(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        update_provider(LLMProvider.ANTHROPIC, "ant-key")
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")

        complete(None, "claude-3-5-sonnet-20241022", "hi")

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["model"] == "claude-3-5-sonnet-20241022"
        assert kwargs["api_key"] == "ant-key"

    @patch("applybot.llm.client.litellm")
    def test_provider_inferred_from_prefix(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        update_provider(LLMProvider.GEMINI, "gem-key")

        complete(None, "gemini/gemini-2.0-flash", "hi")

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["api_key"] == "gem-key"

    @patch("applybot.llm.client.litellm")
    def test_explicit_provider_overrides_inference(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        update_provider(LLMProvider.OPENAI, "sk-test")
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")

        # Pass provider as a string, model resolves to default; provider wins for key lookup
        complete("openai", None, "hi")

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["api_key"] == "sk-test"


class TestProviderStore:
    def test_update_then_configured(self) -> None:
        assert get_configured_providers() == []
        update_provider(LLMProvider.OPENAI, "sk-test")
        assert get_configured_providers() == [LLMProvider.OPENAI]

    def test_delete_removes_provider(self) -> None:
        update_provider(LLMProvider.OPENAI, "sk-test")
        assert LLMProvider.OPENAI in get_configured_providers()
        delete_provider(LLMProvider.OPENAI)
        assert get_configured_providers() == []

    def test_update_accepts_str(self) -> None:
        update_provider("anthropic", "ant-key")
        assert get_configured_providers() == [LLMProvider.ANTHROPIC]

    def test_multiple_providers(self) -> None:
        update_provider(LLMProvider.OPENAI, "sk-1")
        update_provider(LLMProvider.GEMINI, "gem-1")
        assert set(get_configured_providers()) == {
            LLMProvider.OPENAI,
            LLMProvider.GEMINI,
        }

    @patch("applybot.llm.client._backends.write_secret")
    def test_update_writes_secret_version(
        self, mock_write: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GCP_PROJECT_ID", "proj")

        update_provider(LLMProvider.OPENAI, "sk-test")

        mock_write.assert_called_once_with(LLMProvider.OPENAI, "sk-test")
        assert llm_client._key_overrides[LLMProvider.OPENAI] == "sk-test"
        assert "OPENAI_API_KEY" not in os.environ  # no env-var write-back

    @patch("applybot.llm.client._backends.write_secret")
    def test_delete_writes_blank_version(
        self, mock_write: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GCP_PROJECT_ID", "proj")
        update_provider(LLMProvider.OPENAI, "sk-test")

        delete_provider(LLMProvider.OPENAI)

        mock_write.assert_called_with(LLMProvider.OPENAI, "")
        assert get_configured_providers() == []


class TestKeyLookup:
    """Key resolution order: in-process override → mounted file → env var."""

    @staticmethod
    def _mount(tmp_path: Path, provider: LLMProvider, value: str) -> None:
        """Write a mounted-secret lookalike: ``<dir>/<secret_id>/latest``."""
        secret_dir = tmp_path / provider.secret_id
        secret_dir.mkdir()
        (secret_dir / "latest").write_text(value, encoding="utf-8")

    def test_mounted_file_beats_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_SECRETS_DIR", str(tmp_path))
        monkeypatch.setenv(LLMProvider.OPENAI.env_var, "sk-env")
        self._mount(tmp_path, LLMProvider.OPENAI, "sk-mounted\n")

        assert llm_client._get_provider_key(LLMProvider.OPENAI) == "sk-mounted"

    def test_env_var_when_no_mount(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(LLMProvider.OPENAI.env_var, "sk-env")

        assert llm_client._get_provider_key(LLMProvider.OPENAI) == "sk-env"

    def test_override_beats_mount_and_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_SECRETS_DIR", str(tmp_path))
        monkeypatch.setenv(LLMProvider.OPENAI.env_var, "sk-env")
        self._mount(tmp_path, LLMProvider.OPENAI, "sk-mounted")
        llm_client._key_overrides[LLMProvider.OPENAI] = "sk-new"

        assert llm_client._get_provider_key(LLMProvider.OPENAI) == "sk-new"

    def test_mount_refresh_seen_without_restart(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new secret version must be visible on the next access in the same
        process -- the propagation the old TTL/env-var design broke."""
        monkeypatch.setenv("LLM_SECRETS_DIR", str(tmp_path))
        self._mount(tmp_path, LLMProvider.OPENAI, "sk-v1")
        assert llm_client._get_provider_key(LLMProvider.OPENAI) == "sk-v1"

        (tmp_path / LLMProvider.OPENAI.secret_id / "latest").write_text(
            "sk-v2", encoding="utf-8"
        )

        assert llm_client._get_provider_key(LLMProvider.OPENAI) == "sk-v2"

    @patch("applybot.llm.client.litellm")
    def test_complete_uses_mounted_key(
        self,
        mock_litellm: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        monkeypatch.setenv("LLM_SECRETS_DIR", str(tmp_path))
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")
        self._mount(tmp_path, LLMProvider.OPENAI, "sk-mounted")

        complete(None, None, "hi")

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["api_key"] == "sk-mounted"


class TestDefaultModel:
    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")
        assert get_default_model() == "gpt-4o-mini"

    def test_set_then_get(self) -> None:
        set_default_model("claude-3-5-sonnet-20241022")
        assert get_default_model() == "claude-3-5-sonnet-20241022"

    def test_empty_when_unset(self) -> None:
        assert get_default_model() == ""


class TestProviderPrefixes:
    def test_provider_for_model_openai(self) -> None:
        assert llm_client.provider_for_model("gpt-4o") is LLMProvider.OPENAI

    def test_provider_for_model_anthropic(self) -> None:
        assert (
            llm_client.provider_for_model("claude-3-5-sonnet-20241022")
            is LLMProvider.ANTHROPIC
        )

    def test_provider_for_model_gemini(self) -> None:
        assert (
            llm_client.provider_for_model("gemini/gemini-2.0-flash")
            is LLMProvider.GEMINI
        )

    def test_provider_for_model_glm(self) -> None:
        assert llm_client.provider_for_model("zai/glm-5.2") is LLMProvider.GLM

    def test_provider_for_model_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not infer LLM provider"):
            llm_client.provider_for_model("unknown-model")
