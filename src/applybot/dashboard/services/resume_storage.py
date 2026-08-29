"""Resume upload/download orchestration over the applybot.storage layer.

This module is intentionally free of any profile-model dependency: it only
validates, stores, and serves resume files. The profile page owns all
``UserProfile`` state (``resume_path``, saves, enrichment).
"""

from __future__ import annotations

import logging
from pathlib import Path

from starlette.responses import Response

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


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def get_resume_download_response(resume_path: str | None) -> Response | None:
    """Return a download response for the stored resume, or ``None``.

    ``resume_path`` is the storage object name (e.g. ``resumes/resume.pdf``).
    ``None`` signals the caller (the page) that no resume is available so it
    can issue its ``no_resume`` redirect — the service stays free of HTTP
    routing concerns.
    """
    if resume_path and file_exists(resume_path):
        return get_download_response(resume_path, Path(resume_path).name)
    return None


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def store_uploaded_resume(content: bytes, filename: str) -> str:
    """Validate and store an uploaded resume; return its storage object name.

    The caller (profile page) is responsible for recording the returned
    object name on the profile and persisting it.

    Raises:
        InvalidFileTypeError: ``filename`` has a disallowed extension.
        FileTooLargeError: ``content`` exceeds ``MAX_RESUME_SIZE``.
        ResumeStorageError: the underlying storage upload failed.
    """
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise InvalidFileTypeError(filename)
    if len(content) > MAX_RESUME_SIZE:
        raise FileTooLargeError(len(content))

    object_name = f"resumes/resume{ext}"
    upload_file(content, object_name)
    return object_name
