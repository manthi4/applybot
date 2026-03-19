"""Tests for the tracking module (state machine)."""

import uuid

import pytest

from applybot.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusUpdate,
    UpdateSource,
)
from applybot.models.base import get_session, init_db
from applybot.models.job import Job, JobSource
from applybot.tracking.tracker import (
    InvalidTransitionError,
    get_applications,
    get_summary,
    update_status,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield
    with get_session() as session:
        session.query(ApplicationStatusUpdate).delete()
        session.query(Application).delete()
        session.query(Job).delete()
        session.commit()


def _create_application(status: ApplicationStatus = ApplicationStatus.DRAFT) -> int:
    """Helper to create a test application and return its ID."""
    with get_session() as session:
        job = Job(
            title="Test Job",
            company="Co",
            url=f"https://example.com/job/{uuid.uuid4().hex}",
            source=JobSource.MANUAL,
        )
        session.add(job)
        session.commit()

        app = Application(job_id=job.id, status=status)
        session.add(app)
        session.commit()
        return app.id


class TestStatusTransitions:
    def test_valid_draft_to_ready(self):
        app_id = _create_application(ApplicationStatus.DRAFT)
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
            update_status(99999, ApplicationStatus.APPROVED)

    def test_status_update_creates_record(self):
        app_id = _create_application(ApplicationStatus.DRAFT)
        update_status(
            app_id, ApplicationStatus.READY_FOR_REVIEW, UpdateSource.SYSTEM, "Test"
        )

        with get_session() as session:
            updates = (
                session.query(ApplicationStatusUpdate)
                .filter(ApplicationStatusUpdate.application_id == app_id)
                .all()
            )
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
