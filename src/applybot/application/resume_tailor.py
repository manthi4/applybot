"""Resume tailoring agent — customizes resume for specific job postings."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel

from applybot.config import settings
from applybot.llm.client import llm
from applybot.models.job import Job
from applybot.models.profile import UserProfile
from applybot.profile.resume import (
    ResumeData,
    ResumeSection,
    generate_resume,
    parse_resume,
)

logger = logging.getLogger(__name__)


class TailoringPlan(BaseModel):
    """LLM output: how to tailor the resume for a specific job."""

    summary_rewrite: str
    sections: list[SectionEdit]
    notes: str = ""


class SectionEdit(BaseModel):
    """Edit instructions for a single resume section."""

    heading: str
    items: list[str]
    reorder: list[int] = []  # indices to reorder (prioritize)


# Re-declare TailoringPlan after SectionEdit so forward refs work
TailoringPlan.model_rebuild()


def tailor_resume(
    job: Job,
    profile: UserProfile,
    base_resume_path: Path | None = None,
    output_dir: Path = Path("data/tailored"),
) -> Path:
    """Create a tailored resume for a specific job.

    Guardrail: The agent may ONLY rephrase/reorder existing content.
    It must NOT fabricate experiences or skills not present in the profile.

    Args:
        job: The target job.
        profile: User profile with skills/experiences.
        base_resume_path: Path to the base .docx resume.
        output_dir: Directory for output files.

    Returns:
        Path to the generated tailored .docx resume.
    """
    # Parse the base resume
    resume_path = base_resume_path or Path(profile.resume_path)
    if not resume_path.exists():
        raise FileNotFoundError(f"Base resume not found: {resume_path}")

    base_data = parse_resume(resume_path)

    # Get tailoring plan from Claude
    plan = _get_tailoring_plan(job, profile, base_data)

    # Apply the plan to create tailored resume data
    tailored_data = _apply_plan(base_data, plan)

    # Generate the .docx
    output_path = output_dir / f"resume_{job.id}_{_slugify(job.company)}.docx"
    generate_resume(tailored_data, resume_path, output_path)

    logger.info("Tailored resume generated: %s", output_path)
    return output_path


def _get_tailoring_plan(
    job: Job,
    profile: UserProfile,
    resume_data: ResumeData,
) -> TailoringPlan:
    """Ask Claude to create a tailoring plan."""
    # Truncate job description to avoid token limits
    job_desc = job.description[:3000] if job.description else "(no description)"

    resume_summary = "Current resume sections:\n"
    for section in resume_data.sections:
        resume_summary += f"\n## {section.heading}\n"
        for idx, item in enumerate(section.items):
            resume_summary += f"  [{idx}] {item[:200]}\n"

    skills_text = str(profile.skills or {})
    experiences_text = str(profile.experiences or [])

    prompt = f"""You are tailoring a resume for a specific job application.

CRITICAL RULES:
1. You may ONLY rephrase or reorder existing content from the resume and profile.
2. You must NOT fabricate any experiences, skills, projects, or achievements.
3. Emphasize the most relevant existing experiences and skills.
4. Adjust wording to use keywords from the job description where truthful.

JOB POSTING:
Title: {job.title}
Company: {job.company}
Description: {job_desc}

CANDIDATE PROFILE:
Skills: {skills_text}
Experiences: {experiences_text}

CURRENT RESUME:
{resume_summary}

Create a tailoring plan:
- summary_rewrite: A revised professional summary (1-3 sentences) highlighting relevance to THIS job. Use only facts from the profile.
- sections: For each resume section, provide the items list with rephrased content emphasizing job-relevant keywords. Use the reorder field to specify which items should come first (by original index).
- notes: Any observations about the match quality."""

    return llm.structured_output(
        prompt,
        TailoringPlan,
        system="You are an expert resume writer. You tailor resumes to specific jobs while maintaining complete honesty. You NEVER fabricate information.",
        model=settings.anthropic_model_smart,
        max_tokens=4096,
    )


def _apply_plan(base_data: ResumeData, plan: TailoringPlan) -> ResumeData:
    """Apply a tailoring plan to create modified resume data."""
    tailored = ResumeData(
        name=base_data.name,
        contact_info=base_data.contact_info,
        summary=plan.summary_rewrite or base_data.summary,
        sections=[],
    )

    # Map plan sections by heading
    plan_sections = {s.heading.lower(): s for s in plan.sections}

    for base_section in base_data.sections:
        plan_section = plan_sections.get(base_section.heading.lower())

        if plan_section and plan_section.items:
            # Use the plan's items (rephrased content)
            new_section = ResumeSection(
                heading=base_section.heading,
                items=plan_section.items,
            )
        else:
            # Keep original section unchanged
            new_section = ResumeSection(
                heading=base_section.heading,
                items=list(base_section.items),
            )

        tailored.sections.append(new_section)

    return tailored


def _slugify(text: str) -> str:
    """Create a filesystem-safe slug from text."""
    import re

    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50]
