"""Tests for core models and Firestore CRUD operations."""

from applybot.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusUpdate,
    UpdateSource,
    add_application,
    add_status_update,
    get_application,
    get_status_updates,
)
from applybot.models.job import (
    Job,
    JobSource,
    JobStatus,
    add_job,
    get_all_job_urls,
    get_job,
)
from applybot.models.profile import UserProfile, get_profile, save_profile


class TestJobModel:
    def test_create_job(self):
        job = Job(
            title="ML Engineer",
            company="Acme Corp",
            location="Remote",
            description="Build ML models",
            url="https://example.com/job/1",
            source=JobSource.SERPAPI,
            status=JobStatus.NEW,
        )
        job = add_job(job)

        assert job.id != ""
        assert job.title == "ML Engineer"
        assert job.status == JobStatus.NEW

    def test_get_job(self):
        job = Job(
            title="Robotics Eng",
            company="Bot Inc",
            url="https://example.com/job/2",
            source=JobSource.GREENHOUSE,
        )
        job = add_job(job)

        fetched = get_job(job.id)
        assert fetched is not None
        assert fetched.title == "Robotics Eng"
        assert fetched.company == "Bot Inc"

    def test_get_job_not_found(self):
        assert get_job("nonexistent") is None

    def test_job_unique_url_tracking(self):
        """Verify get_all_job_urls returns all stored URLs."""
        job1 = Job(
            title="Job 1",
            company="Co",
            url="https://example.com/unique1",
            source=JobSource.MANUAL,
        )
        job2 = Job(
            title="Job 2",
            company="Co",
            url="https://example.com/unique2",
            source=JobSource.MANUAL,
        )
        add_job(job1)
        add_job(job2)

        urls = get_all_job_urls()
        assert "https://example.com/unique1" in urls
        assert "https://example.com/unique2" in urls


class TestUserProfileModel:
    def test_create_profile(self):
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
        profile = save_profile(profile)

        assert profile.id != ""
        assert profile.name == "Test User"
        assert "Python" in profile.skills["technical"]

    def test_profile_json_fields(self):
        profile = UserProfile(
            name="User",
            skills={"technical": ["a"], "soft": ["b"]},
            experiences=[{"title": "Role"}],
            education=[{"degree": "BS", "school": "University"}],
            preferences={"remote": True, "locations": ["US", "EU"]},
        )
        profile = save_profile(profile)

        fetched = get_profile()
        assert fetched is not None
        assert fetched.preferences["remote"] is True
        assert len(fetched.education) == 1

    def test_get_profile_when_none(self):
        assert get_profile() is None


class TestApplicationModel:
    def test_create_application(self):
        job = Job(
            title="ML Eng",
            company="Co",
            url="https://example.com/job/app-test",
            source=JobSource.MANUAL,
        )
        job = add_job(job)

        app = Application(
            job_id=job.id,
            cover_letter="Dear hiring manager...",
            answers={"q1": "a1", "q2": "a2"},
            status=ApplicationStatus.READY_FOR_REVIEW,
        )
        app = add_application(app)

        assert app.id != ""
        assert app.job_id == job.id
        assert app.answers["q1"] == "a1"

    def test_get_application(self):
        job = Job(
            title="Test",
            company="Co",
            url="https://example.com/job/get-test",
            source=JobSource.MANUAL,
        )
        job = add_job(job)

        app = Application(job_id=job.id, status=ApplicationStatus.READY_FOR_REVIEW)
        app = add_application(app)

        fetched = get_application(app.id)
        assert fetched is not None
        assert fetched.status == ApplicationStatus.READY_FOR_REVIEW

    def test_status_update_tracking(self):
        job = Job(
            title="Test",
            company="Co",
            url="https://example.com/job/status-test",
            source=JobSource.MANUAL,
        )
        job = add_job(job)

        app = Application(job_id=job.id, status=ApplicationStatus.READY_FOR_REVIEW)
        app = add_application(app)

        update = ApplicationStatusUpdate(
            application_id=app.id,
            status=ApplicationStatus.APPROVED,
            source=UpdateSource.SYSTEM,
            details="Auto-approved",
        )
        add_status_update(update)

        updates = get_status_updates(app.id)
        assert len(updates) == 1
        assert updates[0].source == UpdateSource.SYSTEM
