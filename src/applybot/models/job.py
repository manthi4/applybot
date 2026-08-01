"""Job model and Firestore CRUD operations.

``Job`` inherits :class:`~applybot.models.base.FirestoreModel` for document-level
CRUD (``get``/``save``/``update``/``count_by_status``); job-specific batch and
query helpers live as classmethods on the model itself.
"""

from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import Field

from applybot.models import base
from applybot.models.base import FirestoreModel


class JobStatus(str, enum.Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    SKIPPED = "skipped"
    APPLIED = "applied"
    REJECTED = "rejected"


class JobSource(str, enum.Enum):
    SERPAPI = "serpapi"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    EU_REMOTE_JOBS = "eu_remote_jobs"
    MANUAL = "manual"


class Job(FirestoreModel):
    """Job listing stored in Firestore."""

    COLLECTION = "jobs"
    ENUM_FIELDS = ("status", "source")

    title: str
    company: str
    location: str = ""
    description: str = ""
    url: str
    source: JobSource
    posted_date: date | None = None
    discovered_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    relevance_score: float | None = None
    relevance_reasoning: str = ""
    status: JobStatus = JobStatus.NEW
    hard_requirements: list[str] = Field(default_factory=list)
    application_questions: list[str] = Field(default_factory=list)

    def __repr__(self) -> str:
        return f"<Job {self.id}: {self.title} @ {self.company}>"

    def to_doc(self) -> dict[str, Any]:
        """Serialize to a Firestore dict, coercing ``posted_date`` to ISO."""
        data = super().to_doc()
        # Firestore has no native date type — store posted_date as an ISO string.
        posted = data.get("posted_date")
        data["posted_date"] = posted.isoformat() if posted is not None else None
        return data

    @classmethod
    def from_doc(cls, doc: Any) -> Job:
        """Build a Job from a Firestore snapshot, parsing ``posted_date``."""
        data = doc.to_dict()
        if "posted_date" in data and isinstance(data["posted_date"], str):
            data["posted_date"] = date.fromisoformat(data["posted_date"])
        return cls(id=doc.id, **data)

    # -- job-specific helpers ------------------------------------------------
    @classmethod
    def add_many(cls, jobs: list[Job]) -> int:
        """Batch-add jobs to Firestore. Returns count of jobs added.

        Each job's ``id`` is populated in place with its generated document id.
        """
        db = base.get_db()
        batch = db.batch()
        count = 0
        for job in jobs:
            ref = db.collection(cls.COLLECTION).document()
            batch.set(ref, job.to_doc())
            job.id = ref.id
            count += 1
            # Firestore batches limited to 500 writes
            if count % 400 == 0:
                batch.commit()
                batch = db.batch()
        if count % 400 != 0:
            batch.commit()
        return count

    @classmethod
    def query(
        cls,
        *,
        status: JobStatus | None = None,
        min_score: float | None = None,
        limit: int = 100,
    ) -> list[Job]:
        """Query jobs with optional filters. Ordered by relevance_score desc."""
        query = cls._collection().order_by("relevance_score", direction="DESCENDING")
        if status is not None:
            query = query.where(filter=FieldFilter("status", "==", status.value))
        if min_score is not None:
            query = query.where(filter=FieldFilter("relevance_score", ">=", min_score))
        query = query.limit(limit)
        return [cls.from_doc(doc) for doc in query.stream()]

    @classmethod
    def all_urls(cls) -> set[str]:
        """Return all existing job URLs (for deduplication)."""
        docs = cls._collection().select(["url"]).stream()
        return {doc.to_dict()["url"] for doc in docs}
