"""Relevance ranker — uses Claude to score jobs against the user profile."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from applybot.config import settings
from applybot.discovery.scrapers.base import RawJob
from applybot.llm.client import get_llm
from applybot.models.profile import UserProfile

logger = logging.getLogger(__name__)

BATCH_SIZE = 5


class JobScore(BaseModel):
    job_index: int
    score: int  # 0-100
    reasoning: str


class BatchScoreResult(BaseModel):
    scores: list[JobScore]


def rank_jobs(
    jobs: list[RawJob],
    profile: UserProfile,
    threshold: int | None = None,
) -> list[tuple[RawJob, int, str]]:
    """Score and rank jobs by relevance to the user profile.

    Args:
        jobs: Jobs to score.
        profile: User profile to match against.
        threshold: Minimum score to include (default from config).

    Returns:
        List of (job, score, reasoning) tuples sorted by score descending,
        filtered to those above the threshold.
    """
    threshold = (
        threshold if threshold is not None else settings.discovery_relevance_threshold
    )

    profile_summary = _build_profile_summary(profile)
    scored: list[tuple[RawJob, int, str]] = []

    # Process in batches to reduce API calls
    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i : i + BATCH_SIZE]
        try:
            batch_scores = _score_batch(batch, profile_summary)
            scored.extend(batch_scores)
        except Exception:
            logger.exception("Failed to score batch %d-%d", i, i + len(batch))
            # On failure, assign neutral scores so jobs aren't lost
            for job in batch:
                scored.append((job, 50, "Scoring failed — assigned neutral score"))

    # Filter and sort
    above_threshold = [(j, s, r) for j, s, r in scored if s >= threshold]
    above_threshold.sort(key=lambda x: x[1], reverse=True)

    logger.info(
        "Ranked %d jobs: %d above threshold (%d)",
        len(jobs),
        len(above_threshold),
        threshold,
    )
    return above_threshold


def _build_profile_summary(profile: UserProfile) -> str:
    skills = profile.skills or {}
    experiences = profile.experiences or []
    prefs = profile.preferences or {}

    exp_text = ""
    for exp in experiences[:5]:
        if isinstance(exp, dict):
            exp_text += f"- {exp.get('title', '')} at {exp.get('company', '')}: {exp.get('summary', '')}\n"

    return f"""Name: {profile.name}
Summary: {profile.summary}
Skills: {skills}
Recent experience:
{exp_text}
Job preferences: {prefs}"""


def _score_batch(
    batch: list[RawJob],
    profile_summary: str,
) -> list[tuple[RawJob, int, str]]:
    """Score a batch of jobs using a single LLM call."""
    jobs_text = ""
    for idx, job in enumerate(batch):
        # Truncate long descriptions to avoid token limits
        desc = job.description[:1500] if job.description else "(no description)"
        jobs_text += f"""
--- Job {idx} ---
Title: {job.title}
Company: {job.company}
Location: {job.location}
Description: {desc}
"""

    prompt = f"""Score each job's relevance to this candidate's profile (0-100).

CANDIDATE PROFILE:
{profile_summary}

JOBS TO SCORE:
{jobs_text}

For each job, provide:
- job_index: the job number (0-based)
- score: 0-100 (0=completely irrelevant, 50=somewhat relevant, 80+=strong match, 95+=perfect match)
- reasoning: one sentence explaining the score

Consider: skill match, experience relevance, seniority level, industry fit, location preferences."""

    result = get_llm().structured_output(
        prompt,
        BatchScoreResult,
        system="You are an expert recruiter matching candidates to jobs. Be calibrated: most jobs should score 30-70, only truly exceptional matches above 85.",
    )

    scored: list[tuple[RawJob, int, str]] = []
    for score_item in result.scores:
        if 0 <= score_item.job_index < len(batch):
            job = batch[score_item.job_index]
            scored.append((job, score_item.score, score_item.reasoning))

    # Handle any jobs that weren't scored (LLM missed them)
    scored_indices = {s.job_index for s in result.scores}
    for idx, job in enumerate(batch):
        if idx not in scored_indices:
            scored.append((job, 50, "Not scored by LLM — assigned neutral score"))

    return scored
