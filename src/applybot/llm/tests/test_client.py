"""Tests for the litellm-backed LLM client.

litellm itself is mocked — these tests assert the client's contract (model
selection, message building, response parsing) without making network calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from applybot.llm.client import LLMClient, get_llm


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


@pytest.fixture
def reset_singleton() -> Any:
    """Ensure get_llm()'s cached singleton doesn't leak between tests."""
    get_llm.cache_clear()
    yield
    get_llm.cache_clear()

class TestComplete:
    @patch("applybot.llm.client.litellm")
    def test_returns_text_content(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response("hello world")
        result = LLMClient().complete("hi", system="be nice", temperature=0.5)
        assert result == "hello world"

    @patch("applybot.llm.client.litellm")
    def test_passes_model_and_params(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        LLMClient().complete("hi", tier="smart", max_tokens=128, temperature=0.2)

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["model"] == "gpt-4o"  # smart tier default
        assert kwargs["max_tokens"] == 128
        assert kwargs["temperature"] == 0.2
        assert kwargs["messages"] == [
            {"role": "user", "content": "hi"},
        ]

    @patch("applybot.llm.client.litellm")
    def test_prepends_system_message(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        LLMClient().complete("hi", system="sys")

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["messages"][0] == {"role": "system", "content": "sys"}
        assert kwargs["messages"][1] == {"role": "user", "content": "hi"}

    @patch("applybot.llm.client.litellm")
    def test_empty_system_omits_system_message(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response("ok")
        LLMClient().complete("hi")
        _, kwargs = mock_litellm.completion.call_args
        assert all(m["role"] != "system" for m in kwargs["messages"])

    @patch("applybot.llm.client.litellm")
    def test_no_content_raises(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response(None)
        with pytest.raises(ValueError, match="no text content"):
            LLMClient().complete("hi")


class TestStructuredOutput:
    @patch("applybot.llm.client.litellm")
    def test_parses_json_into_model(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response(
            '{"text": "hi", "length": 2}'
        )
        result = LLMClient().structured_output("hi", _Quote, tier="smart")
        assert result == _Quote(text="hi", length=2)

    @patch("applybot.llm.client.litellm")
    def test_passes_response_format(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response(
            '{"text": "x", "length": 1}'
        )
        LLMClient().structured_output("hi", _Quote)

        _, kwargs = mock_litellm.completion.call_args
        assert kwargs["response_format"] is _Quote
        assert kwargs["temperature"] == 0.0

    @patch("applybot.llm.client.litellm")
    def test_invalid_json_raises(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _fake_response("not json")
        with pytest.raises(Exception):
            LLMClient().structured_output("hi", _Quote)


class TestGetLlm:
    def test_returns_singleton(self, reset_singleton: Any) -> None:
        first = get_llm()
        second = get_llm()
        assert first is second
        assert isinstance(first, LLMClient)
