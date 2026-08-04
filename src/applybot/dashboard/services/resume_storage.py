"""Resume upload/download orchestration over the applybot.storage layer.

The profile page used to perform storage I/O, temp-file juggling, and the
parse → map → enrich workflow inline. That domain logic lives here so the
page module is left with only request handling and flash-message routing.

Uploads are stored via the shared ``applybot.storage`` layer (GCS in
production when ``GCS_BUCKET_NAME`` is set, local ``data/`` fallback in dev)
as object ``resumes/resume.<ext>``; ``profile.resume_path`` holds the object
name. Parsing is heuristic-only (``services/resume.py``); after the
heuristic save a fire-and-forget background task
(``services/enrichment.py``) asks the LLM to enrich the profile.
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from pathlib import Path

from starlette.responses import Response

from applybot.dashboard.services.enrichment import (
    enrich_profile_with_llm_async,
    extract_raw_resume_text,
)
from applybot.dashboard.services.resume import ResumeData, parse_resume
from applybot.models.profile import UserProfile
from applybot.storage import file_exists, get_download_response, upload_file

logger = logging.getLogger(__name__)

MAX_RESUME_SIZE = 10 * 1024 * 1024  # 10 MB

_ALLOWED_EXTENSIONS = frozenset({".docx", ".pdf", ".md"})


# ---------------------------------------------------------------------------
# Errors — the page translates these into flash-message redirects.
# ---------------------------------------------------------------------------


class ResumeStorageError(Exception):
    """Base class for resume upload/download failures."""


class InvalidFileTypeError(ResumeStorageError):
    """Uploaded resume has a disallowed extension."""


class FileTooLargeError(ResumeStorageError):
    """Uploaded resume exceeds ``MAX_RESUME_SIZE``."""


class ResumeParseError(ResumeStorageError):
    """The heuristic resume parser failed on the uploaded file."""


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def get_resume_download_response(profile: UserProfile) -> Response | None:
    """Return a download response for the profile's stored resume, or ``None``.

    ``None`` signals the caller (the page) that no resume is available so it
    can issue its ``no_resume`` redirect — the service stays free of HTTP
    routing concerns.
    """
    object_name = profile.resume_path
    if object_name and file_exists(object_name):
        return get_download_response(object_name, Path(object_name).name)
    return None


# ---------------------------------------------------------------------------
# Upload + parse + enrich
# ---------------------------------------------------------------------------


def _map_resume_to_profile(parsed: ResumeData, profile: UserProfile) -> None:
    """Map parsed resume sections to profile fields when they're empty."""
    resume_dict = parsed.to_dict()

    if not profile.name and resume_dict.get("name"):
        profile.name = resume_dict["name"]
    if not profile.summary and resume_dict.get("summary"):
        profile.summary = resume_dict["summary"]

    # Best-effort: extract email from the raw contact_info string produced by the parser.
    # The LLM enrichment step will do a more thorough extraction of all contact fields.
    raw_contact = resume_dict.get("contact_info", "")
    if raw_contact and not profile.contact_info.email:
        email_match = re.search(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", raw_contact
        )
        if email_match:
            profile.contact_info.email = email_match.group(0)

    for section in parsed.sections:
        heading_lower = section.heading.lower()

        if any(
            kw in heading_lower
            for kw in (
                "skill",
                "technologies",
                "tools",
                "tech stack",
                "competenc",
                "language",
                "programming",
            )
        ):
            if profile.skills is None:
                profile.skills = {}
            profile.skills[section.heading] = section.items
        elif any(
            kw in heading_lower
            for kw in ("experience", "employment", "work history", "career")
        ):
            new_entries = [
                {"section": section.heading, "details": item} for item in section.items
            ]
            if profile.experiences is None:
                profile.experiences = new_entries
            else:
                profile.experiences.extend(new_entries)
        elif any(
            kw in heading_lower
            for kw in ("education", "academic", "degree", "university", "school")
        ):
            new_entries = [
                {"section": section.heading, "details": item} for item in section.items
            ]
            if profile.education is None:
                profile.education = new_entries
            else:
                profile.education.extend(new_entries)


def store_uploaded_resume(
    content: bytes, filename: str, profile: UserProfile
) -> None:
    """Store an uploaded resume, parse it into ``profile``, and save.

    Validates the file type and size, uploads the bytes to storage, runs the
    heuristic parser, merges the result into ``profile`` (only filling empty
    fields), persists the profile, and kicks off LLM enrichment as a
    fire-and-forget background task.

    Raises:
        InvalidFileTypeError: ``filename`` has a disallowed extension.
        FileTooLargeError: ``content`` exceeds ``MAX_RESUME_SIZE``.
        ResumeParseError: the heuristic parser raised on the uploaded file.

    The caller is responsible for having already read ``content`` from the
    request and for get-or-creating ``profile``.
    """
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise InvalidFileTypeError(filename)
    if len(content) > MAX_RESUME_SIZE:
        raise FileTooLargeError(len(content))

    # Upload to GCS (or local fallback)
    object_name = f"resumes/resume{ext}"
    upload_file(content, object_name)

    # parse_resume / extract_raw_resume_text need a local Path, so use a temp file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        try:
            parsed = parse_resume(tmp_path)
        except Exception:
            logger.exception("Failed to parse uploaded resume")
            raise ResumeParseError(str(tmp_path)) from None

        profile.resume_path = object_name
        profile.enrichment_warning = ""

        _map_resume_to_profile(parsed, profile)

        profile.save()

        # Kick off LLM enrichment in the background — won't delay the response.
        # Raw file text is used (not the heuristic-parsed JSON) so the LLM sees
        # everything, including sections the keyword matcher may have missed.
        resume_text = extract_raw_resume_text(tmp_path)
        asyncio.create_task(enrich_profile_with_llm_async(profile, resume_text))
    finally:
        tmp_path.unlink(missing_ok=True)
