"""LLM enrichment — verifies scraped job data and extracts structured fields."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from applybot.discovery.scrapers.base import RawJob
from applybot.llm.client import get_llm
from applybot.models.job import Job

logger = logging.getLogger(__name__)


class JobEnrichment(BaseModel):
    """LLM-verified and extracted fields for a job posting."""

    title: str
    """Corrected job title — use the scraped value if it is already accurate."""

    company: str
    """Corrected company name — use the scraped value if it is already accurate."""

    location: str
    """Corrected or clarified location — use the scraped value if it is already accurate."""

    hard_requirements: list[str]
    """Non-negotiable requirements explicitly stated in the posting.
    Examples: 'US citizenship required', '5+ years of Python', 'PhD in Computer Science'.
    Do NOT include preferred/nice-to-have qualifications."""

    application_questions: list[str]
    """Explicit questions the applicant must answer as part of the application.
    Examples: 'Describe a time you led a team under pressure.',
              'Why do you want to work at this company?'.
    Only include questions explicitly directed at the applicant — not general job-description text."""


_SYSTEM = (
    "You are a meticulous recruiter parsing job postings. "
    "Verify basic fields against the raw description and correct any scraping errors. "
    "For hard_requirements, only include items explicitly marked as required or mandatory — "
    "do not include preferred or nice-to-have items. "
    "For application_questions, only include questions explicitly posed to the applicant in "
    "the posting — not general text about the role."
)


def enrich_job(raw_job: RawJob, job: Job) -> Job:
    """Use the LLM to verify scraped fields and extract hard requirements and application questions.

    Sends the raw description and current job record to the LLM.
    On success, updates title/company/location if the LLM finds corrections,
    and populates hard_requirements and application_questions.
    On failure, logs the error and returns the job unchanged.
    """
    desc = (raw_job.description or "(no description)")[:3000]

    prompt = f"""Review this job posting and the record we scraped from it.

SCRAPED JOB RECORD:
  Title:    {job.title}
  Company:  {job.company}
  Location: {job.location}
  URL:      {job.url}

RAW JOB DESCRIPTION:
{desc}

Tasks:
1. Verify title, company, and location are accurate. Correct them if the description contradicts what was scraped.
2. Extract all hard/mandatory requirements (e.g. years of experience, certifications, citizenship, clearances).
3. Extract any explicit application questions the candidate is asked to answer.

Return the verified fields and all extracted data."""

    try:
        enrichment = get_llm().structured_output(
            prompt,
            JobEnrichment,
            system=_SYSTEM,
            tier="fast",
        )
        job.title = enrichment.title
        job.company = enrichment.company
        job.location = enrichment.location
        job.hard_requirements = enrichment.hard_requirements
        job.application_questions = enrichment.application_questions
        logger.debug(
            "Enriched '%s' @ %s: %d hard reqs, %d questions",
            job.title,
            job.company,
            len(job.hard_requirements),
            len(job.application_questions),
        )
    except Exception:
        logger.exception("LLM enrichment failed for job '%s' (%s)", job.title, job.url)

    return job
