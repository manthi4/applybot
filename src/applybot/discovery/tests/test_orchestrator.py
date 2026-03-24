"""Tests for the discovery orchestrator module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from applybot.discovery.orchestrator import (
    DiscoveryResult,
    _map_source,
    _run_scraper,
    get_default_scrapers,
    run_discovery,
)
from applybot.discovery.scrapers.base import BaseScraper
from applybot.discovery.tests.conftest import make_raw_job
from applybot.models.job import JobSource

# ---------------------------------------------------------------------------
# _map_source()
# ---------------------------------------------------------------------------


class TestMapSource:
    def test_known_sources(self):
        assert _map_source("serpapi") == JobSource.SERPAPI
        assert _map_source("greenhouse") == JobSource.GREENHOUSE
        assert _map_source("lever") == JobSource.LEVER
        assert _map_source("eu_remote_jobs") == JobSource.EU_REMOTE_JOBS

    def test_unknown_source_defaults_to_manual(self):
        assert _map_source("unknown_board") == JobSource.MANUAL
        assert _map_source("") == JobSource.MANUAL


# ---------------------------------------------------------------------------
# _run_scraper()
# ---------------------------------------------------------------------------


class TestRunScraper:
    @pytest.mark.asyncio
    async def test_returns_scraper_results(self):
        jobs = [make_raw_job(url="https://a.com/1")]
        scraper = AsyncMock(spec=BaseScraper)
        scraper.source_name = "test"
        scraper.search.return_value = jobs

        result = await _run_scraper(scraper, ["q1"], "Remote", 50)
        assert result == jobs

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        scraper = AsyncMock(spec=BaseScraper)
        scraper.source_name = "failing"
        scraper.search.side_effect = RuntimeError("Network error")

        result = await _run_scraper(scraper, ["q1"], "", 50)
        assert result == []


# ---------------------------------------------------------------------------
# get_default_scrapers()
# ---------------------------------------------------------------------------


class TestGetDefaultScrapers:
    @patch("applybot.discovery.orchestrator.DEFAULT_GREENHOUSE_COMPANIES", [])
    @patch("applybot.discovery.orchestrator.DEFAULT_LEVER_COMPANIES", [])
    def test_default_scrapers_without_company_lists(self):
        scrapers = get_default_scrapers()
        source_names = [s.source_name for s in scrapers]
        assert "serpapi" in source_names
        assert "eu_remote_jobs" in source_names
        assert "greenhouse" not in source_names
        assert "lever" not in source_names

    @patch("applybot.discovery.orchestrator.DEFAULT_GREENHOUSE_COMPANIES", ["acme"])
    @patch("applybot.discovery.orchestrator.DEFAULT_LEVER_COMPANIES", ["techco"])
    def test_default_scrapers_with_company_lists(self):
        scrapers = get_default_scrapers()
        source_names = [s.source_name for s in scrapers]
        assert "greenhouse" in source_names
        assert "lever" in source_names


# ---------------------------------------------------------------------------
# run_discovery()
# ---------------------------------------------------------------------------


class TestRunDiscovery:
    @pytest.mark.asyncio
    @patch("applybot.discovery.orchestrator._save_jobs")
    @patch("applybot.discovery.orchestrator.rank_jobs")
    @patch("applybot.discovery.orchestrator.deduplicate")
    @patch("applybot.discovery.orchestrator.build_search_queries")
    @patch("applybot.discovery.orchestrator.ProfileManager")
    @patch("applybot.discovery.orchestrator.settings")
    async def test_full_pipeline_flow(
        self,
        mock_settings,
        mock_pm_cls,
        mock_build_queries,
        mock_dedup,
        mock_rank,
        mock_save,
    ):
        # Setup
        mock_settings.discovery_max_jobs_per_run = 100
        mock_profile = MagicMock()
        mock_pm_cls.return_value.get_profile.return_value = mock_profile

        mock_build_queries.return_value = ["ml engineer"]

        scraped_jobs = [
            make_raw_job(title="Job 1", url="https://a.com/1"),
            make_raw_job(title="Job 2", url="https://b.com/1"),
        ]
        scraper = AsyncMock(spec=BaseScraper)
        scraper.source_name = "test"
        scraper.search.return_value = scraped_jobs

        mock_dedup.return_value = scraped_jobs
        mock_rank.return_value = [
            (scraped_jobs[0], 85, "Strong match"),
            (scraped_jobs[1], 70, "Good match"),
        ]
        mock_save.return_value = 2

        # Execute
        result = await run_discovery(scrapers=[scraper])

        # Verify
        assert isinstance(result, DiscoveryResult)
        assert result.total_scraped == 2
        assert result.after_dedup == 2
        assert result.above_threshold == 2
        assert result.new_jobs_saved == 2
        assert len(result.top_matches) == 2

        mock_build_queries.assert_called_once_with(mock_profile)
        mock_dedup.assert_called_once()
        mock_rank.assert_called_once()
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    @patch("applybot.discovery.orchestrator._save_jobs")
    @patch("applybot.discovery.orchestrator.deduplicate")
    @patch("applybot.discovery.orchestrator.build_search_queries")
    @patch("applybot.discovery.orchestrator.ProfileManager")
    @patch("applybot.discovery.orchestrator.settings")
    async def test_no_profile_skips_ranking(
        self,
        mock_settings,
        mock_pm_cls,
        mock_build_queries,
        mock_dedup,
        mock_save,
    ):
        mock_settings.discovery_max_jobs_per_run = 100
        mock_pm_cls.return_value.get_profile.return_value = None
        mock_build_queries.return_value = ["default query"]

        scraped_jobs = [make_raw_job(url="https://a.com/1")]
        scraper = AsyncMock(spec=BaseScraper)
        scraper.source_name = "test"
        scraper.search.return_value = scraped_jobs

        mock_dedup.return_value = scraped_jobs
        mock_save.return_value = 1

        result = await run_discovery(scrapers=[scraper])

        # No profile → unranked with score 50
        assert result.above_threshold == 1
        assert result.top_matches[0]["score"] == 50

    @pytest.mark.asyncio
    @patch("applybot.discovery.orchestrator._save_jobs")
    @patch("applybot.discovery.orchestrator.rank_jobs")
    @patch("applybot.discovery.orchestrator.deduplicate")
    @patch("applybot.discovery.orchestrator.build_search_queries")
    @patch("applybot.discovery.orchestrator.ProfileManager")
    @patch("applybot.discovery.orchestrator.settings")
    async def test_scraper_failure_doesnt_crash_pipeline(
        self,
        mock_settings,
        mock_pm_cls,
        mock_build_queries,
        mock_dedup,
        mock_rank,
        mock_save,
    ):
        mock_settings.discovery_max_jobs_per_run = 100
        mock_profile = MagicMock()
        mock_pm_cls.return_value.get_profile.return_value = mock_profile
        mock_build_queries.return_value = ["q"]

        # One scraper succeeds, one fails
        good_scraper = AsyncMock(spec=BaseScraper)
        good_scraper.source_name = "good"
        good_scraper.search.return_value = [make_raw_job(url="https://a.com/1")]

        bad_scraper = AsyncMock(spec=BaseScraper)
        bad_scraper.source_name = "bad"
        bad_scraper.search.side_effect = RuntimeError("Timeout")

        mock_dedup.return_value = [make_raw_job(url="https://a.com/1")]
        mock_rank.return_value = [(make_raw_job(url="https://a.com/1"), 80, "Good")]
        mock_save.return_value = 1

        result = await run_discovery(scrapers=[good_scraper, bad_scraper])

        # Pipeline should complete despite the bad scraper
        assert result.total_scraped >= 1
        assert result.new_jobs_saved == 1

    @pytest.mark.asyncio
    @patch("applybot.discovery.orchestrator._save_jobs")
    @patch("applybot.discovery.orchestrator.rank_jobs")
    @patch("applybot.discovery.orchestrator.deduplicate")
    @patch("applybot.discovery.orchestrator.build_search_queries")
    @patch("applybot.discovery.orchestrator.ProfileManager")
    @patch("applybot.discovery.orchestrator.settings")
    async def test_empty_scraper_results(
        self,
        mock_settings,
        mock_pm_cls,
        mock_build_queries,
        mock_dedup,
        mock_rank,
        mock_save,
    ):
        mock_settings.discovery_max_jobs_per_run = 100
        mock_pm_cls.return_value.get_profile.return_value = MagicMock()
        mock_build_queries.return_value = ["q"]

        scraper = AsyncMock(spec=BaseScraper)
        scraper.source_name = "empty"
        scraper.search.return_value = []

        mock_dedup.return_value = []
        mock_rank.return_value = []
        mock_save.return_value = 0

        result = await run_discovery(scrapers=[scraper])
        assert result.total_scraped == 0
        assert result.new_jobs_saved == 0
        assert result.top_matches == []
