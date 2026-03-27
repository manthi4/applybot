"""Job model and Firestore CRUD operations."""

from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, Field

from applybot.models.base import get_db

COLLECTION = "jobs"


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


class Job(BaseModel):
    """Job listing stored in Firestore."""

    id: str = ""
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

    def __repr__(self) -> str:
        return f"<Job {self.id}: {self.title} @ {self.company}>"


def _doc_to_job(doc: Any) -> Job:
    """Convert a Firestore document snapshot to a Job."""
    data = doc.to_dict()
    # Convert posted_date from ISO string back to date
    if "posted_date" in data and isinstance(data["posted_date"], str):
        data["posted_date"] = date.fromisoformat(data["posted_date"])
    return Job(id=doc.id, **data)


def get_job(job_id: str) -> Job | None:
    """Get a job by document ID."""
    doc = get_db().collection(COLLECTION).document(job_id).get()
    if not doc.exists:
        return None
    return _doc_to_job(doc)


def _job_to_doc(job: Job) -> dict[str, Any]:
    """Convert a Job to a Firestore-compatible dict."""
    data = job.model_dump(exclude={"id"})
    # Convert enums to values
    data["source"] = (
        data["source"].value
        if isinstance(data["source"], JobSource)
        else data["source"]
    )
    data["status"] = (
        data["status"].value
        if isinstance(data["status"], JobStatus)
        else data["status"]
    )
    # Convert date to ISO string (Firestore has no native date type)
    if data.get("posted_date") is not None:
        data["posted_date"] = data["posted_date"].isoformat()
    else:
        data["posted_date"] = None
    return data


def add_job(job: Job) -> Job:
    """Add a new job to Firestore. Returns the job with its generated ID."""
    data = _job_to_doc(job)
    _, ref = get_db().collection(COLLECTION).add(data)
    job.id = ref.id
    return job


def add_jobs(jobs: list[Job]) -> int:
    """Batch-add jobs to Firestore. Returns count of jobs added."""
    db = get_db()
    batch = db.batch()
    count = 0
    for job in jobs:
        ref = db.collection(COLLECTION).document()
        batch.set(ref, _job_to_doc(job))
        job.id = ref.id
        count += 1
        # Firestore batches limited to 500 writes
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
    if count % 400 != 0:
        batch.commit()
    return count


def update_job(job_id: str, **fields: Any) -> None:
    """Update specific fields on a job document."""
    # Convert enum values
    for key in ("status", "source"):
        if key in fields and hasattr(fields[key], "value"):
            fields[key] = fields[key].value
    get_db().collection(COLLECTION).document(job_id).update(fields)


def query_jobs(
    *,
    status: JobStatus | None = None,
    min_score: float | None = None,
    limit: int = 100,
) -> list[Job]:
    """Query jobs with optional filters. Ordered by relevance_score descending."""
    ref = get_db().collection(COLLECTION)
    query = ref.order_by("relevance_score", direction="DESCENDING")
    if status is not None:
        query = query.where(filter=FieldFilter("status", "==", status.value))
    if min_score is not None:
        query = query.where(filter=FieldFilter("relevance_score", ">=", min_score))
    query = query.limit(limit)
    return [_doc_to_job(doc) for doc in query.stream()]


def get_all_job_urls() -> set[str]:
    """Get all existing job URLs (for deduplication)."""
    docs = get_db().collection(COLLECTION).select(["url"]).stream()
    return {doc.to_dict()["url"] for doc in docs}


def count_jobs_by_status() -> dict[str, int]:
    """Count jobs grouped by status."""
    counts: dict[str, int] = {}
    total = 0
    for doc in get_db().collection(COLLECTION).select(["status"]).stream():
        status = doc.to_dict().get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        total += 1
    counts["total"] = total
    return counts
