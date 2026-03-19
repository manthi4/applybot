"""Search query builder — generates effective search queries from the user profile."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from applybot.llm.client import llm
from applybot.models.profile import UserProfile

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    "machine learning engineer",
    "ML engineer robotics",
    "applied machine learning",
    "deep learning engineer",
]


class GeneratedQueries(BaseModel):
    queries: list[str]


def build_search_queries(
    profile: UserProfile | None,
    max_queries: int = 6,
) -> list[str]:
    """Generate search queries based on the user profile.

    Falls back to defaults if no profile or LLM unavailable.
    """
    if profile is None:
        logger.info("No profile available, using default queries")
        return DEFAULT_QUERIES[:max_queries]

    # Build context from profile
    skills = profile.skills or {}
    experiences = profile.experiences or []
    preferences = profile.preferences or {}

    profile_summary = f"""
Name: {profile.name}
Summary: {profile.summary}
Skills: {', '.join(skills.get('technical', [])) if isinstance(skills.get('technical'), list) else str(skills)}
Experience areas: {', '.join(exp.get('title', '') for exp in experiences[:5]) if experiences else 'N/A'}
Job preferences: {preferences}
"""
    prompt = f"""Based on this professional profile, generate {max_queries} varied job search queries
that would find the most relevant job postings. Include variations covering:
- Primary job title matches
- Related/alternative titles
- Niche specializations mentioned in the profile
- Industry-specific terms

Profile:
{profile_summary}

Return only the queries as a JSON object with a "queries" key containing a list of strings."""

    try:
        result = llm.structured_output(
            prompt,
            GeneratedQueries,
            system="You are a job search expert. Generate precise, effective search queries.",
        )
        queries = result.queries[:max_queries]
        logger.info("Generated %d search queries from profile", len(queries))
        return queries
    except Exception:
        logger.exception("Failed to generate queries via LLM, using defaults")
        return DEFAULT_QUERIES[:max_queries]
