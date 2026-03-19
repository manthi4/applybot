"""Gmail integration — scan emails for application status updates."""

from __future__ import annotations

import base64
import logging
from typing import Any

from pydantic import BaseModel

from applybot.config import settings
from applybot.llm.client import llm
from applybot.models.application import Application, ApplicationStatus, UpdateSource
from applybot.models.base import get_session
from applybot.models.job import Job
from applybot.tracking.tracker import update_status

logger = logging.getLogger(__name__)


class EmailClassification(BaseModel):
    """LLM output: classification of an email related to a job application."""

    is_application_related: bool
    company: str = ""
    status: str = ""  # One of: received, rejected, interview, offer, other
    confidence: float = 0.0
    summary: str = ""


STATUS_MAP = {
    "received": ApplicationStatus.RECEIVED,
    "rejected": ApplicationStatus.REJECTED,
    "interview": ApplicationStatus.INTERVIEW,
    "offer": ApplicationStatus.OFFER,
}


def scan_gmail_for_updates() -> list[dict[str, Any]]:
    """Scan Gmail for application-related emails and update statuses.

    Requires Google Gmail API credentials configured.

    Returns:
        List of updates applied.
    """
    if not settings.google_application_credentials:
        logger.warning("Google credentials not configured, skipping Gmail scan")
        return []

    try:
        service = _get_gmail_service()
    except Exception:
        logger.exception("Failed to initialize Gmail API")
        return []

    # Get applied-to companies for targeted search
    companies = _get_applied_companies()
    if not companies:
        logger.info("No submitted applications found, skipping Gmail scan")
        return []

    updates: list[dict[str, Any]] = []

    for company in companies:
        try:
            emails = _search_emails(service, company)
            for email in emails:
                result = _process_email(email, company)
                if result:
                    updates.append(result)
        except Exception:
            logger.exception("Failed to process emails for %s", company)

    logger.info("Gmail scan complete: %d updates applied", len(updates))
    return updates


def _get_gmail_service() -> Any:
    """Initialize the Gmail API service.

    Requires google-auth and google-api-python-client packages.
    These are optional dependencies — import at runtime.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(
        settings.google_application_credentials,
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    return build("gmail", "v1", credentials=creds)


def _get_applied_companies() -> list[str]:
    """Get list of companies with submitted applications."""
    with get_session() as session:
        results = (
            session.query(Job.company)
            .join(Application, Application.job_id == Job.id)
            .filter(
                Application.status.in_(
                    [
                        ApplicationStatus.SUBMITTED,
                        ApplicationStatus.RECEIVED,
                    ]
                )
            )
            .distinct()
            .all()
        )
        return [r[0] for r in results]


def _search_emails(service: Any, company: str) -> list[dict[str, Any]]:
    """Search Gmail for recent emails from/about a company."""
    query = f"from:{company} OR subject:{company} newer_than:3d"
    result = (
        service.users().messages().list(userId="me", q=query, maxResults=10).execute()
    )
    messages = result.get("messages", [])

    emails = []
    for msg_meta in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_meta["id"], format="full")
            .execute()
        )
        emails.append(_parse_email(msg))
    return emails


def _parse_email(message: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant fields from a Gmail API message."""
    headers = {
        h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])
    }

    # Get body text
    body = ""
    payload = message.get("payload", {})
    if payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
            "utf-8", errors="replace"
        )
    elif payload.get("parts"):
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get(
                "data"
            ):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8", errors="replace"
                )
                break

    return {
        "id": message.get("id", ""),
        "from": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "body": body[:3000],  # Truncate for LLM
    }


def _process_email(email: dict[str, Any], company: str) -> dict[str, Any] | None:
    """Classify an email and update application status if relevant."""
    prompt = f"""Classify this email regarding a job application.

Company we applied to: {company}

Email:
From: {email['from']}
Subject: {email['subject']}
Date: {email['date']}
Body: {email['body'][:2000]}

Determine:
1. Is this related to a job application? (automated receipts, rejections, interview invites, offers)
2. What status does it indicate? (received, rejected, interview, offer, other)
3. How confident are you? (0.0-1.0)"""

    try:
        result = llm.structured_output(
            prompt,
            EmailClassification,
            system="You classify job application emails. Be conservative — only classify with high confidence.",
        )
    except Exception:
        logger.exception("Failed to classify email %s", email.get("subject", ""))
        return None

    if not result.is_application_related or result.confidence < 0.7:
        return None

    new_status = STATUS_MAP.get(result.status)
    if new_status is None:
        return None

    # Find the matching application
    with get_session() as session:
        application = (
            session.query(Application)
            .join(Job, Application.job_id == Job.id)
            .filter(Job.company.ilike(f"%{company}%"))
            .filter(
                Application.status.in_(
                    [
                        ApplicationStatus.SUBMITTED,
                        ApplicationStatus.RECEIVED,
                    ]
                )
            )
            .first()
        )

    if application is None:
        logger.debug("No matching application found for %s", company)
        return None

    try:
        update_status(
            application.id,
            new_status,
            source=UpdateSource.GMAIL,
            details=f"Email: {email['subject']} — {result.summary}",
        )
        return {
            "application_id": application.id,
            "company": company,
            "old_status": application.status.value,
            "new_status": new_status.value,
            "email_subject": email["subject"],
            "confidence": result.confidence,
        }
    except Exception:
        logger.exception("Failed to update application %d status", application.id)
        return None
