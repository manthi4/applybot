"""Greenhouse scraper — free public boards API."""

from __future__ import annotations

import logging

import httpx

from applybot.discovery.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"


class GreenhouseScraper(BaseScraper):
    """Fetch jobs from Greenhouse job boards.

    Greenhouse provides a free public API for each company's board.
    Requires a list of target company board slugs.
    """

    source_name = "greenhouse"

    def __init__(self, company_slugs: list[str] | None = None) -> None:
        self._company_slugs = company_slugs or []

    async def search(
        self,
        queries: list[str],
        location: str = "",
        max_results: int = 50,
    ) -> list[RawJob]:
        if not self._company_slugs:
            logger.info("No Greenhouse company slugs configured, skipping")
            return []

        results: list[RawJob] = []
        query_terms = [q.lower() for q in queries]

        async with httpx.AsyncClient(timeout=20.0) as client:
            for slug in self._company_slugs:
                try:
                    jobs = await self._fetch_company_jobs(client, slug)
                    # Filter by query terms
                    for job in jobs:
                        if self._matches_queries(job, query_terms):
                            results.append(job)
                except Exception:
                    logger.exception("Greenhouse fetch failed for: %s", slug)

                if len(results) >= max_results:
                    break

        logger.info("Greenhouse: found %d matching jobs", len(results))
        return results[:max_results]

    async def _fetch_company_jobs(
        self, client: httpx.AsyncClient, slug: str
    ) -> list[RawJob]:
        url = GREENHOUSE_API.format(company=slug)
        resp = await client.get(url, params={"content": "true"})
        resp.raise_for_status()
        data = resp.json()

        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            title = item.get("title", "")
            location_name = ""
            if item.get("location"):
                location_name = item["location"].get("name", "")

            # Description is HTML — strip tags for plain text
            description_html = item.get("content", "")
            description = _strip_html(description_html)

            absolute_url = item.get("absolute_url", "")

            jobs.append(
                RawJob(
                    title=title,
                    company=slug,
                    location=location_name,
                    description=description,
                    url=absolute_url,
                    source=self.source_name,
                    posted_date=None,  # Greenhouse API doesn't provide this
                    extra={"greenhouse_id": item.get("id", "")},
                )
            )
        return jobs

    @staticmethod
    def _matches_queries(job: RawJob, query_terms: list[str]) -> bool:
        """Check if a job matches any of the search query terms."""
        text = f"{job.title} {job.description}".lower()
        return any(term in text for term in query_terms)


def _strip_html(html: str) -> str:
    """Simple HTML tag stripping without external dependencies."""
    import re

    clean = re.sub(r"<[^>]+>", " ", html)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()
