"""Resume → profile update service.

resume_to_profile() takes a path to a resume file and updates a UserProfile
from it by extracting the raw text and asking the LLM to produce an updated
profile (blocking).
"""

from __future__ import annotations

import logging
from pathlib import Path

from docx import Document

from applybot.llm.client import complete
from applybot.models.profile import UserProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw-text extraction
# ---------------------------------------------------------------------------


def _extract_raw_resume_text(path: Path) -> str:
    """Extract plain text from a resume file for use as LLM context.

    Supported formats: ``.md``, ``.docx``, and ``.pdf``
    (text-based only; scanned/image PDFs are not supported).
    """
    ext = path.suffix.lower()
    if ext == ".md":
        return path.read_text(encoding="utf-8")
    if ext == ".docx":
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError(
                "pypdf is required to extract PDF text: pip install pypdf"
            ) from e
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    raise ValueError(f"Unsupported resume format: {ext!r}")


# ---------------------------------------------------------------------------
# LLM enrichment
# ---------------------------------------------------------------------------

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
  Only update a contact_info field if the resume clearly contains that information.
"""


def _enrich_profile_with_llm(profile: UserProfile, resume_text: str) -> UserProfile:
    """Call the LLM to review the existing profile + resume and return an updated profile."""
    prompt = (
        "Here is the existing user profile (JSON):\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        "Here is the resume the user just uploaded:\n"
        f"{resume_text}\n\n"
        "Output the updated user profile as JSON. Keep 'id' and 'resume_path' exactly as-is."
    )

    updated = complete(
        None,
        None,
        prompt,
        system=_SYSTEM_PROMPT,
        max_tokens=8192,
        output_type=UserProfile,
    )

    # Always preserve identity/path fields and guard against a missing name
    updated.id = profile.id
    updated.resume_path = profile.resume_path
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
    logger.info("LLM profile enrichment complete for profile %r", profile.id)
    return updated


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def resume_to_profile(resume_path: Path, profile: UserProfile) -> UserProfile:
    """Update ``profile`` from the resume at ``resume_path``.

    Extracts the raw resume text and asks the LLM to produce an updated
    profile, preserving ``id`` and ``resume_path``. Blocks on the LLM call.
    Returns the updated profile, which may be unchanged if the resume adds nothing new.
    """
    resume_text = _extract_raw_resume_text(resume_path)
    updated_profile = _enrich_profile_with_llm(profile, resume_text)
    return updated_profile
