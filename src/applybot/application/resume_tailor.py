"""Resume tailoring agent — customizes resume for specific job postings."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from pydantic import BaseModel

from applybot.llm.client import get_llm
from applybot.models.job import Job
from applybot.models.profile import UserProfile
from applybot.profile.resume import (
    ResumeData,
    ResumeSection,
    generate_resume,
    parse_resume,
)
from applybot.storage import download_file, file_exists, upload_file

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
) -> str:
    """Create a tailored resume for a specific job.

    Guardrail: The agent may ONLY rephrase/reorder existing content.
    It must NOT fabricate experiences or skills not present in the profile.

    Args:
        job: The target job.
        profile: User profile with skills/experiences.

    Returns:
        GCS object name for the generated tailored .docx resume.
    """
    object_name = profile.resume_path
    if not object_name or not file_exists(object_name):
        raise FileNotFoundError(f"Base resume not found: {object_name}")

    # Download base resume to a temp file for parsing (parse_resume needs a Path)
    content = download_file(object_name)
    ext = Path(object_name).suffix

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    out_path: Path | None = None
    try:
        base_data = parse_resume(tmp_path)

        # Get tailoring plan from Claude
        plan = _get_tailoring_plan(job, profile, base_data)

        # Apply the plan to create tailored resume data
        tailored_data = _apply_plan(base_data, plan)

        # Generate the tailored .docx to another temp file
        output_name = f"resumes/tailored/resume_{job.id}_{_slugify(job.company)}.docx"
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as out_tmp:
            out_path = Path(out_tmp.name)

        generate_resume(tailored_data, tmp_path, out_path)

        # Upload the result to storage
        upload_file(out_path.read_bytes(), output_name)
        logger.info("Tailored resume generated: %s", output_name)
        return output_name
    finally:
        tmp_path.unlink(missing_ok=True)
        if out_path is not None:
            out_path.unlink(missing_ok=True)


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
            resume_summary += f"  [{idx}] {item[:150]}\n"

    skills_text = str(profile.skills or {})
    experiences_text = str(profile.experiences or [])

    prompt = f"""You are tailoring a resume for a specific job application.

CRITICAL RULES:
1. You may ONLY use existing content from the resume and profile.
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

    return get_llm().structured_output(
        prompt,
        TailoringPlan,
        system="You are an expert resume writer. You tailor resumes to specific jobs while maintaining complete honesty. You NEVER fabricate information.",
        tier="smart",
        max_tokens=8192,
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
