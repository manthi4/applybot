"""Tests for the query builder module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from applybot.discovery.query_builder import (
    DEFAULT_QUERIES,
    GeneratedQueries,
    build_search_queries,
)


class TestBuildSearchQueries:
    def test_no_profile_returns_defaults(self):
        result = build_search_queries(None)
        assert result == DEFAULT_QUERIES[:6]

    def test_no_profile_respects_max_queries(self):
        result = build_search_queries(None, max_queries=2)
        assert len(result) == 2
        assert result == DEFAULT_QUERIES[:2]

    def test_no_profile_max_queries_larger_than_defaults(self):
        result = build_search_queries(None, max_queries=100)
        # Should return all defaults, not crash
        assert len(result) == len(DEFAULT_QUERIES)

    @patch("applybot.discovery.query_builder.get_llm")
    def test_llm_generates_queries(self, mock_get_llm, mock_profile):
        mock_get_llm.return_value.structured_output.return_value = GeneratedQueries(
            queries=["robotics ML engineer", "perception engineer", "deep learning"]
        )
        result = build_search_queries(mock_profile, max_queries=3)
        assert result == [
            "robotics ML engineer",
            "perception engineer",
            "deep learning",
        ]
        mock_get_llm.return_value.structured_output.assert_called_once()

    @patch("applybot.discovery.query_builder.get_llm")
    def test_llm_result_truncated_to_max_queries(self, mock_get_llm, mock_profile):
        mock_get_llm.return_value.structured_output.return_value = GeneratedQueries(
            queries=["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8"]
        )
        result = build_search_queries(mock_profile, max_queries=3)
        assert len(result) == 3

    @patch("applybot.discovery.query_builder.get_llm")
    def test_llm_failure_falls_back_to_defaults(self, mock_get_llm, mock_profile):
        mock_get_llm.return_value.structured_output.side_effect = RuntimeError(
            "API down"
        )
        result = build_search_queries(mock_profile)
        assert result == DEFAULT_QUERIES[:6]

    @patch("applybot.discovery.query_builder.get_llm")
    def test_prompt_includes_profile_info(self, mock_get_llm, mock_profile):
        mock_get_llm.return_value.structured_output.return_value = GeneratedQueries(
            queries=["q1"]
        )
        build_search_queries(mock_profile, max_queries=1)

        call_args = mock_get_llm.return_value.structured_output.call_args
        prompt = call_args[0][0]  # First positional arg
        assert "Test User" in prompt or mock_profile.name in prompt
        assert "Python" in prompt or "skills" in prompt.lower()

    @patch("applybot.discovery.query_builder.get_llm")
    def test_profile_with_empty_skills(self, mock_get_llm):
        profile = MagicMock()
        profile.name = "Blank User"
        profile.summary = "Seeking ML roles"
        profile.skills = {}
        profile.experiences = []
        profile.preferences = {}
        mock_get_llm.return_value.structured_output.return_value = GeneratedQueries(
            queries=["ml jobs"]
        )

        result = build_search_queries(profile, max_queries=2)
        assert len(result) >= 1
