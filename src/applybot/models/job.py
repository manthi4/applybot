import enum
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from applybot.models.base import Base


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


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    company: Mapped[str] = mapped_column(String(300))
    location: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    source: Mapped[JobSource] = mapped_column(Enum(JobSource))
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    discovered_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_reasoning: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.NEW)

    def __repr__(self) -> str:
        return f"<Job {self.id}: {self.title} @ {self.company}>"
