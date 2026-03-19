"""Lever scraper — free public postings API."""

from __future__ import annotations

import logging

import httpx

from applybot.discovery.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

LEVER_API = "https://api.lever.co/v0/postings/{company}"


class LeverScraper(BaseScraper):
    """Fetch jobs from Lever job boards.

    Lever provides a free public API for each company's postings.
    Requires a list of target company slugs.
    """

    source_name = "lever"

    def __init__(self, company_slugs: list[str] | None = None) -> None:
        self._company_slugs = company_slugs or []

    async def search(
        self,
        queries: list[str],
        location: str = "",
        max_results: int = 50,
    ) -> list[RawJob]:
        if not self._company_slugs:
            logger.info("No Lever company slugs configured, skipping")
            return []

        results: list[RawJob] = []
        query_terms = [q.lower() for q in queries]

        async with httpx.AsyncClient(timeout=20.0) as client:
            for slug in self._company_slugs:
                try:
                    jobs = await self._fetch_company_jobs(client, slug)
                    for job in jobs:
                        if self._matches_queries(job, query_terms):
                            results.append(job)
                except Exception:
                    logger.exception("Lever fetch failed for: %s", slug)

                if len(results) >= max_results:
                    break

        logger.info("Lever: found %d matching jobs", len(results))
        return results[:max_results]

    async def _fetch_company_jobs(
        self, client: httpx.AsyncClient, slug: str
    ) -> list[RawJob]:
        url = LEVER_API.format(company=slug)
        resp = await client.get(url)
        resp.raise_for_status()
        postings = resp.json()

        jobs: list[RawJob] = []
        for item in postings:
            title = item.get("text", "")
            categories = item.get("categories", {})
            location_name = categories.get("location", "")

            # Build description from lists
            description_parts: list[str] = []
            if item.get("descriptionPlain"):
                description_parts.append(item["descriptionPlain"])
            for lst in item.get("lists", []):
                description_parts.append(lst.get("text", ""))
                description_parts.append(lst.get("content", ""))

            jobs.append(
                RawJob(
                    title=title,
                    company=slug,
                    location=location_name,
                    description="\n".join(description_parts),
                    url=item.get("hostedUrl", ""),
                    source=self.source_name,
                    posted_date=None,
                    extra={
                        "lever_id": item.get("id", ""),
                        "team": categories.get("team", ""),
                        "commitment": categories.get("commitment", ""),
                    },
                )
            )
        return jobs

    @staticmethod
    def _matches_queries(job: RawJob, query_terms: list[str]) -> bool:
        text = f"{job.title} {job.description}".lower()
        return any(term in text for term in query_terms)
