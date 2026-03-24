from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from applybot.models.base import Base
from applybot.models.job import Job


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


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    tailored_resume_path: Mapped[str] = mapped_column(String(500), default="")
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            "draft",
            "ready_for_review",
            "approved",
            "submitted",
            "received",
            "interview",
            "offer",
            "rejected",
            "withdrawn",
            name="applicationstatus",
        ),
        default=ApplicationStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job: Mapped[Job] = relationship("Job", lazy="joined")
    status_updates: Mapped[list[ApplicationStatusUpdate]] = relationship(
        back_populates="application", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Application {self.id}: job={self.job_id} status={self.status}>"


class ApplicationStatusUpdate(Base):
    __tablename__ = "application_status_updates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            "draft",
            "ready_for_review",
            "approved",
            "submitted",
            "received",
            "interview",
            "offer",
            "rejected",
            "withdrawn",
            name="applicationstatus",
        )
    )
    source: Mapped[UpdateSource] = mapped_column(
        Enum("manual", "gmail", "system", name="updatesource")
    )
    details: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    application: Mapped[Application] = relationship(back_populates="status_updates")

    def __repr__(self) -> str:
        return f"<StatusUpdate {self.id}: {self.status} via {self.source}>"
