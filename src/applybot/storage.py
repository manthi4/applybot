"""Thin GCS storage layer with local-filesystem fallback for development."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from starlette.responses import Response

from applybot.config import settings

logger = logging.getLogger(__name__)

# Local data directory for fallback (when GCS is not configured)
_LOCAL_ROOT = Path("data")

# MIME types for common resume formats
_MIME_TYPES: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}

# ---------------------------------------------------------------------------
# GCS bucket singleton (lazy init, same pattern as models/base.py)
# ---------------------------------------------------------------------------

_bucket: Any = None


def _get_bucket() -> Any:
    """Return the GCS bucket client singleton (lazy-initialized).

    Only called when ``settings.gcs_bucket_name`` is set.
    """
    global _bucket
    if _bucket is None:
        from google.cloud import storage as gcs

        kwargs: dict[str, str] = {}
        if settings.gcp_project_id:
            kwargs["project"] = settings.gcp_project_id
        client = gcs.Client(**kwargs)
        _bucket = client.bucket(settings.gcs_bucket_name)
        logger.info("GCS bucket initialized: %s", settings.gcs_bucket_name)
    return _bucket


def _use_gcs() -> bool:
    """Return True if GCS is configured."""
    return bool(settings.gcs_bucket_name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def upload_file(content: bytes, object_name: str) -> str:
    """Upload bytes to GCS (or write locally in dev).

    Args:
        content: File content as bytes.
        object_name: Object path, e.g. ``resumes/resume.pdf``.

    Returns:
        The object name (unchanged).
    """
    if _use_gcs():
        blob = _get_bucket().blob(object_name)
        content_type = _guess_content_type(object_name)
        blob.upload_from_string(content, content_type=content_type)
        logger.info("Uploaded to GCS: %s (%d bytes)", object_name, len(content))
    else:
        local_path = _LOCAL_ROOT / object_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)
        logger.info("Wrote locally: %s (%d bytes)", local_path, len(content))
    return object_name


def download_file(object_name: str) -> bytes:
    """Download from GCS (or read locally in dev).

    Args:
        object_name: Object path, e.g. ``resumes/resume.pdf``.

    Returns:
        File content as bytes.

    Raises:
        FileNotFoundError: If the object does not exist.
    """
    if _use_gcs():
        blob = _get_bucket().blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"GCS object not found: {object_name}")
        return blob.download_as_bytes()  # type: ignore[no-any-return]
    else:
        local_path = _LOCAL_ROOT / object_name
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")
        return local_path.read_bytes()


def file_exists(object_name: str) -> bool:
    """Check whether an object exists in GCS (or locally in dev).

    Args:
        object_name: Object path, e.g. ``resumes/resume.pdf``.

    Returns:
        True if the object exists.
    """
    if _use_gcs():
        blob = _get_bucket().blob(object_name)
        return blob.exists()  # type: ignore[no-any-return]
    else:
        return (_LOCAL_ROOT / object_name).exists()


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _guess_content_type(object_name: str) -> str:
    """Guess MIME type from the object name's extension."""
    ext = Path(object_name).suffix.lower()
    if ext in _MIME_TYPES:
        return _MIME_TYPES[ext]
    guessed, _ = mimetypes.guess_type(object_name)
    return guessed or "application/octet-stream"
