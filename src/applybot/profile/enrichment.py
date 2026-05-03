"""LLM-based profile enrichment.

After the heuristic resume parser runs, this module calls the LLM to review
the existing profile alongside the raw resume text and write back a fully
updated profile. Runs as a fire-and-forget background task so the upload
response is not delayed.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from applybot.llm.client import get_llm
from applybot.models.profile import UserProfile, save_profile, update_profile_fields

logger = logging.getLogger(__name__)

# Strong references to in-flight background tasks to prevent GC from dropping them
_background_tasks: set[asyncio.Task[None]] = set()

_SYSTEM_PROMPT = """You are a helpful assistant managing a job applicant's profile.

Given their existing profile and their newly uploaded resume, output an updated
profile that incorporates any new or improved information from the resume.

Rules:
- Do not change the 'id' or 'resume_path' fields.
- If the profile already looks complete and the resume adds nothing new, return the profile unchanged.
- Expand skills, experiences, and education from the resume if they are missing or incomplete in the profile.
- Write a strong professional summary if the existing one is empty or weak.
- Extract contact information from the resume and populate the contact_info fields:
  - contact_info.email: email address
  - contact_info.linkedin: LinkedIn profile URL or username
  - contact_info.phone: phone number
  - contact_info.github: GitHub profile URL or username
  Only update a contact_info field if the resume clearly contains that information and the field is currently empty.
"""


def extract_raw_resume_text(path: Path) -> str:
    """Extract plain text from a resume file for use as LLM context.

    Unlike parse_resume(), this returns the full raw text without heuristic
    filtering, so the LLM sees everything the heuristic parser may have missed.
    """
    ext = path.suffix.lower()
    if ext == ".md":
        return path.read_text(encoding="utf-8")
    elif ext == ".docx":
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError(
                "pypdf is required to extract PDF text: pip install pypdf"
            ) from e
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    else:
        raise ValueError(f"Unsupported resume format: {ext!r}")


def enrich_profile_with_llm(profile: UserProfile, resume_text: str) -> UserProfile:
    """Call the LLM to review the existing profile + resume and save an updated profile.

    This is a synchronous, blocking call — use enrich_profile_with_llm_async
    to run it as a background task from an async context.
    """
    prompt = (
        "Here is the existing user profile (JSON):\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        "Here is the resume the user just uploaded:\n"
        f"{resume_text}\n\n"
        "Output the updated user profile. Keep 'id' and 'resume_path' exactly as-is."
    )

    updated = get_llm().structured_output(
        prompt,
        UserProfile,
        system=_SYSTEM_PROMPT,
        tier="smart",
    )

    # Always preserve identity/path fields and guard against a missing name
    updated.id = profile.id
    updated.resume_path = profile.resume_path
    updated.enrichment_warning = ""
    if not updated.name:
        updated.name = profile.name
    # Preserve any contact fields the LLM left blank but the profile already had
    if not updated.contact_info.email and profile.contact_info.email:
        updated.contact_info.email = profile.contact_info.email
    if not updated.contact_info.linkedin and profile.contact_info.linkedin:
        updated.contact_info.linkedin = profile.contact_info.linkedin
    if not updated.contact_info.phone and profile.contact_info.phone:
        updated.contact_info.phone = profile.contact_info.phone
    if not updated.contact_info.github and profile.contact_info.github:
        updated.contact_info.github = profile.contact_info.github

    save_profile(updated)
    logger.info("LLM profile enrichment complete for profile %r", profile.id)
    return updated


async def enrich_profile_with_llm_async(profile: UserProfile, resume_text: str) -> None:
    """Fire-and-forget background wrapper around enrich_profile_with_llm.

    Runs the blocking LLM + Firestore calls in a thread-pool executor so the
    Uvicorn event loop is not blocked. Errors are logged, not re-raised.

    The task is tracked in _background_tasks to prevent it from being garbage
    collected before it completes.
    """
    task = asyncio.current_task()
    if task is not None:
        _background_tasks.add(task)
    try:
        await asyncio.to_thread(enrich_profile_with_llm, profile, resume_text)
    except Exception:
        logger.exception("LLM profile enrichment failed — profile unchanged")
        try:
            update_profile_fields(
                enrichment_warning=(
                    "We could not run AI profile enrichment after your resume upload. "
                    "Your profile still includes the standard parsed resume data."
                )
            )
        except Exception:
            logger.exception("Failed to persist profile enrichment warning")
    finally:
        if task is not None:
            _background_tasks.discard(task)
