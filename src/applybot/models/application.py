"""Application model with Firestore CRUD operations.

``Application`` inherits :class:`~applybot.models.base.FirestoreModel` for
document-level CRUD (``get``/``save``/``update``/``count_by_status``);
application-specific query helpers live as classmethods on the model.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import Field

from applybot.models.base import FirestoreModel


class ApplicationStatus(str, enum.Enum):
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    RECEIVED = "received"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Application(FirestoreModel):
    """Job application stored in Firestore."""

    COLLECTION = "applications"
    ENUM_FIELDS = ("status",)

    job_id: str = ""
    tailored_resume_path: str = ""
    cover_letter: str = ""
    answers: dict[str, Any] = Field(default_factory=dict)
    profile_gaps: list[dict[str, str]] = Field(default_factory=list)
    status: ApplicationStatus = ApplicationStatus.READY_FOR_REVIEW
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    submitted_at: datetime | None = None

    def __repr__(self) -> str:
        return f"<Application {self.id}: job={self.job_id} status={self.status.value}>"

    @classmethod
    def from_doc(cls, doc: Any) -> Application:
        """Build an Application from a Firestore snapshot.

        Migrates the legacy ``"draft"`` status (removed from the enum) to
        ``READY_FOR_REVIEW`` on read.
        """
        data = doc.to_dict()
        if data.get("status") == "draft":
            data["status"] = ApplicationStatus.READY_FOR_REVIEW.value
        return cls(id=doc.id, **data)

    # -- application-specific helpers ----------------------------------------
    @classmethod
    def query(
        cls,
        *,
        status: ApplicationStatus | None = None,
        limit: int = 100,
    ) -> list[Application]:
        """Query applications with optional status filter. Ordered by created_at desc."""
        query = cls._collection().order_by("created_at", direction="DESCENDING")
        if status is not None:
            query = query.where(filter=FieldFilter("status", "==", status.value))
        query = query.limit(limit)
        return [cls.from_doc(doc) for doc in query.stream()]

    @classmethod
    def by_statuses(cls, statuses: list[ApplicationStatus]) -> list[Application]:
        """Return applications matching any of the given statuses."""
        if not statuses:
            return []
        status_values = [s.value for s in statuses]
        docs = (
            cls._collection()
            .where(filter=FieldFilter("status", "in", status_values))
            .stream()
        )
        return [cls.from_doc(doc) for doc in docs]

    @classmethod
    def set_status(
        cls, application_id: str, new_status: ApplicationStatus
    ) -> Application:
        """Set an application's status directly, stamping ``submitted_at``
        when the status becomes ``SUBMITTED``.

        Raises ``ValueError`` if the application does not exist.
        """
        application = cls.get(application_id)
        if application is None:
            raise ValueError(f"Application {application_id} not found")
        fields: dict[str, Any] = {"status": new_status}
        if new_status is ApplicationStatus.SUBMITTED:
            fields["submitted_at"] = datetime.now(UTC)
        cls.update(application_id, **fields)
        updated = cls.get(application_id)
        assert updated is not None
        return updated
