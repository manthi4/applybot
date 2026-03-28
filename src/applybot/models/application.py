"""Application and status update models with Firestore CRUD operations."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, Field

from applybot.models.base import get_db

COLLECTION = "applications"
STATUS_UPDATES_COLLECTION = "application_status_updates"


class ApplicationStatus(str, enum.Enum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    RECEIVED = "received"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class UpdateSource(str, enum.Enum):
    MANUAL = "manual"
    GMAIL = "gmail"
    SYSTEM = "system"


class Application(BaseModel):
    """Job application stored in Firestore."""

    id: str = ""
    job_id: str = ""
    tailored_resume_path: str = ""
    cover_letter: str = ""
    answers: dict[str, Any] = Field(default_factory=dict)
    profile_gaps: list[dict[str, str]] = Field(default_factory=list)
    status: ApplicationStatus = ApplicationStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    submitted_at: datetime | None = None

    def __repr__(self) -> str:
        return f"<Application {self.id}: job={self.job_id} status={self.status}>"


class ApplicationStatusUpdate(BaseModel):
    """Audit trail entry for application status changes."""

    id: str = ""
    application_id: str = ""
    status: ApplicationStatus
    source: UpdateSource
    details: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<StatusUpdate {self.id}: {self.status} via {self.source}>"


def _app_to_doc(app: Application) -> dict[str, Any]:
    """Convert an Application to a Firestore-compatible dict."""
    data = app.model_dump(exclude={"id"})
    data["status"] = (
        data["status"].value
        if isinstance(data["status"], ApplicationStatus)
        else data["status"]
    )
    return data


def _doc_to_app(doc: Any) -> Application:
    """Convert a Firestore document snapshot to an Application."""
    data = doc.to_dict()
    return Application(id=doc.id, **data)


def _update_to_doc(update: ApplicationStatusUpdate) -> dict[str, Any]:
    """Convert an ApplicationStatusUpdate to a Firestore-compatible dict."""
    data = update.model_dump(exclude={"id"})
    data["status"] = (
        data["status"].value
        if isinstance(data["status"], ApplicationStatus)
        else data["status"]
    )
    data["source"] = (
        data["source"].value
        if isinstance(data["source"], UpdateSource)
        else data["source"]
    )
    return data


def _doc_to_update(doc: Any) -> ApplicationStatusUpdate:
    """Convert a Firestore document to an ApplicationStatusUpdate."""
    data = doc.to_dict()
    return ApplicationStatusUpdate(id=doc.id, **data)


def get_application(app_id: str) -> Application | None:
    """Get an application by document ID."""
    doc = get_db().collection(COLLECTION).document(app_id).get()
    if not doc.exists:
        return None
    return _doc_to_app(doc)


def add_application(app: Application) -> Application:
    """Add a new application. Returns with ID populated."""
    data = _app_to_doc(app)
    _, ref = get_db().collection(COLLECTION).add(data)
    app.id = ref.id
    return app


def update_application(app_id: str, **fields: Any) -> None:
    """Update specific fields on an application document."""
    # Convert enum values
    if "status" in fields and hasattr(fields["status"], "value"):
        fields["status"] = fields["status"].value
    get_db().collection(COLLECTION).document(app_id).update(fields)


def query_applications(
    *,
    status: ApplicationStatus | None = None,
    limit: int = 100,
) -> list[Application]:
    """Query applications with optional status filter. Ordered by created_at desc."""
    ref = get_db().collection(COLLECTION)
    query = ref.order_by("created_at", direction="DESCENDING")
    if status is not None:
        query = query.where(filter=FieldFilter("status", "==", status.value))
    query = query.limit(limit)
    return [_doc_to_app(doc) for doc in query.stream()]


def count_applications_by_status() -> dict[str, int]:
    """Count applications grouped by status."""
    counts: dict[str, int] = {}
    total = 0
    for doc in get_db().collection(COLLECTION).select(["status"]).stream():
        status = doc.to_dict().get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        total += 1
    counts["total"] = total
    return counts


def add_status_update(update: ApplicationStatusUpdate) -> ApplicationStatusUpdate:
    """Add a status update record."""
    data = _update_to_doc(update)
    _, ref = get_db().collection(STATUS_UPDATES_COLLECTION).add(data)
    update.id = ref.id
    return update


def get_status_updates(app_id: str) -> list[ApplicationStatusUpdate]:
    """Get all status updates for an application."""
    docs = (
        get_db()
        .collection(STATUS_UPDATES_COLLECTION)
        .where(filter=FieldFilter("application_id", "==", app_id))
        .order_by("timestamp")
        .stream()
    )
    return [_doc_to_update(doc) for doc in docs]


def get_applications_by_statuses(
    statuses: list[ApplicationStatus],
) -> list[Application]:
    """Get applications matching any of the given statuses."""
    if not statuses:
        return []
    status_values = [s.value for s in statuses]
    docs = (
        get_db()
        .collection(COLLECTION)
        .where(filter=FieldFilter("status", "in", status_values))
        .stream()
    )
    return [_doc_to_app(doc) for doc in docs]
