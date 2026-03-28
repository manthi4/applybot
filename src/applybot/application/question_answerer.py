"""Question answerer — drafts answers for common job application questions."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel

from applybot.config import settings
from applybot.llm.client import llm
from applybot.models.job import Job
from applybot.models.profile import UserProfile

logger = logging.getLogger(__name__)


@dataclass
class ProfileGap:
    """Information missing from the profile that's needed for an application."""

    question: str
    context: str


class AnswerSet(BaseModel):
    """LLM output: answers to application questions."""

    answers: dict[str, str]
    missing_info: list[str] = []


COMMON_QUESTIONS = [
    "Why are you interested in this role?",
    "Why do you want to work at {company}?",
    "Describe your most relevant experience for this role.",
    "What is your greatest strength related to this position?",
]


def answer_questions(
    job: Job,
    profile: UserProfile,
    custom_questions: list[str] | None = None,
) -> tuple[dict[str, str], list[ProfileGap]]:
    """Generate answers for common and custom application questions.

    Args:
        job: The target job.
        profile: User profile.
        custom_questions: Additional questions from the specific application.

    Returns:
        Tuple of (question→answer dict, list of profile gaps).
    """
    # Build question list
    questions = [q.format(company=job.company) for q in COMMON_QUESTIONS]
    if custom_questions:
        questions.extend(custom_questions)

    # Build profile context
    profile_context = _build_profile_context(profile)

    # Truncate job description
    job_desc = job.description[:3000] if job.description else "(no description)"

    prompt = f"""You are helping a candidate answer job application questions.

CRITICAL RULES:
1. Only use information from the candidate's profile below. Do NOT fabricate experiences.
2. If you don't have enough information to answer a question, add the question to "missing_info".
3. Be professional, concise, and specific. Reference actual experiences.
4. Tailor each answer to this specific job and company.

JOB POSTING:
Title: {job.title}
Company: {job.company}
Description: {job_desc}

CANDIDATE PROFILE:
{profile_context}

QUESTIONS TO ANSWER:
{chr(10).join(f'{i+1}. {q}' for i, q in enumerate(questions))}

Provide answers as a JSON object with:
- "answers": dict mapping each question to its answer
- "missing_info": list of questions you couldn't fully answer due to missing profile information"""

    try:
        result = llm.structured_output(
            prompt,
            AnswerSet,
            system="You are an expert career coach helping with job applications. Be concise, professional, and truthful.",
            model=settings.vertex_model_smart,
            max_tokens=4096,
        )

        gaps = [
            ProfileGap(question=q, context=f"Needed for {job.title} at {job.company}")
            for q in result.missing_info
        ]

        logger.info(
            "Generated %d answers, %d gaps for %s at %s",
            len(result.answers),
            len(gaps),
            job.title,
            job.company,
        )
        return result.answers, gaps

    except Exception:
        logger.exception("Failed to generate answers for job %d", job.id)
        return {}, [
            ProfileGap(
                question="All questions",
                context=f"LLM failed for {job.title} at {job.company}",
            )
        ]


def generate_cover_letter(
    job: Job,
    profile: UserProfile,
) -> str:
    """Generate a cover letter for the job application."""
    profile_context = _build_profile_context(profile)
    job_desc = job.description[:3000] if job.description else "(no description)"

    prompt = f"""Write a concise cover letter for this job application.

RULES:
1. Only reference real experiences from the candidate's profile.
2. Keep it to 3-4 paragraphs.
3. Be specific about why this role and company are a good match.
4. Professional but not overly formal tone.

JOB:
Title: {job.title}
Company: {job.company}
Description: {job_desc}

CANDIDATE PROFILE:
{profile_context}"""

    try:
        return llm.complete(
            prompt,
            system="You are an expert career coach. Write authentic, specific cover letters.",
            model=settings.vertex_model_smart,
        )
    except Exception:
        logger.exception("Failed to generate cover letter for job %d", job.id)
        return ""


def _build_profile_context(profile: UserProfile) -> str:
    """Build a text summary of the user profile for LLM prompts."""
    skills = profile.skills or {}
    experiences = profile.experiences or []
    education = profile.education or []

    exp_text = ""
    for exp in experiences[:8]:
        if isinstance(exp, dict):
            exp_text += f"- {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('dates', '')})\n"
            exp_text += f"  {exp.get('summary', '')}\n"

    edu_text = ""
    for edu in education[:3]:
        if isinstance(edu, dict):
            edu_text += f"- {edu.get('degree', '')} from {edu.get('school', '')}\n"

    return f"""Name: {profile.name}
Email: {profile.email}
Summary: {profile.summary}

Skills: {skills}

Experience:
{exp_text}

Education:
{edu_text}"""
