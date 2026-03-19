"""Tests for the discovery module (deduplicator, query builder)."""

from applybot.discovery.deduplicator import _normalize_url, deduplicate
from applybot.discovery.scrapers.base import RawJob


class TestDeduplicator:
    def _make_job(
        self, title: str, company: str, url: str, location: str = ""
    ) -> RawJob:
        return RawJob(
            title=title,
            company=company,
            location=location,
            description="",
            url=url,
            source="test",
        )

    def test_no_duplicates(self):
        jobs = [
            self._make_job("ML Engineer", "Acme", "https://a.com/1"),
            self._make_job("Data Scientist", "Beta", "https://b.com/2"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 2

    def test_exact_url_duplicate(self):
        jobs = [
            self._make_job("ML Engineer", "Acme", "https://a.com/1"),
            self._make_job("ML Engineer", "Acme", "https://a.com/1"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 1

    def test_fuzzy_duplicate(self):
        jobs = [
            self._make_job("Machine Learning Engineer", "Acme Corp", "https://a.com/1"),
            self._make_job(
                "Machine Learning Engineer", "Acme Corp.", "https://b.com/2"
            ),
        ]
        result = deduplicate(jobs)
        assert len(result) == 1

    def test_different_jobs_same_company(self):
        jobs = [
            self._make_job("ML Engineer", "Acme", "https://a.com/1"),
            self._make_job("Data Scientist", "Acme", "https://a.com/2"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 2

    def test_url_normalization(self):
        assert (
            _normalize_url("https://example.com/job?utm_source=google&id=1")
            == "https://example.com/job?id=1"
        )
        assert (
            _normalize_url("https://example.com/job#section")
            == "https://example.com/job"
        )

    def test_empty_input(self):
        assert deduplicate([]) == []


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://jobs.com/apply?ref=email&position=123"
        result = _normalize_url(url)
        assert "ref=" not in result
        assert "position=123" in result

    def test_preserves_clean_url(self):
        url = "https://jobs.com/apply?position=123"
        result = _normalize_url(url)
        assert "position=123" in result

    def test_empty_url(self):
        assert _normalize_url("") == ""
