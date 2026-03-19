"""EuRemoteJobs scraper — custom HTTP scraper for euremotejobs.com."""

from __future__ import annotations

import logging

import httpx
from lxml import html as lxml_html

from applybot.discovery.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

BASE_URL = "https://euremotejobs.com"


class EuRemoteJobsScraper(BaseScraper):
    """Scrape job listings from euremotejobs.com."""

    source_name = "eu_remote_jobs"

    async def search(
        self,
        queries: list[str],
        location: str = "",
        max_results: int = 50,
    ) -> list[RawJob]:
        results: list[RawJob] = []

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for query in queries:
                try:
                    jobs = await self._search_query(client, query, max_results)
                    results.extend(jobs)
                except Exception:
                    logger.exception("EuRemoteJobs search failed for query: %s", query)
                if len(results) >= max_results:
                    break

        # Deduplicate by URL within this scraper
        seen_urls: set[str] = set()
        unique: list[RawJob] = []
        for job in results:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique.append(job)

        logger.info("EuRemoteJobs: found %d jobs", len(unique))
        return unique[:max_results]

    async def _search_query(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
    ) -> list[RawJob]:
        # Search URL pattern — adjust based on actual site structure
        search_url = f"{BASE_URL}/"
        params = {"s": query}
        resp = await client.get(search_url, params=params)
        resp.raise_for_status()

        tree = lxml_html.fromstring(resp.text)
        jobs: list[RawJob] = []

        # Parse job listing cards — selectors may need adjustment
        # Common patterns: article elements, job-listing classes
        articles = tree.cssselect("article") or tree.cssselect(".job-listing")
        if not articles:
            # Fallback: look for links with job-like patterns
            articles = tree.cssselect("a[href*='job'], a[href*='position']")

        for article in articles[:limit]:
            try:
                raw = self._parse_listing(article)
                if raw:
                    jobs.append(raw)
            except Exception:
                logger.debug("Failed to parse listing element", exc_info=True)

        return jobs

    def _parse_listing(self, element) -> RawJob | None:  # type: ignore[no-untyped-def]
        """Parse a single listing element into a RawJob."""
        # Try to find title and URL
        link = element.cssselect("a[href]")
        if not link:
            if element.tag == "a":
                link = [element]
            else:
                return None

        url = link[0].get("href", "")
        if url and not url.startswith("http"):
            url = BASE_URL + url

        title = link[0].text_content().strip()
        if not title or not url:
            return None

        # Try to extract company
        company_el = element.cssselect(".company, .employer, [class*='company']")
        company = company_el[0].text_content().strip() if company_el else ""

        # Try to extract location
        loc_el = element.cssselect(".location, [class*='location']")
        location = loc_el[0].text_content().strip() if loc_el else "Remote (EU)"

        return RawJob(
            title=title,
            company=company,
            location=location,
            description="",  # Would need to fetch individual page for full description
            url=url,
            source=self.source_name,
            posted_date=None,
        )
