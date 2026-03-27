"""Discovery orchestrator — runs the full job discovery pipeline."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from applybot.config import settings
from applybot.discovery.deduplicator import deduplicate
from applybot.discovery.query_builder import build_search_queries
from applybot.discovery.ranker import rank_jobs
from applybot.discovery.scrapers.base import BaseScraper, RawJob
from applybot.discovery.scrapers.euremotejobs import EuRemoteJobsScraper
from applybot.discovery.scrapers.greenhouse import GreenhouseScraper
from applybot.discovery.scrapers.lever import LeverScraper
from applybot.discovery.scrapers.serpapi import SerpAPIScraper
from applybot.models.job import Job, JobSource, JobStatus, add_jobs, get_all_job_urls
from applybot.profile.manager import ProfileManager

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Summary of a discovery run."""

    total_scraped: int
    after_dedup: int
    above_threshold: int
    new_jobs_saved: int
    top_matches: list[dict[str, Any]]


# Default company slugs for Greenhouse/Lever scrapers
# These can be configured via environment or a managed list
DEFAULT_GREENHOUSE_COMPANIES: list[str] = [
    # Robotics / ML companies known to use Greenhouse
    # Users should customize this list
]

DEFAULT_LEVER_COMPANIES: list[str] = [
    # Robotics / ML companies known to use Lever
]


def get_default_scrapers() -> list[BaseScraper]:
    """Create the default set of scrapers."""
    scrapers: list[BaseScraper] = [
        SerpAPIScraper(),
        EuRemoteJobsScraper(),
    ]
    if DEFAULT_GREENHOUSE_COMPANIES:
        scrapers.append(GreenhouseScraper(DEFAULT_GREENHOUSE_COMPANIES))
    if DEFAULT_LEVER_COMPANIES:
        scrapers.append(LeverScraper(DEFAULT_LEVER_COMPANIES))
    return scrapers


async def _run_scraper(
    scraper: BaseScraper,
    queries: list[str],
    location: str,
    max_results: int,
) -> list[RawJob]:
    """Run a single scraper with error handling."""
    try:
        results = await scraper.search(queries, location, max_results)
        logger.info("Scraper %s returned %d jobs", scraper.source_name, len(results))
        return results
    except Exception:
        logger.exception("Scraper %s failed", scraper.source_name)
        return []


async def run_discovery(
    scrapers: list[BaseScraper] | None = None,
    location: str = "",
    max_results: int | None = None,
) -> DiscoveryResult:
    """Run the full discovery pipeline.

    1. Build search queries from profile
    2. Run all scrapers in parallel
    3. Deduplicate results
    4. Rank by relevance
    5. Save new jobs to database
    """
    scrapers = scrapers or get_default_scrapers()
    max_results = max_results or settings.discovery_max_jobs_per_run

    # Get user profile
    pm = ProfileManager()
    profile = pm.get_profile()

    # Build search queries
    queries = build_search_queries(profile)
    logger.info("Using search queries: %s", queries)

    # Run all scrapers concurrently
    tasks = [_run_scraper(s, queries, location, max_results) for s in scrapers]
    scraper_results = await asyncio.gather(*tasks)
    all_jobs = [job for result in scraper_results for job in result]
    logger.info("Total scraped: %d jobs", len(all_jobs))

    # Deduplicate
    unique_jobs = deduplicate(all_jobs)
    logger.info("After dedup: %d jobs", len(unique_jobs))

    # Rank (skip if no profile)
    if profile is not None:
        ranked = rank_jobs(unique_jobs, profile)
    else:
        ranked = [(job, 50, "No profile — unranked") for job in unique_jobs]

    # Save to database
    new_count = _save_jobs(ranked)

    top_matches = [
        {
            "title": job.title,
            "company": job.company,
            "score": score,
            "reasoning": reasoning,
            "url": job.url,
        }
        for job, score, reasoning in ranked[:10]
    ]

    result = DiscoveryResult(
        total_scraped=len(all_jobs),
        after_dedup=len(unique_jobs),
        above_threshold=len(ranked),
        new_jobs_saved=new_count,
        top_matches=top_matches,
    )

    logger.info(
        "Discovery complete: %d scraped → %d unique → %d relevant → %d new saved",
        result.total_scraped,
        result.after_dedup,
        result.above_threshold,
        result.new_jobs_saved,
    )
    return result


def _save_jobs(ranked: list[tuple[RawJob, int, str]]) -> int:
    """Save ranked jobs to the database, skipping existing URLs."""
    existing_urls = get_all_job_urls()
    new_jobs: list[Job] = []

    for raw_job, score, reasoning in ranked:
        if raw_job.url in existing_urls:
            continue

        source = _map_source(raw_job.source)
        job = Job(
            title=raw_job.title,
            company=raw_job.company,
            location=raw_job.location,
            description=raw_job.description,
            url=raw_job.url,
            source=source,
            posted_date=raw_job.posted_date,
            discovered_date=datetime.now(UTC),
            relevance_score=score,
            relevance_reasoning=reasoning,
            status=JobStatus.NEW,
        )
        new_jobs.append(job)
        existing_urls.add(raw_job.url)

    if new_jobs:
        add_jobs(new_jobs)
    return len(new_jobs)


def _map_source(source_name: str) -> JobSource:
    """Map scraper source name to JobSource enum."""
    mapping = {
        "serpapi": JobSource.SERPAPI,
        "greenhouse": JobSource.GREENHOUSE,
        "lever": JobSource.LEVER,
        "eu_remote_jobs": JobSource.EU_REMOTE_JOBS,
    }
    return mapping.get(source_name, JobSource.MANUAL)
