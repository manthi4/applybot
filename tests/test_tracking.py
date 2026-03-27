"""Tests for the tracking module (state machine)."""

import pytest

from applybot.models.application import (
    Application,
    ApplicationStatus,
    add_application,
    get_status_updates,
)
from applybot.models.job import Job, JobSource, add_job
from applybot.tracking.tracker import (
    InvalidTransitionError,
    get_applications,
    get_summary,
    update_status,
)


def _create_application(status: ApplicationStatus = ApplicationStatus.DRAFT) -> str:
    """Helper to create a test application and return its ID."""
    job = Job(
        title="Test Job",
        company="Co",
        url=f"https://example.com/job/track-{id(status)}-{status.value}",
        source=JobSource.MANUAL,
    )
    job = add_job(job)

    app = Application(job_id=job.id, status=status)
    app = add_application(app)
    return app.id


class TestStatusTransitions:
    def test_valid_draft_to_ready(self):
        app_id = _create_application(ApplicationStatus.DRAFT)
        from applybot.models.application import UpdateSource

        app = update_status(
            app_id, ApplicationStatus.READY_FOR_REVIEW, UpdateSource.SYSTEM
        )
        assert app.status == ApplicationStatus.READY_FOR_REVIEW

    def test_valid_ready_to_approved(self):
        app_id = _create_application(ApplicationStatus.READY_FOR_REVIEW)
        app = update_status(app_id, ApplicationStatus.APPROVED)
        assert app.status == ApplicationStatus.APPROVED

    def test_valid_approved_to_submitted(self):
        app_id = _create_application(ApplicationStatus.APPROVED)
        app = update_status(app_id, ApplicationStatus.SUBMITTED)
        assert app.status == ApplicationStatus.SUBMITTED
        assert app.submitted_at is not None

    def test_valid_submitted_to_rejected(self):
        app_id = _create_application(ApplicationStatus.SUBMITTED)
        from applybot.models.application import UpdateSource

        app = update_status(
            app_id, ApplicationStatus.REJECTED, UpdateSource.GMAIL, "Rejection email"
        )
        assert app.status == ApplicationStatus.REJECTED

    def test_valid_submitted_to_interview(self):
        app_id = _create_application(ApplicationStatus.SUBMITTED)
        app = update_status(app_id, ApplicationStatus.INTERVIEW)
        assert app.status == ApplicationStatus.INTERVIEW

    def test_invalid_draft_to_submitted(self):
        app_id = _create_application(ApplicationStatus.DRAFT)
        with pytest.raises(InvalidTransitionError):
            update_status(app_id, ApplicationStatus.SUBMITTED)

    def test_invalid_rejected_to_anything(self):
        app_id = _create_application(ApplicationStatus.REJECTED)
        with pytest.raises(InvalidTransitionError):
            update_status(app_id, ApplicationStatus.INTERVIEW)

    def test_withdrawn_is_terminal(self):
        app_id = _create_application(ApplicationStatus.WITHDRAWN)
        with pytest.raises(InvalidTransitionError):
            update_status(app_id, ApplicationStatus.DRAFT)

    def test_nonexistent_application(self):
        with pytest.raises(ValueError, match="not found"):
            update_status("nonexistent_id", ApplicationStatus.APPROVED)

    def test_status_update_creates_record(self):
        app_id = _create_application(ApplicationStatus.DRAFT)
        from applybot.models.application import UpdateSource

        update_status(
            app_id, ApplicationStatus.READY_FOR_REVIEW, UpdateSource.SYSTEM, "Test"
        )

        updates = get_status_updates(app_id)
        assert len(updates) == 1
        assert updates[0].status == ApplicationStatus.READY_FOR_REVIEW
        assert updates[0].details == "Test"


class TestGetApplications:
    def test_filter_by_status(self):
        _create_application(ApplicationStatus.DRAFT)
        _create_application(ApplicationStatus.DRAFT)
        _create_application(ApplicationStatus.READY_FOR_REVIEW)

        drafts = get_applications(status=ApplicationStatus.DRAFT)
        assert len(drafts) == 2

        ready = get_applications(status=ApplicationStatus.READY_FOR_REVIEW)
        assert len(ready) == 1

    def test_get_all(self):
        _create_application(ApplicationStatus.DRAFT)
        _create_application(ApplicationStatus.READY_FOR_REVIEW)
        all_apps = get_applications()
        assert len(all_apps) == 2


class TestGetSummary:
    def test_summary_counts(self):
        _create_application(ApplicationStatus.DRAFT)
        _create_application(ApplicationStatus.DRAFT)
        _create_application(ApplicationStatus.READY_FOR_REVIEW)

        summary = get_summary()
        assert summary["draft"] == 2
        assert summary["ready_for_review"] == 1
        assert summary["total"] == 3
