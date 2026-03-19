from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from applybot.models.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    experiences: Mapped[list[Any]] = mapped_column(JSON, default=list)
    education: Mapped[list[Any]] = mapped_column(JSON, default=list)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resume_path: Mapped[str] = mapped_column(String(500), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<UserProfile {self.id}: {self.name}>"
