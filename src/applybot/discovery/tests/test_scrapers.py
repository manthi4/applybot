"""Tests for scraper implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from applybot.discovery.scrapers.base import BaseScraper, RawJob
from applybot.discovery.scrapers.greenhouse import GreenhouseScraper, _strip_html
from applybot.discovery.scrapers.lever import LeverScraper
from applybot.discovery.scrapers.serpapi import SerpAPIScraper

# ---------------------------------------------------------------------------
# BaseScraper ABC
# ---------------------------------------------------------------------------


class TestBaseScraper:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            BaseScraper()  # type: ignore[abstract]

    def test_concrete_subclass_works(self):
        class DummyScraper(BaseScraper):
            source_name = "dummy"

            async def search(self, queries, location="", max_results=50):
                return []

        scraper = DummyScraper()
        assert scraper.source_name == "dummy"


# ---------------------------------------------------------------------------
# SerpAPIScraper
# ---------------------------------------------------------------------------


class TestSerpAPIScraper:
    @patch("applybot.discovery.scrapers.serpapi.settings")
    def test_skips_when_no_api_key(self, mock_settings):
        mock_settings.serpapi_key = ""
        scraper = SerpAPIScraper.__new__(SerpAPIScraper)
        scraper._api_key = ""

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            scraper.search(["ml engineer"])
        )
        assert result == []

    @patch("applybot.discovery.scrapers.serpapi.settings")
    def test_parse_job_returns_none_for_empty_title(self, mock_settings):
        mock_settings.serpapi_key = "test-key"
        scraper = SerpAPIScraper.__new__(SerpAPIScraper)
        scraper._api_key = "test-key"

        result = scraper._parse_job({"company_name": "Acme"})
        assert result is None

    @patch("applybot.discovery.scrapers.serpapi.settings")
    def test_parse_job_returns_none_for_empty_company(self, mock_settings):
        mock_settings.serpapi_key = "test-key"
        scraper = SerpAPIScraper.__new__(SerpAPIScraper)
        scraper._api_key = "test-key"

        result = scraper._parse_job({"title": "ML Engineer"})
        assert result is None

    @patch("applybot.discovery.scrapers.serpapi.settings")
    def test_parse_job_extracts_fields(self, mock_settings):
        mock_settings.serpapi_key = "key"
        scraper = SerpAPIScraper.__new__(SerpAPIScraper)
        scraper._api_key = "key"

        item = {
            "title": "ML Engineer",
            "company_name": "Acme",
            "location": "Remote",
            "description": "Build models",
            "apply_options": [{"link": "https://acme.com/apply"}],
        }
        result = scraper._parse_job(item)
        assert result is not None
        assert result.title == "ML Engineer"
        assert result.company == "Acme"
        assert result.url == "https://acme.com/apply"
        assert result.source == "serpapi"

    @patch("applybot.discovery.scrapers.serpapi.settings")
    def test_parse_job_fallback_to_share_link(self, mock_settings):
        mock_settings.serpapi_key = "key"
        scraper = SerpAPIScraper.__new__(SerpAPIScraper)
        scraper._api_key = "key"

        item = {
            "title": "Engineer",
            "company_name": "Co",
            "share_link": "https://google.com/share/123",
        }
        result = scraper._parse_job(item)
        assert result is not None
        assert result.url == "https://google.com/share/123"


# ---------------------------------------------------------------------------
# GreenhouseScraper
# ---------------------------------------------------------------------------


class TestGreenhouseScraper:
    @pytest.mark.asyncio
    async def test_skips_when_no_slugs(self):
        scraper = GreenhouseScraper(company_slugs=[])
        result = await scraper.search(["ml engineer"])
        assert result == []

    def test_matches_queries_positive(self):
        job = RawJob(
            title="Machine Learning Engineer",
            company="acme",
            location="Remote",
            description="Deep learning and NLP experience required",
            url="https://greenhouse.io/1",
            source="greenhouse",
        )
        assert GreenhouseScraper._matches_queries(job, ["machine learning"])

    def test_matches_queries_negative(self):
        job = RawJob(
            title="Sales Manager",
            company="acme",
            location="NYC",
            description="Manage enterprise sales pipeline",
            url="https://greenhouse.io/2",
            source="greenhouse",
        )
        assert not GreenhouseScraper._matches_queries(job, ["machine learning"])

    def test_matches_queries_in_description(self):
        job = RawJob(
            title="Engineer",
            company="acme",
            location="",
            description="Work on deep learning models for robotics",
            url="https://greenhouse.io/3",
            source="greenhouse",
        )
        assert GreenhouseScraper._matches_queries(job, ["deep learning"])

    @pytest.mark.asyncio
    async def test_fetch_and_filter(self):
        """Mock HTTP response and verify parsing + filtering."""
        scraper = GreenhouseScraper(company_slugs=["acme"])

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jobs": [
                {
                    "title": "ML Engineer",
                    "location": {"name": "Remote"},
                    "content": "<p>Deep learning role</p>",
                    "absolute_url": "https://greenhouse.io/acme/ml",
                    "id": "123",
                },
                {
                    "title": "Office Manager",
                    "location": {"name": "NYC"},
                    "content": "<p>Admin tasks</p>",
                    "absolute_url": "https://greenhouse.io/acme/admin",
                    "id": "456",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        jobs = await scraper._fetch_company_jobs(mock_client, "acme")
        assert len(jobs) == 2

        # Now filter with queries
        filtered = [j for j in jobs if scraper._matches_queries(j, ["ml engineer"])]
        assert len(filtered) == 1
        assert filtered[0].title == "ML Engineer"


class TestStripHtml:
    def test_strips_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_collapses_whitespace(self):
        assert _strip_html("<p>Hello</p>   <p>World</p>") == "Hello World"

    def test_empty_input(self):
        assert _strip_html("") == ""

    def test_no_tags(self):
        assert _strip_html("plain text") == "plain text"


# ---------------------------------------------------------------------------
# LeverScraper
# ---------------------------------------------------------------------------


class TestLeverScraper:
    @pytest.mark.asyncio
    async def test_skips_when_no_slugs(self):
        scraper = LeverScraper(company_slugs=[])
        result = await scraper.search(["ml engineer"])
        assert result == []

    def test_matches_queries_positive(self):
        job = RawJob(
            title="ML Engineer",
            company="techco",
            location="Remote",
            description="PyTorch and deep learning",
            url="https://lever.co/1",
            source="lever",
        )
        assert LeverScraper._matches_queries(job, ["ml engineer"])

    def test_matches_queries_negative(self):
        job = RawJob(
            title="Accountant",
            company="finco",
            location="London",
            description="Financial reporting",
            url="https://lever.co/2",
            source="lever",
        )
        assert not LeverScraper._matches_queries(job, ["ml engineer"])

    @pytest.mark.asyncio
    async def test_fetch_company_jobs_parses_response(self):
        scraper = LeverScraper(company_slugs=["techco"])

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "text": "ML Engineer",
                "categories": {
                    "location": "Remote",
                    "team": "Engineering",
                    "commitment": "Full-time",
                },
                "descriptionPlain": "Build ML pipelines",
                "lists": [
                    {"text": "Requirements", "content": "5+ years experience"},
                ],
                "hostedUrl": "https://jobs.lever.co/techco/123",
                "id": "abc123",
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        jobs = await scraper._fetch_company_jobs(mock_client, "techco")
        assert len(jobs) == 1
        assert jobs[0].title == "ML Engineer"
        assert jobs[0].location == "Remote"
        assert jobs[0].source == "lever"
        assert "abc123" in jobs[0].extra.get("lever_id", "")
        assert "Build ML pipelines" in jobs[0].description
