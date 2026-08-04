"""Thin GCS storage layer for file storage (resumes, etc.)."""

from __future__ import annotations

import logging
import mimetypes
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.cloud import storage as gcs
from starlette.responses import Response

logger = logging.getLogger(__name__)

# MIME types for common resume formats
_MIME_TYPES: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}

# ---------------------------------------------------------------------------
# GCS bucket singleton (lazy init, same pattern as models/base.py::get_db)
# ---------------------------------------------------------------------------


def _get_bucket() -> Any:
    raise NotImplementedError("GCS storage needs rework")


def _guess_content_type(object_name: str) -> str:
    """Guess MIME type from the object name's extension."""
    ext = Path(object_name).suffix.lower()
    if ext in _MIME_TYPES:
        return _MIME_TYPES[ext]
    guessed, _ = mimetypes.guess_type(object_name)
    return guessed or "application/octet-stream"


def upload_file(content: bytes, object_name: str) -> str:
    """Upload bytes to GCS.

    Args:
        content: File content as bytes.
        object_name: Object path, e.g. ``resumes/resume.pdf``.

    Returns:
        The object name (unchanged).
    """
    blob = _get_bucket().blob(object_name)
    content_type = _guess_content_type(object_name)
    blob.upload_from_string(content, content_type=content_type)
    logger.info("Uploaded to GCS: %s (%d bytes)", object_name, len(content))
    return object_name


def download_file(object_name: str) -> bytes:
    """Download from GCS.

    Args:
        object_name: Object path, e.g. ``resumes/resume.pdf``.

    Returns:
        File content as bytes.

    Raises:
        FileNotFoundError: If the object does not exist.
    """
    blob = _get_bucket().blob(object_name)
    if not blob.exists():
        raise FileNotFoundError(f"GCS object not found: {object_name}")
    return blob.download_as_bytes()  # type: ignore[no-any-return]


def file_exists(object_name: str) -> bool:
    """Check whether an object exists in GCS.

    Args:
        object_name: Object path, e.g. ``resumes/resume.pdf``.

    Returns:
        True if the object exists.
    """
    blob = _get_bucket().blob(object_name)
    return blob.exists()  # type: ignore[no-any-return]


def get_download_response(object_name: str, filename: str) -> Response:
    """Return a Starlette ``Response`` with the file content.

    Args:
        object_name: Object path in storage.
        filename: The download filename shown to the user.

    Returns:
        A :class:`starlette.responses.Response` with correct media type.
    """
    content = download_file(object_name)
    media_type = _guess_content_type(object_name)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
