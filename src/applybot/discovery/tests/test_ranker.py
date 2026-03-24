"""Tests for the relevance ranker module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from applybot.discovery.ranker import (
    BATCH_SIZE,
    BatchScoreResult,
    JobScore,
    _build_profile_summary,
    _score_batch,
    rank_jobs,
)
from applybot.discovery.tests.conftest import make_raw_job


class TestRankJobs:
    @patch("applybot.discovery.ranker.rank_jobs.__module__")  # dummy to get scope
    def _make_score_result(self, batch_size: int, score: int = 75) -> BatchScoreResult:
        """Helper to build a BatchScoreResult for a batch."""
        return BatchScoreResult(
            scores=[
                JobScore(job_index=i, score=score, reasoning=f"Good match #{i}")
                for i in range(batch_size)
            ]
        )

    @patch("applybot.discovery.ranker._score_batch")
    @patch("applybot.discovery.ranker.settings")
    def test_returns_jobs_above_threshold(
        self, mock_settings, mock_score, mock_profile
    ):
        mock_settings.discovery_relevance_threshold = 50
        jobs = [
            make_raw_job(title="Good Job", url="https://a.com/1"),
            make_raw_job(title="Bad Job", url="https://b.com/1"),
        ]
        mock_score.return_value = [
            (jobs[0], 80, "Strong match"),
            (jobs[1], 30, "Weak match"),
        ]

        result = rank_jobs(jobs, mock_profile)
        assert len(result) == 1
        assert result[0][0].title == "Good Job"
        assert result[0][1] == 80

    @patch("applybot.discovery.ranker._score_batch")
    @patch("applybot.discovery.ranker.settings")
    def test_custom_threshold_overrides_config(
        self, mock_settings, mock_score, mock_profile
    ):
        mock_settings.discovery_relevance_threshold = 50
        jobs = [make_raw_job(url="https://a.com/1")]
        mock_score.return_value = [(jobs[0], 60, "Decent match")]

        result = rank_jobs(jobs, mock_profile, threshold=70)
        assert len(result) == 0  # 60 is below custom threshold of 70

    @patch("applybot.discovery.ranker._score_batch")
    @patch("applybot.discovery.ranker.settings")
    def test_sorted_by_score_descending(self, mock_settings, mock_score, mock_profile):
        mock_settings.discovery_relevance_threshold = 0
        jobs = [
            make_raw_job(title="Mid", url="https://a.com/1"),
            make_raw_job(title="High", url="https://b.com/1"),
            make_raw_job(title="Low", url="https://c.com/1"),
        ]
        mock_score.return_value = [
            (jobs[0], 50, "Mid"),
            (jobs[1], 90, "High"),
            (jobs[2], 20, "Low"),
        ]

        result = rank_jobs(jobs, mock_profile)
        scores = [s for _, s, _ in result]
        assert scores == sorted(scores, reverse=True)

    @patch("applybot.discovery.ranker._score_batch")
    @patch("applybot.discovery.ranker.settings")
    def test_empty_jobs_list(self, mock_settings, mock_score, mock_profile):
        mock_settings.discovery_relevance_threshold = 50
        result = rank_jobs([], mock_profile)
        assert result == []
        mock_score.assert_not_called()

    @patch("applybot.discovery.ranker._score_batch")
    @patch("applybot.discovery.ranker.settings")
    def test_batch_failure_assigns_neutral_score(
        self, mock_settings, mock_score, mock_profile
    ):
        mock_settings.discovery_relevance_threshold = 0
        jobs = [make_raw_job(url="https://a.com/1")]
        mock_score.side_effect = RuntimeError("LLM timeout")

        result = rank_jobs(jobs, mock_profile)
        assert len(result) == 1
        assert result[0][1] == 50  # Neutral score
        assert "failed" in result[0][2].lower()

    @patch("applybot.discovery.ranker._score_batch")
    @patch("applybot.discovery.ranker.settings")
    def test_processes_in_batches(self, mock_settings, mock_score, mock_profile):
        mock_settings.discovery_relevance_threshold = 0
        jobs = [make_raw_job(url=f"https://a.com/{i}") for i in range(BATCH_SIZE + 2)]

        # Return scored tuples for each batch call
        def score_side_effect(batch, profile_summary):
            return [(j, 70, "Ok") for j in batch]

        mock_score.side_effect = score_side_effect

        result = rank_jobs(jobs, mock_profile)
        assert mock_score.call_count == 2  # ceil((BATCH_SIZE+2)/BATCH_SIZE) == 2
        assert len(result) == BATCH_SIZE + 2


class TestScoreBatch:
    @patch("applybot.discovery.ranker.llm")
    @patch("applybot.discovery.ranker.settings")
    def test_scores_all_jobs_in_batch(self, mock_settings, mock_llm):
        mock_settings.anthropic_model_fast = "test-model"
        jobs = [
            make_raw_job(title="ML Engineer", url="https://a.com/1"),
            make_raw_job(title="Data Scientist", url="https://b.com/1"),
        ]
        mock_llm.structured_output.return_value = BatchScoreResult(
            scores=[
                JobScore(job_index=0, score=85, reasoning="Strong ML match"),
                JobScore(job_index=1, score=60, reasoning="Partial match"),
            ]
        )

        result = _score_batch(jobs, "profile summary text")
        assert len(result) == 2
        assert result[0][1] == 85
        assert result[1][1] == 60

    @patch("applybot.discovery.ranker.llm")
    @patch("applybot.discovery.ranker.settings")
    def test_missing_index_gets_neutral_score(self, mock_settings, mock_llm):
        mock_settings.anthropic_model_fast = "test-model"
        jobs = [
            make_raw_job(title="Job A", url="https://a.com/1"),
            make_raw_job(title="Job B", url="https://b.com/1"),
        ]
        # LLM only returns score for index 0, omits index 1
        mock_llm.structured_output.return_value = BatchScoreResult(
            scores=[JobScore(job_index=0, score=80, reasoning="Good")]
        )

        result = _score_batch(jobs, "profile")
        assert len(result) == 2
        scored_titles = {r[0].title: r[1] for r in result}
        assert scored_titles["Job A"] == 80
        assert scored_titles["Job B"] == 50  # Neutral fallback

    @patch("applybot.discovery.ranker.llm")
    @patch("applybot.discovery.ranker.settings")
    def test_out_of_range_index_ignored(self, mock_settings, mock_llm):
        mock_settings.anthropic_model_fast = "test-model"
        jobs = [make_raw_job(url="https://a.com/1")]
        mock_llm.structured_output.return_value = BatchScoreResult(
            scores=[
                JobScore(job_index=0, score=80, reasoning="Good"),
                JobScore(job_index=99, score=90, reasoning="Ghost job"),
            ]
        )

        result = _score_batch(jobs, "profile")
        assert len(result) == 1
        assert result[0][1] == 80

    @patch("applybot.discovery.ranker.llm")
    @patch("applybot.discovery.ranker.settings")
    def test_truncates_long_descriptions(self, mock_settings, mock_llm):
        mock_settings.anthropic_model_fast = "test-model"
        long_desc = "x" * 5000
        jobs = [make_raw_job(description=long_desc, url="https://a.com/1")]
        mock_llm.structured_output.return_value = BatchScoreResult(
            scores=[JobScore(job_index=0, score=50, reasoning="Ok")]
        )

        _score_batch(jobs, "profile")
        prompt = mock_llm.structured_output.call_args[0][0]
        # Description in prompt should be truncated to 1500 chars
        assert "x" * 1501 not in prompt


class TestBuildProfileSummary:
    def test_includes_profile_fields(self, mock_profile):
        summary = _build_profile_summary(mock_profile)
        assert "Test User" in summary
        assert "ML engineer" in summary

    def test_handles_empty_experiences(self):
        profile = MagicMock()
        profile.name = "Empty User"
        profile.summary = ""
        profile.skills = {}
        profile.experiences = []
        profile.preferences = {}

        summary = _build_profile_summary(profile)
        assert "Empty User" in summary

    def test_includes_experience_entries(self, mock_profile):
        summary = _build_profile_summary(mock_profile)
        assert "ML Engineer" in summary
        assert "RoboTech" in summary
