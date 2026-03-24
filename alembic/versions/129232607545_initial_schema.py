"""initial schema

Revision ID: 129232607545
Revises:
Create Date: 2026-03-23 22:41:35.698936

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "129232607545"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company", sa.String(length=300), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "serpapi",
                "greenhouse",
                "lever",
                "eu_remote_jobs",
                "manual",
                name="jobsource",
            ),
            nullable=False,
        ),
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.Column("discovered_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("relevance_reasoning", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "new",
                "reviewing",
                "approved",
                "skipped",
                "applied",
                "rejected",
                name="jobstatus",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=300), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("experiences", sa.JSON(), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("resume_path", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("tailored_resume_path", sa.String(length=500), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
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
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "application_status_updates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
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
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum("manual", "gmail", "system", name="updatesource"),
            nullable=False,
        ),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("application_status_updates")
    op.drop_table("applications")
    op.drop_table("user_profiles")
    op.drop_table("jobs")
    sa.Enum(name="updatesource").drop(op.get_bind())
    sa.Enum(name="applicationstatus").drop(op.get_bind())
    sa.Enum(name="jobstatus").drop(op.get_bind())
    sa.Enum(name="jobsource").drop(op.get_bind())
