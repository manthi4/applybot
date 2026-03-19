"""Deduplicator — fuzzy matching to remove duplicate job listings across sources."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse

from rapidfuzz import fuzz

from applybot.discovery.scrapers.base import RawJob

logger = logging.getLogger(__name__)

# Minimum similarity score (0-100) to consider two jobs as duplicates
SIMILARITY_THRESHOLD = 85


def deduplicate(jobs: list[RawJob]) -> list[RawJob]:
    """Remove duplicate jobs using fuzzy matching on title + company + location.

    Keeps the first occurrence (earliest in the list).
    """
    if not jobs:
        return []

    unique: list[RawJob] = []
    seen_urls: set[str] = set()

    for job in jobs:
        normalized_url = _normalize_url(job.url)

        # Exact URL match
        if normalized_url in seen_urls:
            continue

        # Fuzzy match against existing unique jobs
        candidate_key = _build_key(job)
        is_dup = False
        for existing in unique:
            existing_key = _build_key(existing)
            score = fuzz.token_sort_ratio(candidate_key, existing_key)
            if score >= SIMILARITY_THRESHOLD:
                is_dup = True
                logger.debug(
                    "Duplicate (score=%d): '%s @ %s' ≈ '%s @ %s'",
                    score,
                    job.title,
                    job.company,
                    existing.title,
                    existing.company,
                )
                break

        if not is_dup:
            unique.append(job)
            seen_urls.add(normalized_url)

    removed = len(jobs) - len(unique)
    if removed:
        logger.info(
            "Deduplication: %d jobs → %d unique (%d removed)",
            len(jobs),
            len(unique),
            removed,
        )

    return unique


def _build_key(job: RawJob) -> str:
    """Build a comparison key from title + company + location."""
    parts = [job.title, job.company, job.location]
    return " ".join(p.strip().lower() for p in parts if p)


def _normalize_url(url: str) -> str:
    """Normalize a URL by stripping tracking params and fragments."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # Strip common tracking params
        clean_query = re.sub(
            r"(utm_\w+|ref|source|tracking_id|gh_jid|lever_origin)=[^&]*&?",
            "",
            parsed.query,
        )
        clean_query = clean_query.rstrip("&")
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, "")
        )
    except Exception:
        return url
