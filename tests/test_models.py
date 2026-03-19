"""Tests for core models and database operations."""

import pytest

from applybot.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusUpdate,
    UpdateSource,
)
from applybot.models.base import get_session, init_db
from applybot.models.job import Job, JobSource, JobStatus
from applybot.models.profile import UserProfile


@pytest.fixture(autouse=True)
def setup_db():
    """Create a fresh database for each test."""
    init_db()
    yield
    # Clean up
    with get_session() as session:
        session.query(ApplicationStatusUpdate).delete()
        session.query(Application).delete()
        session.query(Job).delete()
        session.query(UserProfile).delete()
        session.commit()


class TestJobModel:
    def test_create_job(self):
        with get_session() as session:
            job = Job(
                title="ML Engineer",
                company="Acme Corp",
                location="Remote",
                description="Build ML models",
                url="https://example.com/job/1",
                source=JobSource.SERPAPI,
                status=JobStatus.NEW,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            assert job.id is not None
            assert job.title == "ML Engineer"
            assert job.status == JobStatus.NEW
            assert job.discovered_date is not None

    def test_job_status_transitions(self):
        with get_session() as session:
            job = Job(
                title="Robotics Eng",
                company="Bot Inc",
                url="https://example.com/job/2",
                source=JobSource.GREENHOUSE,
            )
            session.add(job)
            session.commit()

            job.status = JobStatus.APPROVED
            session.commit()
            session.refresh(job)
            assert job.status == JobStatus.APPROVED

    def test_job_unique_url(self):
        with get_session() as session:
            job1 = Job(
                title="Job 1",
                company="Co",
                url="https://example.com/unique",
                source=JobSource.MANUAL,
            )
            session.add(job1)
            session.commit()

            job2 = Job(
                title="Job 2",
                company="Co",
                url="https://example.com/unique",
                source=JobSource.MANUAL,
            )
            session.add(job2)
            with pytest.raises(Exception):  # IntegrityError
                session.commit()
            session.rollback()


class TestUserProfileModel:
    def test_create_profile(self):
        with get_session() as session:
            profile = UserProfile(
                name="Test User",
                email="test@example.com",
                summary="ML engineer with 5 years experience",
                skills={"technical": ["Python", "PyTorch", "ROS"]},
                experiences=[
                    {
                        "title": "ML Engineer",
                        "company": "TechCo",
                        "summary": "Built ML pipelines",
                    }
                ],
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)

            assert profile.id is not None
            assert profile.name == "Test User"
            assert "Python" in profile.skills["technical"]

    def test_profile_json_fields(self):
        with get_session() as session:
            profile = UserProfile(
                name="User",
                skills={"technical": ["a"], "soft": ["b"]},
                experiences=[{"title": "Role"}],
                education=[{"degree": "BS", "school": "University"}],
                preferences={"remote": True, "locations": ["US", "EU"]},
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)

            assert profile.preferences["remote"] is True
            assert len(profile.education) == 1


class TestApplicationModel:
    def test_create_application(self):
        with get_session() as session:
            job = Job(
                title="ML Eng",
                company="Co",
                url="https://example.com/job/app-test",
                source=JobSource.MANUAL,
            )
            session.add(job)
            session.commit()

            app = Application(
                job_id=job.id,
                cover_letter="Dear hiring manager...",
                answers={"q1": "a1", "q2": "a2"},
                status=ApplicationStatus.DRAFT,
            )
            session.add(app)
            session.commit()
            session.refresh(app)

            assert app.id is not None
            assert app.job_id == job.id
            assert app.answers["q1"] == "a1"

    def test_status_update_tracking(self):
        with get_session() as session:
            job = Job(
                title="Test",
                company="Co",
                url="https://example.com/job/status-test",
                source=JobSource.MANUAL,
            )
            session.add(job)
            session.commit()

            app = Application(job_id=job.id, status=ApplicationStatus.DRAFT)
            session.add(app)
            session.commit()

            update = ApplicationStatusUpdate(
                application_id=app.id,
                status=ApplicationStatus.READY_FOR_REVIEW,
                source=UpdateSource.SYSTEM,
                details="Auto-prepared",
            )
            session.add(update)
            session.commit()

            session.refresh(app)
            assert len(app.status_updates) == 1
            assert app.status_updates[0].source == UpdateSource.SYSTEM
