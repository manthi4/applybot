"""SerpAPI scraper — covers LinkedIn + Indeed via Google Jobs API."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import httpx

from applybot.config import settings
from applybot.discovery.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"


class SerpAPIScraper(BaseScraper):
    """Fetch jobs from Google Jobs via SerpAPI.

    SerpAPI's Google Jobs endpoint aggregates listings from LinkedIn,
    Indeed, Glassdoor, and other major boards in a single API call.
    """

    source_name = "serpapi"

    def __init__(self) -> None:
        self._api_key = settings.serpapi_key

    async def search(
        self,
        queries: list[str],
        location: str = "",
        max_results: int = 50,
    ) -> list[RawJob]:
        if not self._api_key:
            logger.warning("SerpAPI key not configured, skipping")
            return []

        results: list[RawJob] = []
        per_query_limit = max(10, max_results // len(queries)) if queries else 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for query in queries:
                try:
                    jobs = await self._search_query(
                        client, query, location, per_query_limit
                    )
                    results.extend(jobs)
                except Exception:
                    logger.exception("SerpAPI search failed for query: %s", query)

                if len(results) >= max_results:
                    break

        return results[:max_results]

    async def _search_query(
        self,
        client: httpx.AsyncClient,
        query: str,
        location: str,
        limit: int,
    ) -> list[RawJob]:
        params: dict[str, str | int] = {
            "engine": "google_jobs",
            "q": query,
            "api_key": self._api_key,
            "num": min(limit, 10),  # SerpAPI returns up to 10 per page
        }
        if location:
            params["location"] = location

        # Restrict to recent postings (last 3 days)
        params["chips"] = "date_posted:3days"

        all_jobs: list[RawJob] = []
        start = 0

        while len(all_jobs) < limit:
            params["start"] = start
            resp = await client.get(SERPAPI_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            jobs_results = data.get("jobs_results", [])
            if not jobs_results:
                break

            for item in jobs_results:
                raw = self._parse_job(item)
                if raw:
                    all_jobs.append(raw)

            # Check for next page
            if not data.get("serpapi_pagination", {}).get("next"):
                break
            start += 10

        logger.info("SerpAPI: found %d jobs for query '%s'", len(all_jobs), query)
        return all_jobs

    def _parse_job(self, item: dict[str, Any]) -> RawJob | None:
        title = item.get("title", "")
        company = item.get("company_name", "")
        if not title or not company:
            return None

        # Build URL: prefer apply link, fall back to share link
        apply_options = item.get("apply_options", [])
        url = ""
        if apply_options:
            url = apply_options[0].get("link", "")
        if not url:
            url = item.get("share_link", "")
            if not url:
                url = item.get("job_id", "")

        # Parse posted date
        posted_date = self._parse_date(item.get("detected_extensions", {}))

        return RawJob(
            title=title,
            company=company,
            location=item.get("location", ""),
            description=item.get("description", ""),
            url=url,
            source=self.source_name,
            posted_date=posted_date,
            extra={
                "job_id": item.get("job_id", ""),
                "via": item.get("via", ""),
                "extensions": item.get("detected_extensions", {}),
            },
        )

    @staticmethod
    def _parse_date(extensions: dict[str, Any]) -> date | None:
        """Try to parse a relative date like '2 days ago'."""
        posted = extensions.get("posted_at", "")
        if not posted:
            return None
        posted_lower = posted.lower()
        today = date.today()
        if "today" in posted_lower or "just" in posted_lower:
            return today
        if "yesterday" in posted_lower or "1 day" in posted_lower:
            return today - timedelta(days=1)
        # Try to extract number of days
        for word in posted_lower.split():
            if word.isdigit():
                days = int(word)
                if "day" in posted_lower:
                    return today - timedelta(days=days)
                if "week" in posted_lower:
                    return today - timedelta(weeks=days)
                if "month" in posted_lower:
                    return today - timedelta(days=days * 30)
        return None
